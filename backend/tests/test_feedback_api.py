from collections.abc import Iterator
from contextlib import contextmanager

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import engine, get_db
from app.main import app
from app.models import Competency, Employee, EntityHistory, Manager, ReviewCycle
from app.models.entities import employee_competencies


@contextmanager
def rollback_client() -> Iterator[tuple[TestClient, Session]]:
    connection = engine.connect()
    transaction = connection.begin()
    db = Session(bind=connection)
    original_overrides = app.dependency_overrides.copy()

    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    try:
        with TestClient(app) as client:
            yield client, db
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(original_overrides)
        db.close()
        transaction.rollback()
        connection.close()


def _feedback_payload(db: Session) -> dict:
    manager_id, author_id, subject_id = db.execute(
        select(Manager.id, Manager.employee_id, Employee.id)
        .join(Employee, Employee.manager_id == Manager.id)
        .where(Manager.employee_id != Employee.id)
        .limit(1)
    ).one()
    competency_id = db.scalar(select(Competency.id).where(Competency.status == "active").order_by(Competency.id).limit(1))
    cycle_id = db.scalar(select(ReviewCycle.id).where(ReviewCycle.status == "open").order_by(ReviewCycle.id).limit(1))
    assert manager_id and competency_id and cycle_id
    return {
        "author_employee_id": author_id,
        "subject_employee_id": subject_id,
        "reviewer_relationship": "manager",
        "review_cycle_id": cycle_id,
        "content": "Provided specific feedback with an actionable example.",
        "visibility": "manager",
        "status": "draft",
        "competency_ids": [competency_id],
    }


def test_competency_list_and_details_use_existing_postgresql_records() -> None:
    with TestClient(app) as client:
        listed = client.get("/api/v1/competencies", params={"page": 1, "page_size": 5})
        assert listed.status_code == 200
        payload = listed.json()
        assert payload["total"] == 20
        assert len(payload["items"]) == 5
        assert payload["items"][0]["description"]
        assert payload["items"][0]["employee_count"] > 0

        details = client.get(f"/api/v1/competencies/{payload['items'][0]['id']}")
        assert details.status_code == 200
        assert details.json()["id"] == payload["items"][0]["id"]


def test_employee_competencies_include_generated_proficiency_and_dates() -> None:
    with TestClient(app) as client:
        employee_id = client.get("/api/v1/employees", params={"page": 1, "page_size": 1}).json()["items"][0]["id"]
        linked = client.get(f"/api/v1/employees/{employee_id}/competencies")
        assert linked.status_code == 200
        assert len(linked.json()) == 3
        assert all(
            0 <= float(item["proficiency"]) <= 5 and item["effective_from"]
            for item in linked.json()
        )


def test_feedback_create_relationship_edit_lifecycle_and_audit_history() -> None:
    with rollback_client() as (client, db):
        payload = _feedback_payload(db)
        created = client.post("/api/v1/feedback", json=payload)
        assert created.status_code == 201, created.text
        record = created.json()
        feedback_id = record["id"]
        assert record["reviewer_relationship"] == "manager"
        assert record["author_name"] and record["subject_name"]
        assert record["editable"] is True
        assert record["competencies"][0]["id"] == payload["competency_ids"][0]

        updated = client.patch(
            f"/api/v1/feedback/{feedback_id}",
            json={"content": "Updated with a clear next step.", "status": "submitted"},
        )
        assert updated.status_code == 200
        assert updated.json()["status"] == "submitted"
        assert updated.json()["editable"] is False
        assert updated.json()["content"] == "Updated with a clear next step."

        forbidden_edit = client.patch(
            f"/api/v1/feedback/{feedback_id}", json={"content": "This edit is not allowed."}
        )
        assert forbidden_edit.status_code == 409
        withdrawn = client.patch(f"/api/v1/feedback/{feedback_id}", json={"status": "withdrawn"})
        assert withdrawn.status_code == 200
        terminal_edit = client.patch(
            f"/api/v1/feedback/{feedback_id}", json={"status": "submitted"}
        )
        assert terminal_edit.status_code == 409

        events = db.scalars(
            select(EntityHistory)
            .where(EntityHistory.entity_type == "Feedback", EntityHistory.entity_id == feedback_id)
            .order_by(EntityHistory.recorded_at)
        ).all()
        assert {event.action for event in events} >= {"INSERT", "UPDATE", "RELATIONSHIP_INSERTED"}
        assert all(event.actor_employee_id == payload["author_employee_id"] for event in events)


def test_feedback_rejects_invalid_people_self_review_and_reviewer_relationship() -> None:
    with TestClient(app) as client:
        page = client.get("/api/v1/employees", params={"page": 1, "page_size": 1}).json()
        employee_id = page["items"][0]["id"]
        base = {
            "author_employee_id": employee_id,
            "subject_employee_id": employee_id,
            "content": "Self feedback is prohibited.",
            "competency_ids": ["COMP-000001"],
            "reviewer_relationship": "peer",
        }
        self_feedback = client.post("/api/v1/feedback", json=base)
        assert self_feedback.status_code == 422

        invalid_author = client.post(
            "/api/v1/feedback",
            json={**base, "author_employee_id": "MGR-999999", "subject_employee_id": "EMP-999999"},
        )
        assert invalid_author.status_code == 422

    with rollback_client() as (client, db):
        payload = _feedback_payload(db)
        payload["reviewer_relationship"] = "peer"
        mismatch = client.post("/api/v1/feedback", json=payload)
        assert mismatch.status_code == 422


def test_feedback_rejects_unknown_competency_and_closed_cycle() -> None:
    with rollback_client() as (client, db):
        payload = _feedback_payload(db)
        invalid_competency = client.post(
            "/api/v1/feedback", json={**payload, "competency_ids": ["COMP-999999"]}
        )
        assert invalid_competency.status_code == 422

        closed_cycle = db.scalar(select(ReviewCycle.id).where(ReviewCycle.status == "closed").limit(1))
        invalid_cycle = client.post(
            "/api/v1/feedback", json={**payload, "review_cycle_id": closed_cycle}
        )
        assert invalid_cycle.status_code == 409


def test_feedback_list_search_filters_and_detail_show_reviewer_relationship() -> None:
    with TestClient(app) as client:
        listed = client.get(
            "/api/v1/feedback",
            params={"page": 1, "page_size": 5, "relationship": "peer"},
        )
        assert listed.status_code == 200
        result = listed.json()
        assert result["total"] > 0
        assert all(item["reviewer_relationship"] == "peer" for item in result["items"])

        details = client.get(f"/api/v1/feedback/{result['items'][0]['id']}")
        assert details.status_code == 200
        assert details.json()["reviewer_relationship"] == "peer"
