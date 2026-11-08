from fastapi import APIRouter, Depends, HTTPException, Query
from decimal import Decimal
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.models import Employee, Goal, KeyResult, Manager, ReviewCycle
from app.schemas.goals import (
    GoalCreate,
    GoalResponse,
    GoalUpdate,
    KeyResultInput,
    KeyResultResponse,
    KeyResultUpdate,
    PaginatedGoals,
)
from app.services.goal_progress import KeyResultProgressInput, calculate_goal_progress, calculate_key_result_progress
from app.services.record_ids import next_goal_id, next_key_result_id

router = APIRouter(tags=["goals"])


def _commit(db: Session) -> None:
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="The change conflicts with a database constraint.") from None
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(status_code=503, detail="The database could not save this change.") from None


def _goal_query():
    return select(Goal).options(
        selectinload(Goal.employee),
        selectinload(Goal.review_cycle),
        selectinload(Goal.key_results),
    )


def _key_result_progress(item: KeyResult) -> Decimal:
    try:
        return calculate_key_result_progress(item.current_value, item.target_value)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


def _goal_response(goal: Goal) -> GoalResponse:
    try:
        progress = calculate_goal_progress(
            [
                KeyResultProgressInput(
                    target_value=result.target_value,
                    actual_value=result.current_value,
                    weight=result.weight,
                )
                for result in goal.key_results
            ]
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=f"Goal progress cannot be calculated: {exc}") from exc
    return GoalResponse(
        id=goal.id,
        employee_id=goal.employee_id,
        employee_name=f"{goal.employee.first_name} {goal.employee.last_name}",
        review_cycle_id=goal.review_cycle_id,
        review_cycle_name=goal.review_cycle.name,
        owner_manager_id=goal.owner_manager_id,
        title=goal.title,
        description=goal.description,
        effective_from=goal.effective_from,
        effective_to=goal.effective_to,
        due_date=goal.due_date,
        status=goal.status,
        progress=progress,
        key_results=[
            KeyResultResponse.model_validate(result).model_copy(update={"progress": _key_result_progress(result)})
            for result in sorted(goal.key_results, key=lambda value: value.id)
        ],
        created_at=goal.created_at,
        updated_at=goal.updated_at,
    )


def _goal_or_404(db: Session, goal_id: str) -> Goal:
    goal = db.scalar(_goal_query().where(Goal.id == goal_id))
    if goal is None:
        raise HTTPException(status_code=404, detail="Goal not found.")
    return goal


def _require_open_cycle(db: Session, cycle_id: str) -> ReviewCycle:
    cycle = db.get(ReviewCycle, cycle_id)
    if cycle is None:
        raise HTTPException(status_code=422, detail="review_cycle_id must reference an existing cycle.")
    if cycle.status not in {"draft", "open"}:
        raise HTTPException(status_code=409, detail="Goals in a closed or archived cycle cannot be edited.")
    return cycle


def _validate_dates(cycle: ReviewCycle, start, due) -> None:
    if start < cycle.starts_on or due > cycle.ends_on:
        raise HTTPException(status_code=422, detail="Goal dates must fall within the review cycle.")


def _add_key_result(db: Session, goal: Goal, payload: KeyResultInput) -> KeyResult:
    result = KeyResult(
        id=next_key_result_id(db, goal.id),
        goal_id=goal.id,
        **payload.model_dump(),
    )
    db.add(result)
    return result


@router.get("/goals", response_model=PaginatedGoals)
def list_goals(
    search: str | None = None,
    status: str | None = None,
    department: str | None = None,
    employee_id: str | None = None,
    review_cycle_id: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    db: Session = Depends(get_db),
) -> PaginatedGoals:
    query = select(Goal).join(Employee).join(ReviewCycle)
    predicates = []
    if search:
        term = f"%{search.strip()}%"
        predicates.append(or_(Goal.id.ilike(term), Goal.title.ilike(term), Employee.first_name.ilike(term), Employee.last_name.ilike(term)))
    if status:
        predicates.append(Goal.status == status)
    if department:
        predicates.append(Employee.department == department)
    if employee_id:
        predicates.append(Goal.employee_id == employee_id)
    if review_cycle_id:
        predicates.append(Goal.review_cycle_id == review_cycle_id)
    if predicates:
        query = query.where(*predicates)
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    ids = db.scalars(
        query.order_by(Goal.due_date, Goal.id).offset((page - 1) * page_size).limit(page_size)
    ).all()
    goals = db.scalars(_goal_query().where(Goal.id.in_([goal.id for goal in ids]))).all() if ids else []
    order = {goal.id: index for index, goal in enumerate(ids)}
    goals.sort(key=lambda goal: order[goal.id])
    return PaginatedGoals(
        items=[_goal_response(goal) for goal in goals],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/goals/{goal_id}", response_model=GoalResponse)
def get_goal(goal_id: str, db: Session = Depends(get_db)) -> GoalResponse:
    return _goal_response(_goal_or_404(db, goal_id))


@router.post("/goals", response_model=GoalResponse, status_code=201)
def create_goal(payload: GoalCreate, db: Session = Depends(get_db)) -> GoalResponse:
    cycle = _require_open_cycle(db, payload.review_cycle_id)
    if db.get(Employee, payload.employee_id) is None:
        raise HTTPException(status_code=422, detail="employee_id must reference an existing employee.")
    if payload.owner_manager_id and db.get(Manager, payload.owner_manager_id) is None:
        raise HTTPException(status_code=422, detail="owner_manager_id must reference an existing manager.")
    _validate_dates(cycle, payload.effective_from, payload.due_date)
    results = payload.key_results
    goal = Goal(
        id=next_goal_id(db, payload.employee_id),
        **payload.model_dump(exclude={"key_results"}),
    )
    db.add(goal)
    db.flush()
    for result in results:
        if result.effective_from < cycle.starts_on or result.due_date > cycle.ends_on:
            raise HTTPException(status_code=422, detail="Key result dates must fall within the review cycle.")
        _add_key_result(db, goal, result)
    _commit(db)
    return _goal_response(_goal_or_404(db, goal.id))


@router.patch("/goals/{goal_id}", response_model=GoalResponse)
def update_goal(goal_id: str, payload: GoalUpdate, db: Session = Depends(get_db)) -> GoalResponse:
    goal = _goal_or_404(db, goal_id)
    _require_open_cycle(db, goal.review_cycle_id)
    changes = payload.model_dump(exclude_unset=True)
    owner_id = changes.get("owner_manager_id")
    if owner_id and db.get(Manager, owner_id) is None:
        raise HTTPException(status_code=422, detail="owner_manager_id must reference an existing manager.")
    for key, value in changes.items():
        setattr(goal, key, value)
    if goal.effective_to and goal.effective_to < goal.effective_from:
        raise HTTPException(status_code=422, detail="effective_to cannot be before effective_from.")
    _commit(db)
    return _goal_response(_goal_or_404(db, goal.id))


@router.post("/goals/{goal_id}/key-results", response_model=KeyResultResponse, status_code=201)
def create_key_result(
    goal_id: str, payload: KeyResultInput, db: Session = Depends(get_db)
) -> KeyResultResponse:
    goal = _goal_or_404(db, goal_id)
    cycle = _require_open_cycle(db, goal.review_cycle_id)
    if payload.effective_from < cycle.starts_on or payload.due_date > cycle.ends_on:
        raise HTTPException(status_code=422, detail="Key result dates must fall within the review cycle.")
    existing_weights = [result.weight for result in goal.key_results]
    if payload.weight is not None or any(weight is not None for weight in existing_weights):
        weights = existing_weights + [payload.weight]
        if any(weight is None for weight in weights) or sum(weights, 0) != 100:
            raise HTTPException(status_code=422, detail="Key result weights must all be set and sum to 100.")
    result = _add_key_result(db, goal, payload)
    _commit(db)
    return KeyResultResponse.model_validate(result).model_copy(update={"progress": _key_result_progress(result)})


@router.patch("/key-results/{key_result_id}", response_model=KeyResultResponse)
def update_key_result(
    key_result_id: str, payload: KeyResultUpdate, db: Session = Depends(get_db)
) -> KeyResultResponse:
    result = db.get(KeyResult, key_result_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Key result not found.")
    goal = _goal_or_404(db, result.goal_id)
    cycle = _require_open_cycle(db, goal.review_cycle_id)
    changes = payload.model_dump(exclude_unset=True)
    status = changes.get("status")
    if status and status not in {"draft", "active", "on_track", "at_risk", "completed", "cancelled"}:
        raise HTTPException(status_code=422, detail="Invalid key result status.")
    for key, value in changes.items():
        setattr(result, key, value)
    if result.due_date < result.effective_from or result.due_date > cycle.ends_on:
        raise HTTPException(status_code=422, detail="Key result due date must fall within the review cycle.")
    if result.effective_to and result.effective_to < result.effective_from:
        raise HTTPException(status_code=422, detail="effective_to cannot be before effective_from.")
    _commit(db)
    db.refresh(result)
    return KeyResultResponse.model_validate(result).model_copy(update={"progress": _key_result_progress(result)})
