from collections import defaultdict
import re
from typing import Any

from app.generation.types import (
    BRIDGE_TABLES,
    ENTITY_TABLES,
    EXPORT_TABLES,
    SUPPORT_TABLES,
    GeneratedDataset,
)
from app.models import Base
from app.services.goal_progress import KeyResultProgressInput, calculate_goal_progress
from sqlalchemy import UniqueConstraint

_ENUMS = {
    "employees": {"status": {"active", "leave", "inactive", "terminated"}},
    "managers": {"status": {"active", "inactive"}},
    "review_cycles": {"status": {"draft", "open", "closed", "archived"}, "half": {"H1", "H2"}},
    "goals": {
        "status": {"draft", "active", "on_track", "at_risk", "completed", "cancelled"}
    },
    "key_results": {
        "status": {"draft", "active", "on_track", "at_risk", "completed", "cancelled"}
    },
    "checkins": {"status": {"scheduled", "completed", "missed", "cancelled"}},
    "competencies": {"status": {"active", "inactive"}},
    "feedback": {
        "status": {"draft", "submitted", "withdrawn"},
        "visibility": {"private", "manager", "review_cycle"},
    },
    "reviews": {
        "status": {"draft", "in_progress", "submitted", "approved", "acknowledged"}
    },
    "development_plans": {
        "status": {"draft", "active", "completed", "cancelled"}
    },
    "review_approvals": {"status": {"pending", "approved", "rejected"}},
    "development_plan_approvals": {"status": {"pending", "approved", "rejected"}},
}


_ID_PATTERNS = {
    "employees": re.compile(r"EMP-\d{6}\Z"),
    "managers": re.compile(r"MGR-\d{6}\Z"),
    "review_cycles": re.compile(r"CYCLE-\d{4}-H[12]\Z"),
    "goals": re.compile(r"GOAL-EMP-\d{6}-\d{3}\Z"),
    "key_results": re.compile(r"KR-GOAL-EMP-\d{6}-\d{3}-\d{2}\Z"),
    "checkins": re.compile(r"CHK-\d{6}\Z"),
    "competencies": re.compile(r"COMP-\d{6}\Z"),
    "feedback": re.compile(r"FB-\d{6}\Z"),
    "reviews": re.compile(r"REV-\d{4}-\d{6}\Z"),
    "development_plans": re.compile(r"DEV-\d{6}\Z"),
    "evidence": re.compile(r"EVD-\d{6}\Z"),
}


def _primary_key(table_name: str) -> tuple[str, ...]:
    return tuple(column.name for column in Base.metadata.tables[table_name].primary_key.columns)


def validate_dataset(dataset: GeneratedDataset) -> dict[str, Any]:
    expected_tables = set(ENTITY_TABLES + BRIDGE_TABLES + SUPPORT_TABLES)
    if set(dataset.tables) != expected_tables:
        raise ValueError(f"dataset table set mismatch: {set(dataset.tables) ^ expected_tables}")

    indexes: dict[str, dict[tuple[Any, ...], dict[str, Any]]] = {}
    for table_name in sorted(expected_tables):
        primary_key = _primary_key(table_name)
        records: dict[tuple[Any, ...], dict[str, Any]] = {}
        for row in dataset.tables[table_name]:
            key = tuple(row.get(column) for column in primary_key)
            if any(value is None for value in key):
                raise ValueError(f"{table_name} row has an incomplete primary key: {key}")
            if key in records:
                raise ValueError(f"duplicate primary key in {table_name}: {key}")
            records[key] = row
            id_pattern = _ID_PATTERNS.get(table_name)
            if id_pattern and not id_pattern.fullmatch(str(row.get("id", ""))):
                raise ValueError(f"invalid deterministic ID in {table_name}: {row.get('id')}")
            for column, allowed in _ENUMS.get(table_name, {}).items():
                if row.get(column) not in allowed:
                    raise ValueError(f"invalid {table_name}.{column}: {row.get(column)}")
            for start_key, end_key in (
                ("effective_from", "effective_to"),
                ("starts_on", "ends_on"),
            ):
                start, end = row.get(start_key), row.get(end_key)
                if start is not None and end is not None and end < start:
                    raise ValueError(f"invalid {table_name} date range: {start_key}/{end_key}")
            if row.get("due_date") and row.get("effective_from") and row["due_date"] < row["effective_from"]:
                raise ValueError(f"invalid due date in {table_name}")
        indexes[table_name] = records

        for constraint in Base.metadata.tables[table_name].constraints:
            if not isinstance(constraint, UniqueConstraint):
                continue
            columns = tuple(column.name for column in constraint.columns)
            seen: set[tuple[Any, ...]] = set()
            for row in dataset.tables[table_name]:
                unique_key = tuple(row.get(column) for column in columns)
                if any(value is None for value in unique_key):
                    continue
                if unique_key in seen:
                    raise ValueError(f"duplicate unique key in {table_name}: {unique_key}")
                seen.add(unique_key)

    foreign_key_count = 0
    for table_name in expected_tables:
        table = Base.metadata.tables[table_name]
        for row in dataset.tables[table_name]:
            for foreign_key in table.foreign_keys:
                foreign_key_count += 1
                source_value = row.get(foreign_key.parent.name)
                if source_value is None:
                    if foreign_key.parent.nullable:
                        continue
                    raise ValueError(
                        f"null foreign key {table_name}.{foreign_key.parent.name}"
                    )
                target = foreign_key.column.table.name
                if (source_value,) not in indexes[target]:
                    raise ValueError(
                        f"invalid foreign key {table_name}.{foreign_key.parent.name}={source_value}"
                    )

    goals = {row["id"]: row for row in dataset.tables["goals"]}
    results_by_goal: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for result in dataset.tables["key_results"]:
        results_by_goal[result["goal_id"]].append(result)
    for goal_id, goal in goals.items():
        if goal_id != f"GOAL-{goal['employee_id']}-{goal_id.rsplit('-', 1)[1]}":
            raise ValueError(f"goal ID does not include its owner: {goal_id}")
        results = results_by_goal.get(goal_id, [])
        if not results:
            raise ValueError(f"goal {goal_id} has no key results")
        calculated = calculate_goal_progress(
            [
                KeyResultProgressInput(
                    target_value=result["target_value"],
                    actual_value=result["current_value"],
                    weight=result["weight"],
                )
                for result in results
            ]
        )
        if dataset.goal_progress.get(goal_id) != calculated:
            raise ValueError(f"goal progress mismatch for {goal_id}")
        if calculated > 100:
            raise ValueError(f"goal progress exceeds 100 for {goal_id}")
        cycle_status = dataset.cycles_by_id[goal["review_cycle_id"]]["status"]
        cycle = dataset.cycles_by_id[goal["review_cycle_id"]]
        if goal["effective_from"] < cycle["starts_on"] or goal["due_date"] > cycle["ends_on"]:
            raise ValueError(f"goal {goal_id} is outside its review cycle")
        if cycle_status == "closed" and goal["status"] in {"draft", "active"}:
            raise ValueError(f"goal {goal_id} has an inconsistent status in a closed cycle")
        for result in results:
            if not result["id"].startswith(f"KR-{goal_id}-"):
                raise ValueError(f"key result ID does not include its parent goal: {result['id']}")

    employees = {row["id"] for row in dataset.tables["employees"]}
    managers = {row["id"]: row for row in dataset.tables["managers"]}
    for employee_id, manager_id in dataset.employee_managers.items():
        if employee_id not in employees or (manager_id is not None and manager_id not in managers):
            raise ValueError(f"invalid reporting hierarchy for {employee_id}")

    def valid_assigned_manager(employee_id: str, manager_id: str | None) -> bool:
        direct_manager = dataset.employee_managers[employee_id]
        if direct_manager is not None:
            return manager_id == direct_manager
        return manager_id in managers and managers[manager_id]["employee_id"] != employee_id

    for row in dataset.tables["goals"]:
        if not valid_assigned_manager(row["employee_id"], row["owner_manager_id"]):
            raise ValueError(f"goal {row['id']} has an invalid owner manager")
    for row in dataset.tables["checkins"]:
        if not valid_assigned_manager(row["employee_id"], row["manager_id"]):
            raise ValueError(f"check-in {row['id']} has an invalid manager")
        cycle = dataset.cycles_by_id[row["review_cycle_id"]]
        if not cycle["starts_on"] <= row["checkin_date"] <= cycle["ends_on"]:
            raise ValueError(f"check-in {row['id']} falls outside its review cycle")
    for row in dataset.tables["reviews"]:
        if not valid_assigned_manager(row["employee_id"], row["reviewer_manager_id"]):
            raise ValueError(f"review {row['id']} has an invalid reviewer")
        if row["year"] != dataset.cycles_by_id[row["review_cycle_id"]]["year"]:
            raise ValueError(f"review {row['id']} year does not match its cycle")
    for row in dataset.tables["development_plans"]:
        if not valid_assigned_manager(row["employee_id"], row["owner_manager_id"]):
            raise ValueError(f"development plan {row['id']} has an invalid owner")

    approval_rows = {
        "review_approvals": {
            "pending": lambda row: row["decided_at"] is None,
            "approved": lambda row: row["decided_at"] is not None,
            "rejected": lambda row: row["decided_at"] is not None,
        },
        "development_plan_approvals": {
            "pending": lambda row: row["decided_at"] is None,
            "approved": lambda row: row["decided_at"] is not None,
            "rejected": lambda row: row["decided_at"] is not None,
        },
    }
    for table_name, rules in approval_rows.items():
        for row in dataset.tables[table_name]:
            if not rules[row["status"]](row):
                raise ValueError(f"inconsistent approval lifecycle in {table_name}")

    if len(dataset.tables["employees"]) != dataset.scale.employees:
        raise ValueError("employee count does not match scale")
    if len(dataset.tables["managers"]) != dataset.scale.managers:
        raise ValueError("manager count does not match scale")
    if len(dataset.tables["goals"]) != dataset.scale.goals:
        raise ValueError("goal count does not match scale")
    if len(dataset.tables["checkins"]) != dataset.scale.checkins:
        raise ValueError("check-in count does not match scale")

    return {
        "tables": {name: len(dataset.tables[name]) for name in sorted(expected_tables)},
        "total_rows": sum(len(dataset.tables[name]) for name in expected_tables),
        "foreign_key_columns_validated": foreign_key_count,
        "goal_progress_count": len(dataset.goal_progress),
        "duplicate_primary_keys": 0,
    }
