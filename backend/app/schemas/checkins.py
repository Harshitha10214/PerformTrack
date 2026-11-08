from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class CheckInCreate(BaseModel):
    employee_id: str
    manager_id: str
    review_cycle_id: str | None = None
    checkin_date: date
    notes: str
    status: str = "scheduled"
    key_result_ids: list[str] = Field(default_factory=list)


class CheckInUpdate(BaseModel):
    checkin_date: date | None = None
    notes: str | None = None
    status: str | None = None
    key_result_ids: list[str] | None = None


class CheckInResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    employee_id: str
    employee_name: str
    manager_id: str | None
    manager_name: str | None
    review_cycle_id: str | None
    checkin_date: date
    notes: str
    status: str
    key_result_ids: list[str]
    created_at: datetime
    updated_at: datetime


class PaginatedCheckIns(BaseModel):
    items: list[CheckInResponse]
    total: int
    page: int
    page_size: int
