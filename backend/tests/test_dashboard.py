from fastapi.testclient import TestClient

from app.main import app


def test_dashboard_analytics_returns_live_database_metrics() -> None:
    response = TestClient(app).get("/api/v1/dashboard/analytics")

    assert response.status_code == 200
    payload = response.json()
    overview = payload["overview"]
    assert overview["total_employees"] >= 0
    assert overview["total_managers"] >= 0
    assert overview["total_goals"] >= overview["completed_goals"] >= 0
    assert overview["active_review_cycles"] >= 0
    assert overview["pending_reviews"] >= 0
    assert overview["average_goal_progress"] is None or (
        0 <= overview["average_goal_progress"] <= 100
    )

    assert sum(band["count"] for band in payload["goal_progress_distribution"]) <= overview[
        "total_goals"
    ]
    assert len(payload["recent_check_ins"]) <= 8
    assert all(
        department["average_goal_progress"] is None
        or 0 <= department["average_goal_progress"] <= 100
        for department in payload["department_performance"]
    )
    quality = payload["data_quality"]
    assert quality["checks_passed"] + sum(
        not check["passed"] for check in quality["checks"]
    ) == quality["checks_total"]
