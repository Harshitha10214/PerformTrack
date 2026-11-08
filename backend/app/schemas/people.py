from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator


class EmployeeFields(BaseModel):
    email: EmailStr
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    job_title: str = Field(min_length=1, max_length=160)
    department: str = Field(min_length=1, max_length=160)
    hire_date: date
    effective_from: date
    effective_to: date | None = None
    status: str = "active"
    manager_id: str | None = None

    @model_validator(mode="after")
    def validate_dates_and_status(self):
        if self.status not in {"active", "leave", "inactive", "terminated"}:
            raise ValueError("Invalid employee status")
        if self.effective_to and self.effective_to < self.effective_from:
            raise ValueError("effective_to cannot be before effective_from")
        return self


class EmployeeCreate(EmployeeFields):
    pass


class EmployeeUpdate(BaseModel):
    email: EmailStr | None = None
    first_name: str | None = Field(default=None, min_length=1, max_length=100)
    last_name: str | None = Field(default=None, min_length=1, max_length=100)
    job_title: str | None = Field(default=None, min_length=1, max_length=160)
    department: str | None = Field(default=None, min_length=1, max_length=160)
    hire_date: date | None = None
    effective_from: date | None = None
    effective_to: date | None = None
    status: str | None = None
    manager_id: str | None = None


class EmployeeResponse(EmployeeFields):
    model_config = ConfigDict(from_attributes=True)
    id: str
    created_at: datetime
    updated_at: datetime


class ManagerCreate(BaseModel):
    employee_id: str
    effective_from: date
    effective_to: date | None = None
    status: str = "active"

    @model_validator(mode="after")
    def validate_dates_and_status(self):
        if self.status not in {"active", "inactive"}:
            raise ValueError("Invalid manager status")
        if self.effective_to and self.effective_to < self.effective_from:
            raise ValueError("effective_to cannot be before effective_from")
        return self


class ManagerUpdate(BaseModel):
    effective_from: date | None = None
    effective_to: date | None = None
    status: str | None = None


class ManagerResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    employee_id: str
    employee_name: str
    email: str
    job_title: str
    department: str
    report_count: int
    effective_from: date
    effective_to: date | None
    status: str
    created_at: datetime
    updated_at: datetime


class PaginatedEmployees(BaseModel):
    items: list[EmployeeResponse]
    total: int
    page: int
    page_size: int


class PaginatedManagers(BaseModel):
    items: list[ManagerResponse]
    total: int
    page: int
    page_size: int
