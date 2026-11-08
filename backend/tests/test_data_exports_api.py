import csv
import hashlib
import io
import json
import re
from pathlib import Path

from fastapi.testclient import TestClient

from app.generation.types import EXPORT_TABLES
from app.main import app


BACKEND_DIR = Path(__file__).resolve().parents[1]
EXPORT_DIR = BACKEND_DIR / "generated" / "full"
INSERT_PATTERN = re.compile(rb'^INSERT INTO "([a-z_]+)" ', re.MULTILINE)


def test_export_status_reports_validated_full_prepared_dataset() -> None:
    with TestClient(app) as client:
        response = client.get("/api/v1/data-exports")

    assert response.status_code == 200, response.text
    status = response.json()
    summary = json.loads((EXPORT_DIR / "generation_summary.json").read_text(encoding="utf-8"))
    validation = json.loads((EXPORT_DIR / "validation_report.json").read_text(encoding="utf-8"))

    assert status["status"] == "ready"
    assert status["source_database"] == "performtrack_db"
    assert status["preparation_mode"] == "read_only_merge"
    assert status["total_rows"] == 130126
    assert status["total_rows"] == validation["total_rows"]
    assert status["dataset_sha256"] == summary["dataset_sha256"]
    assert status["validation"]["duplicate_primary_keys"] == 0
    assert status["validation"]["foreign_key_columns_validated"] == 292500
    assert len(status["tables"]) == len(EXPORT_TABLES)

    for table in status["tables"]:
        assert table["table"] in EXPORT_TABLES
        assert table["rows"] == summary["counts"][table["table"]]
        for file_format in ("csv", "json"):
            artifact = table[file_format]
            content = (EXPORT_DIR / artifact["file_name"]).read_bytes()
            assert hashlib.sha256(content).hexdigest() == artifact["sha256"]
            if file_format == "csv":
                assert len(list(csv.DictReader(io.StringIO(content.decode("utf-8"))))) == table["rows"]
            else:
                assert len(json.loads(content)) == table["rows"]

    sql_content = (EXPORT_DIR / "seed.sql").read_bytes()
    sql_counts = {name: 0 for name in EXPORT_TABLES}
    for table_name in INSERT_PATTERN.findall(sql_content):
        decoded_name = table_name.decode("ascii")
        if decoded_name in sql_counts:
            sql_counts[decoded_name] += 1
    assert sql_counts == summary["counts"]
    assert status["sql"]["rows"] == 130126
    assert status["sql"]["sha256"] == hashlib.sha256(sql_content).hexdigest()
    assert status["documentation"]


def test_csv_json_and_sql_downloads_are_existing_data(tmp_path: Path) -> None:
    with TestClient(app) as client:
        csv_response = client.get("/api/v1/data-exports/csv/employees.csv")
        json_response = client.get("/api/v1/data-exports/json/employees.json")
        sql_response = client.get("/api/v1/data-exports/sql/seed.sql")
        validation_response = client.get("/api/v1/data-exports/json/validation_report.json")
        readme_response = client.get("/api/v1/data-exports/docs/README.md")
        schema_response = client.get("/api/v1/data-exports/docs/DATABASE_SCHEMA.md")
        dictionary_response = client.get("/api/v1/data-exports/docs/DATA_DICTIONARY.md")

    assert csv_response.status_code == 200
    assert json_response.status_code == 200
    assert sql_response.status_code == 200
    assert validation_response.status_code == 200
    assert readme_response.status_code == 200
    assert schema_response.status_code == 200
    assert dictionary_response.status_code == 200

    csv_rows = list(csv.DictReader(io.StringIO(csv_response.content.decode("utf-8"))))
    json_rows = json_response.json()
    assert len(csv_rows) == len(json_rows) == 3000
    assert csv_rows[0]["id"] == json_rows[0]["id"] == "EMP-000001"

    sql_insert_counts = {name: 0 for name in EXPORT_TABLES}
    for table_name in INSERT_PATTERN.findall(sql_response.content):
        name = table_name.decode("ascii")
        if name in sql_insert_counts:
            sql_insert_counts[name] += 1
    assert sum(sql_insert_counts.values()) == 130126
    assert sql_insert_counts["evidence"] == 4600
    assert b"INSERT INTO \"employees\"" in sql_response.content
    assert csv_response.content == (EXPORT_DIR / "employees.csv").read_bytes()
    assert json_response.content == (EXPORT_DIR / "employees.json").read_bytes()
    assert sql_response.content == (EXPORT_DIR / "seed.sql").read_bytes()
    assert validation_response.json()["duplicate_primary_keys"] == 0
    assert b"Data & Exports" in readme_response.content
    assert b"PerformTrack database schema" in schema_response.content
    assert b"entity_history" in dictionary_response.content
    assert list(tmp_path.iterdir()) == []


def test_export_routes_reject_unknown_formats_paths_and_mutations() -> None:
    with TestClient(app) as client:
        path_traversal = client.get("/api/v1/data-exports/csv/..%2F..%2FREADME.md")
        unknown_file = client.get("/api/v1/data-exports/csv/seed.csv")
        unknown_format = client.get("/api/v1/data-exports/zip/employees.zip")
        overwrite = client.put(
            "/api/v1/data-exports/csv/employees.csv",
            content=b"replace",
        )
        delete = client.delete("/api/v1/data-exports/sql/seed.sql")

    assert path_traversal.status_code in {404, 405}
    assert unknown_file.status_code == 404
    assert unknown_format.status_code == 422
    assert overwrite.status_code == 405
    assert delete.status_code == 405
