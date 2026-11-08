from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.models import (
    Competency,
    DevelopmentPlan,
    DevelopmentPlanApproval,
    Employee,
    EntityHistory,
    Goal,
    Manager,
    ReviewCycle,
)
from app.schemas.development_plans import (
    DevelopmentPlanApprovalDecision,
    DevelopmentPlanApprovalResponse,
    DevelopmentPlanCompetencySummary,
    DevelopmentPlanCreate,
    DevelopmentPlanGoalSummary,
    DevelopmentPlanResponse,
    DevelopmentPlanUpdate,
    PaginatedDevelopmentPlans,
)
from app.services.audit import set_audit_actor
from app.services.record_ids import next_development_plan_id

router = APIRouter(tags=["development-plans"])


def _commit(db: Session) -> None:
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="The change conflicts with a database constraint.") from None
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(status_code=503, detail="The database could not save this change.") from None


def _plan_query():
    return select(DevelopmentPlan).options(
        selectinload(DevelopmentPlan.employee),
        selectinload(DevelopmentPlan.owner).selectinload(Manager.employee),
        selectinload(DevelopmentPlan.review_cycle),
        selectinload(DevelopmentPlan.goals),
        selectinload(DevelopmentPlan.competencies),
        selectinload(DevelopmentPlan.approvals)
        .selectinload(DevelopmentPlanApproval.approver)
        .selectinload(Manager.employee),
    )


def _plan_or_404(db: Session, plan_id: str) -> DevelopmentPlan:
    plan = db.scalar(_plan_query().where(DevelopmentPlan.id == plan_id))
    if plan is None:
        raise HTTPException(status_code=404, detail="Development plan not found.")
    return plan


def _cycle_is_editable(plan: DevelopmentPlan) -> bool:
    return plan.review_cycle is None or plan.review_cycle.status in {"draft", "open"}


def _approval_actionable(plan: DevelopmentPlan) -> bool:
    return (
        plan.status == "draft"
        and _cycle_is_editable(plan)
        and any(approval.status == "pending" for approval in plan.approvals)
    )


def _development_plan_response(plan: DevelopmentPlan) -> DevelopmentPlanResponse:
    return DevelopmentPlanResponse(
        id=plan.id,
        employee_id=plan.employee_id,
        employee_name=f"{plan.employee.first_name} {plan.employee.last_name}",
        owner_manager_id=plan.owner_manager_id,
        owner_manager_name=f"{plan.owner.employee.first_name} {plan.owner.employee.last_name}",
        review_cycle_id=plan.review_cycle_id,
        review_cycle_name=plan.review_cycle.name if plan.review_cycle else None,
        title=plan.title,
        description=plan.description,
        effective_from=plan.effective_from,
        effective_to=plan.effective_to,
        status=plan.status,
        editable=plan.status == "draft" and _cycle_is_editable(plan),
        approval_actionable=_approval_actionable(plan),
        goals=[
            DevelopmentPlanGoalSummary(id=goal.id, title=goal.title)
            for goal in sorted(plan.goals, key=lambda item: item.id)
        ],
        competencies=[
            DevelopmentPlanCompetencySummary(id=item.id, name=item.name, category=item.category)
            for item in sorted(plan.competencies, key=lambda item: (item.category, item.name, item.id))
        ],
        approvals=[
            DevelopmentPlanApprovalResponse(
                approver_manager_id=approval.approver_manager_id,
                approver_name=(
                    f"{approval.approver.employee.first_name} {approval.approver.employee.last_name}"
                ),
                approver_employee_id=approval.approver.employee_id,
                status=approval.status,
                decided_at=approval.decided_at,
                comments=approval.comments,
            )
            for approval in sorted(plan.approvals, key=lambda item: item.approver_manager_id)
        ],
        created_at=plan.created_at,
        updated_at=plan.updated_at,
    )


def _validate_owner(employee: Employee, owner: Manager) -> None:
    if employee.manager_id is not None and employee.manager_id != owner.id:
        raise HTTPException(
            status_code=422,
            detail="owner_manager_id must be the employee's assigned manager.",
        )
    if owner.employee_id == employee.id:
        raise HTTPException(status_code=422, detail="An employee cannot own their own development plan.")


def _validate_cycle_and_dates(
    db: Session,
    cycle_id: str | None,
    effective_from,
    effective_to,
    *,
    require_open: bool,
) -> ReviewCycle | None:
    cycle = db.get(ReviewCycle, cycle_id) if cycle_id else None
    if cycle_id and cycle is None:
        raise HTTPException(status_code=422, detail="review_cycle_id must reference an existing review cycle.")
    if cycle is not None:
        if require_open and cycle.status not in {"draft", "open"}:
            raise HTTPException(status_code=409, detail="Development plans cannot be changed in a closed cycle.")
        if effective_from < cycle.starts_on or effective_from > cycle.ends_on:
            raise HTTPException(status_code=422, detail="Plan start date must fall within the review cycle.")
        if effective_to is not None and effective_to > cycle.ends_on:
            raise HTTPException(status_code=422, detail="Plan end date must fall within the review cycle.")
    if effective_to is not None and effective_to < effective_from:
        raise HTTPException(status_code=422, detail="effective_to cannot be before effective_from.")
    return cycle


def _validate_goals(db: Session, employee_id: str, goal_ids: list[str]) -> list[Goal]:
    goals = list(db.scalars(select(Goal).where(Goal.id.in_(goal_ids))).all()) if goal_ids else []
    if len(goals) != len(goal_ids):
        raise HTTPException(status_code=422, detail="Every goal_id must reference an existing goal.")
    if any(goal.employee_id != employee_id for goal in goals):
        raise HTTPException(
            status_code=422,
            detail="Development-plan goals must belong to the plan's employee.",
        )
    return goals


def _validate_competencies(db: Session, competency_ids: list[str]) -> list[Competency]:
    competencies = (
        list(db.scalars(select(Competency).where(Competency.id.in_(competency_ids))).all())
        if competency_ids
        else []
    )
    if len(competencies) != len(competency_ids):
        raise HTTPException(status_code=422, detail="Every competency_id must reference an existing competency.")
    return competencies


def _approval_snapshot(approval: DevelopmentPlanApproval) -> dict:
    return {
        "development_plan_id": approval.development_plan_id,
        "approver_manager_id": approval.approver_manager_id,
        "status": approval.status,
        "decided_at": approval.decided_at.isoformat() if approval.decided_at else None,
        "comments": approval.comments,
    }


def _record_approval_history(
    db: Session,
    plan_id: str,
    actor_employee_id: str,
    action: str,
    before: dict | None,
    after: dict | None,
) -> None:
    db.add(
        EntityHistory(
            event_id=str(uuid4()),
            entity_type="DevelopmentPlan",
            entity_id=plan_id,
            actor_id=actor_employee_id,
            actor_employee_id=actor_employee_id,
            action=action,
            before_data={"approval": before} if before else None,
            after_data={"approval": after} if after else None,
            recorded_at=datetime.now(timezone.utc),
        )
    )


@router.get("/development-plans", response_model=PaginatedDevelopmentPlans)
def list_development_plans(
    search: str | None = None,
    status: str | None = None,
    department: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    db: Session = Depends(get_db),
) -> PaginatedDevelopmentPlans:
    query = select(DevelopmentPlan).join(Employee)
    predicates = []
    if search and search.strip():
        term = f"%{search.strip()}%"
        predicates.append(
            or_(
                DevelopmentPlan.id.ilike(term),
                DevelopmentPlan.title.ilike(term),
                Employee.first_name.ilike(term),
                Employee.last_name.ilike(term),
            )
        )
    if status:
        predicates.append(DevelopmentPlan.status == status)
    if department:
        predicates.append(Employee.department == department)
    if predicates:
        query = query.where(*predicates)

    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    plans = db.scalars(
        query.options(
            selectinload(DevelopmentPlan.employee),
            selectinload(DevelopmentPlan.owner).selectinload(Manager.employee),
            selectinload(DevelopmentPlan.review_cycle),
            selectinload(DevelopmentPlan.goals),
            selectinload(DevelopmentPlan.competencies),
            selectinload(DevelopmentPlan.approvals)
            .selectinload(DevelopmentPlanApproval.approver)
            .selectinload(Manager.employee),
        )
        .order_by(DevelopmentPlan.effective_from.desc(), DevelopmentPlan.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return PaginatedDevelopmentPlans(
        items=[_development_plan_response(plan) for plan in plans],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/development-plans/{plan_id}", response_model=DevelopmentPlanResponse)
def get_development_plan(plan_id: str, db: Session = Depends(get_db)) -> DevelopmentPlanResponse:
    return _development_plan_response(_plan_or_404(db, plan_id))


@router.post("/development-plans", response_model=DevelopmentPlanResponse, status_code=201)
def create_development_plan(
    payload: DevelopmentPlanCreate, db: Session = Depends(get_db)
) -> DevelopmentPlanResponse:
    employee = db.get(Employee, payload.employee_id)
    owner = db.get(Manager, payload.owner_manager_id)
    if employee is None:
        raise HTTPException(status_code=422, detail="employee_id must reference an existing employee.")
    if owner is None:
        raise HTTPException(status_code=422, detail="owner_manager_id must reference an existing manager.")
    _validate_owner(employee, owner)
    _validate_cycle_and_dates(
        db,
        payload.review_cycle_id,
        payload.effective_from,
        payload.effective_to,
        require_open=True,
    )
    goals = _validate_goals(db, employee.id, payload.goal_ids)
    competencies = _validate_competencies(db, payload.competency_ids)

    set_audit_actor(db, owner.employee_id)
    plan = DevelopmentPlan(
        id=next_development_plan_id(db),
        employee_id=employee.id,
        owner_manager_id=owner.id,
        review_cycle_id=payload.review_cycle_id,
        title=payload.title,
        description=payload.description,
        effective_from=payload.effective_from,
        effective_to=payload.effective_to,
        status="draft",
        goals=goals,
        competencies=competencies,
    )
    db.add(plan)
    db.flush()
    approval = DevelopmentPlanApproval(
        development_plan_id=plan.id,
        approver_manager_id=owner.id,
        status="pending",
    )
    db.add(approval)
    _record_approval_history(db, plan.id, owner.employee_id, "INSERT", None, _approval_snapshot(approval))
    _commit(db)
    return _development_plan_response(_plan_or_404(db, plan.id))


@router.patch("/development-plans/{plan_id}", response_model=DevelopmentPlanResponse)
def update_development_plan(
    plan_id: str, payload: DevelopmentPlanUpdate, db: Session = Depends(get_db)
) -> DevelopmentPlanResponse:
    plan = _plan_or_404(db, plan_id)
    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        return _development_plan_response(plan)

    status = changes.pop("status", None)
    content_changes = set(changes) - {"goal_ids", "competency_ids"}
    relationship_changes = {"goal_ids", "competency_ids"} & set(changes)
    if plan.status == "draft":
        if status is not None:
            raise HTTPException(
                status_code=409,
                detail="Draft plans become active only through approval.",
            )
        if not plan.approvals or any(item.status != "pending" for item in plan.approvals):
            raise HTTPException(status_code=409, detail="Only plans awaiting approval can be edited.")
    elif plan.status == "active":
        if content_changes or relationship_changes:
            raise HTTPException(status_code=409, detail="Active plan details cannot be edited.")
        if status not in {"completed", "cancelled"}:
            raise HTTPException(
                status_code=409,
                detail="Active plans can only transition to completed or cancelled.",
            )
    else:
        raise HTTPException(status_code=409, detail="Completed or cancelled plans cannot be changed.")

    effective_from = changes.get("effective_from", plan.effective_from)
    effective_to = changes.get("effective_to", plan.effective_to)
    _validate_cycle_and_dates(
        db,
        plan.review_cycle_id,
        effective_from,
        effective_to,
        require_open=True,
    )
    goals = (
        _validate_goals(db, plan.employee_id, changes["goal_ids"])
        if "goal_ids" in changes
        else None
    )
    competencies = (
        _validate_competencies(db, changes["competency_ids"])
        if "competency_ids" in changes
        else None
    )

    set_audit_actor(db, plan.owner.employee_id)
    for field in ("title", "description", "effective_from", "effective_to"):
        if field in changes:
            setattr(plan, field, changes[field])
    if goals is not None:
        plan.goals = goals
    if competencies is not None:
        plan.competencies = competencies
    if status is not None:
        plan.status = status
    _commit(db)
    return _development_plan_response(_plan_or_404(db, plan.id))


@router.post(
    "/development-plans/{plan_id}/approval",
    response_model=DevelopmentPlanResponse,
)
def decide_development_plan_approval(
    plan_id: str,
    payload: DevelopmentPlanApprovalDecision,
    db: Session = Depends(get_db),
) -> DevelopmentPlanResponse:
    plan = _plan_or_404(db, plan_id)
    if plan.status != "draft" or not _cycle_is_editable(plan):
        raise HTTPException(status_code=409, detail="Only draft plans in an editable cycle can be decided.")
    if payload.approver_manager_id != plan.owner_manager_id:
        raise HTTPException(status_code=422, detail="The approver must be the plan owner's manager profile.")
    approval = next(
        (item for item in plan.approvals if item.approver_manager_id == payload.approver_manager_id),
        None,
    )
    if approval is None or approval.status != "pending":
        raise HTTPException(status_code=409, detail="No pending approval exists for this development plan.")

    before = _approval_snapshot(approval)
    decided_at = datetime.now(timezone.utc)
    approval.status = payload.status
    approval.decided_at = decided_at
    approval.comments = payload.comments
    plan.status = "active" if payload.status == "approved" else "cancelled"
    actor_employee_id = approval.approver.employee_id
    set_audit_actor(db, actor_employee_id)
    _record_approval_history(
        db,
        plan.id,
        actor_employee_id,
        "UPDATE",
        before,
        _approval_snapshot(approval),
    )
    _commit(db)
    return _development_plan_response(_plan_or_404(db, plan.id))
