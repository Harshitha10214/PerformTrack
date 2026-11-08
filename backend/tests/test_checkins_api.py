from collections.abc import Iterator
from contextlib import contextmanager
from datetime import timedelta

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import engine, get_db
from app.main import app
from app.models import CheckIn, Employee, EntityHistory, Goal, KeyResult, Manager, ReviewCycle


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


def _valid_references(db: Session) -> tuple[Employee, Manager, ReviewCycle, KeyResult]:
    employee, manager, cycle, key_result = db.execute(
        select(Employee, Manager, ReviewCycle, KeyResult)
        .join(Manager, Employee.manager_id == Manager.id)
        .join(Goal, Goal.employee_id == Employee.id)
        .join(KeyResult, KeyResult.goal_id == Goal.id)
        .join(ReviewCycle, ReviewCycle.id == Goal.review_cycle_id)
        .where(ReviewCycle.status == "open")
        .order_by(Employee.id, KeyResult.id)
        .limit(1)
    ).one()
    return employee, manager, cycle, key_result


def _payload(
    employee: Employee,
    manager: Manager,
    cycle: ReviewCycle,
    key_result_ids: list[str] | None = None,
) -> dict:
    return {
        "employee_id": employee.id,
        "manager_id": manager.id,
        "review_cycle_id": cycle.id,
        "checkin_date": cycle.starts_on.isoformat(),
        "notes": "Discuss progress and next steps.",
        "status": "scheduled",
        "key_result_ids": key_result_ids or [],
    }


def test_checkins_api_returns_live_linked_records() -> None:
    response = TestClient(app).get("/api/v1/check-ins", params={"page": 1, "page_size": 5})

    assert response.status_code == 200
    result = response.json()
    assert result["total"] == 20000
    assert len(result["items"]) == 5
    for item in result["items"]:
        assert item["employee_id"]
        assert item["manager_id"]
        assert item["employee_name"]
        assert item["manager_name"]
        assert isinstance(item["key_result_ids"], list)


def test_valid_creation_and_updates_preserve_database_audit_history() -> None:
    with rollback_client() as (client, db):
        employee, manager, cycle, key_result = _valid_references(db)
        created = client.post(
            "/api/v1/check-ins",
            json=_payload(employee, manager, cycle, [key_result.id]),
        )

        assert created.status_code == 201, created.text
        record = created.json()
        assert record["employee_id"] == employee.id
        assert record["manager_id"] == manager.id
        assert record["review_cycle_id"] == cycle.id
        assert record["key_result_ids"] == [key_result.id]

        updated = client.patch(
            f"/api/v1/check-ins/{record['id']}",
            json={"notes": "Reviewed progress and updated next steps.", "status": "completed"},
        )
        assert updated.status_code == 200
        assert updated.json()["status"] == "completed"
        assert updated.json()["notes"] == "Reviewed progress and updated next steps."

        history = db.scalars(
            select(EntityHistory)
            .where(EntityHistory.entity_type == "CheckIn", EntityHistory.entity_id == record["id"])
            .order_by(EntityHistory.recorded_at)
        ).all()
        assert {event.action for event in history} >= {
            "INSERT",
            "UPDATE",
            "RELATIONSHIP_INSERTED",
        }
        assert any(
            event.after_data and event.after_data.get("key_result_id") == key_result.id
            for event in history
            if event.action == "RELATIONSHIP_INSERTED"
        )


def test_creation_rejects_closed_draft_or_archived_cycles() -> None:
    with rollback_client() as (client, db):
        employee, manager, _, _ = _valid_references(db)
        inactive_cycles = db.scalars(
            select(ReviewCycle)
            .where(ReviewCycle.status.in_(("draft", "closed", "archived")))
            .order_by(ReviewCycle.id)
        ).all()
        assert {cycle.status for cycle in inactive_cycles} >= {"closed"}

        for cycle in inactive_cycles:
            response = client.post(
                "/api/v1/check-ins",
                json=_payload(employee, manager, cycle),
            )
            assert response.status_code == 409


def test_update_rejects_checkins_in_closed_cycles_without_mutation() -> None:
    with rollback_client() as (client, db):
        item = db.scalar(
            select(CheckIn)
            .join(ReviewCycle, ReviewCycle.id == CheckIn.review_cycle_id)
            .where(ReviewCycle.status.in_(("draft", "closed", "archived")))
            .order_by(CheckIn.id)
            .limit(1)
        )
        assert item is not None
        original_notes = item.notes
        history_before = db.scalar(
            select(EntityHistory.event_id).where(
                EntityHistory.entity_type == "CheckIn",
                EntityHistory.entity_id == item.id,
                EntityHistory.action == "UPDATE",
            )
        )

        response = client.patch(
            f"/api/v1/check-ins/{item.id}",
            json={"notes": "This update must not be persisted."},
        )

        assert response.status_code == 409
        db.refresh(item)
        assert item.notes == original_notes
        history_after = db.scalar(
            select(EntityHistory.event_id).where(
                EntityHistory.entity_type == "CheckIn",
                EntityHistory.entity_id == item.id,
                EntityHistory.action == "UPDATE",
            )
        )
        assert history_after == history_before


def test_creation_and_update_reject_invalid_employee_manager_cycle_and_key_result_links() -> None:
    with rollback_client() as (client, db):
        employee, manager, cycle, key_result = _valid_references(db)
        payload = _payload(employee, manager, cycle, [key_result.id])

        other_manager = db.scalar(
            select(Manager).where(Manager.id != manager.id).order_by(Manager.id).limit(1)
        )
        other_employee = db.scalar(
            select(Employee).where(Employee.id != employee.id).order_by(Employee.id).limit(1)
        )
        other_key_result = db.scalar(
            select(KeyResult)
            .join(Goal, Goal.id == KeyResult.goal_id)
            .where(Goal.employee_id != employee.id)
            .order_by(KeyResult.id)
            .limit(1)
        )
        assert other_manager is not None
        assert other_employee is not None
        assert other_key_result is not None

        invalid_employee = client.post(
            "/api/v1/check-ins",
            json={**payload, "employee_id": "EMP-999999"},
        )
        invalid_manager = client.post(
            "/api/v1/check-ins",
            json={**payload, "manager_id": other_manager.id},
        )
        invalid_cycle = client.post(
            "/api/v1/check-ins",
            json={**payload, "review_cycle_id": "CYCLE-9999-H1"},
        )
        invalid_key_result = client.post(
            "/api/v1/check-ins",
            json={**payload, "key_result_ids": [other_key_result.id]},
        )
        out_of_cycle_date = client.post(
            "/api/v1/check-ins",
            json={**payload, "checkin_date": (cycle.starts_on - timedelta(days=1)).isoformat()},
        )
        assert invalid_employee.status_code == 422
        assert invalid_manager.status_code == 422
        assert invalid_cycle.status_code == 422
        assert invalid_key_result.status_code == 422
        assert out_of_cycle_date.status_code == 422

        created = client.post(
            "/api/v1/check-ins",
            json=_payload(employee, manager, cycle, [key_result.id]),
        )
        assert created.status_code == 201
        invalid_link_update = client.patch(
            f"/api/v1/check-ins/{created.json()['id']}",
            json={"key_result_ids": [other_key_result.id]},
        )
        assert invalid_link_update.status_code == 422
