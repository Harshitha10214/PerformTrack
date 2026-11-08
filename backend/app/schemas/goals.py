from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class KeyResultInput(BaseModel):
    title: str = Field(min_length=1, max_length=240)
    description: str
    unit: str = Field(min_length=1, max_length=40)
    target_value: Decimal = Field(gt=0)
    current_value: Decimal | None = Field(default=None, ge=0)
    weight: Decimal | None = Field(default=None, ge=0, le=100)
    effective_from: date
    effective_to: date | None = None
    due_date: date
    status: str = "active"

    @model_validator(mode="after")
    def validate_key_result(self):
        if self.status not in {"draft", "active", "on_track", "at_risk", "completed", "cancelled"}:
            raise ValueError("Invalid key result status")
        if self.due_date < self.effective_from:
            raise ValueError("Key result due date cannot be before its effective date")
        if self.effective_to and self.effective_to < self.effective_from:
            raise ValueError("Key result effective_to cannot be before effective_from")
        return self


class KeyResultUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=240)
    description: str | None = None
    unit: str | None = Field(default=None, min_length=1, max_length=40)
    target_value: Decimal | None = Field(default=None, gt=0)
    current_value: Decimal | None = Field(default=None, ge=0)
    weight: Decimal | None = Field(default=None, ge=0, le=100)
    effective_from: date | None = None
    effective_to: date | None = None
    due_date: date | None = None
    status: str | None = None


class KeyResultResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    goal_id: str
    title: str
    description: str
    unit: str
    target_value: Decimal
    current_value: Decimal | None
    weight: Decimal | None
    effective_from: date
    effective_to: date | None
    due_date: date
    status: str
    progress: Decimal = Decimal("0")
    created_at: datetime
    updated_at: datetime


class GoalFields(BaseModel):
    employee_id: str
    review_cycle_id: str
    owner_manager_id: str | None = None
    title: str = Field(min_length=1, max_length=240)
    description: str
    effective_from: date
    effective_to: date | None = None
    due_date: date
    status: str = "active"

    @model_validator(mode="after")
    def validate_goal(self):
        if self.status not in {"draft", "active", "on_track", "at_risk", "completed", "cancelled"}:
            raise ValueError("Invalid goal status")
        if self.due_date < self.effective_from:
            raise ValueError("Goal due date cannot be before its effective date")
        if self.effective_to and self.effective_to < self.effective_from:
            raise ValueError("Goal effective_to cannot be before effective_from")
        return self


class GoalCreate(GoalFields):
    key_results: list[KeyResultInput] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_weights(self):
        weights = [result.weight for result in self.key_results]
        if any(weight is not None for weight in weights):
            if any(weight is None for weight in weights) or sum(weights, Decimal("0")) != Decimal("100"):
                raise ValueError("Key result weights must all be set and sum to 100")
        return self


class GoalUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=240)
    description: str | None = None
    owner_manager_id: str | None = None
    effective_to: date | None = None
    due_date: date | None = None
    status: str | None = None


class GoalResponse(BaseModel):
    id: str
    employee_id: str
    employee_name: str
    review_cycle_id: str
    review_cycle_name: str
    owner_manager_id: str | None
    title: str
    description: str
    effective_from: date
    effective_to: date | None
    due_date: date
    status: str
    progress: Decimal
    key_results: list[KeyResultResponse]
    created_at: datetime
    updated_at: datetime


class PaginatedGoals(BaseModel):
    items: list[GoalResponse]
    total: int
    page: int
    page_size: int
