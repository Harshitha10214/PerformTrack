from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from app.generation.types import (
    BRIDGE_TABLES,
    EXPORT_TABLES,
    GeneratedDataset,
)
from app.models import Base
from app.services.goal_progress import KeyResultProgressInput, calculate_goal_progress


_BRIDGE_PARENT = {
    "employee_competencies": ("employee_id", "employees"),
    "goal_competencies": ("goal_id", "goals"),
    "checkin_key_results": ("checkin_id", "checkins"),
    "feedback_competencies": ("feedback_id", "feedback"),
    "review_competencies": ("review_id", "reviews"),
    "development_plan_goals": ("development_plan_id", "development_plans"),
    "development_plan_competencies": ("development_plan_id", "development_plans"),
}
_APPROVAL_PARENT = {
    "review_approvals": ("review_id", "reviews"),
    "development_plan_approvals": ("development_plan_id", "development_plans"),
}


def _primary_key(table_name: str) -> tuple[str, ...]:
    return tuple(
        column.name
        for column in Base.metadata.tables[table_name].primary_key.columns
    )


def merge_existing_rows(
    generated: GeneratedDataset,
    existing_rows: Mapping[str, Sequence[Mapping[str, Any]]],
) -> GeneratedDataset:
    """Preserve existing rows and parent relationships while adding generated rows."""
    for table_name in existing_rows:
        if table_name not in EXPORT_TABLES:
            raise ValueError(f"unsupported existing-data table: {table_name}")

    merged = GeneratedDataset(scale=generated.scale, seed=generated.seed)
    existing_by_table = {
        table_name: [dict(row) for row in existing_rows.get(table_name, ())]
        for table_name in EXPORT_TABLES
    }

    for table_name in EXPORT_TABLES:
        key_columns = _primary_key(table_name)
        existing_by_key: dict[tuple[Any, ...], dict[str, Any]] = {}
        for row in existing_by_table[table_name]:
            key = tuple(row[column] for column in key_columns)
            if key in existing_by_key:
                raise ValueError(f"duplicate existing primary key in {table_name}: {key}")
            existing_by_key[key] = row

        generated_rows = generated.tables[table_name]
        if table_name in BRIDGE_TABLES:
            parent_column, _ = _BRIDGE_PARENT[table_name]
            existing_links_by_parent = {
                row[parent_column]
                for row in existing_by_table[table_name]
            }
            generated_rows = [
                row
                for row in generated_rows
                if row[parent_column] not in existing_links_by_parent
            ]
        elif table_name in _APPROVAL_PARENT:
            parent_column, parent_table = _APPROVAL_PARENT[table_name]
            existing_parent_ids = {
                row["id"] for row in existing_by_table[parent_table]
            }
            generated_rows = [
                row
                for row in generated_rows
                if row[parent_column] not in existing_parent_ids
            ]

        merged_by_key = {
            tuple(row[column] for column in key_columns): dict(row)
            for row in generated_rows
        }
        merged_by_key.update(existing_by_key)
        merged.tables[table_name] = [
            merged_by_key[key] for key in sorted(merged_by_key)
        ]

    merged.employee_managers = {
        row["id"]: row["manager_id"] for row in merged.tables["employees"]
    }
    merged.cycles_by_id = {
        row["id"]: row for row in merged.tables["review_cycles"]
    }

    results_by_goal: dict[str, list[dict[str, Any]]] = {}
    for result in merged.tables["key_results"]:
        results_by_goal.setdefault(result["goal_id"], []).append(result)
    merged.goal_progress = {
        goal["id"]: calculate_goal_progress(
            [
                KeyResultProgressInput(
                    target_value=result["target_value"],
                    actual_value=result["current_value"],
                    weight=result["weight"],
                )
                for result in results_by_goal.get(goal["id"], [])
            ]
        )
        for goal in merged.tables["goals"]
    }
    return merged
