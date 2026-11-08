from __future__ import annotations

from typing import Any

from app.generation.types import GeneratedDataset


EXPECTED_DECISIONS = {
    "goal_owner_mismatch": "REJECT",
    "unjustified_progress_over_100": "FLAG",
    "invalid_reviewer_relationship": "REJECT",
    "silent_edit_in_closed_cycle": "REJECT",
    "untraceable_feedback": "FLAG",
}


def build_anomaly_fixtures(dataset: GeneratedDataset) -> list[dict[str, Any]]:
    goals = dataset.tables["goals"]
    reviews = dataset.tables["reviews"]
    feedback = dataset.tables["feedback"]
    managers_by_id = {row["id"]: row for row in dataset.tables["managers"]}
    goal = next(
        goal
        for goal in goals
        if managers_by_id[goal["owner_manager_id"]]["employee_id"] != goal["employee_id"]
    )
    progress_goal = next(candidate for candidate in goals if candidate["id"] != goal["id"])
    closed_goal = next(
        candidate
        for candidate in goals
        if candidate["id"] not in {goal["id"], progress_goal["id"]}
        and dataset.cycles_by_id[candidate["review_cycle_id"]]["status"] == "closed"
    )
    review = reviews[0]
    other_manager = next(
        manager["id"]
        for manager in dataset.tables["managers"]
        if manager["id"] != review["reviewer_manager_id"]
    )
    feedback_row = feedback[0]
    return [
        {
            "issue_type": "goal_owner_mismatch",
            "record_id": goal["id"],
            "observed": {
                "employee_id": goal["employee_id"],
                "owner_employee_id": managers_by_id[goal["owner_manager_id"]]["employee_id"],
            },
        },
        {
            "issue_type": "unjustified_progress_over_100",
            "record_id": progress_goal["id"],
            "observed": {"progress_percent": "125.00", "justification": None},
        },
        {
            "issue_type": "invalid_reviewer_relationship",
            "record_id": review["id"],
            "observed": {
                "employee_id": review["employee_id"],
                "assigned_manager_id": review["reviewer_manager_id"],
                "reviewer_manager_id": other_manager,
            },
        },
        {
            "issue_type": "silent_edit_in_closed_cycle",
            "record_id": closed_goal["id"],
            "observed": {
                "review_cycle_id": closed_goal["review_cycle_id"],
                "cycle_status": "closed",
                "has_audit_event": False,
            },
        },
        {
            "issue_type": "untraceable_feedback",
            "record_id": feedback_row["id"],
            "observed": {"author_employee_id": None, "source_reference": None},
        },
    ]


def detect_anomaly(fixture: dict[str, Any]) -> str | None:
    issue_type = fixture.get("issue_type")
    observed = fixture.get("observed", {})
    if issue_type == "goal_owner_mismatch":
        if observed.get("employee_id") != observed.get("owner_employee_id"):
            return EXPECTED_DECISIONS[issue_type]
    elif issue_type == "unjustified_progress_over_100":
        if float(observed.get("progress_percent", 0)) > 100 and not observed.get("justification"):
            return EXPECTED_DECISIONS[issue_type]
    elif issue_type == "invalid_reviewer_relationship":
        if observed.get("assigned_manager_id") != observed.get("reviewer_manager_id"):
            return EXPECTED_DECISIONS[issue_type]
    elif issue_type == "silent_edit_in_closed_cycle":
        if observed.get("cycle_status") == "closed" and not observed.get("has_audit_event"):
            return EXPECTED_DECISIONS[issue_type]
    elif issue_type == "untraceable_feedback":
        if not observed.get("author_employee_id") or not observed.get("source_reference"):
            return EXPECTED_DECISIONS[issue_type]
    return None


def build_ground_truth(fixtures: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "issue_type": fixture["issue_type"],
            "ground_truth_label": "anomaly",
            "expected_decision": EXPECTED_DECISIONS[fixture["issue_type"]],
            "record_id": fixture["record_id"],
        }
        for fixture in fixtures
    ]
