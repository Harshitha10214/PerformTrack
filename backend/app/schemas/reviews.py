from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, model_validator


ReviewCycleStatus = Literal["draft", "open", "closed", "archived"]
ReviewStatus = Literal["draft", "in_progress", "submitted", "approved", "acknowledged"]
ApprovalStatus = Literal["pending", "approved", "rejected"]


class ReviewCycleCreate(BaseModel):
    year: int = Field(ge=1, le=9999)
    half: Literal["H1", "H2"]
    name: str = Field(min_length=1, max_length=120)
    starts_on: date
    ends_on: date

    @model_validator(mode="after")
    def validate_period(self):
        self.name = self.name.strip()
        if not self.name:
            raise ValueError("name cannot be blank")
        half_start = date(self.year, 1 if self.half == "H1" else 7, 1)
        half_end = date(self.year, 6, 30) if self.half == "H1" else date(self.year, 12, 31)
        if self.starts_on < half_start or self.ends_on > half_end or self.ends_on < self.starts_on:
            raise ValueError("Cycle dates must fall within the selected half-year.")
        return self


class ReviewCycleUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    starts_on: date | None = None
    ends_on: date | None = None
    status: ReviewCycleStatus | None = None

    @model_validator(mode="after")
    def validate_name(self):
        if self.name is not None:
            self.name = self.name.strip()
            if not self.name:
                raise ValueError("name cannot be blank")
        return self


class ReviewCycleResponse(BaseModel):
    id: str
    year: int
    half: Literal["H1", "H2"]
    name: str
    starts_on: date
    ends_on: date
    status: ReviewCycleStatus
    review_count: int
    pending_review_count: int
    approved_review_count: int
    created_at: datetime
    updated_at: datetime


class PaginatedReviewCycles(BaseModel):
    items: list[ReviewCycleResponse]
    total: int
    page: int
    page_size: int


class ReviewCreate(BaseModel):
    employee_id: str
    reviewer_manager_id: str
    review_cycle_id: str
    summary: str = Field(min_length=1)
    rating: Decimal | None = Field(default=None, ge=0, le=5)
    effective_from: date
    effective_to: date | None = None
    competency_ids: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_content(self):
        self.summary = self.summary.strip()
        if not self.summary:
            raise ValueError("summary cannot be blank")
        if self.effective_to and self.effective_to < self.effective_from:
            raise ValueError("effective_to cannot be before effective_from")
        self.competency_ids = list(dict.fromkeys(self.competency_ids))
        return self


class ReviewUpdate(BaseModel):
    summary: str | None = Field(default=None, min_length=1)
    rating: Decimal | None = Field(default=None, ge=0, le=5)
    effective_to: date | None = None
    status: ReviewStatus | None = None
    competency_ids: list[str] | None = None

    @model_validator(mode="after")
    def validate_content(self):
        if self.summary is not None:
            self.summary = self.summary.strip()
            if not self.summary:
                raise ValueError("summary cannot be blank")
        if self.competency_ids is not None:
            self.competency_ids = list(dict.fromkeys(self.competency_ids))
        return self


class ReviewApprovalDecision(BaseModel):
    approver_manager_id: str
    status: Literal["approved", "rejected"]
    comments: str | None = Field(default=None, max_length=4000)

    @model_validator(mode="after")
    def normalize_comments(self):
        if self.comments is not None:
            self.comments = self.comments.strip() or None
        return self


class ReviewCompetencySummary(BaseModel):
    id: str
    name: str
    category: str


class ReviewApprovalResponse(BaseModel):
    approver_manager_id: str
    approver_name: str
    approver_employee_id: str
    status: ApprovalStatus
    decided_at: datetime | None
    comments: str | None


class ReviewResponse(BaseModel):
    id: str
    year: int
    employee_id: str
    employee_name: str
    department: str
    reviewer_manager_id: str
    reviewer_name: str
    reviewer_employee_id: str
    review_cycle_id: str
    review_cycle_name: str
    review_cycle_status: ReviewCycleStatus
    summary: str
    rating: Decimal | None
    effective_from: date
    effective_to: date | None
    status: ReviewStatus
    editable: bool
    approval_actionable: bool
    acknowledgeable: bool
    competencies: list[ReviewCompetencySummary]
    approvals: list[ReviewApprovalResponse]
    created_at: datetime
    updated_at: datetime


class PaginatedReviews(BaseModel):
    items: list[ReviewResponse]
    total: int
    page: int
    page_size: int
