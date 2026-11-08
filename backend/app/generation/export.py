from __future__ import annotations

import csv
import hashlib
import json
import os
import shutil
import tempfile
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from app.generation.anomalies import build_anomaly_fixtures, build_ground_truth
from app.generation.types import EXPORT_TABLES, GeneratedDataset
from app.generation.validation import validate_dataset


def _json_value(value: Any) -> Any:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return format(value, "f")
    return value


def _canonical_json(value: Any) -> str:
    return json.dumps(value, default=_json_value, sort_keys=True, separators=(",", ":"))


def _sql_literal(value: Any) -> str:
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, (int, float, Decimal)):
        return str(value)
    if isinstance(value, (date, datetime)):
        return "'" + value.isoformat().replace("'", "''") + "'"
    if isinstance(value, dict):
        return "'" + _canonical_json(value).replace("'", "''") + "'::jsonb"
    return "'" + str(value).replace("'", "''") + "'"


def _insert_sql(table_name: str, rows: list[dict[str, Any]]) -> list[str]:
    statements: list[str] = []
    for row in rows:
        columns = list(row)
        column_sql = ", ".join(f'"{column}"' for column in columns)
        values_sql = ", ".join(_sql_literal(row[column]) for column in columns)
        statements.append(
            f'INSERT INTO "{table_name}" ({column_sql}) VALUES ({values_sql}) '
            "ON CONFLICT DO NOTHING;"
        )
    return statements


def _sql_export(dataset: GeneratedDataset) -> str:
    statements = [
        "-- Deterministic PerformTrack baseline; anomaly fixtures and ground truth are excluded.",
        "BEGIN;",
        "SET CONSTRAINTS ALL DEFERRED;",
    ]
    for table_name in EXPORT_TABLES:
        statements.extend(_insert_sql(table_name, dataset.tables[table_name]))
    statements.extend(("COMMIT;", ""))
    return "\n".join(statements)


def _export_contents(
    dataset: GeneratedDataset,
    preparation_report: dict[str, Any] | None = None,
) -> dict[str, bytes]:
    validation = validate_dataset(dataset)
    fixtures = build_anomaly_fixtures(dataset)
    truth = build_ground_truth(fixtures)
    baseline = {
        "seed": dataset.seed,
        "scale": dataset.scale.name,
        "tables": dataset.tables,
        "derived_goal_progress": dataset.goal_progress,
    }
    dataset_checksum = hashlib.sha256(_canonical_json(baseline).encode("utf-8")).hexdigest()
    row_counts = {name: len(dataset.tables[name]) for name in sorted(dataset.tables)}
    summary = {
        "seed": dataset.seed,
        "scale": dataset.scale.name,
        "counts": row_counts,
        "total_exported_rows": sum(row_counts.values()),
        "derived_goal_progress_count": len(dataset.goal_progress),
        "dataset_sha256": dataset_checksum,
        "validation": validation,
        "anomaly_fixture_count": len(fixtures),
        "ground_truth_is_separate": True,
    }
    if preparation_report is not None:
        summary["database_preparation"] = preparation_report
    files: dict[str, bytes] = {}
    for table_name in EXPORT_TABLES:
        json_payload = json.dumps(
            dataset.tables[table_name], default=_json_value, indent=2, sort_keys=True
        ) + "\n"
        files[f"{table_name}.json"] = json_payload.encode("utf-8")
        csv_path = _csv_bytes(dataset.tables[table_name])
        files[f"{table_name}.csv"] = csv_path
    files["dataset.json"] = (
        json.dumps(
            {
                "seed": dataset.seed,
                "scale": dataset.scale.name,
                "tables": dataset.tables,
                "derived_goal_progress": dataset.goal_progress,
            },
            default=_json_value,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")
    files["goal_progress.json"] = (
        json.dumps(dataset.goal_progress, default=_json_value, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    files["seed.sql"] = _sql_export(dataset).encode("utf-8")
    files["anomaly_fixtures.json"] = (
        json.dumps(fixtures, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    files["ground_truth.json"] = (
        json.dumps(truth, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    files["ground_truth.csv"] = _ground_truth_csv(truth)
    files["generation_summary.json"] = (
        json.dumps(summary, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    files["validation_report.json"] = (
        json.dumps(validation, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    return files


def dataset_checksum(dataset: GeneratedDataset) -> str:
    baseline = {
        "seed": dataset.seed,
        "scale": dataset.scale.name,
        "tables": dataset.tables,
        "derived_goal_progress": dataset.goal_progress,
    }
    return hashlib.sha256(_canonical_json(baseline).encode("utf-8")).hexdigest()


def _csv_bytes(rows: list[dict[str, Any]]) -> bytes:
    if not rows:
        return b""
    import io

    buffer = io.StringIO(newline="")
    columns = sorted({key for row in rows for key in row})
    writer = csv.DictWriter(buffer, fieldnames=columns, extrasaction="raise", lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow(
            {
                key: _canonical_json(value) if isinstance(value, (dict, list)) else _json_value(value)
                for key, value in row.items()
            }
        )
    return buffer.getvalue().encode("utf-8")


def _ground_truth_csv(rows: list[dict[str, Any]]) -> bytes:
    import io

    buffer = io.StringIO(newline="")
    columns = ("issue_type", "ground_truth_label", "expected_decision", "record_id")
    writer = csv.DictWriter(buffer, fieldnames=columns, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue().encode("utf-8")


def export_dataset(
    dataset: GeneratedDataset,
    output_dir: Path,
    preparation_report: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Write deterministic exports without replacing any pre-existing different file."""
    contents = _export_contents(dataset, preparation_report)
    output_dir = output_dir.resolve()
    if output_dir.exists():
        if not output_dir.is_dir():
            raise FileExistsError(f"export path exists and is not a directory: {output_dir}")
        existing_entries = list(output_dir.iterdir())
        if any(not path.is_file() for path in existing_entries):
            raise FileExistsError(
                f"refusing to overwrite an export directory containing unexpected entries: {output_dir}"
            )
        existing_names = {path.name for path in existing_entries}
        expected_names = set(contents)
        if existing_names != expected_names:
            raise FileExistsError(
                f"refusing to overwrite existing export directory with different contents: {output_dir}"
            )
        for name, payload in contents.items():
            if (output_dir / name).read_bytes() != payload:
                raise FileExistsError(
                    f"refusing to overwrite different export file: {output_dir / name}"
                )
        return {"output_dir": str(output_dir), "files": len(contents), "already_identical": True}

    output_dir.parent.mkdir(parents=True, exist_ok=True)
    staging_dir = Path(tempfile.mkdtemp(prefix=f".{output_dir.name}-", dir=output_dir.parent))
    try:
        for name, payload in contents.items():
            (staging_dir / name).write_bytes(payload)
        os.replace(staging_dir, output_dir)
    except Exception:
        if staging_dir.exists():
            shutil.rmtree(staging_dir)
        raise
    return {"output_dir": str(output_dir), "files": len(contents), "already_identical": False}
