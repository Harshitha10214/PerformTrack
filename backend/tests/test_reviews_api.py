from collections.abc import Iterator
from contextlib import contextmanager

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import engine, get_db
from app.main import app
from app.models import Competency, Employee, EntityHistory, Manager, ReviewCycle


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


def _employee_with_manager(db: Session, *, exclude_id: str | None = None) -> Employee:
    query = select(Employee).where(Employee.manager_id.is_not(None))
    if exclude_id:
        query = query.where(Employee.id != exclude_id)
    employee = db.scalar(query.order_by(Employee.id).limit(1))
    assert employee is not None
    return employee


def _new_cycle(client: TestClient, year: int = 2032) -> dict:
    response = client.post(
        "/api/v1/review-cycles",
        json={
            "year": year,
            "half": "H1",
            "name": f"{year} H1 Test Cycle",
            "starts_on": f"{year}-01-01",
            "ends_on": f"{year}-06-30",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def _new_review(client: TestClient, db: Session, cycle_id: str, *, exclude_id: str | None = None) -> dict:
    employee = _employee_with_manager(db, exclude_id=exclude_id)
    competency_id = db.scalar(
        select(Competency.id).where(Competency.status == "active").order_by(Competency.id).limit(1)
    )
    response = client.post(
        "/api/v1/reviews",
        json={
            "employee_id": employee.id,
            "reviewer_manager_id": employee.manager_id,
            "review_cycle_id": cycle_id,
            "summary": "Performance summary with clear evidence and growth context.",
            "rating": "4.25",
            "effective_from": "2032-01-01",
            "effective_to": None,
            "competency_ids": [competency_id],
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_review_cycle_listing_retrieval_creation_and_updates() -> None:
    with rollback_client() as (client, _):
        listed = client.get("/api/v1/review-cycles", params={"page": 1, "page_size": 10})
        assert listed.status_code == 200
        assert listed.json()["total"] >= 6
        assert listed.json()["items"][0]["review_count"] >= 0

        cycle = _new_cycle(client)
        details = client.get(f"/api/v1/review-cycles/{cycle['id']}")
        assert details.status_code == 200
        assert details.json()["status"] == "draft"

        updated = client.patch(
            f"/api/v1/review-cycles/{cycle['id']}",
            json={"name": "Updated test cycle", "status": "open"},
        )
        assert updated.status_code == 200
        assert updated.json()["name"] == "Updated test cycle"
        assert updated.json()["status"] == "open"


def test_review_creation_validation_lifecycle_approval_and_audit() -> None:
    with rollback_client() as (client, db):
        cycle = _new_cycle(client)
        assert client.patch(f"/api/v1/review-cycles/{cycle['id']}", json={"status": "open"}).status_code == 200
        review = _new_review(client, db, cycle["id"])
        review_id = review["id"]
        assert review["employee_name"]
        assert review["reviewer_name"]
        assert review["approvals"][0]["status"] == "pending"
        assert review["competencies"][0]["id"]

        details = client.get(f"/api/v1/reviews/{review_id}")
        assert details.status_code == 200
        listed = client.get("/api/v1/reviews", params={"review_cycle_id": cycle["id"]})
        assert listed.status_code == 200
        assert listed.json()["total"] == 1

        started = client.patch(f"/api/v1/reviews/{review_id}", json={"status": "in_progress"})
        assert started.status_code == 200
        submitted = client.patch(
            f"/api/v1/reviews/{review_id}",
            json={"summary": "Finalized review summary with next steps.", "status": "submitted"},
        )
        assert submitted.status_code == 200
        assert submitted.json()["approval_actionable"] is True
        locked = client.patch(f"/api/v1/reviews/{review_id}", json={"summary": "Not editable now."})
        assert locked.status_code == 409
        direct_approval = client.patch(f"/api/v1/reviews/{review_id}", json={"status": "approved"})
        assert direct_approval.status_code == 409

        other_manager = db.scalar(
            select(Manager.id).where(Manager.id != review["reviewer_manager_id"]).order_by(Manager.id).limit(1)
        )
        wrong_approver = client.post(
            f"/api/v1/reviews/{review_id}/approval",
            json={"approver_manager_id": other_manager, "status": "approved"},
        )
        assert wrong_approver.status_code == 422

        approved = client.post(
            f"/api/v1/reviews/{review_id}/approval",
            json={
                "approver_manager_id": review["reviewer_manager_id"],
                "status": "approved",
                "comments": "Approved with evidence.",
            },
        )
        assert approved.status_code == 200
        assert approved.json()["status"] == "approved"
        assert approved.json()["approvals"][0]["comments"] == "Approved with evidence."
        acknowledged = client.patch(f"/api/v1/reviews/{review_id}", json={"status": "acknowledged"})
        assert acknowledged.status_code == 200
        assert acknowledged.json()["status"] == "acknowledged"

        history = db.scalars(
            select(EntityHistory)
            .where(EntityHistory.entity_type == "Review", EntityHistory.entity_id == review_id)
            .order_by(EntityHistory.recorded_at)
        ).all()
        assert {event.action for event in history} >= {"INSERT", "UPDATE", "RELATIONSHIP_INSERTED"}
        approval_events = [event for event in history if event.after_data and "approval" in event.after_data]
        assert len(approval_events) >= 2
        assert all(event.actor_employee_id for event in history)


def test_review_relationship_and_competency_validation() -> None:
    with rollback_client() as (client, db):
        cycle = _new_cycle(client)
        employee = _employee_with_manager(db)
        other_manager_id = db.scalar(
            select(Manager.id)
            .where(Manager.id != employee.manager_id)
            .order_by(Manager.id)
            .limit(1)
        )
        assert other_manager_id is not None
        competency = db.scalar(select(Competency.id).order_by(Competency.id).limit(1))
        payload = {
            "employee_id": employee.id,
            "reviewer_manager_id": employee.manager_id,
            "review_cycle_id": cycle["id"],
            "summary": "Review summary for relationship validation.",
            "effective_from": "2032-01-01",
            "competency_ids": [competency],
        }
        invalid_employee = client.post("/api/v1/reviews", json={**payload, "employee_id": "EMP-999999"})
        assert invalid_employee.status_code == 422

        invalid_reviewer = client.post(
            "/api/v1/reviews",
            json={**payload, "reviewer_manager_id": other_manager_id},
        )
        assert invalid_reviewer.status_code == 422

        invalid_competency = client.post(
            "/api/v1/reviews",
            json={**payload, "competency_ids": ["COMP-999999"]},
        )
        assert invalid_competency.status_code == 422

        invalid_cycle = client.post(
            "/api/v1/reviews",
            json={**payload, "review_cycle_id": "CYCLE-2032-H2"},
        )
        assert invalid_cycle.status_code == 422

        created = client.post("/api/v1/reviews", json=payload)
        assert created.status_code == 201
        duplicate = client.post("/api/v1/reviews", json=payload)
        assert duplicate.status_code == 409


def test_manager_employee_can_be_reviewed_by_another_manager() -> None:
    with rollback_client() as (client, db):
        cycle = _new_cycle(client)
        manager_employee = db.scalar(
            select(Employee)
            .join(Manager, Manager.employee_id == Employee.id)
            .order_by(Employee.id)
            .limit(1)
        )
        other_manager = db.scalar(
            select(Manager)
            .where(Manager.employee_id != manager_employee.id)
            .order_by(Manager.id)
            .limit(1)
        )
        assert manager_employee is not None
        assert other_manager is not None
        response = client.post(
            "/api/v1/reviews",
            json={
                "employee_id": manager_employee.id,
                "reviewer_manager_id": other_manager.id,
                "review_cycle_id": cycle["id"],
                "summary": "Manager review using a valid peer manager.",
                "effective_from": "2032-01-01",
                "competency_ids": [],
            },
        )
        assert response.status_code == 201, response.text
        assert response.json()["reviewer_name"] == (
            f"{other_manager.employee.first_name} {other_manager.employee.last_name}"
        )


def test_review_rejection_resubmission_and_closed_cycle_edit_rejection() -> None:
    with rollback_client() as (client, db):
        cycle = _new_cycle(client)
        client.patch(f"/api/v1/review-cycles/{cycle['id']}", json={"status": "open"})
        review = _new_review(client, db, cycle["id"])
        review_id = review["id"]
        client.patch(f"/api/v1/reviews/{review_id}", json={"status": "in_progress"})
        client.patch(f"/api/v1/reviews/{review_id}", json={"status": "submitted"})
        rejected = client.post(
            f"/api/v1/reviews/{review_id}/approval",
            json={
                "approver_manager_id": review["reviewer_manager_id"],
                "status": "rejected",
                "comments": "Please add more detail.",
            },
        )
        assert rejected.status_code == 200
        assert rejected.json()["status"] == "in_progress"

        resubmitted = client.patch(
            f"/api/v1/reviews/{review_id}",
            json={"summary": "Updated after review comments.", "status": "submitted"},
        )
        assert resubmitted.status_code == 200
        assert resubmitted.json()["approvals"][0]["status"] == "pending"

        assert client.patch(f"/api/v1/review-cycles/{cycle['id']}", json={"status": "closed"}).status_code == 200
        closed_edit = client.patch(f"/api/v1/reviews/{review_id}", json={"summary": "Closed cycle edit."})
        assert closed_edit.status_code == 409
        closed_approval = client.post(
            f"/api/v1/reviews/{review_id}/approval",
            json={
                "approver_manager_id": review["reviewer_manager_id"],
                "status": "approved",
            },
        )
        assert closed_approval.status_code == 409
        closed_creation = client.post(
            "/api/v1/reviews",
            json={
                "employee_id": review["employee_id"],
                "reviewer_manager_id": review["reviewer_manager_id"],
                "review_cycle_id": cycle["id"],
                "summary": "Cannot create in a closed cycle.",
                "effective_from": "2032-01-01",
                "competency_ids": [],
            },
        )
        assert closed_creation.status_code == 409
