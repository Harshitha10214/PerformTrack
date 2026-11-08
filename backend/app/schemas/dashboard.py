from typing import Literal

from pydantic import BaseModel


class DashboardOverview(BaseModel):
    total_employees: int
    total_managers: int
    total_goals: int
    completed_goals: int
    average_goal_progress: float | None
    active_review_cycles: int
    pending_reviews: int


class GoalProgressBand(BaseModel):
    label: str
    count: int


class DepartmentPerformance(BaseModel):
    department: str
    employee_count: int
    goal_count: int
    completed_goals: int
    average_goal_progress: float | None


class RecentCheckIn(BaseModel):
    id: str
    employee_name: str
    manager_name: str | None
    checkin_date: str
    status: str


class DataQualityCheck(BaseModel):
    label: str
    affected_records: int
    passed: bool


class DataQualitySummary(BaseModel):
    status: Literal["healthy", "attention_required"]
    checks_passed: int
    checks_total: int
    checks: list[DataQualityCheck]


class DashboardAnalyticsResponse(BaseModel):
    overview: DashboardOverview
    goal_progress_distribution: list[GoalProgressBand]
    department_performance: list[DepartmentPerformance]
    recent_check_ins: list[RecentCheckIn]
    data_quality: DataQualitySummary
