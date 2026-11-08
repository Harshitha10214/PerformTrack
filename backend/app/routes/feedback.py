from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session, aliased, selectinload

from app.database import get_db
from app.models import Competency, Employee, Feedback, Manager, ReviewCycle
from app.models.entities import employee_competencies
from app.schemas.feedback import (
    CompetencyResponse,
    CompetencySummary,
    EmployeeCompetencyResponse,
    FeedbackCreate,
    FeedbackResponse,
    FeedbackUpdate,
    PaginatedCompetencies,
    PaginatedFeedback,
    ReviewerRelationship,
)
from app.services.audit import set_audit_actor
from app.services.record_ids import next_feedback_id

router = APIRouter(tags=["competencies-and-feedback"])

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


def _competency_counts():
    return (
        select(
            Competency.id.label("id"),
            func.count(employee_competencies.c.employee_id).label("employee_count"),
        )
        .outerjoin(
            employee_competencies,
            employee_competencies.c.competency_id == Competency.id,
        )
        .group_by(Competency.id)
        .subquery()
    )


def _competency_response(competency: Competency, employee_count: int = 0) -> CompetencyResponse:
    return CompetencyResponse(
        id=competency.id,
        name=competency.name,
        category=competency.category,
        description=competency.description,
        effective_from=competency.effective_from,
        effective_to=competency.effective_to,
        status=competency.status,
        employee_count=employee_count,
    )


@router.get("/competencies", response_model=PaginatedCompetencies)
def list_competencies(
    search: str | None = None,
    category: str | None = None,
    status: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    db: Session = Depends(get_db),
) -> PaginatedCompetencies:
    counts = _competency_counts()
    query = select(Competency, counts.c.employee_count).join(counts, counts.c.id == Competency.id)
    predicates = []
    if search:
        term = f"%{search.strip()}%"
        predicates.append(
            or_(
                Competency.id.ilike(term),
                Competency.name.ilike(term),
                Competency.description.ilike(term),
            )
        )
    if category:
        predicates.append(Competency.category == category)
    if status:
        predicates.append(Competency.status == status)
    if predicates:
        query = query.where(*predicates)
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = db.execute(
        query.order_by(Competency.category, Competency.name, Competency.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return PaginatedCompetencies(
        items=[_competency_response(competency, count) for competency, count in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/competencies/{competency_id}", response_model=CompetencyResponse)
def get_competency(competency_id: str, db: Session = Depends(get_db)) -> CompetencyResponse:
    counts = _competency_counts()
    row = db.execute(
        select(Competency, counts.c.employee_count)
        .join(counts, counts.c.id == Competency.id)
        .where(Competency.id == competency_id)
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Competency not found.")
    return _competency_response(row[0], row[1])


@router.get(
    "/employees/{employee_id}/competencies",
    response_model=list[EmployeeCompetencyResponse],
)
def list_employee_competencies(
    employee_id: str, db: Session = Depends(get_db)
) -> list[EmployeeCompetencyResponse]:
    employee = db.get(Employee, employee_id)
    if employee is None:
        raise HTTPException(status_code=404, detail="Employee not found.")
    rows = db.execute(
        select(
            Competency,
            employee_competencies.c.proficiency,
            employee_competencies.c.effective_from,
            employee_competencies.c.effective_to,
        )
        .join(
            employee_competencies,
            employee_competencies.c.competency_id == Competency.id,
        )
        .where(employee_competencies.c.employee_id == employee_id)
        .order_by(Competency.category, Competency.name)
    ).all()
    return [
        EmployeeCompetencyResponse(
            competency_id=competency.id,
            name=competency.name,
            category=competency.category,
            description=competency.description,
            proficiency=proficiency,
            effective_from=effective_from,
            effective_to=effective_to,
        )
        for competency, proficiency, effective_from, effective_to in rows
    ]


def _feedback_query():
    return select(Feedback).options(
        selectinload(Feedback.author).selectinload(Employee.manager_profile),
        selectinload(Feedback.subject),
        selectinload(Feedback.review_cycle),
        selectinload(Feedback.competencies),
    )


def _feedback_or_404(db: Session, feedback_id: str) -> Feedback:
    feedback = db.scalar(_feedback_query().where(Feedback.id == feedback_id))
    if feedback is None:
        raise HTTPException(status_code=404, detail="Feedback not found.")
    return feedback


def _relationship(feedback: Feedback) -> ReviewerRelationship:
    manager = feedback.author.manager_profile
    if manager is not None and feedback.subject.manager_id == manager.id:
        return "manager"
    return "peer"


def _feedback_response(feedback: Feedback) -> FeedbackResponse:
    return FeedbackResponse(
        id=feedback.id,
        author_employee_id=feedback.author_employee_id,
        author_name=f"{feedback.author.first_name} {feedback.author.last_name}",
        subject_employee_id=feedback.subject_employee_id,
        subject_name=f"{feedback.subject.first_name} {feedback.subject.last_name}",
        reviewer_relationship=_relationship(feedback),
        review_cycle_id=feedback.review_cycle_id,
        review_cycle_name=feedback.review_cycle.name if feedback.review_cycle else None,
        content=feedback.content,
        visibility=feedback.visibility,
        status=feedback.status,
        editable=(
            feedback.status == "draft"
            and (feedback.review_cycle is None or feedback.review_cycle.status in {"draft", "open"})
        ),
        withdrawable=(
            feedback.status in {"draft", "submitted"}
            and (feedback.review_cycle is None or feedback.review_cycle.status in {"draft", "open"})
        ),
        competencies=[
            CompetencySummary(id=item.id, name=item.name, category=item.category)
            for item in sorted(feedback.competencies, key=lambda competency: (competency.category, competency.name))
        ],
        created_at=feedback.created_at,
        updated_at=feedback.updated_at,
    )


def _validate_feedback_references(
    db: Session,
    author_id: str,
    subject_id: str,
    cycle_id: str | None,
    competency_ids: list[str],
    expected_relationship: ReviewerRelationship | None = None,
) -> tuple[Employee, Employee, list[Competency]]:
    author = db.get(Employee, author_id)
    subject = db.get(Employee, subject_id)
    if author is None:
        raise HTTPException(status_code=422, detail="author_employee_id must reference an existing employee reviewer.")
    if subject is None:
        raise HTTPException(status_code=422, detail="subject_employee_id must reference an existing employee.")
    if author.id == subject.id:
        raise HTTPException(status_code=422, detail="Employees cannot provide feedback about themselves.")
    manager_id = db.scalar(select(Manager.id).where(Manager.employee_id == author.id))
    actual_relationship: ReviewerRelationship = (
        "manager" if manager_id is not None and subject.manager_id == manager_id else "peer"
    )
    if expected_relationship is not None and expected_relationship != actual_relationship:
        raise HTTPException(
            status_code=422,
            detail=f"reviewer_relationship must match the employee records ({actual_relationship}).",
        )
    if cycle_id:
        cycle = db.get(ReviewCycle, cycle_id)
        if cycle is None:
            raise HTTPException(status_code=422, detail="review_cycle_id must reference an existing review cycle.")
        if cycle.status not in {"draft", "open"}:
            raise HTTPException(status_code=409, detail="Feedback cannot be added to a closed or archived review cycle.")

    competencies = (
        list(db.scalars(select(Competency).where(Competency.id.in_(competency_ids))).all())
        if competency_ids
        else []
    )
    if len(competencies) != len(set(competency_ids)):
        raise HTTPException(status_code=422, detail="Every competency_id must reference an existing competency.")
    today = date.today()
    if any(
        item.status != "active"
        or item.effective_from > today
        or (item.effective_to is not None and item.effective_to < today)
        for item in competencies
    ):
        raise HTTPException(status_code=422, detail="Feedback can only be associated with active competencies.")
    return author, subject, competencies


@router.get("/feedback", response_model=PaginatedFeedback)
def list_feedback(
    search: str | None = None,
    status: str | None = None,
    visibility: str | None = None,
    relationship: ReviewerRelationship | None = None,
    subject_employee_id: str | None = None,
    author_employee_id: str | None = None,
    review_cycle_id: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    db: Session = Depends(get_db),
) -> PaginatedFeedback:
    author = aliased(Employee)
    subject = aliased(Employee)
    query = (
        select(Feedback)
        .join(author, Feedback.author_employee_id == author.id)
        .join(subject, Feedback.subject_employee_id == subject.id)
    )
    predicates = []
    if search:
        term = f"%{search.strip()}%"
        predicates.append(
            or_(
                Feedback.id.ilike(term),
                Feedback.content.ilike(term),
                author.first_name.ilike(term),
                author.last_name.ilike(term),
                subject.first_name.ilike(term),
                subject.last_name.ilike(term),
            )
        )
    if status:
        predicates.append(Feedback.status == status)
    if visibility:
        predicates.append(Feedback.visibility == visibility)
    if subject_employee_id:
        predicates.append(Feedback.subject_employee_id == subject_employee_id)
    if author_employee_id:
        predicates.append(Feedback.author_employee_id == author_employee_id)
    if review_cycle_id:
        predicates.append(Feedback.review_cycle_id == review_cycle_id)
    direct_manager = (
        select(Manager.id)
        .where(
            Manager.employee_id == Feedback.author_employee_id,
            Manager.id == subject.manager_id,
        )
        .exists()
    )
    if relationship == "manager":
        predicates.append(direct_manager)
    elif relationship == "peer":
        predicates.append(~direct_manager)
    if predicates:
        query = query.where(*predicates)
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    feedback_ids = db.scalars(
        query.order_by(Feedback.created_at.desc(), Feedback.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    rows = (
        db.scalars(_feedback_query().where(Feedback.id.in_([item.id for item in feedback_ids]))).all()
        if feedback_ids
        else []
    )
    order = {item.id: index for index, item in enumerate(feedback_ids)}
    rows.sort(key=lambda item: order[item.id])
    return PaginatedFeedback(
        items=[_feedback_response(item) for item in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/feedback/{feedback_id}", response_model=FeedbackResponse)
def get_feedback(feedback_id: str, db: Session = Depends(get_db)) -> FeedbackResponse:
    return _feedback_response(_feedback_or_404(db, feedback_id))


@router.post("/feedback", response_model=FeedbackResponse, status_code=201)
def create_feedback(payload: FeedbackCreate, db: Session = Depends(get_db)) -> FeedbackResponse:
    author, _, competencies = _validate_feedback_references(
        db,
        payload.author_employee_id,
        payload.subject_employee_id,
        payload.review_cycle_id,
        payload.competency_ids,
        payload.reviewer_relationship,
    )
    set_audit_actor(db, author.id)
    feedback = Feedback(
        id=next_feedback_id(db),
        author_employee_id=author.id,
        subject_employee_id=payload.subject_employee_id,
        review_cycle_id=payload.review_cycle_id,
        content=payload.content,
        visibility=payload.visibility,
        status=payload.status,
        competencies=competencies,
    )
    db.add(feedback)
    _commit(db)
    return _feedback_response(_feedback_or_404(db, feedback.id))


@router.patch("/feedback/{feedback_id}", response_model=FeedbackResponse)
def update_feedback(
    feedback_id: str, payload: FeedbackUpdate, db: Session = Depends(get_db)
) -> FeedbackResponse:
    feedback = _feedback_or_404(db, feedback_id)
    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        return _feedback_response(feedback)
    current_status = feedback.status
    next_status = changes.get("status", current_status)
    content_changes = set(changes) - {"status"}
    if content_changes and current_status != "draft":
        raise HTTPException(status_code=409, detail="Only draft feedback can be edited.")
    if current_status == "withdrawn":
        raise HTTPException(status_code=409, detail="Withdrawn feedback cannot be changed.")
    allowed_transitions = {
        "draft": {"draft", "submitted", "withdrawn"},
        "submitted": {"submitted", "withdrawn"},
    }
    if next_status not in allowed_transitions.get(current_status, set()):
        raise HTTPException(status_code=409, detail="This feedback status transition is not allowed.")
    if feedback.review_cycle_id:
        cycle = db.get(ReviewCycle, feedback.review_cycle_id)
        if cycle is not None and cycle.status in {"closed", "archived"}:
            raise HTTPException(status_code=409, detail="Feedback in a closed or archived cycle cannot be edited.")
    competencies = None
    if "competency_ids" in changes:
        _, _, competencies = _validate_feedback_references(
            db,
            feedback.author_employee_id,
            feedback.subject_employee_id,
            feedback.review_cycle_id,
            changes["competency_ids"],
        )
    set_audit_actor(db, feedback.author_employee_id)
    if "content" in changes:
        feedback.content = changes["content"]
    if "visibility" in changes:
        feedback.visibility = changes["visibility"]
    if "status" in changes:
        feedback.status = changes["status"]
    if competencies is not None:
        feedback.competencies = competencies
    _commit(db)
    return _feedback_response(_feedback_or_404(db, feedback.id))
