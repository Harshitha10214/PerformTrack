from collections import defaultdict
from decimal import Decimal
from typing import Any

from sqlalchemy import and_, exists, func, or_, select
from sqlalchemy.orm import Session, aliased

from app.models import (
    CheckIn,
    DevelopmentPlan,
    Employee,
    Goal,
    KeyResult,
    Manager,
    Review,
    ReviewCycle,
)
from app.models.entities import checkin_key_results
from app.schemas.dashboard import (
    DashboardAnalyticsResponse,
    DashboardOverview,
    DataQualityCheck,
    DataQualitySummary,
    DepartmentPerformance,
    GoalProgressBand,
    RecentCheckIn,
)
from app.services.goal_progress import KeyResultProgressInput, calculate_goal_progress


_DISTRIBUTION_BANDS = (
    ("0–24%", Decimal("0"), Decimal("25")),
    ("25–49%", Decimal("25"), Decimal("50")),
    ("50–74%", Decimal("50"), Decimal("75")),
    ("75–99%", Decimal("75"), Decimal("100")),
    ("100%", Decimal("100"), Decimal("101")),
)


def _count(session: Session, statement: Any) -> int:
    return int(session.scalar(statement) or 0)


def _orphaned_relationship_count(session: Session) -> int:
    manager_for_checkin = aliased(Manager)
    review_manager = aliased(Manager)

    checks = (
        select(func.count(Goal.id))
        .select_from(Goal)
        .outerjoin(Employee, Goal.employee_id == Employee.id)
        .outerjoin(ReviewCycle, Goal.review_cycle_id == ReviewCycle.id)
        .where(or_(Employee.id.is_(None), ReviewCycle.id.is_(None))),
        select(func.count(KeyResult.id))
        .select_from(KeyResult)
        .outerjoin(Goal, KeyResult.goal_id == Goal.id)
        .where(Goal.id.is_(None)),
        select(func.count(CheckIn.id))
        .select_from(CheckIn)
        .outerjoin(Employee, CheckIn.employee_id == Employee.id)
        .outerjoin(manager_for_checkin, CheckIn.manager_id == manager_for_checkin.id)
        .outerjoin(ReviewCycle, CheckIn.review_cycle_id == ReviewCycle.id)
        .where(
            or_(
                Employee.id.is_(None),
                and_(CheckIn.manager_id.is_not(None), manager_for_checkin.id.is_(None)),
                and_(CheckIn.review_cycle_id.is_not(None), ReviewCycle.id.is_(None)),
            )
        ),
        select(func.count(Review.id))
        .select_from(Review)
        .outerjoin(Employee, Review.employee_id == Employee.id)
        .outerjoin(review_manager, Review.reviewer_manager_id == review_manager.id)
        .outerjoin(ReviewCycle, Review.review_cycle_id == ReviewCycle.id)
        .where(
            or_(
                Employee.id.is_(None),
                review_manager.id.is_(None),
                ReviewCycle.id.is_(None),
            )
        ),
        select(func.count(DevelopmentPlan.id))
        .select_from(DevelopmentPlan)
        .outerjoin(Employee, DevelopmentPlan.employee_id == Employee.id)
        .outerjoin(Manager, DevelopmentPlan.owner_manager_id == Manager.id)
        .where(or_(Employee.id.is_(None), Manager.id.is_(None))),
    )
    return sum(_count(session, check) for check in checks)


def get_dashboard_analytics(session: Session) -> DashboardAnalyticsResponse:
    progress_by_goal: dict[str, Decimal] = {}
    goal_rows = session.execute(
        select(
            Goal.id,
            Goal.employee_id,
            Goal.status,
            KeyResult.target_value,
            KeyResult.current_value,
            KeyResult.weight,
        )
        .select_from(Goal)
        .outerjoin(KeyResult, KeyResult.goal_id == Goal.id)
        .order_by(Goal.id, KeyResult.id)
    )
    goal_results: dict[str, list[KeyResultProgressInput]] = defaultdict(list)
    goal_employees: dict[str, str] = {}
    goal_statuses: dict[str, str] = {}
    for row in goal_rows:
        goal_id, employee_id, status, target, actual, weight = row
        goal_employees[goal_id] = employee_id
        goal_statuses[goal_id] = status
        if target is not None:
            goal_results[goal_id].append(
                KeyResultProgressInput(
                    target_value=target,
                    actual_value=actual,
                    weight=weight,
                )
            )

    for goal_id, results in goal_results.items():
        progress_by_goal[goal_id] = calculate_goal_progress(results)

    employee_departments = dict(
        session.execute(select(Employee.id, Employee.department)).all()
    )
    progress_distribution = [
        GoalProgressBand(
            label=label,
            count=sum(
                lower <= progress < upper
                for progress in progress_by_goal.values()
            ),
        )
        for label, lower, upper in _DISTRIBUTION_BANDS
    ]

    department_stats: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "employees": set(),
            "goals": 0,
            "completed": 0,
            "progress": [],
        }
    )
    for goal_id, employee_id in goal_employees.items():
        department = employee_departments.get(employee_id)
        if department is None:
            continue
        stats = department_stats[department]
        stats["employees"].add(employee_id)
        stats["goals"] += 1
        stats["completed"] += goal_statuses[goal_id] == "completed"
        if goal_id in progress_by_goal:
            stats["progress"].append(progress_by_goal[goal_id])

    department_performance = [
        DepartmentPerformance(
            department=department,
            employee_count=len(stats["employees"]),
            goal_count=stats["goals"],
            completed_goals=stats["completed"],
            average_goal_progress=(
                float(sum(stats["progress"], Decimal("0")) / len(stats["progress"]))
                if stats["progress"]
                else None
            ),
        )
        for department, stats in sorted(department_stats.items())
    ]

    manager_employee = aliased(Employee)
    checkin_rows = session.execute(
        select(
            CheckIn.id,
            Employee.first_name,
            Employee.last_name,
            manager_employee.first_name,
            manager_employee.last_name,
            CheckIn.checkin_date,
            CheckIn.status,
        )
        .select_from(CheckIn)
        .join(Employee, CheckIn.employee_id == Employee.id)
        .outerjoin(Manager, CheckIn.manager_id == Manager.id)
        .outerjoin(manager_employee, Manager.employee_id == manager_employee.id)
        .order_by(CheckIn.checkin_date.desc(), CheckIn.id.desc())
        .limit(8)
    )
    recent_check_ins = [
        RecentCheckIn(
            id=row[0],
            employee_name=f"{row[1]} {row[2]}",
            manager_name=f"{row[3]} {row[4]}" if row[3] is not None else None,
            checkin_date=row[5].isoformat(),
            status=row[6],
        )
        for row in checkin_rows
    ]

    goals_without_key_results = _count(
        session,
        select(func.count(Goal.id)).where(
            ~exists(select(KeyResult.id).where(KeyResult.goal_id == Goal.id))
        ),
    )
    checkins_without_key_results = _count(
        session,
        select(func.count(CheckIn.id)).where(
            ~exists(
                select(checkin_key_results.c.checkin_id).where(
                    checkin_key_results.c.checkin_id == CheckIn.id
                )
            )
        ),
    )
    quality_checks = [
        ("Orphaned core relationships", _orphaned_relationship_count(session)),
        ("Goals without key results", goals_without_key_results),
        ("Check-ins without linked key results", checkins_without_key_results),
    ]
    quality_check_results = [
        DataQualityCheck(
            label=label,
            affected_records=affected_records,
            passed=affected_records == 0,
        )
        for label, affected_records in quality_checks
    ]
    checks_passed = sum(check.passed for check in quality_check_results)

    average_goal_progress = (
        float(sum(progress_by_goal.values(), Decimal("0")) / len(progress_by_goal))
        if progress_by_goal
        else None
    )
    return DashboardAnalyticsResponse(
        overview=DashboardOverview(
            total_employees=_count(session, select(func.count(Employee.id))),
            total_managers=_count(session, select(func.count(Manager.id))),
            total_goals=_count(session, select(func.count(Goal.id))),
            completed_goals=_count(
                session,
                select(func.count(Goal.id)).where(Goal.status == "completed"),
            ),
            average_goal_progress=average_goal_progress,
            active_review_cycles=_count(
                session,
                select(func.count(ReviewCycle.id)).where(ReviewCycle.status == "open"),
            ),
            pending_reviews=_count(
                session,
                select(func.count(Review.id)).where(
                    Review.status.in_(("draft", "in_progress", "submitted"))
                ),
            ),
        ),
        goal_progress_distribution=progress_distribution,
        department_performance=department_performance,
        recent_check_ins=recent_check_ins,
        data_quality=DataQualitySummary(
            status=(
                "healthy"
                if checks_passed == len(quality_check_results)
                else "attention_required"
            ),
            checks_passed=checks_passed,
            checks_total=len(quality_check_results),
            checks=quality_check_results,
        ),
    )
