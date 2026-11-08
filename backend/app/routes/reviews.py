from datetime import date, datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import case, func, or_, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session, aliased, selectinload

from app.database import get_db
from app.models import (
    Competency,
    Employee,
    EntityHistory,
    Goal,
    CheckIn,
    Feedback,
    DevelopmentPlan,
    Manager,
    Review,
    ReviewApproval,
    ReviewCycle,
)

from app.models.ids import format_cycle_id
from app.schemas.reviews import (
    PaginatedReviewCycles,
    PaginatedReviews,
    ReviewApprovalDecision,
    ReviewApprovalResponse,
    ReviewCompetencySummary,
    ReviewCreate,
    ReviewCycleCreate,
    ReviewCycleResponse,
    ReviewCycleUpdate,
    ReviewResponse,
    ReviewUpdate,
)
from app.services.audit import set_audit_actor
from app.services.record_ids import next_review_id

router = APIRouter(tags=["review-cycles-and-reviews"])


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


def _cycle_counts(db: Session, cycle_ids: list[str]) -> dict[str, tuple[int, int, int]]:
    if not cycle_ids:
        return {}
    rows = db.execute(
        select(
            Review.review_cycle_id,
            func.count(Review.id),
            func.sum(case((Review.status.in_(("draft", "in_progress", "submitted")), 1), else_=0)),
            func.sum(case((Review.status.in_(("approved", "acknowledged")), 1), else_=0)),
        )
        .where(Review.review_cycle_id.in_(cycle_ids))
        .group_by(Review.review_cycle_id)
    ).all()
    return {
        cycle_id: (int(total or 0), int(pending or 0), int(approved or 0))
        for cycle_id, total, pending, approved in rows
    }


def _cycle_response(cycle: ReviewCycle, counts: tuple[int, int, int] = (0, 0, 0)) -> ReviewCycleResponse:
    return ReviewCycleResponse(
        id=cycle.id,
        year=cycle.year,
        half=cycle.half,
        name=cycle.name,
        starts_on=cycle.starts_on,
        ends_on=cycle.ends_on,
        status=cycle.status,
        review_count=counts[0],
        pending_review_count=counts[1],
        approved_review_count=counts[2],
        created_at=cycle.created_at,
        updated_at=cycle.updated_at,
    )


def _review_query():
    return select(Review).options(
        selectinload(Review.employee),
        selectinload(Review.reviewer).selectinload(Manager.employee),
        selectinload(Review.review_cycle),
        selectinload(Review.competencies),
        selectinload(Review.approvals).selectinload(ReviewApproval.approver).selectinload(Manager.employee),
    )


def _review_or_404(db: Session, review_id: str) -> Review:
    review = db.scalar(_review_query().where(Review.id == review_id))
    if review is None:
        raise HTTPException(status_code=404, detail="Review not found.")
    return review


def _cycle_or_404(db: Session, cycle_id: str) -> ReviewCycle:
    cycle = db.get(ReviewCycle, cycle_id)
    if cycle is None:
        raise HTTPException(status_code=404, detail="Review cycle not found.")
    return cycle


def _ensure_cycle_editable(cycle: ReviewCycle) -> None:
    if cycle.status not in {"draft", "open"}:
        raise HTTPException(status_code=409, detail="Reviews in a closed or archived cycle cannot be changed.")


def _approval_snapshot(approval: ReviewApproval) -> dict:
    return {
        "review_id": approval.review_id,
        "approver_manager_id": approval.approver_manager_id,
        "status": approval.status,
        "decided_at": approval.decided_at.isoformat() if approval.decided_at else None,
        "comments": approval.comments,
    }


def _record_approval_history(
    db: Session,
    review_id: str,
    actor_employee_id: str,
    action: str,
    before: dict | None,
    after: dict | None,
) -> None:
    db.add(
        EntityHistory(
            event_id=str(uuid4()),
            entity_type="Review",
            entity_id=review_id,
            actor_id=actor_employee_id,
            actor_employee_id=actor_employee_id,
            action=action,
            before_data={"approval": before} if before else None,
            after_data={"approval": after} if after else None,
            recorded_at=datetime.now(timezone.utc),
        )
    )


def _review_response(review: Review) -> ReviewResponse:
    pending_approval = any(approval.status == "pending" for approval in review.approvals)
    return ReviewResponse(
        id=review.id,
        year=review.year,
        employee_id=review.employee_id,
        employee_name=f"{review.employee.first_name} {review.employee.last_name}",
        department=review.employee.department,
        reviewer_manager_id=review.reviewer_manager_id,
        reviewer_name=f"{review.reviewer.employee.first_name} {review.reviewer.employee.last_name}",
        reviewer_employee_id=review.reviewer.employee_id,
        review_cycle_id=review.review_cycle_id,
        review_cycle_name=review.review_cycle.name,
        review_cycle_status=review.review_cycle.status,
        summary=review.summary,
        rating=review.rating,
        effective_from=review.effective_from,
        effective_to=review.effective_to,
        status=review.status,
        editable=(
            review.status in {"draft", "in_progress"}
            and review.review_cycle.status in {"draft", "open"}
        ),
        approval_actionable=(
            review.status == "submitted"
            and pending_approval
            and review.review_cycle.status in {"draft", "open"}
        ),
        acknowledgeable=(
            review.status == "approved" and review.review_cycle.status in {"draft", "open"}
        ),
        competencies=[
            ReviewCompetencySummary(id=item.id, name=item.name, category=item.category)
            for item in sorted(review.competencies, key=lambda competency: (competency.category, competency.name))
        ],
        approvals=[
            ReviewApprovalResponse(
                approver_manager_id=item.approver_manager_id,
                approver_name=f"{item.approver.employee.first_name} {item.approver.employee.last_name}",
                approver_employee_id=item.approver.employee_id,
                status=item.status,
                decided_at=item.decided_at,
                comments=item.comments,
            )
            for item in sorted(review.approvals, key=lambda approval: approval.approver_manager_id)
        ],
        created_at=review.created_at,
        updated_at=review.updated_at,
    )


def _validate_references(
    db: Session,
    employee_id: str,
    reviewer_manager_id: str,
    cycle_id: str,
    effective_from,
    effective_to,
    competency_ids: list[str],
) -> tuple[Employee, Manager, ReviewCycle, list[Competency]]:
    employee = db.get(Employee, employee_id)
    if employee is None:
        raise HTTPException(status_code=422, detail="employee_id must reference an existing employee.")
    reviewer = db.get(Manager, reviewer_manager_id)
    if reviewer is None:
        raise HTTPException(status_code=422, detail="reviewer_manager_id must reference an existing manager.")
    if reviewer.employee_id == employee.id:
        raise HTTPException(
            status_code=422,
            detail="Employees cannot review themselves.",
        )
    if employee.manager_id is not None:
        if employee.manager_id != reviewer.id:
            raise HTTPException(
                status_code=422,
                detail="The reviewer must be the employee's assigned manager.",
            )
    else:
        manager_profile_id = db.scalar(
            select(Manager.id).where(Manager.employee_id == employee.id)
        )
        if manager_profile_id is None or manager_profile_id == reviewer.id:
            raise HTTPException(
                status_code=422,
                detail="An employee without an assigned manager must have a manager profile and be reviewed by another manager.",
            )
    cycle = db.get(ReviewCycle, cycle_id)
    if cycle is None:
        raise HTTPException(status_code=422, detail="review_cycle_id must reference an existing review cycle.")
    _ensure_cycle_editable(cycle)
    if cycle.year != effective_from.year or effective_from < cycle.starts_on:
        raise HTTPException(status_code=422, detail="Review dates must fall within the review cycle.")
    if effective_to is not None and (effective_to < effective_from or effective_to > cycle.ends_on):
        raise HTTPException(status_code=422, detail="Review dates must fall within the review cycle.")
    if effective_from > cycle.ends_on:
        raise HTTPException(status_code=422, detail="Review dates must fall within the review cycle.")

    competencies = (
        list(db.scalars(select(Competency).where(Competency.id.in_(competency_ids))).all())
        if competency_ids
        else []
    )
    if len(competencies) != len(set(competency_ids)):
        raise HTTPException(status_code=422, detail="Every competency_id must reference an existing competency.")
    return employee, reviewer, cycle, competencies


@router.get("/review-cycles", response_model=PaginatedReviewCycles)
def list_review_cycles(
    search: str | None = None,
    status: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    db: Session = Depends(get_db),
) -> PaginatedReviewCycles:
    query = select(ReviewCycle)
    if search:
        term = f"%{search.strip()}%"
        query = query.where(or_(ReviewCycle.id.ilike(term), ReviewCycle.name.ilike(term)))
    if status:
        query = query.where(ReviewCycle.status == status)
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    cycles = db.scalars(
        query.order_by(ReviewCycle.year.desc(), ReviewCycle.half.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    counts = _cycle_counts(db, [cycle.id for cycle in cycles])
    return PaginatedReviewCycles(
        items=[_cycle_response(cycle, counts.get(cycle.id, (0, 0, 0))) for cycle in cycles],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/review-cycles/{cycle_id}", response_model=ReviewCycleResponse)
def get_review_cycle(cycle_id: str, db: Session = Depends(get_db)) -> ReviewCycleResponse:
    cycle = _cycle_or_404(db, cycle_id)
    return _cycle_response(cycle, _cycle_counts(db, [cycle.id]).get(cycle.id, (0, 0, 0)))


@router.post("/review-cycles", response_model=ReviewCycleResponse, status_code=201)
def create_review_cycle(payload: ReviewCycleCreate, db: Session = Depends(get_db)) -> ReviewCycleResponse:
    cycle = ReviewCycle(
        id=format_cycle_id(payload.year, payload.half),
        year=payload.year,
        half=payload.half,
        name=payload.name,
        starts_on=payload.starts_on,
        ends_on=payload.ends_on,
        status="draft",
    )
    db.add(cycle)
    _commit(db)
    db.refresh(cycle)
    return _cycle_response(cycle)


@router.patch("/review-cycles/{cycle_id}", response_model=ReviewCycleResponse)
def update_review_cycle(
    cycle_id: str, payload: ReviewCycleUpdate, db: Session = Depends(get_db)
) -> ReviewCycleResponse:
    cycle = _cycle_or_404(db, cycle_id)
    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        return _cycle_response(cycle, _cycle_counts(db, [cycle.id]).get(cycle.id, (0, 0, 0)))
    next_status = changes.get("status", cycle.status)
    allowed = {
        "draft": {"draft", "open"},
        "open": {"open", "closed"},
        "closed": {"closed", "archived"},
        "archived": {"archived"},
    }
    if next_status not in allowed[cycle.status]:
        raise HTTPException(status_code=409, detail="This review-cycle status transition is not allowed.")
    metadata_changes = set(changes) - {"status"}
    if metadata_changes and cycle.status != "draft":
        raise HTTPException(status_code=409, detail="Only draft review cycles can be edited.")
    start = changes.get("starts_on", cycle.starts_on)
    end = changes.get("ends_on", cycle.ends_on)
    half_start = date(cycle.year, 1 if cycle.half == "H1" else 7, 1)
    half_end = date(cycle.year, 6, 30) if cycle.half == "H1" else date(cycle.year, 12, 31)
    if start < half_start or end > half_end or end < start:
        raise HTTPException(status_code=422, detail="Cycle dates must fall within its half-year.")
    if {"starts_on", "ends_on"} & metadata_changes:
        dependent_count = sum(
            db.scalar(select(func.count()).select_from(model).where(model.review_cycle_id == cycle.id)) or 0
            for model in (Review, Goal, CheckIn, Feedback, DevelopmentPlan)
        )
        if dependent_count:
            raise HTTPException(status_code=409, detail="Cycle dates cannot change after records are associated.")
    for key, value in changes.items():
        setattr(cycle, key, value)
    _commit(db)
    db.refresh(cycle)
    return _cycle_response(cycle, _cycle_counts(db, [cycle.id]).get(cycle.id, (0, 0, 0)))


@router.get("/reviews", response_model=PaginatedReviews)
def list_reviews(
    search: str | None = None,
    status: str | None = None,
    review_cycle_id: str | None = None,
    employee_id: str | None = None,
    reviewer_manager_id: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    db: Session = Depends(get_db),
) -> PaginatedReviews:
    employee = aliased(Employee)
    reviewer_employee = aliased(Employee)
    query = (
        select(Review)
        .join(employee, Review.employee_id == employee.id)
        .join(ReviewCycle, Review.review_cycle_id == ReviewCycle.id)
        .join(Manager, Review.reviewer_manager_id == Manager.id)
        .join(reviewer_employee, Manager.employee_id == reviewer_employee.id)
    )
    predicates = []
    if search:
        term = f"%{search.strip()}%"
        predicates.append(
            or_(
                Review.id.ilike(term),
                Review.summary.ilike(term),
                employee.first_name.ilike(term),
                employee.last_name.ilike(term),
                reviewer_employee.first_name.ilike(term),
                reviewer_employee.last_name.ilike(term),
                ReviewCycle.name.ilike(term),
            )
        )
    if status:
        predicates.append(Review.status == status)
    if review_cycle_id:
        predicates.append(Review.review_cycle_id == review_cycle_id)
    if employee_id:
        predicates.append(Review.employee_id == employee_id)
    if reviewer_manager_id:
        predicates.append(Review.reviewer_manager_id == reviewer_manager_id)
    if predicates:
        query = query.where(*predicates)
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    ids = db.scalars(
        query.order_by(Review.updated_at.desc(), Review.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    reviews = db.scalars(_review_query().where(Review.id.in_([item.id for item in ids]))).all() if ids else []
    order = {item.id: index for index, item in enumerate(ids)}
    reviews.sort(key=lambda item: order[item.id])
    return PaginatedReviews(
        items=[_review_response(item) for item in reviews],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/reviews/{review_id}", response_model=ReviewResponse)
def get_review(review_id: str, db: Session = Depends(get_db)) -> ReviewResponse:
    return _review_response(_review_or_404(db, review_id))


@router.post("/reviews", response_model=ReviewResponse, status_code=201)
def create_review(payload: ReviewCreate, db: Session = Depends(get_db)) -> ReviewResponse:
    employee, reviewer, cycle, competencies = _validate_references(
        db,
        payload.employee_id,
        payload.reviewer_manager_id,
        payload.review_cycle_id,
        payload.effective_from,
        payload.effective_to,
        payload.competency_ids,
    )
    if db.scalar(
        select(Review.id).where(
            Review.employee_id == employee.id,
            Review.review_cycle_id == cycle.id,
        )
    ):
        raise HTTPException(status_code=409, detail="This employee already has a review in the selected cycle.")
    set_audit_actor(db, reviewer.employee_id)
    review = Review(
        id=next_review_id(db, cycle.year),
        year=cycle.year,
        employee_id=employee.id,
        reviewer_manager_id=reviewer.id,
        review_cycle_id=cycle.id,
        summary=payload.summary,
        rating=payload.rating,
        effective_from=payload.effective_from,
        effective_to=payload.effective_to,
        status="draft",
        competencies=competencies,
    )
    db.add(review)
    approval = ReviewApproval(
        review_id=review.id,
        approver_manager_id=reviewer.id,
        status="pending",
    )
    db.add(approval)
    _record_approval_history(db, review.id, reviewer.employee_id, "INSERT", None, _approval_snapshot(approval))
    _commit(db)
    return _review_response(_review_or_404(db, review.id))


@router.patch("/reviews/{review_id}", response_model=ReviewResponse)
def update_review(review_id: str, payload: ReviewUpdate, db: Session = Depends(get_db)) -> ReviewResponse:
    review = _review_or_404(db, review_id)
    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        return _review_response(review)
    _ensure_cycle_editable(review.review_cycle)
    current_status = review.status
    next_status = changes.get("status", current_status)
    transitions = {
        "draft": {"draft", "in_progress"},
        "in_progress": {"in_progress", "submitted"},
        "submitted": {"submitted"},
        "approved": {"approved", "acknowledged"},
        "acknowledged": {"acknowledged"},
    }
    if next_status not in transitions[current_status]:
        raise HTTPException(status_code=409, detail="This review status transition is not allowed.")
    content_changes = set(changes) - {"status"}
    if content_changes and current_status not in {"draft", "in_progress"}:
        raise HTTPException(status_code=409, detail="Only draft or in-progress reviews can be edited.")
    if next_status == "submitted" and current_status not in {"in_progress", "submitted"}:
        raise HTTPException(status_code=409, detail="A review must be in progress before it can be submitted.")
    effective_to = changes.get("effective_to", review.effective_to)
    if effective_to is not None and (
        effective_to < review.effective_from or effective_to > review.review_cycle.ends_on
    ):
        raise HTTPException(status_code=422, detail="Review dates must fall within the review cycle.")

    competencies = None
    if "competency_ids" in changes:
        competency_ids = changes["competency_ids"]
        competencies = (
            list(db.scalars(select(Competency).where(Competency.id.in_(competency_ids))).all())
            if competency_ids
            else []
        )
        if len(competencies) != len(set(competency_ids)):
            raise HTTPException(status_code=422, detail="Every competency_id must reference an existing competency.")

    set_audit_actor(db, review.reviewer.employee_id)
    for key in ("summary", "rating", "effective_to", "status"):
        if key in changes:
            setattr(review, key, changes[key])
    if competencies is not None:
        review.competencies = competencies

    if next_status == "submitted":
        approval = next(
            (item for item in review.approvals if item.approver_manager_id == review.reviewer_manager_id),
            None,
        )
        if approval is None:
            approval = ReviewApproval(
                review_id=review.id,
                approver_manager_id=review.reviewer_manager_id,
                status="pending",
            )
            db.add(approval)
            _record_approval_history(
                db, review.id, review.reviewer.employee_id, "INSERT", None, _approval_snapshot(approval)
            )
        elif approval.status == "rejected":
            before = _approval_snapshot(approval)
            approval.status = "pending"
            approval.decided_at = None
            approval.comments = None
            _record_approval_history(
                db,
                review.id,
                review.reviewer.employee_id,
                "UPDATE",
                before,
                _approval_snapshot(approval),
            )
    _commit(db)
    return _review_response(_review_or_404(db, review.id))


@router.post("/reviews/{review_id}/approval", response_model=ReviewResponse)
def decide_review_approval(
    review_id: str, payload: ReviewApprovalDecision, db: Session = Depends(get_db)
) -> ReviewResponse:
    review = _review_or_404(db, review_id)
    _ensure_cycle_editable(review.review_cycle)
    if review.status != "submitted":
        raise HTTPException(status_code=409, detail="Only submitted reviews can be approved or rejected.")
    if payload.approver_manager_id != review.reviewer_manager_id:
        raise HTTPException(status_code=422, detail="The approver must be the reviewer's assigned manager.")
    approver = db.get(Manager, payload.approver_manager_id)
    if approver is None or approver.employee_id == review.employee_id:
        raise HTTPException(status_code=422, detail="approver_manager_id must reference a valid manager.")
    approval = next(
        (item for item in review.approvals if item.approver_manager_id == approver.id),
        None,
    )
    if approval is None or approval.status != "pending":
        raise HTTPException(status_code=409, detail="No pending approval exists for this review.")
    before = _approval_snapshot(approval)
    decided_at = datetime.now(timezone.utc)
    approval.status = payload.status
    approval.decided_at = decided_at
    approval.comments = payload.comments
    review.status = "approved" if payload.status == "approved" else "in_progress"
    set_audit_actor(db, approver.employee_id)
    _record_approval_history(
        db,
        review.id,
        approver.employee_id,
        "UPDATE",
        before,
        _approval_snapshot(approval),
    )
    _commit(db)
    return _review_response(_review_or_404(db, review.id))
