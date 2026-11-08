from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any


@dataclass(frozen=True)
class DatasetScale:
    name: str
    employees: int
    managers: int
    goals: int
    checkins: int


STARTER_SCALE = DatasetScale("starter", 30, 5, 100, 200)
FULL_SCALE = DatasetScale("full", 3000, 500, 10000, 20000)

ENTITY_TABLES = (
    "employees",
    "managers",
    "review_cycles",
    "goals",
    "key_results",
    "checkins",
    "competencies",
    "feedback",
    "reviews",
    "development_plans",
)

BRIDGE_TABLES = (
    "employee_competencies",
    "goal_competencies",
    "checkin_key_results",
    "feedback_competencies",
    "review_competencies",
    "development_plan_goals",
    "development_plan_competencies",
)

SUPPORT_TABLES = ("evidence", "review_approvals", "development_plan_approvals")
EXPORT_TABLES = (
    "employees",
    "managers",
    "review_cycles",
    "goals",
    "key_results",
    "checkins",
    "checkin_key_results",
    "competencies",
    "employee_competencies",
    "goal_competencies",
    "feedback",
    "feedback_competencies",
    "reviews",
    "evidence",
    "review_competencies",
    "development_plans",
    "development_plan_goals",
    "development_plan_competencies",
    "review_approvals",
    "development_plan_approvals",
)

FIXED_TIMESTAMP = datetime(2026, 11, 6, 12, 0, tzinfo=timezone.utc)
AS_OF_DATE = date(2026, 11, 6)


@dataclass
class GeneratedDataset:
    scale: DatasetScale
    seed: int
    tables: dict[str, list[dict[str, Any]]] = field(
        default_factory=lambda: {name: [] for name in EXPORT_TABLES}
    )
    goal_progress: dict[str, Decimal] = field(default_factory=dict)
    employee_managers: dict[str, str | None] = field(default_factory=dict)
    cycles_by_id: dict[str, dict[str, Any]] = field(default_factory=dict)

    def append(self, table_name: str, **values: Any) -> dict[str, Any]:
        row = dict(values)
        if table_name in ENTITY_TABLES or table_name in SUPPORT_TABLES:
            row.setdefault("created_at", FIXED_TIMESTAMP)
            row.setdefault("updated_at", FIXED_TIMESTAMP)
        self.tables[table_name].append(row)
        return row
