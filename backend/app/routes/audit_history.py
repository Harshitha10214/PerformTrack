from datetime import date, datetime, time, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session, aliased

from app.database import get_db
from app.models import Employee, EntityHistory
from app.schemas.audit_history import (
    AuditEntityType,
    AuditOperation,
    AuditHistoryResponse,
    PaginatedAuditHistory,
)

router = APIRouter(tags=["audit-history"])


def _query():
    actor = aliased(Employee)
    return actor, select(EntityHistory, actor)


def _response(history: EntityHistory, actor: Employee | None) -> AuditHistoryResponse:
    return AuditHistoryResponse(
        event_id=history.event_id,
        entity_type=history.entity_type,
        entity_id=history.entity_id,
        actor_id=history.actor_id,
        actor_employee_id=history.actor_employee_id,
        actor_name=(
            f"{actor.first_name} {actor.last_name}"
            if actor is not None
            else None
        ),
        actor_attribution_available=history.actor_employee_id is not None,
        operation=history.action,
        recorded_at=history.recorded_at,
        before_data=history.before_data,
        after_data=history.after_data,
    )


def _history_or_404(db: Session, event_id: str) -> tuple[EntityHistory, Employee | None]:
    try:
        normalized_event_id = str(UUID(event_id))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Audit history event not found.") from exc
    actor, query = _query()
    row = db.execute(
        query.outerjoin(actor, actor.id == EntityHistory.actor_employee_id)
        .where(EntityHistory.event_id == normalized_event_id)
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Audit history event not found.")
    return row[0], row[1]


@router.get("/audit-history", response_model=PaginatedAuditHistory)
def list_audit_history(
    entity_type: AuditEntityType | None = None,
    entity_id: str | None = Query(default=None, max_length=40),
    operation: AuditOperation | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    db: Session = Depends(get_db),
) -> PaginatedAuditHistory:
    if date_from and date_to and date_from > date_to:
        raise HTTPException(status_code=422, detail="date_from must be on or before date_to.")

    predicates = []
    if entity_type:
        predicates.append(EntityHistory.entity_type == entity_type)
    if entity_id:
        predicates.append(EntityHistory.entity_id == entity_id.strip())
    if operation:
        predicates.append(EntityHistory.action == operation)
    if date_from:
        predicates.append(
            EntityHistory.recorded_at
            >= datetime.combine(date_from, time.min, tzinfo=timezone.utc)
        )
    if date_to:
        predicates.append(
            EntityHistory.recorded_at
            < datetime.combine(date_to + timedelta(days=1), time.min, tzinfo=timezone.utc)
        )

    count_query = select(func.count(EntityHistory.event_id))
    query = select(EntityHistory)
    if predicates:
        count_query = count_query.where(*predicates)
        query = query.where(*predicates)
    total = db.scalar(count_query) or 0

    actor, query = _query()
    rows = db.execute(
        query.outerjoin(actor, actor.id == EntityHistory.actor_employee_id)
        .where(*predicates)
        .order_by(EntityHistory.recorded_at.desc(), EntityHistory.event_id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return PaginatedAuditHistory(
        items=[_response(history, employee) for history, employee in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/audit-history/{event_id}", response_model=AuditHistoryResponse)
def get_audit_history(event_id: str, db: Session = Depends(get_db)) -> AuditHistoryResponse:
    history, actor = _history_or_404(db, event_id)
    return _response(history, actor)
