import hashlib
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.database import engine, get_db
from app.main import app
from app.models import Employee, EntityHistory, Goal, KeyResult


@contextmanager
def rollback_client(storage_dir: Path) -> Iterator[tuple[TestClient, Session]]:
    connection = engine.connect()
    transaction = connection.begin()
    db = Session(bind=connection)
    original_overrides = app.dependency_overrides.copy()
    previous_storage_dir = settings.evidence_storage_dir
    settings.evidence_storage_dir = str(storage_dir)

    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    try:
        with TestClient(app) as client:
            yield client, db
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(original_overrides)
        settings.evidence_storage_dir = previous_storage_dir
        db.close()
        transaction.rollback()
        connection.close()


def _key_result_reference(db: Session) -> tuple[str, str]:
    return db.execute(
        select(KeyResult.id, Goal.employee_id)
        .join(Goal)
        .order_by(KeyResult.id)
        .limit(1)
    ).one()


def _upload(client: TestClient, employee_id: str, target_id: str, filename: str = "support.txt", content: bytes = b"Supporting evidence.\n"):
    return client.post(
        "/api/v1/evidence",
        data={
            "employee_id": employee_id,
            "target_type": "key_result",
            "target_id": target_id,
            "description": "Supporting documentation",
        },
        files={"file": (filename, content, "text/plain")},
    )


def test_evidence_list_and_details_return_existing_records() -> None:
    with TestClient(app) as client:
        response = client.get("/api/v1/evidence", params={"page": 1, "page_size": 3})

        assert response.status_code == 200
        result = response.json()
        assert result["total"] == 4600
        assert len(result["items"]) == 3
        assert result["items"][0]["employee_name"]
        assert result["items"][0]["linked_record_id"]
        assert result["items"][0]["file_name"] == "check-in-summary.txt"
        assert result["items"][0]["downloadable"] is False

        details = client.get(f"/api/v1/evidence/{result['items'][0]['id']}")
        assert details.status_code == 200
        assert details.json()["sha256"] == result["items"][0]["sha256"]
        unavailable_file = client.get(f"/api/v1/evidence/{result['items'][0]['id']}/file")
        assert unavailable_file.status_code == 404


def test_upload_retrieval_checksum_and_audit_history(
    tmp_path: Path,
) -> None:
    with rollback_client(tmp_path) as (client, db):
        target_id, employee_id = _key_result_reference(db)
        content = b"New supporting evidence.\n"

        response = _upload(client, employee_id, target_id, content=content)

        assert response.status_code == 201, response.text
        record = response.json()
        assert record["file_name"] == "support.txt"
        assert record["target_type"] == "key_result"
        assert record["downloadable"] is True
        assert record["size_bytes"] == len(content)
        assert record["sha256"] == hashlib.sha256(content).hexdigest()
        assert record["uri"].startswith(f"local-evidence://{record['id']}/")
        assert (tmp_path / record["id"]).read_bytes() == content

        downloaded = client.get(f"/api/v1/evidence/{record['id']}/file")
        assert downloaded.status_code == 200
        assert downloaded.content == content
        assert hashlib.sha256(downloaded.content).hexdigest() == record["sha256"]
        assert downloaded.headers["x-content-type-options"] == "nosniff"

        history = db.scalar(
            select(EntityHistory).where(
                EntityHistory.entity_type == "Evidence",
                EntityHistory.entity_id == record["id"],
                EntityHistory.action == "INSERT",
            )
        )
        assert history is not None
        assert history.actor_employee_id == employee_id
        assert history.after_data["sha256"] == record["sha256"]

        (tmp_path / record["id"]).write_bytes(b"X" * len(content))
        mismatch = client.get(f"/api/v1/evidence/{record['id']}/file")
        assert mismatch.status_code == 409
        assert "checksum" in mismatch.json()["detail"].lower()


def test_upload_rejects_unsupported_type_and_traversal_filename(tmp_path: Path) -> None:
    with rollback_client(tmp_path) as (client, db):
        target_id, employee_id = _key_result_reference(db)
        unsupported = client.post(
            "/api/v1/evidence",
            data={
                "employee_id": employee_id,
                "target_type": "key_result",
                "target_id": target_id,
                "description": "Unsupported file",
            },
            files={"file": ("malware.exe", b"not executable", "application/octet-stream")},
        )
        assert unsupported.status_code == 415

        traversal = _upload(client, employee_id, target_id, filename="..\\..\\outside.txt")
        assert traversal.status_code == 422
        assert list(tmp_path.iterdir()) == []


def test_upload_rejects_files_over_limit(tmp_path: Path) -> None:
    with rollback_client(tmp_path) as (client, db):
        target_id, employee_id = _key_result_reference(db)
        oversized = _upload(
            client,
            employee_id,
            target_id,
            content=b"x" * (10 * 1024 * 1024 + 1),
        )
        assert oversized.status_code == 413
        assert list(tmp_path.iterdir()) == []


def test_upload_rejects_missing_or_mismatched_relationships(tmp_path: Path) -> None:
    with rollback_client(tmp_path) as (client, db):
        target_id, linked_employee_id = _key_result_reference(db)
        other_employee_id = db.scalar(
            select(Employee.id).where(Employee.id != linked_employee_id).order_by(Employee.id).limit(1)
        )
        assert other_employee_id is not None

        mismatch = _upload(client, other_employee_id, target_id)
        missing = _upload(client, linked_employee_id, "KR-MISSING")

        assert mismatch.status_code == 422
        assert missing.status_code == 422
        assert list(tmp_path.iterdir()) == []


def test_evidence_endpoints_reject_path_traversal_ids() -> None:
    with TestClient(app) as client:
        response = client.get("/api/v1/evidence/../../etc/passwd/file")
        assert response.status_code in {404, 405}
