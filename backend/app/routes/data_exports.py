import csv
import hashlib
import json
import re
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.generation.types import EXPORT_TABLES

router = APIRouter(tags=["data-exports"])

ExportFormat = Literal["csv", "json", "sql", "docs"]

_BACKEND_ROOT = Path(__file__).resolve().parents[2]
_PROJECT_ROOT = _BACKEND_ROOT.parent
_EXPORT_ROOT = (_BACKEND_ROOT / "generated" / "full").resolve()
_TABLES = frozenset(EXPORT_TABLES)
_JSON_FILES = frozenset(
    (*EXPORT_TABLES, "dataset", "goal_progress", "generation_summary", "validation_report")
)
_DOC_FILES = {
    "README.md": _PROJECT_ROOT / "README.md",
    "DATABASE_SCHEMA.md": _PROJECT_ROOT / "docs" / "DATABASE_SCHEMA.md",
    "DATA_DICTIONARY.md": _PROJECT_ROOT / "docs" / "DATA_DICTIONARY.md",
}
_SQL_INSERT = re.compile(r'^INSERT INTO "([a-z_]+)" ', re.MULTILINE)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _export_file(filename: str, file_format: ExportFormat) -> Path:
    if file_format == "csv":
        allowed = _TABLES
        suffix = ".csv"
    elif file_format == "json":
        allowed = _JSON_FILES
        suffix = ".json"
    elif file_format == "sql":
        allowed = frozenset({"seed"})
        suffix = ".sql"
    else:
        allowed = frozenset(name.removesuffix(".md") for name in _DOC_FILES)
        suffix = ".md"

    stem = filename.removesuffix(suffix)
    if filename != f"{stem}{suffix}" or stem not in allowed:
        raise HTTPException(status_code=404, detail="Export file not found.")

    if file_format == "docs":
        path = _DOC_FILES[filename]
        expected_parent = (_PROJECT_ROOT / "docs").resolve() if filename != "README.md" else _PROJECT_ROOT
        if path.resolve().parent != expected_parent:
            raise HTTPException(status_code=404, detail="Export file not found.")
        return path

    path = (_EXPORT_ROOT / filename).resolve()
    if path.parent != _EXPORT_ROOT:
        raise HTTPException(status_code=404, detail="Export file not found.")
    return path


def _artifact(filename: str, file_format: ExportFormat, rows: int | None = None) -> dict:
    path = _export_file(filename, file_format)
    if not path.is_file():
        raise HTTPException(
            status_code=503,
            detail=f"Prepared {file_format.upper()} export is unavailable: {filename}.",
        )
    return {
        "file_name": filename,
        "format": file_format,
        "size_bytes": path.stat().st_size,
        "sha256": _sha256_file(path),
        "rows": rows,
        "download_url": f"/api/v1/data-exports/{file_format}/{filename}",
    }


def _validate_prepared_exports(summary: dict, validation: dict) -> list[dict]:
    if summary.get("scale") != "full" or summary.get("database_preparation", {}).get("mode") != "read_only_merge":
        raise HTTPException(
            status_code=503,
            detail="The full-scale prepared export metadata is missing or invalid.",
        )
    if summary.get("database_preparation", {}).get("database") != "performtrack_db":
        raise HTTPException(
            status_code=503,
            detail="The prepared export does not identify the PerformTrack PostgreSQL database.",
        )
    if summary.get("counts") != validation.get("tables"):
        raise HTTPException(
            status_code=503,
            detail="Prepared export row counts do not match the validation report.",
        )

    table_files = []
    for table_name in EXPORT_TABLES:
        expected_rows = summary["counts"].get(table_name)
        if not isinstance(expected_rows, int):
            raise HTTPException(status_code=503, detail=f"Missing row count for {table_name}.")

        csv_path = _export_file(f"{table_name}.csv", "csv")
        json_path = _export_file(f"{table_name}.json", "json")
        try:
            with csv_path.open("r", encoding="utf-8", newline="") as source:
                csv_rows = sum(1 for _ in csv.DictReader(source))
            with json_path.open("r", encoding="utf-8") as source:
                json_rows = json.load(source)
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, csv.Error) as exc:
            raise HTTPException(
                status_code=503,
                detail=f"Prepared export file for {table_name} is invalid.",
            ) from exc
        if not isinstance(json_rows, list) or len(json_rows) != expected_rows or csv_rows != expected_rows:
            raise HTTPException(
                status_code=503,
                detail=f"Prepared CSV/JSON row counts for {table_name} do not match the validation report.",
            )

        table_files.append(
            {
                "table": table_name,
                "rows": expected_rows,
                "csv": _artifact(f"{table_name}.csv", "csv", expected_rows),
                "json": _artifact(f"{table_name}.json", "json", expected_rows),
            }
        )

    sql_path = _export_file("seed.sql", "sql")
    try:
        sql_content = sql_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise HTTPException(status_code=503, detail="The prepared SQL export is invalid.") from exc
    sql_counts = {name: 0 for name in EXPORT_TABLES}
    for match in _SQL_INSERT.finditer(sql_content):
        table_name = match.group(1)
        if table_name in sql_counts:
            sql_counts[table_name] += 1
    if sql_counts != summary["counts"]:
        raise HTTPException(
            status_code=503,
            detail="Prepared SQL insert counts do not match the validation report.",
        )

    return table_files


@router.get("/data-exports")
def get_data_exports_status() -> dict:
    summary_path = _export_file("generation_summary.json", "json")
    validation_path = _export_file("validation_report.json", "json")
    try:
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        validation = json.loads(validation_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=503, detail="Prepared export reports are unavailable or invalid.") from exc

    tables = _validate_prepared_exports(summary, validation)
    total_rows = sum(summary["counts"].values())
    if total_rows != validation.get("total_rows") or total_rows != summary.get("total_exported_rows"):
        raise HTTPException(status_code=503, detail="Prepared export total row count is inconsistent.")

    supplementary = [
        _artifact("dataset.json", "json"),
        _artifact("goal_progress.json", "json"),
        _artifact("generation_summary.json", "json"),
        _artifact("validation_report.json", "json"),
    ]
    documents = [
        {
            "file_name": filename,
            "format": "docs",
            "size_bytes": path.stat().st_size,
            "sha256": _sha256_file(path),
            "download_url": f"/api/v1/data-exports/docs/{filename}",
        }
        for filename, path in _DOC_FILES.items()
        if path.is_file()
    ]
    if len(documents) != len(_DOC_FILES):
        raise HTTPException(status_code=503, detail="Required export documentation is unavailable.")

    return {
        "status": "ready",
        "generated_at": summary_path.stat().st_mtime,
        "source_database": summary["database_preparation"]["database"],
        "preparation_mode": summary["database_preparation"]["mode"],
        "dataset_sha256": summary["dataset_sha256"],
        "total_rows": total_rows,
        "validation": validation,
        "tables": tables,
        "sql": _artifact("seed.sql", "sql", total_rows),
        "supplementary": supplementary,
        "documentation": documents,
    }


@router.get("/data-exports/{file_format}/{filename}")
def download_data_export(file_format: ExportFormat, filename: str) -> FileResponse:
    path = _export_file(filename, file_format)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Export file not found.")
    media_types = {
        "csv": "text/csv; charset=utf-8",
        "json": "application/json",
        "sql": "application/sql; charset=utf-8",
        "docs": "text/markdown; charset=utf-8",
    }
    return FileResponse(
        path,
        media_type=media_types[file_format],
        filename=filename,
        headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"},
    )
