from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


Visibility = Literal["private", "manager", "review_cycle"]
FeedbackStatus = Literal["draft", "submitted", "withdrawn"]
ReviewerRelationship = Literal["manager", "peer"]


class CompetencyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    category: str
    description: str
    effective_from: date
    effective_to: date | None
    status: str
    employee_count: int = 0


class PaginatedCompetencies(BaseModel):
    items: list[CompetencyResponse]
    total: int
    page: int
    page_size: int


class EmployeeCompetencyResponse(BaseModel):
    competency_id: str
    name: str
    category: str
    description: str
    proficiency: Decimal
    effective_from: date
    effective_to: date | None


class CompetencySummary(BaseModel):
    id: str
    name: str
    category: str


class FeedbackCreate(BaseModel):
    author_employee_id: str
    subject_employee_id: str
    reviewer_relationship: ReviewerRelationship | None = None
    review_cycle_id: str | None = None
    content: str = Field(min_length=1)
    visibility: Visibility = "private"
    status: FeedbackStatus = "draft"
    competency_ids: list[str] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_people_and_competencies(self):
        self.content = self.content.strip()
        if not self.content:
            raise ValueError("content cannot be blank")
        self.competency_ids = list(dict.fromkeys(self.competency_ids))
        return self


class FeedbackUpdate(BaseModel):
    content: str | None = Field(default=None, min_length=1)
    visibility: Visibility | None = None
    status: FeedbackStatus | None = None
    competency_ids: list[str] | None = None

    @model_validator(mode="after")
    def validate_content(self):
        if self.content is not None:
            self.content = self.content.strip()
            if not self.content:
                raise ValueError("content cannot be blank")
        if self.competency_ids is not None:
            self.competency_ids = list(dict.fromkeys(self.competency_ids))
        return self


class FeedbackResponse(BaseModel):
    id: str
    author_employee_id: str
    author_name: str
    subject_employee_id: str
    subject_name: str
    reviewer_relationship: ReviewerRelationship
    review_cycle_id: str | None
    review_cycle_name: str | None
    content: str
    visibility: Visibility
    status: FeedbackStatus
    editable: bool
    withdrawable: bool
    competencies: list[CompetencySummary]
    created_at: datetime
    updated_at: datetime


class PaginatedFeedback(BaseModel):
    items: list[FeedbackResponse]
    total: int
    page: int
    page_size: int
