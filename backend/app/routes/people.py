from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Employee, Manager
from app.schemas.people import (
    EmployeeCreate,
    EmployeeResponse,
    EmployeeUpdate,
    ManagerCreate,
    ManagerResponse,
    ManagerUpdate,
    PaginatedEmployees,
    PaginatedManagers,
)
from app.services.record_ids import next_employee_id, next_manager_id

router = APIRouter(tags=["people"])


def _commit(db: Session) -> None:
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="The change conflicts with an existing record or database constraint.",
        ) from None
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(status_code=503, detail="The database could not save this change.") from None


def _employee_or_404(db: Session, employee_id: str) -> Employee:
    employee = db.get(Employee, employee_id)
    if employee is None:
        raise HTTPException(status_code=404, detail="Employee not found.")
    return employee


def _manager_or_404(db: Session, manager_id: str) -> Manager:
    manager = db.get(Manager, manager_id)
    if manager is None:
        raise HTTPException(status_code=404, detail="Manager not found.")
    return manager


@router.get("/employees", response_model=PaginatedEmployees)
def list_employees(
    search: str | None = None,
    status: str | None = None,
    department: str | None = None,
    manager_id: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    db: Session = Depends(get_db),
) -> PaginatedEmployees:
    query = select(Employee)
    predicates = []
    if search:
        term = f"%{search.strip()}%"
        predicates.append(
            or_(
                Employee.id.ilike(term),
                Employee.email.ilike(term),
                Employee.first_name.ilike(term),
                Employee.last_name.ilike(term),
                Employee.job_title.ilike(term),
            )
        )
    if status:
        predicates.append(Employee.status == status)
    if department:
        predicates.append(Employee.department == department)
    if manager_id:
        predicates.append(Employee.manager_id == manager_id)
    if predicates:
        query = query.where(*predicates)
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    employees = db.scalars(
        query.order_by(Employee.last_name, Employee.first_name, Employee.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return PaginatedEmployees(items=employees, total=total, page=page, page_size=page_size)


@router.get("/employees/{employee_id}", response_model=EmployeeResponse)
def get_employee(employee_id: str, db: Session = Depends(get_db)) -> Employee:
    return _employee_or_404(db, employee_id)


@router.post("/employees", response_model=EmployeeResponse, status_code=201)
def create_employee(payload: EmployeeCreate, db: Session = Depends(get_db)) -> Employee:
    if payload.manager_id and db.get(Manager, payload.manager_id) is None:
        raise HTTPException(status_code=422, detail="manager_id must reference an existing manager.")
    employee = Employee(id=next_employee_id(db), **payload.model_dump())
    db.add(employee)
    _commit(db)
    db.refresh(employee)
    return employee


@router.patch("/employees/{employee_id}", response_model=EmployeeResponse)
def update_employee(
    employee_id: str, payload: EmployeeUpdate, db: Session = Depends(get_db)
) -> Employee:
    employee = _employee_or_404(db, employee_id)
    changes = payload.model_dump(exclude_unset=True)
    manager_id = changes.get("manager_id")
    if manager_id and db.get(Manager, manager_id) is None:
        raise HTTPException(status_code=422, detail="manager_id must reference an existing manager.")
    for key, value in changes.items():
        setattr(employee, key, value)
    if employee.effective_to and employee.effective_to < employee.effective_from:
        raise HTTPException(status_code=422, detail="effective_to cannot be before effective_from.")
    _commit(db)
    db.refresh(employee)
    return employee


def _manager_response(db: Session, manager: Manager) -> ManagerResponse:
    employee = manager.employee
    report_count = db.scalar(select(func.count(Employee.id)).where(Employee.manager_id == manager.id)) or 0
    return ManagerResponse(
        id=manager.id,
        employee_id=manager.employee_id,
        employee_name=f"{employee.first_name} {employee.last_name}",
        email=employee.email,
        job_title=employee.job_title,
        department=employee.department,
        report_count=report_count,
        effective_from=manager.effective_from,
        effective_to=manager.effective_to,
        status=manager.status,
        created_at=manager.created_at,
        updated_at=manager.updated_at,
    )


@router.get("/managers", response_model=PaginatedManagers)
def list_managers(
    search: str | None = None,
    status: str | None = None,
    department: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    db: Session = Depends(get_db),
) -> PaginatedManagers:
    query = select(Manager).join(Employee, Manager.employee_id == Employee.id)
    predicates = []
    if search:
        term = f"%{search.strip()}%"
        predicates.append(
            or_(
                Manager.id.ilike(term),
                Employee.id.ilike(term),
                Employee.email.ilike(term),
                Employee.first_name.ilike(term),
                Employee.last_name.ilike(term),
            )
        )
    if status:
        predicates.append(Manager.status == status)
    if department:
        predicates.append(Employee.department == department)
    if predicates:
        query = query.where(*predicates)
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    managers = db.scalars(
        query.order_by(Employee.last_name, Employee.first_name, Manager.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return PaginatedManagers(
        items=[_manager_response(db, manager) for manager in managers],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/managers/{manager_id}", response_model=ManagerResponse)
def get_manager(manager_id: str, db: Session = Depends(get_db)) -> ManagerResponse:
    return _manager_response(db, _manager_or_404(db, manager_id))


@router.post("/managers", response_model=ManagerResponse, status_code=201)
def create_manager(payload: ManagerCreate, db: Session = Depends(get_db)) -> ManagerResponse:
    _employee_or_404(db, payload.employee_id)
    if db.scalar(select(Manager.id).where(Manager.employee_id == payload.employee_id)):
        raise HTTPException(status_code=409, detail="This employee already has a manager profile.")
    manager = Manager(id=next_manager_id(db), **payload.model_dump())
    db.add(manager)
    _commit(db)
    db.refresh(manager)
    return _manager_response(db, manager)


@router.patch("/managers/{manager_id}", response_model=ManagerResponse)
def update_manager(
    manager_id: str, payload: ManagerUpdate, db: Session = Depends(get_db)
) -> ManagerResponse:
    manager = _manager_or_404(db, manager_id)
    changes = payload.model_dump(exclude_unset=True)
    if "status" in changes and changes["status"] not in {"active", "inactive"}:
        raise HTTPException(status_code=422, detail="Invalid manager status.")
    for key, value in changes.items():
        setattr(manager, key, value)
    if manager.effective_to and manager.effective_to < manager.effective_from:
        raise HTTPException(status_code=422, detail="effective_to cannot be before effective_from.")
    _commit(db)
    db.refresh(manager)
    return _manager_response(db, manager)
