import re

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.models import (
    CheckIn,
    DevelopmentPlan,
    Employee,
    Evidence,
    Feedback,
    Goal,
    KeyResult,
    Manager,
    Review,
)
from app.models.ids import format_review_id


def _allocate_numeric_id(
    db: Session,
    model: type[Employee] | type[Manager] | type[Evidence] | type[DevelopmentPlan],
    prefix: str,
) -> str:
    db.execute(text("SELECT pg_advisory_xact_lock(20261022)"))
    existing_id = db.scalar(select(model.id).where(model.id.like(f"{prefix}-%")).order_by(model.id.desc()).limit(1))
    counter = int(existing_id.rsplit("-", 1)[1]) + 1 if existing_id else 1
    while True:
        candidate = f"{prefix}-{counter:06d}"
        if db.get(model, candidate) is None:
            return candidate
        counter += 1


def next_employee_id(db: Session) -> str:
    return _allocate_numeric_id(db, Employee, "EMP")


def next_manager_id(db: Session) -> str:
    return _allocate_numeric_id(db, Manager, "MGR")


def next_goal_id(db: Session, employee_id: str) -> str:
    db.execute(text("SELECT pg_advisory_xact_lock(20261022)"))
    prefix = f"GOAL-{employee_id}-"
    existing_id = db.scalar(
        select(Goal.id).where(Goal.id.like(f"{prefix}%")).order_by(Goal.id.desc()).limit(1)
    )
    counter = int(existing_id.rsplit("-", 1)[1]) + 1 if existing_id else 1
    while True:
        candidate = f"{prefix}{counter:03d}"
        if db.get(Goal, candidate) is None:
            return candidate
        counter += 1


def next_key_result_id(db: Session, goal_id: str) -> str:
    db.execute(text("SELECT pg_advisory_xact_lock(20261022)"))
    prefix = f"KR-{goal_id}-"
    existing_id = db.scalar(
        select(KeyResult.id).where(KeyResult.id.like(f"{prefix}%")).order_by(KeyResult.id.desc()).limit(1)
    )
    counter = int(existing_id.rsplit("-", 1)[1]) + 1 if existing_id else 1
    while True:
        candidate = f"{prefix}{counter:02d}"
        if db.get(KeyResult, candidate) is None:
            return candidate
        counter += 1


def next_checkin_id(db: Session) -> str:
    return _allocate_numeric_id(db, CheckIn, "CHK")


def next_feedback_id(db: Session) -> str:
    return _allocate_numeric_id(db, Feedback, "FB")


def next_evidence_id(db: Session) -> str:
    return _allocate_numeric_id(db, Evidence, "EVD")


def next_development_plan_id(db: Session) -> str:
    return _allocate_numeric_id(db, DevelopmentPlan, "DEV")


def next_review_id(db: Session, year: int) -> str:
    db.execute(text("SELECT pg_advisory_xact_lock(20261022)"))
    existing_id = db.scalar(
        select(Review.id)
        .where(Review.year == year)
        .order_by(Review.id.desc())
        .limit(1)
    )
    counter = int(existing_id.rsplit("-", 1)[1]) + 1 if existing_id else 1
    while True:
        candidate = format_review_id(year, counter)
        if db.get(Review, candidate) is None:
            return candidate
        counter += 1


def parse_counter(value: str, prefix: str) -> int:
    match = re.fullmatch(rf"{re.escape(prefix)}-(\d{{6}})", value)
    if not match:
        raise ValueError(f"Invalid {prefix} identifier")
    return int(match.group(1))
