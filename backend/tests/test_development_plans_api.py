from collections.abc import Iterator
from contextlib import contextmanager

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import engine, get_db
from app.main import app
from app.models import (
    Competency,
    DevelopmentPlan,
    Employee,
    EntityHistory,
    Goal,
    Manager,
    ReviewCycle,
)


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


def _references(db: Session) -> tuple[Employee, Manager, Goal, Competency]:
    employee, manager, goal = db.execute(
        select(Employee, Manager, Goal)
        .join(Manager, Employee.manager_id == Manager.id)
        .join(Goal, Goal.employee_id == Employee.id)
        .order_by(Employee.id, Goal.id)
        .limit(1)
    ).one()
    competency = db.scalar(select(Competency).order_by(Competency.id).limit(1))
    assert competency is not None
    return employee, manager, goal, competency


def _payload(employee: Employee, owner: Manager, goal: Goal, competency: Competency) -> dict:
    return {
        "employee_id": employee.id,
        "owner_manager_id": owner.id,
        "title": "Build strategic planning skills",
        "description": "Complete a guided planning project and review outcomes.",
        "effective_from": "2026-11-08",
        "goal_ids": [goal.id],
        "competency_ids": [competency.id],
    }


def test_development_plans_api_returns_paginated_records() -> None:
    response = TestClient(app).get(
        "/api/v1/development-plans",
        params={"page": 1, "page_size": 3},
    )

    assert response.status_code == 200
    result = response.json()
    assert result["total"] == 3000
    assert len(result["items"]) == 3
    assert result["page"] == 1
    assert result["page_size"] == 3
    assert {
        "id",
        "employee_id",
        "employee_name",
        "owner_manager_id",
        "owner_manager_name",
        "review_cycle_id",
        "review_cycle_name",
        "title",
        "description",
        "effective_from",
        "effective_to",
        "status",
        "goals",
        "competencies",
        "approvals",
        "editable",
        "approval_actionable",
    } <= result["items"][0].keys()


def test_development_plans_api_filters_by_status() -> None:
    client = TestClient(app)
    all_plans = client.get("/api/v1/development-plans", params={"page_size": 1}).json()
    status = all_plans["items"][0]["status"]

    response = client.get(
        "/api/v1/development-plans",
        params={"status": status, "page": 1, "page_size": 10},
    )

    assert response.status_code == 200
    result = response.json()
    assert result["items"]
    assert all(plan["status"] == status for plan in result["items"])


def test_create_update_relationships_approval_lifecycle_and_audit() -> None:
    with rollback_client() as (client, db):
        employee, owner, goal, competency = _references(db)
        created = client.post(
            "/api/v1/development-plans",
            json=_payload(employee, owner, goal, competency),
        )
        assert created.status_code == 201, created.text
        plan = created.json()
        plan_id = plan["id"]
        assert plan["status"] == "draft"
        assert plan["editable"] is True
        assert plan["approval_actionable"] is True
        assert plan["goals"] == [{"id": goal.id, "title": goal.title}]
        assert plan["competencies"][0]["id"] == competency.id
        assert plan["approvals"][0]["status"] == "pending"

        details = client.get(f"/api/v1/development-plans/{plan_id}")
        assert details.status_code == 200
        assert details.json()["employee_name"] == f"{employee.first_name} {employee.last_name}"

        updated = client.patch(
            f"/api/v1/development-plans/{plan_id}",
            json={
                "title": "Build stronger planning skills",
                "goal_ids": [],
                "competency_ids": [],
            },
        )
        assert updated.status_code == 200
        assert updated.json()["title"] == "Build stronger planning skills"
        assert updated.json()["goals"] == []
        assert updated.json()["competencies"] == []

        linked_again = client.patch(
            f"/api/v1/development-plans/{plan_id}",
            json={"goal_ids": [goal.id], "competency_ids": [competency.id]},
        )
        assert linked_again.status_code == 200
        assert linked_again.json()["goals"][0]["id"] == goal.id
        assert linked_again.json()["competencies"][0]["id"] == competency.id

        approved = client.post(
            f"/api/v1/development-plans/{plan_id}/approval",
            json={
                "approver_manager_id": owner.id,
                "status": "approved",
                "comments": "Approved for the current cycle.",
            },
        )
        assert approved.status_code == 200
        assert approved.json()["status"] == "active"
        assert approved.json()["approvals"][0]["comments"] == "Approved for the current cycle."
        assert approved.json()["editable"] is False

        content_edit = client.patch(f"/api/v1/development-plans/{plan_id}", json={"title": "Too late"})
        invalid_transition = client.patch(f"/api/v1/development-plans/{plan_id}", json={"status": "draft"})
        completed = client.patch(f"/api/v1/development-plans/{plan_id}", json={"status": "completed"})
        terminal_edit = client.patch(f"/api/v1/development-plans/{plan_id}", json={"title": "Terminal edit"})
        assert content_edit.status_code == invalid_transition.status_code == 409
        assert completed.status_code == 200
        assert completed.json()["status"] == "completed"
        assert terminal_edit.status_code == 409

        events = db.scalars(
            select(EntityHistory).where(
                EntityHistory.entity_type == "DevelopmentPlan",
                EntityHistory.entity_id == plan_id,
            )
        ).all()
        actions = {event.action for event in events}
        assert {"INSERT", "UPDATE", "RELATIONSHIP_INSERTED", "RELATIONSHIP_DELETED"} <= actions
        approval_events = [event for event in events if event.after_data and "approval" in event.after_data]
        assert len(approval_events) == 2
        assert all(event.actor_employee_id == owner.employee_id for event in events)
        assert any(event.after_data["approval"]["status"] == "approved" for event in approval_events)


def test_plan_creation_rejects_invalid_employee_owner_and_link_relationships() -> None:
    with rollback_client() as (client, db):
        employee, owner, goal, competency = _references(db)
        payload = _payload(employee, owner, goal, competency)
        invalid_employee = client.post(
            "/api/v1/development-plans",
            json={**payload, "employee_id": "EMP-999999"},
        )
        assert invalid_employee.status_code == 422

        other_owner = db.scalar(select(Manager).where(Manager.id != owner.id).order_by(Manager.id).limit(1))
        assert other_owner is not None
        invalid_owner = client.post(
            "/api/v1/development-plans",
            json={**payload, "owner_manager_id": other_owner.id},
        )
        assert invalid_owner.status_code == 422

        other_goal = db.scalar(
            select(Goal).where(Goal.employee_id != employee.id).order_by(Goal.id).limit(1)
        )
        assert other_goal is not None
        invalid_goal = client.post(
            "/api/v1/development-plans",
            json={**payload, "goal_ids": [other_goal.id]},
        )
        missing_goal = client.post(
            "/api/v1/development-plans",
            json={**payload, "goal_ids": ["GOAL-MISSING"]},
        )
        invalid_competency = client.post(
            "/api/v1/development-plans",
            json={**payload, "competency_ids": ["COMP-999999"]},
        )
        closed_cycle = db.scalar(
            select(ReviewCycle).where(ReviewCycle.status == "closed").order_by(ReviewCycle.id).limit(1)
        )
        assert closed_cycle is not None
        closed_cycle_plan = client.post(
            "/api/v1/development-plans",
            json={
                **payload,
                "review_cycle_id": closed_cycle.id,
                "effective_from": closed_cycle.starts_on.isoformat(),
            },
        )
        assert invalid_goal.status_code == 422
        assert missing_goal.status_code == 422
        assert invalid_competency.status_code == 422
        assert closed_cycle_plan.status_code == 409

        created = client.post("/api/v1/development-plans", json=payload)
        assert created.status_code == 201
        other_goal = db.scalar(
            select(Goal).where(Goal.employee_id != employee.id).order_by(Goal.id).limit(1)
        )
        assert other_goal is not None
        invalid_goal_link = client.patch(
            f"/api/v1/development-plans/{created.json()['id']}",
            json={"goal_ids": [other_goal.id]},
        )
        invalid_competency_link = client.patch(
            f"/api/v1/development-plans/{created.json()['id']}",
            json={"competency_ids": ["COMP-999999"]},
        )
        assert invalid_goal_link.status_code == 422
        assert invalid_competency_link.status_code == 422


def test_rejection_cancels_plan_and_prevents_repeated_decision() -> None:
    with rollback_client() as (client, db):
        employee, owner, goal, competency = _references(db)
        created = client.post(
            "/api/v1/development-plans",
            json=_payload(employee, owner, goal, competency),
        )
        assert created.status_code == 201, created.text
        plan_id = created.json()["id"]

        wrong_approver = client.post(
            f"/api/v1/development-plans/{plan_id}/approval",
            json={"approver_manager_id": "MGR-999999", "status": "approved"},
        )
        rejected = client.post(
            f"/api/v1/development-plans/{plan_id}/approval",
            json={"approver_manager_id": owner.id, "status": "rejected", "comments": "Needs revision."},
        )
        repeat = client.post(
            f"/api/v1/development-plans/{plan_id}/approval",
            json={"approver_manager_id": owner.id, "status": "approved"},
        )

        assert wrong_approver.status_code == 422
        assert rejected.status_code == 200
        assert rejected.json()["status"] == "cancelled"
        assert rejected.json()["approvals"][0]["status"] == "rejected"
        assert repeat.status_code == 409
        history = db.scalars(
            select(EntityHistory).where(
                EntityHistory.entity_type == "DevelopmentPlan",
                EntityHistory.entity_id == plan_id,
            )
        ).all()
        assert any(
            item.after_data
            and item.after_data.get("approval", {}).get("status") == "rejected"
            for item in history
        )
