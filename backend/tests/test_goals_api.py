from fastapi.testclient import TestClient

from app.main import app
from app.schemas.goals import GoalCreate


def test_goals_api_returns_progress_calculated_from_key_results() -> None:
    response = TestClient(app).get("/api/v1/goals", params={"page": 1, "page_size": 3})

    assert response.status_code == 200
    result = response.json()
    assert result["total"] == 10000
    assert len(result["items"]) == 3
    for goal in result["items"]:
        assert goal["key_results"]
        assert 0 <= float(goal["progress"]) <= 100
        expected = sum(
            min(float(item["current_value"] or 0) * 100 / float(item["target_value"]), 100)
            * (float(item["weight"]) / 100 if item["weight"] is not None else 1 / len(goal["key_results"]))
            for item in goal["key_results"]
        )
        assert abs(float(goal["progress"]) - expected) < 0.02


def test_goal_create_schema_requires_key_results_and_valid_weights() -> None:
    base = {
        "employee_id": "EMP-000001",
        "review_cycle_id": "CYCLE-2026-H1",
        "title": "Improve outcomes",
        "description": "Deliver measurable outcomes.",
        "effective_from": "2026-01-01",
        "due_date": "2026-06-30",
        "key_results": [
            {
                "title": "Ship adoption",
                "description": "Increase adoption.",
                "unit": "percent",
                "target_value": 100,
                "weight": 70,
                "effective_from": "2026-01-01",
                "due_date": "2026-06-30",
            },
            {
                "title": "Reduce incidents",
                "description": "Reduce incidents.",
                "unit": "count",
                "target_value": 20,
                "weight": 20,
                "effective_from": "2026-01-01",
                "due_date": "2026-06-30",
            },
        ],
    }
    try:
        GoalCreate(**base)
    except ValueError as exc:
        assert "sum to 100" in str(exc)
    else:
        raise AssertionError("Invalid key-result weights must be rejected")
