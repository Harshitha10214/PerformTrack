from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator


DevelopmentPlanStatus = Literal["draft", "active", "completed", "cancelled"]
ApprovalStatus = Literal["pending", "approved", "rejected"]


class DevelopmentPlanCreate(BaseModel):
    employee_id: str
    owner_manager_id: str
    review_cycle_id: str | None = None
    title: str = Field(min_length=1, max_length=240)
    description: str = Field(min_length=1)
    effective_from: date
    effective_to: date | None = None
    goal_ids: list[str] = Field(default_factory=list)
    competency_ids: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def normalize_content(self):
        self.title = self.title.strip()
        self.description = self.description.strip()
        if not self.title or not self.description:
            raise ValueError("title and description cannot be blank")
        if self.effective_to and self.effective_to < self.effective_from:
            raise ValueError("effective_to cannot be before effective_from")
        self.goal_ids = list(dict.fromkeys(self.goal_ids))
        self.competency_ids = list(dict.fromkeys(self.competency_ids))
        return self


class DevelopmentPlanUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=240)
    description: str | None = Field(default=None, min_length=1)
    effective_from: date | None = None
    effective_to: date | None = None
    status: DevelopmentPlanStatus | None = None
    goal_ids: list[str] | None = None
    competency_ids: list[str] | None = None

    @model_validator(mode="after")
    def normalize_content(self):
        if self.title is not None:
            self.title = self.title.strip()
            if not self.title:
                raise ValueError("title cannot be blank")
        if self.description is not None:
            self.description = self.description.strip()
            if not self.description:
                raise ValueError("description cannot be blank")
        if self.goal_ids is not None:
            self.goal_ids = list(dict.fromkeys(self.goal_ids))
        if self.competency_ids is not None:
            self.competency_ids = list(dict.fromkeys(self.competency_ids))
        return self


class DevelopmentPlanApprovalDecision(BaseModel):
    approver_manager_id: str
    status: Literal["approved", "rejected"]
    comments: str | None = Field(default=None, max_length=4000)

    @model_validator(mode="after")
    def normalize_comments(self):
        if self.comments is not None:
            self.comments = self.comments.strip() or None
        return self


class DevelopmentPlanGoalSummary(BaseModel):
    id: str
    title: str


class DevelopmentPlanCompetencySummary(BaseModel):
    id: str
    name: str
    category: str


class DevelopmentPlanApprovalResponse(BaseModel):
    approver_manager_id: str
    approver_name: str
    approver_employee_id: str
    status: ApprovalStatus
    decided_at: datetime | None
    comments: str | None


class DevelopmentPlanResponse(BaseModel):
    id: str
    employee_id: str
    employee_name: str
    owner_manager_id: str
    owner_manager_name: str
    review_cycle_id: str | None
    review_cycle_name: str | None
    title: str
    description: str
    effective_from: date
    effective_to: date | None
    status: DevelopmentPlanStatus
    editable: bool
    approval_actionable: bool
    goals: list[DevelopmentPlanGoalSummary]
    competencies: list[DevelopmentPlanCompetencySummary]
    approvals: list[DevelopmentPlanApprovalResponse]
    created_at: datetime
    updated_at: datetime


class PaginatedDevelopmentPlans(BaseModel):
    items: list[DevelopmentPlanResponse]
    total: int
    page: int
    page_size: int
