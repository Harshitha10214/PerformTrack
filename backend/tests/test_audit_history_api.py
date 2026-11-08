from fastapi.testclient import TestClient

from app.main import app


def test_audit_history_list_is_paginated_and_chronological() -> None:
    with TestClient(app) as client:
        first_response = client.get(
            "/api/v1/audit-history",
            params={"page": 1, "page_size": 5},
        )
        second_response = client.get(
            "/api/v1/audit-history",
            params={"page": 2, "page_size": 5},
        )

    assert first_response.status_code == 200
    assert second_response.status_code == 200
    first = first_response.json()
    second = second_response.json()
    assert first["total"] == 119526
    assert len(first["items"]) == 5
    assert first["page"] == 1
    assert second["page"] == 2
    first_keys = [(item["recorded_at"], item["event_id"]) for item in first["items"]]
    assert first_keys == sorted(first_keys, reverse=True)
    assert set(item["event_id"] for item in first["items"]).isdisjoint(
        item["event_id"] for item in second["items"]
    )
    assert first["items"][0]["actor_id"] == "SYSTEM"
    assert first["items"][0]["actor_attribution_available"] is False
    assert first["items"][0]["operation"] in {"INSERT", "RELATIONSHIP_INSERTED"}


def test_audit_history_filters_entity_operation_and_date_range() -> None:
    with TestClient(app) as client:
        employees = client.get(
            "/api/v1/audit-history",
            params={
                "entity_type": "Employee",
                "entity_id": "EMP-000001",
                "operation": "INSERT",
                "date_from": "2026-11-06",
                "date_to": "2026-11-06",
                "page": 1,
                "page_size": 10,
            },
        )
        goals = client.get(
            "/api/v1/audit-history",
            params={"entity_type": "Goal", "page": 1, "page_size": 1},
        )
        reviews = client.get(
            "/api/v1/audit-history",
            params={"entity_type": "Review", "page": 1, "page_size": 1},
        )
        evidence = client.get(
            "/api/v1/audit-history",
            params={"entity_type": "Evidence", "page": 1, "page_size": 1},
        )

    assert employees.status_code == 200
    employee_result = employees.json()
    assert employee_result["total"] == 1
    assert employee_result["items"][0]["entity_id"] == "EMP-000001"
    assert employee_result["items"][0]["entity_type"] == "Employee"
    assert employee_result["items"][0]["operation"] == "INSERT"
    assert employee_result["items"][0]["recorded_at"].startswith("2026-11-06")
    assert employee_result["items"][0]["after_data"]["id"] == "EMP-000001"
    assert goals.json()["total"] > 0
    assert goals.json()["items"][0]["entity_type"] == "Goal"
    assert reviews.json()["total"] > 0
    assert reviews.json()["items"][0]["entity_type"] == "Review"
    assert evidence.json()["total"] == 0


def test_audit_history_rejects_invalid_filters_and_date_ranges() -> None:
    with TestClient(app) as client:
        invalid_type = client.get("/api/v1/audit-history", params={"entity_type": "Payroll"})
        invalid_operation = client.get("/api/v1/audit-history", params={"operation": "UPSERT"})
        invalid_range = client.get(
            "/api/v1/audit-history",
            params={"date_from": "2026-11-07", "date_to": "2026-11-06"},
        )

    assert invalid_type.status_code == 422
    assert invalid_operation.status_code == 422
    assert invalid_range.status_code == 422


def test_audit_history_detail_is_read_only() -> None:
    with TestClient(app) as client:
        listed = client.get("/api/v1/audit-history", params={"page": 1, "page_size": 1}).json()
        event_id = listed["items"][0]["event_id"]
        details = client.get(f"/api/v1/audit-history/{event_id}")
        update = client.put(f"/api/v1/audit-history/{event_id}", json={"actor_id": "spoofed"})
        delete = client.delete(f"/api/v1/audit-history/{event_id}")
        invalid_id = client.get("/api/v1/audit-history/not-an-event-id")

    assert details.status_code == 200
    assert details.json()["event_id"] == event_id
    assert details.json()["before_data"] is None
    assert details.json()["after_data"]
    assert update.status_code == 405
    assert delete.status_code == 405
    assert invalid_id.status_code == 404
