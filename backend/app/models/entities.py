from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Table,
    Text,
    UniqueConstraint,
    Column,
    text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


employee_competencies = Table(
    "employee_competencies",
    Base.metadata,
    Column("employee_id", String(40), ForeignKey("employees.id", ondelete="RESTRICT"), primary_key=True),
    Column("competency_id", String(40), ForeignKey("competencies.id", ondelete="RESTRICT"), primary_key=True),
    Column("effective_from", Date, nullable=False),
    Column("effective_to", Date),
    Column("proficiency", Numeric(3, 2), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    CheckConstraint("effective_to IS NULL OR effective_to >= effective_from", name="ck_employee_competencies_dates"),
    CheckConstraint("proficiency >= 0 AND proficiency <= 5", name="ck_employee_competencies_proficiency"),
)

goal_competencies = Table(
    "goal_competencies",
    Base.metadata,
    Column("goal_id", String(40), ForeignKey("goals.id", ondelete="RESTRICT"), primary_key=True),
    Column("competency_id", String(40), ForeignKey("competencies.id", ondelete="RESTRICT"), primary_key=True),
)

checkin_key_results = Table(
    "checkin_key_results",
    Base.metadata,
    Column("checkin_id", String(40), ForeignKey("checkins.id", ondelete="RESTRICT"), primary_key=True),
    Column("key_result_id", String(40), ForeignKey("key_results.id", ondelete="RESTRICT"), primary_key=True),
)

feedback_competencies = Table(
    "feedback_competencies",
    Base.metadata,
    Column("feedback_id", String(40), ForeignKey("feedback.id", ondelete="RESTRICT"), primary_key=True),
    Column("competency_id", String(40), ForeignKey("competencies.id", ondelete="RESTRICT"), primary_key=True),
)

review_competencies = Table(
    "review_competencies",
    Base.metadata,
    Column("review_id", String(40), ForeignKey("reviews.id", ondelete="RESTRICT"), primary_key=True),
    Column("competency_id", String(40), ForeignKey("competencies.id", ondelete="RESTRICT"), primary_key=True),
)

development_plan_goals = Table(
    "development_plan_goals",
    Base.metadata,
    Column("development_plan_id", String(40), ForeignKey("development_plans.id", ondelete="RESTRICT"), primary_key=True),
    Column("goal_id", String(40), ForeignKey("goals.id", ondelete="RESTRICT"), primary_key=True),
)

development_plan_competencies = Table(
    "development_plan_competencies",
    Base.metadata,
    Column("development_plan_id", String(40), ForeignKey("development_plans.id", ondelete="RESTRICT"), primary_key=True),
    Column("competency_id", String(40), ForeignKey("competencies.id", ondelete="RESTRICT"), primary_key=True),
)


class Employee(TimestampMixin, Base):
    __tablename__ = "employees"
    __table_args__ = (
        CheckConstraint("id ~ '^EMP-[0-9]{6}$'", name="ck_employees_id_format"),
        CheckConstraint(
            "status IN ('active', 'leave', 'inactive', 'terminated')", name="ck_employees_status"
        ),
        CheckConstraint(
            "effective_to IS NULL OR effective_to >= effective_from", name="ck_employees_effective_dates"
        ),
        UniqueConstraint("email", name="uq_employees_email"),
        Index("ix_employees_manager_id", "manager_id"),
        Index("ix_employees_status", "status"),
    )

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    manager_id: Mapped[str | None] = mapped_column(
        String(40),
        ForeignKey(
            "managers.id",
            name="fk_employees_manager_id_managers",
            ondelete="RESTRICT",
            use_alter=True,
            deferrable=True,
            initially="DEFERRED",
        ),
    )
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    job_title: Mapped[str] = mapped_column(String(160), nullable=False)
    department: Mapped[str] = mapped_column(String(160), nullable=False)
    hire_date: Mapped[date] = mapped_column(Date, nullable=False)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'active'"))

    manager: Mapped[Manager | None] = relationship(
        back_populates="reports", foreign_keys=[manager_id]
    )
    manager_profile: Mapped[Manager | None] = relationship(
        back_populates="employee", foreign_keys="Manager.employee_id", uselist=False
    )
    goals: Mapped[list[Goal]] = relationship(back_populates="employee")
    checkins: Mapped[list[CheckIn]] = relationship(back_populates="employee")
    authored_feedback: Mapped[list[Feedback]] = relationship(
        back_populates="author", foreign_keys="Feedback.author_employee_id"
    )
    received_feedback: Mapped[list[Feedback]] = relationship(
        back_populates="subject", foreign_keys="Feedback.subject_employee_id"
    )
    reviews: Mapped[list[Review]] = relationship(
        back_populates="employee", foreign_keys="Review.employee_id"
    )
    development_plans: Mapped[list[DevelopmentPlan]] = relationship(back_populates="employee")
    competencies: Mapped[list[Competency]] = relationship(
        secondary=employee_competencies, back_populates="employees"
    )


class Manager(TimestampMixin, Base):
    __tablename__ = "managers"
    __table_args__ = (
        CheckConstraint("id ~ '^MGR-[0-9]{6}$'", name="ck_managers_id_format"),
        CheckConstraint("status IN ('active', 'inactive')", name="ck_managers_status"),
        CheckConstraint(
            "effective_to IS NULL OR effective_to >= effective_from", name="ck_managers_effective_dates"
        ),
        UniqueConstraint("employee_id", name="uq_managers_employee_id"),
        Index("ix_managers_status", "status"),
    )

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    employee_id: Mapped[str] = mapped_column(
        String(40),
        ForeignKey(
            "employees.id",
            name="fk_managers_employee_id_employees",
            ondelete="RESTRICT",
            deferrable=True,
            initially="DEFERRED",
        ),
        nullable=False,
    )
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'active'"))

    employee: Mapped[Employee] = relationship(
        back_populates="manager_profile", foreign_keys=[employee_id]
    )
    reports: Mapped[list[Employee]] = relationship(
        back_populates="manager", foreign_keys="Employee.manager_id"
    )
    checkins: Mapped[list[CheckIn]] = relationship(back_populates="manager")
    reviews: Mapped[list[Review]] = relationship(back_populates="reviewer")
    development_plans: Mapped[list[DevelopmentPlan]] = relationship(back_populates="owner")


class ReviewCycle(TimestampMixin, Base):
    __tablename__ = "review_cycles"
    __table_args__ = (
        CheckConstraint("id ~ '^CYCLE-[0-9]{4}-H[12]$'", name="ck_review_cycles_id_format"),
        CheckConstraint(
            "id = 'CYCLE-' || lpad(year::text, 4, '0') || '-' || half",
            name="ck_review_cycles_id_matches_period",
        ),
        CheckConstraint(
            "status IN ('draft', 'open', 'closed', 'archived')", name="ck_review_cycles_status"
        ),
        CheckConstraint("ends_on >= starts_on", name="ck_review_cycles_dates"),
        UniqueConstraint("year", "half", name="uq_review_cycles_year_half"),
        CheckConstraint("year BETWEEN 1 AND 9999", name="ck_review_cycles_year"),
        CheckConstraint("half IN ('H1', 'H2')", name="ck_review_cycles_half"),
        Index("ix_review_cycles_status", "status"),
    )

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    half: Mapped[str] = mapped_column(String(2), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    starts_on: Mapped[date] = mapped_column(Date, nullable=False)
    ends_on: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'draft'"))

    goals: Mapped[list[Goal]] = relationship(back_populates="review_cycle")
    checkins: Mapped[list[CheckIn]] = relationship(back_populates="review_cycle")
    feedback: Mapped[list[Feedback]] = relationship(back_populates="review_cycle")
    reviews: Mapped[list[Review]] = relationship(back_populates="review_cycle")
    development_plans: Mapped[list[DevelopmentPlan]] = relationship(back_populates="review_cycle")


class Goal(TimestampMixin, Base):
    __tablename__ = "goals"
    __table_args__ = (
        CheckConstraint(
            "id ~ ('^GOAL-' || employee_id || '-[0-9]{3}$')",
            name="ck_goals_id_matches_employee",
        ),
        CheckConstraint(
            "status IN ('draft', 'active', 'on_track', 'at_risk', 'completed', 'cancelled')",
            name="ck_goals_status",
        ),
        CheckConstraint(
            "effective_to IS NULL OR effective_to >= effective_from", name="ck_goals_effective_dates"
        ),
        CheckConstraint("due_date >= effective_from", name="ck_goals_due_date"),
        Index("ix_goals_employee_cycle", "employee_id", "review_cycle_id"),
        Index("ix_goals_status_due", "status", "due_date"),
    )

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    employee_id: Mapped[str] = mapped_column(
        String(40), ForeignKey("employees.id", ondelete="RESTRICT"), nullable=False
    )
    review_cycle_id: Mapped[str] = mapped_column(
        String(40), ForeignKey("review_cycles.id", ondelete="RESTRICT"), nullable=False
    )
    owner_manager_id: Mapped[str | None] = mapped_column(
        String(40), ForeignKey("managers.id", ondelete="RESTRICT")
    )
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[date | None] = mapped_column(Date)
    due_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'draft'"))

    employee: Mapped[Employee] = relationship(back_populates="goals")
    review_cycle: Mapped[ReviewCycle] = relationship(back_populates="goals")
    owner: Mapped[Manager | None] = relationship()
    key_results: Mapped[list[KeyResult]] = relationship(back_populates="goal")
    competencies: Mapped[list[Competency]] = relationship(
        secondary=goal_competencies, back_populates="goals"
    )
    development_plans: Mapped[list[DevelopmentPlan]] = relationship(
        secondary=development_plan_goals, back_populates="goals"
    )


class KeyResult(TimestampMixin, Base):
    __tablename__ = "key_results"
    __table_args__ = (
        CheckConstraint(
            "id ~ ('^KR-' || goal_id || '-[0-9]{2}$')",
            name="ck_key_results_id_matches_goal",
        ),
        CheckConstraint(
            "status IN ('draft', 'active', 'on_track', 'at_risk', 'completed', 'cancelled')",
            name="ck_key_results_status",
        ),
        CheckConstraint("target_value > 0", name="ck_key_results_target_positive"),
        CheckConstraint("current_value >= 0", name="ck_key_results_current_nonnegative"),
        CheckConstraint(
            "weight IS NULL OR (weight >= 0 AND weight <= 100)",
            name="ck_key_results_weight_range",
        ),
        CheckConstraint("effective_to IS NULL OR effective_to >= effective_from", name="ck_key_results_effective_dates"),
        CheckConstraint("due_date >= effective_from", name="ck_key_results_due_date"),
        Index("ix_key_results_goal_id", "goal_id"),
    )

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    goal_id: Mapped[str] = mapped_column(
        String(40), ForeignKey("goals.id", ondelete="RESTRICT"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    unit: Mapped[str] = mapped_column(String(40), nullable=False)
    target_value: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    current_value: Mapped[Decimal | None] = mapped_column(Numeric(14, 4))
    weight: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[date | None] = mapped_column(Date)
    due_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'draft'"))

    goal: Mapped[Goal] = relationship(back_populates="key_results")
    checkins: Mapped[list[CheckIn]] = relationship(
        secondary=checkin_key_results, back_populates="key_results"
    )


class CheckIn(TimestampMixin, Base):
    __tablename__ = "checkins"
    __table_args__ = (
        CheckConstraint("id ~ '^CHK-[0-9]{6}$'", name="ck_checkins_id_format"),
        CheckConstraint(
            "status IN ('scheduled', 'completed', 'missed', 'cancelled')",
            name="ck_checkins_status",
        ),
        Index("ix_checkins_employee_date", "employee_id", "checkin_date"),
        Index("ix_checkins_manager_id", "manager_id"),
    )

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    employee_id: Mapped[str] = mapped_column(
        String(40), ForeignKey("employees.id", ondelete="RESTRICT"), nullable=False
    )
    manager_id: Mapped[str | None] = mapped_column(
        String(40), ForeignKey("managers.id", ondelete="RESTRICT")
    )
    review_cycle_id: Mapped[str | None] = mapped_column(
        String(40), ForeignKey("review_cycles.id", ondelete="RESTRICT")
    )
    checkin_date: Mapped[date] = mapped_column(Date, nullable=False)
    notes: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'completed'"))

    employee: Mapped[Employee] = relationship(back_populates="checkins")
    manager: Mapped[Manager | None] = relationship(back_populates="checkins")
    review_cycle: Mapped[ReviewCycle | None] = relationship(back_populates="checkins")
    key_results: Mapped[list[KeyResult]] = relationship(
        secondary=checkin_key_results, back_populates="checkins"
    )


class Competency(TimestampMixin, Base):
    __tablename__ = "competencies"
    __table_args__ = (
        CheckConstraint("id ~ '^COMP-[0-9]{6}$'", name="ck_competencies_id_format"),
        CheckConstraint("status IN ('active', 'inactive')", name="ck_competencies_status"),
        CheckConstraint(
            "effective_to IS NULL OR effective_to >= effective_from",
            name="ck_competencies_effective_dates",
        ),
        UniqueConstraint("name", name="uq_competencies_name"),
        Index("ix_competencies_category_status", "category", "status"),
    )

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    category: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'active'"))

    employees: Mapped[list[Employee]] = relationship(
        secondary=employee_competencies, back_populates="competencies"
    )
    goals: Mapped[list[Goal]] = relationship(
        secondary=goal_competencies, back_populates="competencies"
    )
    feedback: Mapped[list[Feedback]] = relationship(
        secondary=feedback_competencies, back_populates="competencies"
    )
    reviews: Mapped[list[Review]] = relationship(
        secondary=review_competencies, back_populates="competencies"
    )
    development_plans: Mapped[list[DevelopmentPlan]] = relationship(
        secondary=development_plan_competencies, back_populates="competencies"
    )


class Feedback(TimestampMixin, Base):
    __tablename__ = "feedback"
    __table_args__ = (
        CheckConstraint("id ~ '^FB-[0-9]{6}$'", name="ck_feedback_id_format"),
        CheckConstraint(
            "status IN ('draft', 'submitted', 'withdrawn')", name="ck_feedback_status"
        ),
        CheckConstraint(
            "visibility IN ('private', 'manager', 'review_cycle')",
            name="ck_feedback_visibility",
        ),
        CheckConstraint("author_employee_id <> subject_employee_id", name="ck_feedback_distinct_people"),
        Index("ix_feedback_subject_cycle", "subject_employee_id", "review_cycle_id"),
        Index("ix_feedback_author_id", "author_employee_id"),
    )

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    author_employee_id: Mapped[str] = mapped_column(
        String(40), ForeignKey("employees.id", ondelete="RESTRICT"), nullable=False
    )
    subject_employee_id: Mapped[str] = mapped_column(
        String(40), ForeignKey("employees.id", ondelete="RESTRICT"), nullable=False
    )
    review_cycle_id: Mapped[str | None] = mapped_column(
        String(40), ForeignKey("review_cycles.id", ondelete="RESTRICT")
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    visibility: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'private'"))
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'submitted'"))

    author: Mapped[Employee] = relationship(
        back_populates="authored_feedback", foreign_keys=[author_employee_id]
    )
    subject: Mapped[Employee] = relationship(
        back_populates="received_feedback", foreign_keys=[subject_employee_id]
    )
    review_cycle: Mapped[ReviewCycle | None] = relationship(back_populates="feedback")
    competencies: Mapped[list[Competency]] = relationship(
        secondary=feedback_competencies, back_populates="feedback"
    )


class Review(TimestampMixin, Base):
    __tablename__ = "reviews"
    __table_args__ = (
        CheckConstraint("id ~ '^REV-[0-9]{4}-[0-9]{6}$'", name="ck_reviews_id_format"),
        CheckConstraint(
            "status IN ('draft', 'in_progress', 'submitted', 'approved', 'acknowledged')",
            name="ck_reviews_status",
        ),
        CheckConstraint("rating IS NULL OR (rating >= 0 AND rating <= 5)", name="ck_reviews_rating"),
        CheckConstraint(
            "effective_to IS NULL OR effective_to >= effective_from",
            name="ck_reviews_effective_dates",
        ),
        CheckConstraint("year BETWEEN 1 AND 9999", name="ck_reviews_year"),
        CheckConstraint(
            "id ~ ('^REV-' || lpad(year::text, 4, '0') || '-[0-9]{6}$')",
            name="ck_reviews_id_matches_year",
        ),
        CheckConstraint(
            "review_cycle_id ~ ('^CYCLE-' || lpad(year::text, 4, '0') || '-H[12]$')",
            name="ck_reviews_cycle_matches_year",
        ),
        UniqueConstraint("employee_id", "review_cycle_id", name="uq_reviews_employee_cycle"),
        Index("ix_reviews_cycle_status", "review_cycle_id", "status"),
        Index("ix_reviews_reviewer_id", "reviewer_manager_id"),
    )

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    employee_id: Mapped[str] = mapped_column(
        String(40), ForeignKey("employees.id", ondelete="RESTRICT"), nullable=False
    )
    reviewer_manager_id: Mapped[str] = mapped_column(
        String(40), ForeignKey("managers.id", ondelete="RESTRICT"), nullable=False
    )
    review_cycle_id: Mapped[str] = mapped_column(
        String(40), ForeignKey("review_cycles.id", ondelete="RESTRICT"), nullable=False
    )
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    rating: Mapped[Decimal | None] = mapped_column(Numeric(3, 2))
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'draft'"))

    employee: Mapped[Employee] = relationship(
        back_populates="reviews", foreign_keys=[employee_id]
    )
    reviewer: Mapped[Manager] = relationship(back_populates="reviews")
    review_cycle: Mapped[ReviewCycle] = relationship(back_populates="reviews")
    competencies: Mapped[list[Competency]] = relationship(
        secondary=review_competencies, back_populates="reviews"
    )
    approvals: Mapped[list[ReviewApproval]] = relationship(back_populates="review")


class DevelopmentPlan(TimestampMixin, Base):
    __tablename__ = "development_plans"
    __table_args__ = (
        CheckConstraint("id ~ '^DEV-[0-9]{6}$'", name="ck_development_plans_id_format"),
        CheckConstraint(
            "status IN ('draft', 'active', 'completed', 'cancelled')",
            name="ck_development_plans_status",
        ),
        CheckConstraint(
            "effective_to IS NULL OR effective_to >= effective_from",
            name="ck_development_plans_effective_dates",
        ),
        Index("ix_development_plans_employee_status", "employee_id", "status"),
    )

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    employee_id: Mapped[str] = mapped_column(
        String(40), ForeignKey("employees.id", ondelete="RESTRICT"), nullable=False
    )
    owner_manager_id: Mapped[str] = mapped_column(
        String(40), ForeignKey("managers.id", ondelete="RESTRICT"), nullable=False
    )
    review_cycle_id: Mapped[str | None] = mapped_column(
        String(40), ForeignKey("review_cycles.id", ondelete="RESTRICT")
    )
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'draft'"))

    employee: Mapped[Employee] = relationship(back_populates="development_plans")
    owner: Mapped[Manager] = relationship(back_populates="development_plans")
    review_cycle: Mapped[ReviewCycle | None] = relationship(back_populates="development_plans")
    goals: Mapped[list[Goal]] = relationship(
        secondary=development_plan_goals, back_populates="development_plans"
    )
    competencies: Mapped[list[Competency]] = relationship(
        secondary=development_plan_competencies, back_populates="development_plans"
    )
    approvals: Mapped[list[DevelopmentPlanApproval]] = relationship(back_populates="development_plan")


class Evidence(TimestampMixin, Base):
    __tablename__ = "evidence"
    __table_args__ = (
        CheckConstraint("id ~ '^EVD-[0-9]{6}$'", name="ck_evidence_id_format"),
        CheckConstraint(
            "num_nonnulls(key_result_id, checkin_id, feedback_id, review_id) = 1",
            name="ck_evidence_exactly_one_target",
        ),
        CheckConstraint(
            "sha256 IS NULL OR sha256 ~ '^[0-9a-f]{64}$'", name="ck_evidence_sha256"
        ),
        Index("ix_evidence_employee_id", "employee_id"),
    )

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    employee_id: Mapped[str] = mapped_column(
        String(40), ForeignKey("employees.id", ondelete="RESTRICT"), nullable=False
    )
    key_result_id: Mapped[str | None] = mapped_column(
        String(40), ForeignKey("key_results.id", ondelete="RESTRICT")
    )
    checkin_id: Mapped[str | None] = mapped_column(
        String(40), ForeignKey("checkins.id", ondelete="RESTRICT")
    )
    feedback_id: Mapped[str | None] = mapped_column(
        String(40), ForeignKey("feedback.id", ondelete="RESTRICT")
    )
    review_id: Mapped[str | None] = mapped_column(
        String(40), ForeignKey("reviews.id", ondelete="RESTRICT")
    )
    uri: Mapped[str] = mapped_column(Text, nullable=False)
    media_type: Mapped[str] = mapped_column(String(160), nullable=False)
    sha256: Mapped[str | None] = mapped_column(String(64))
    description: Mapped[str] = mapped_column(Text, nullable=False)

    employee: Mapped[Employee] = relationship()
    key_result: Mapped[KeyResult | None] = relationship()
    checkin: Mapped[CheckIn | None] = relationship()
    feedback: Mapped[Feedback | None] = relationship()
    review: Mapped[Review | None] = relationship()


class ReviewApproval(TimestampMixin, Base):
    __tablename__ = "review_approvals"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'approved', 'rejected')", name="ck_review_approvals_status"
        ),
        CheckConstraint(
            "(status = 'pending' AND decided_at IS NULL) OR "
            "(status IN ('approved', 'rejected') AND decided_at IS NOT NULL)",
            name="ck_review_approvals_decision",
        ),
        Index("ix_review_approvals_approver", "approver_manager_id"),
    )

    review_id: Mapped[str] = mapped_column(
        String(40), ForeignKey("reviews.id", ondelete="RESTRICT"), primary_key=True
    )
    approver_manager_id: Mapped[str] = mapped_column(
        String(40), ForeignKey("managers.id", ondelete="RESTRICT"), primary_key=True
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'pending'"))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    comments: Mapped[str | None] = mapped_column(Text)

    review: Mapped[Review] = relationship(back_populates="approvals")
    approver: Mapped[Manager] = relationship()


class DevelopmentPlanApproval(TimestampMixin, Base):
    __tablename__ = "development_plan_approvals"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'approved', 'rejected')",
            name="ck_development_plan_approvals_status",
        ),
        CheckConstraint(
            "(status = 'pending' AND decided_at IS NULL) OR "
            "(status IN ('approved', 'rejected') AND decided_at IS NOT NULL)",
            name="ck_development_plan_approvals_decision",
        ),
        Index("ix_development_plan_approvals_approver", "approver_manager_id"),
    )

    development_plan_id: Mapped[str] = mapped_column(
        String(40), ForeignKey("development_plans.id", ondelete="RESTRICT"), primary_key=True
    )
    approver_manager_id: Mapped[str] = mapped_column(
        String(40), ForeignKey("managers.id", ondelete="RESTRICT"), primary_key=True
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'pending'"))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    comments: Mapped[str | None] = mapped_column(Text)

    development_plan: Mapped[DevelopmentPlan] = relationship(back_populates="approvals")
    approver: Mapped[Manager] = relationship()


class EntityHistory(TimestampMixin, Base):
    __tablename__ = "entity_history"
    __table_args__ = (
        CheckConstraint(
            "entity_type IN ('Employee', 'Manager', 'ReviewCycle', 'Goal', 'KeyResult', "
            "'CheckIn', 'Competency', 'Feedback', 'Review', 'DevelopmentPlan', 'Evidence')",
            name="ck_entity_history_type",
        ),
        CheckConstraint(
            "action IN ('INSERT', 'UPDATE', 'DELETE', 'RELATIONSHIP_INSERTED', "
            "'RELATIONSHIP_UPDATED', 'RELATIONSHIP_DELETED')",
            name="ck_entity_history_action",
        ),
        CheckConstraint(
            "before_data IS NOT NULL OR after_data IS NOT NULL",
            name="ck_entity_history_snapshot_present",
        ),
        Index("ix_entity_history_type_recorded", "entity_type", "recorded_at"),
    )

    event_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    entity_type: Mapped[str] = mapped_column(String(40), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(40), nullable=False)
    actor_id: Mapped[str] = mapped_column(String(40), nullable=False, server_default=text("'SYSTEM'"))
    actor_employee_id: Mapped[str | None] = mapped_column(
        String(40), ForeignKey("employees.id", ondelete="RESTRICT")
    )
    action: Mapped[str] = mapped_column(String(24), nullable=False)
    before_data: Mapped[dict | None] = mapped_column(JSONB)
    after_data: Mapped[dict | None] = mapped_column(JSONB)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
