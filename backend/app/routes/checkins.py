from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.models import CheckIn, Employee, Goal, KeyResult, Manager, ReviewCycle
from app.schemas.checkins import CheckInCreate, CheckInResponse, CheckInUpdate, PaginatedCheckIns
from app.services.record_ids import next_checkin_id

router = APIRouter(tags=["check-ins"])


def _commit(db: Session) -> None:
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="The change conflicts with a database constraint.") from None
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(status_code=503, detail="The database could not save this change.") from None


def _query():
    return select(CheckIn).options(
        selectinload(CheckIn.employee), selectinload(CheckIn.manager), selectinload(CheckIn.key_results)
    )


def _response(checkin: CheckIn) -> CheckInResponse:
    return CheckInResponse(
        id=checkin.id,
        employee_id=checkin.employee_id,
        employee_name=f"{checkin.employee.first_name} {checkin.employee.last_name}",
        manager_id=checkin.manager_id,
        manager_name=(
            f"{checkin.manager.employee.first_name} {checkin.manager.employee.last_name}"
            if checkin.manager else None
        ),
        review_cycle_id=checkin.review_cycle_id,
        checkin_date=checkin.checkin_date,
        notes=checkin.notes,
        status=checkin.status,
        key_result_ids=sorted(item.id for item in checkin.key_results),
        created_at=checkin.created_at,
        updated_at=checkin.updated_at,
    )


def _checkin_or_404(db: Session, checkin_id: str) -> CheckIn:
    item = db.scalar(_query().where(CheckIn.id == checkin_id))
    if item is None:
        raise HTTPException(status_code=404, detail="Check-in not found.")
    return item


def _validate_references(
    db: Session,
    employee_id: str,
    manager_id: str,
    cycle_id: str | None,
    checkin_date,
    key_result_ids: list[str],
) -> tuple[Employee, Manager, list[KeyResult]]:
    employee = db.get(Employee, employee_id)
    manager = db.get(Manager, manager_id)
    if employee is None:
        raise HTTPException(status_code=422, detail="employee_id must reference an existing employee.")
    cycle = db.get(ReviewCycle, cycle_id) if cycle_id else None
    if cycle_id and cycle is None:
        raise HTTPException(status_code=422, detail="review_cycle_id must reference an existing review cycle.")
    if cycle is not None:
        if cycle.status != "open":
            raise HTTPException(
                status_code=409,
                detail="Check-ins can only be created or updated in an open review cycle.",
            )
        if not cycle.starts_on <= checkin_date <= cycle.ends_on:
            raise HTTPException(status_code=422, detail="checkin_date must fall within the review cycle.")
    if manager is None:
        raise HTTPException(status_code=422, detail="manager_id must reference an existing manager.")
    if employee.manager_id is not None and employee.manager_id != manager.id:
        raise HTTPException(status_code=422, detail="manager_id must be the employee's assigned manager.")
    if manager.employee_id == employee.id:
        raise HTTPException(status_code=422, detail="An employee cannot be their own check-in manager.")
    results = (
        list(db.scalars(select(KeyResult).where(KeyResult.id.in_(key_result_ids))).all())
        if key_result_ids
        else []
    )
    if len(results) != len(set(key_result_ids)):
        raise HTTPException(status_code=422, detail="Every key_result_id must reference an existing key result.")
    if results:
        goal_references = {
            row.id: (row.employee_id, row.review_cycle_id)
            for row in db.execute(
                select(KeyResult.id, Goal.employee_id, Goal.review_cycle_id)
                .join(Goal)
                .where(KeyResult.id.in_(key_result_ids))
            )
        }
        if any(
            goal_references.get(result.id, (None, None))[0] != employee_id
            or (cycle is not None and goal_references.get(result.id, (None, None))[1] != cycle.id)
            for result in results
        ):
            raise HTTPException(status_code=422, detail="Key results must belong to the check-in employee.")
    return employee, manager, results


@router.get("/check-ins", response_model=PaginatedCheckIns)
def list_checkins(
    search: str | None = None,
    status: str | None = None,
    employee_id: str | None = None,
    manager_id: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    db: Session = Depends(get_db),
) -> PaginatedCheckIns:
    query = select(CheckIn).join(Employee).outerjoin(Manager, CheckIn.manager_id == Manager.id)
    predicates = []
    if search:
        term = f"%{search.strip()}%"
        predicates.append(or_(CheckIn.id.ilike(term), Employee.first_name.ilike(term), Employee.last_name.ilike(term)))
    if status:
        predicates.append(CheckIn.status == status)
    if employee_id:
        predicates.append(CheckIn.employee_id == employee_id)
    if manager_id:
        predicates.append(CheckIn.manager_id == manager_id)
    if predicates:
        query = query.where(*predicates)
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    ids = db.scalars(query.order_by(CheckIn.checkin_date.desc(), CheckIn.id).offset((page-1)*page_size).limit(page_size)).all()
    rows = db.scalars(_query().where(CheckIn.id.in_([item.id for item in ids]))).all() if ids else []
    order = {item.id: i for i, item in enumerate(ids)}
    rows.sort(key=lambda item: order[item.id])
    return PaginatedCheckIns(items=[_response(item) for item in rows], total=total, page=page, page_size=page_size)


@router.get("/check-ins/{checkin_id}", response_model=CheckInResponse)
def get_checkin(checkin_id: str, db: Session = Depends(get_db)) -> CheckInResponse:
    return _response(_checkin_or_404(db, checkin_id))


@router.post("/check-ins", response_model=CheckInResponse, status_code=201)
def create_checkin(payload: CheckInCreate, db: Session = Depends(get_db)) -> CheckInResponse:
    if payload.status not in {"scheduled", "completed", "missed", "cancelled"}:
        raise HTTPException(status_code=422, detail="Invalid check-in status.")
    _, manager, results = _validate_references(
        db,
        payload.employee_id,
        payload.manager_id,
        payload.review_cycle_id,
        payload.checkin_date,
        payload.key_result_ids,
    )
    item = CheckIn(
        id=next_checkin_id(db),
        employee_id=payload.employee_id,
        manager_id=manager.id,
        review_cycle_id=payload.review_cycle_id,
        checkin_date=payload.checkin_date,
        notes=payload.notes,
        status=payload.status,
        key_results=results,
    )
    db.add(item)
    _commit(db)
    return _response(_checkin_or_404(db, item.id))


@router.patch("/check-ins/{checkin_id}", response_model=CheckInResponse)
def update_checkin(checkin_id: str, payload: CheckInUpdate, db: Session = Depends(get_db)) -> CheckInResponse:
    item = _checkin_or_404(db, checkin_id)
    changes = payload.model_dump(exclude_unset=True, exclude={"key_result_ids"})
    if "status" in changes and changes["status"] not in {"scheduled", "completed", "missed", "cancelled"}:
        raise HTTPException(status_code=422, detail="Invalid check-in status.")
    checkin_date = changes.get("checkin_date", item.checkin_date)
    _, _, results = _validate_references(
        db,
        item.employee_id,
        item.manager_id,
        item.review_cycle_id,
        checkin_date,
        payload.key_result_ids if payload.key_result_ids is not None else [result.id for result in item.key_results],
    )
    for key, value in changes.items():
        setattr(item, key, value)
    if payload.key_result_ids is not None:
        item.key_results = results
    _commit(db)
    return _response(_checkin_or_404(db, item.id))
