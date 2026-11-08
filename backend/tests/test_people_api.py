from fastapi.testclient import TestClient

from app.main import app
from app.schemas.people import EmployeeCreate, ManagerCreate


def test_employee_and_manager_lists_read_live_postgresql_records() -> None:
    client = TestClient(app)
    employees = client.get("/api/v1/employees", params={"page": 1, "page_size": 5})
    managers = client.get("/api/v1/managers", params={"page": 1, "page_size": 5})

    assert employees.status_code == 200
    assert managers.status_code == 200
    assert employees.json()["total"] == 3000
    assert managers.json()["total"] == 500
    assert len(employees.json()["items"]) == len(managers.json()["items"]) == 5
    assert {"id", "email", "manager_id", "department"} <= set(employees.json()["items"][0])
    assert {
        "id",
        "employee_id",
        "employee_name",
        "department",
        "report_count",
    } <= set(managers.json()["items"][0])


def test_people_api_search_and_filter_use_live_records() -> None:
    client = TestClient(app)
    employee = client.get(
        "/api/v1/employees",
        params={"search": "emp-000004", "status": "active", "page_size": 10},
    )
    manager = client.get(
        "/api/v1/managers",
        params={"search": "MGR-000004", "status": "active", "page_size": 10},
    )

    assert employee.status_code == manager.status_code == 200
    assert employee.json()["total"] >= 1
    assert all(row["status"] == "active" for row in employee.json()["items"])
    assert manager.json()["total"] >= 1
    assert all(row["status"] == "active" for row in manager.json()["items"])


def test_people_input_schemas_reject_invalid_business_values() -> None:
    try:
        EmployeeCreate(
            email="not-an-email",
            first_name="A",
            last_name="B",
            job_title="Engineer",
            department="Engineering",
            hire_date="2026-01-01",
            effective_from="2026-01-01",
            status="unknown",
        )
    except ValueError:
        pass
    else:
        raise AssertionError("Invalid employee email/status must be rejected")

    try:
        ManagerCreate(
            employee_id="EMP-000001",
            effective_from="2026-02-01",
            effective_to="2026-01-01",
        )
    except ValueError:
        pass
    else:
        raise AssertionError("Invalid manager effective dates must be rejected")
