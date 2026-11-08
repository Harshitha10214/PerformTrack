from __future__ import annotations

import hashlib
import random
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from typing import Any

from app.models.ids import DeterministicIdAllocator, ID_GENERATION_SEED
from app.services.goal_progress import KeyResultProgressInput, calculate_goal_progress
from app.generation.types import (
    AS_OF_DATE,
    BRIDGE_TABLES,
    FIXED_TIMESTAMP,
    FULL_SCALE,
    STARTER_SCALE,
    DatasetScale,
    GeneratedDataset,
)

_COMPETENCIES = (
    ("Communication", "Collaboration"),
    ("Strategic Thinking", "Leadership"),
    ("Execution", "Delivery"),
    ("Customer Focus", "Impact"),
    ("Data Literacy", "Technical"),
    ("Problem Solving", "Technical"),
    ("Adaptability", "Growth"),
    ("Mentoring", "Leadership"),
    ("Decision Making", "Leadership"),
    ("Ownership", "Delivery"),
    ("Planning", "Delivery"),
    ("Innovation", "Growth"),
    ("Quality", "Technical"),
    ("Influence", "Collaboration"),
    ("Learning Agility", "Growth"),
    ("Accountability", "Delivery"),
    ("Empathy", "Collaboration"),
    ("Product Thinking", "Impact"),
    ("Risk Management", "Leadership"),
    ("Operational Excellence", "Delivery"),
)
_FIRST_NAMES = (
    "Aarav", "Aditi", "Ananya", "Arjun", "Diya", "Ishaan", "Kabir", "Meera",
    "Neha", "Rohan", "Sana", "Vihaan", "Zoya", "Kavya", "Reyansh", "Tara",
)
_LAST_NAMES = (
    "Sharma", "Patel", "Reddy", "Gupta", "Nair", "Mehta", "Rao", "Kapoor",
    "Iyer", "Joshi", "Khan", "Das", "Malhotra", "Singh", "Menon", "Verma",
)
_DEPARTMENTS = ("Engineering", "Product", "People", "Sales", "Operations")
_TITLES = ("Analyst", "Engineer", "Designer", "Specialist", "Product Manager", "Lead")
_GOAL_TEMPLATES = (
    ("Improve delivery predictability", "Increase planned work delivered on time."),
    ("Improve customer outcomes", "Resolve customer needs with measurable quality."),
    ("Strengthen team capability", "Share knowledge and improve team practices."),
    ("Increase operational reliability", "Reduce avoidable operational interruptions."),
    ("Advance strategic execution", "Deliver agreed milestones for the strategic roadmap."),
)
_FEEDBACK = (
    "Communicates progress clearly and follows through on commitments.",
    "Collaborates across teams and incorporates constructive feedback.",
    "Shows strong ownership while continuing to develop prioritization skills.",
    "Consistently contributes thoughtful analysis to team decisions.",
)


def available_scales() -> dict[str, DatasetScale]:
    return {"starter": STARTER_SCALE, "full": FULL_SCALE}


class SyntheticDataGenerator:
    def __init__(self, scale: DatasetScale = STARTER_SCALE, seed: int = ID_GENERATION_SEED):
        if seed != ID_GENERATION_SEED:
            raise ValueError(f"PerformTrack generation seed is fixed at {ID_GENERATION_SEED}")
        if min(scale.employees, scale.managers, scale.goals, scale.checkins) < 1:
            raise ValueError("all scale counts must be positive")
        if scale.managers >= scale.employees:
            raise ValueError("manager count must be less than employee count")
        self.scale = scale
        self.seed = seed
        self.random = random.Random(seed)
        self._random_states: dict[str, object] = {}
        self.ids = DeterministicIdAllocator(seed)
        self.dataset = GeneratedDataset(scale=scale, seed=seed)

    def generate(self) -> GeneratedDataset:
        self._generate_people()
        self._generate_hierarchy()
        self._generate_review_cycles()
        self._generate_goals()
        self._generate_key_results()
        self._generate_checkins()
        self._generate_evidence()
        self._generate_competencies()
        self._generate_feedback()
        self._generate_reviews()
        self._generate_additional_checkin_evidence()
        self._generate_development_plans()
        self._generate_approvals()
        return self.dataset

    def _generate_people(self) -> None:
        employee_ids = [self.ids.employee_id() for _ in range(self.scale.employees)]
        manager_ids = [self.ids.manager_id() for _ in range(self.scale.managers)]
        for index, employee_id in enumerate(employee_ids):
            if index < STARTER_SCALE.managers:
                manager_id = None
            elif index < STARTER_SCALE.employees or self.scale.managers == STARTER_SCALE.managers:
                manager_id = manager_ids[index % STARTER_SCALE.managers]
            else:
                manager_index = STARTER_SCALE.managers + (
                    index - STARTER_SCALE.employees
                ) % (self.scale.managers - STARTER_SCALE.managers)
                manager_id = manager_ids[manager_index]
            hire_date = date(self.random.randint(2015, 2024), self.random.randint(1, 12), 1)
            self.dataset.append(
                "employees",
                id=employee_id,
                manager_id=manager_id,
                email=f"{employee_id.lower()}@performtrack.example",
                first_name=self.random.choice(_FIRST_NAMES),
                last_name=f"{self.random.choice(_LAST_NAMES)}{index:04d}",
                job_title=self.random.choice(_TITLES),
                department=self.random.choice(_DEPARTMENTS),
                hire_date=hire_date,
                effective_from=hire_date,
                effective_to=None,
                status=self.random.choices(
                    ("active", "leave", "inactive", "terminated"), (88, 5, 5, 2), k=1
                )[0],
            )
            self.dataset.employee_managers[employee_id] = manager_id
            self._checkpoint_random_state(
                "people", index, min(STARTER_SCALE.employees, self.scale.employees)
            )

        for index, manager_id in enumerate(manager_ids):
            self.dataset.append(
                "managers",
                id=manager_id,
                employee_id=employee_ids[index],
                effective_from=date(2020, 1, 1),
                effective_to=None,
                status="active",
            )
        self._restore_random_state("people")
        self.employee_ids = employee_ids
        self.manager_ids = manager_ids
        starter_manager_count = min(STARTER_SCALE.managers, len(manager_ids))
        self.manager_for_employee = {
            employee_id: self.dataset.employee_managers[employee_id]
            or manager_ids[(index + 1) % starter_manager_count]
            for index, employee_id in enumerate(employee_ids)
        }

    def _generate_hierarchy(self) -> None:
        managers_by_id = {row["id"]: row for row in self.dataset.tables["managers"]}
        employees_by_id = {row["id"]: row for row in self.dataset.tables["employees"]}
        for employee_id, manager_id in self.dataset.employee_managers.items():
            if manager_id is not None:
                manager = managers_by_id[manager_id]
                employee = employees_by_id[employee_id]
                if manager["employee_id"] == employee_id:
                    raise ValueError("an employee cannot report to their own manager profile")

    def _generate_review_cycles(self) -> None:
        for year in (2024, 2025, 2026):
            for half in ("H1", "H2"):
                cycle_id = self.ids.review_cycle_id(year, half)
                starts_on = date(year, 1 if half == "H1" else 7, 1)
                ends_on = date(year, 6, 30) if half == "H1" else date(year, 12, 31)
                status = "open" if (year, half) == (2026, "H2") else "closed"
                row = self.dataset.append(
                    "review_cycles",
                    id=cycle_id,
                    year=year,
                    half=half,
                    name=f"{year} {half} Performance Cycle",
                    starts_on=starts_on,
                    ends_on=ends_on,
                    status=status,
                )
                self.dataset.cycles_by_id[cycle_id] = row
        self.cycle_ids = sorted(self.dataset.cycles_by_id)
        self.open_cycle_id = "CYCLE-2026-H2"

    def _generate_goals(self) -> None:
        starter_employee_count = min(STARTER_SCALE.employees, len(self.employee_ids))
        for index in range(self.scale.goals):
            employee_count = (
                starter_employee_count
                if index < STARTER_SCALE.goals
                else len(self.employee_ids)
            )
            employee_id = self.employee_ids[index % employee_count]
            cycle_id = self.cycle_ids[index % len(self.cycle_ids)]
            cycle = self.dataset.cycles_by_id[cycle_id]
            title, description = _GOAL_TEMPLATES[index % len(_GOAL_TEMPLATES)]
            goal_id = self.ids.goal_id(employee_id)
            self.dataset.append(
                "goals",
                id=goal_id,
                employee_id=employee_id,
                review_cycle_id=cycle_id,
                owner_manager_id=self.manager_for_employee[employee_id],
                title=f"{title} ({index + 1:05d})",
                description=description,
                effective_from=cycle["starts_on"],
                effective_to=None,
                due_date=cycle["ends_on"],
                status="draft",
            )

    def _generate_key_results(self) -> None:
        goals = self.dataset.tables["goals"]
        keys_by_goal: dict[str, list[KeyResultProgressInput]] = {}
        for goal_index, goal in enumerate(goals):
            goal_key_results: list[KeyResultProgressInput] = []
            for result_index in range(2):
                target = Decimal(self.random.randint(8, 120))
                incomplete = (goal_index + result_index) % 7 == 0
                ratio = Decimal(self.random.randint(0, 100)) / Decimal(100)
                actual = None if incomplete else (target * ratio).quantize(Decimal("0.0001"))
                key_result_id = self.ids.key_result_id(goal["id"])
                cycle = self.dataset.cycles_by_id[goal["review_cycle_id"]]
                result_ratio = Decimal("0") if actual is None else actual / target
                if cycle["status"] == "closed":
                    result_status = (
                        "completed"
                        if result_ratio == 1
                        else "at_risk"
                        if result_ratio < Decimal("0.4")
                        else "on_track"
                    )
                else:
                    result_status = (
                        "active" if result_ratio < Decimal("0.4") else "on_track"
                    )
                self.dataset.append(
                    "key_results",
                    id=key_result_id,
                    goal_id=goal["id"],
                    title=f"Measure {result_index + 1} for {goal['title']}",
                    description="Track measurable progress toward the goal outcome.",
                    unit=("items", "percent", "days")[result_index % 3],
                    target_value=target,
                    current_value=actual,
                    weight=Decimal("50.00"),
                    effective_from=goal["effective_from"],
                    effective_to=None,
                    due_date=goal["due_date"],
                    status=result_status,
                )
                goal_key_results.append(
                    KeyResultProgressInput(target_value=target, actual_value=actual, weight=50)
                )
            self._checkpoint_random_state(
                "key_results",
                goal_index,
                min(STARTER_SCALE.goals, len(goals)),
            )
            progress = calculate_goal_progress(goal_key_results)
            self.dataset.goal_progress[goal["id"]] = progress
            cycle = self.dataset.cycles_by_id[goal["review_cycle_id"]]
            if progress == Decimal("100.00"):
                goal["status"] = "completed"
            elif cycle["status"] == "closed" and progress < Decimal("40.00"):
                goal["status"] = "at_risk"
            elif cycle["status"] == "closed":
                goal["status"] = "completed" if progress >= Decimal("80.00") else "on_track"
            else:
                goal["status"] = "active" if progress < Decimal("40.00") else "on_track"
        self._restore_random_state("key_results")

    def _generate_checkins(self) -> None:
        goals = self.dataset.tables["goals"]
        starter_goal_count = min(STARTER_SCALE.goals, len(goals))
        key_results_by_goal: dict[str, list[str]] = {}
        for result in self.dataset.tables["key_results"]:
            key_results_by_goal.setdefault(result["goal_id"], []).append(result["id"])
        for index in range(self.scale.checkins):
            goal_count = (
                starter_goal_count
                if index < STARTER_SCALE.checkins
                else len(goals)
            )
            goal = goals[index % goal_count]
            cycle = self.dataset.cycles_by_id[goal["review_cycle_id"]]
            latest = min(cycle["ends_on"], AS_OF_DATE)
            span = max((latest - cycle["starts_on"]).days, 0)
            checkin_date = cycle["starts_on"] + timedelta(days=self.random.randint(0, span))
            checkin_id = self.ids.checkin_id()
            employee_id = goal["employee_id"]
            self.dataset.append(
                "checkins",
                id=checkin_id,
                employee_id=employee_id,
                manager_id=self.manager_for_employee[employee_id],
                review_cycle_id=goal["review_cycle_id"],
                checkin_date=checkin_date,
                notes="Discussed progress, blockers, and next actions.",
                status=self.random.choices(("completed", "missed"), (96, 4), k=1)[0],
            )
            self.dataset.tables["checkin_key_results"].append(
                {
                    "checkin_id": checkin_id,
                    "key_result_id": key_results_by_goal[goal["id"]][index % 2],
                }
            )
            self._checkpoint_random_state(
                "checkins",
                index,
                min(STARTER_SCALE.checkins, self.scale.checkins),
            )
        self._restore_random_state("checkins")

    def _generate_evidence(self) -> None:
        checks = self.dataset.tables["checkins"]
        self._generate_checkin_evidence(checks[:STARTER_SCALE.checkins:5])

    def _generate_additional_checkin_evidence(self) -> None:
        self._generate_checkin_evidence(
            self.dataset.tables["checkins"][STARTER_SCALE.checkins::5]
        )

    def _generate_checkin_evidence(self, checks: list[dict[str, Any]]) -> None:
        key_results = self.dataset.tables["key_results"]
        key_result_by_id = {row["id"]: row for row in key_results}
        checkin_links = self.dataset.tables["checkin_key_results"]
        links_by_checkin = {row["checkin_id"]: row["key_result_id"] for row in checkin_links}
        for checkin in checks:
            evidence_id = self.ids.evidence_id()
            key_result_id = links_by_checkin[checkin["id"]]
            uri = f"synthetic-evidence://{evidence_id}/check-in-summary.txt"
            digest = hashlib.sha256(uri.encode("utf-8")).hexdigest()
            self.dataset.append(
                "evidence",
                id=evidence_id,
                employee_id=checkin["employee_id"],
                key_result_id=key_result_id,
                checkin_id=None,
                feedback_id=None,
                review_id=None,
                uri=uri,
                media_type="text/plain",
                sha256=digest,
                description=f"Progress note for {key_result_by_id[key_result_id]['id']}",
            )

    def _generate_competencies(self) -> None:
        competency_ids: list[str] = []
        for name, category in _COMPETENCIES:
            competency_id = self.ids.competency_id()
            competency_ids.append(competency_id)
            self.dataset.append(
                "competencies",
                id=competency_id,
                name=name,
                category=category,
                description=f"{name} competency used for performance development.",
                effective_from=date(2024, 1, 1),
                effective_to=None,
                status="active",
            )

        for employee_index, employee_id in enumerate(self.employee_ids):
            selected = {
                (employee_index * 3 + offset * 7) % len(competency_ids)
                for offset in range(3)
            }
            for index in sorted(selected):
                self.dataset.tables["employee_competencies"].append(
                    {
                        "employee_id": employee_id,
                        "competency_id": competency_ids[index],
                        "effective_from": date(2024, 1, 1),
                        "effective_to": None,
                        "proficiency": Decimal(self.random.randint(2, 5)),
                        "created_at": FIXED_TIMESTAMP,
                    }
                )
            self._checkpoint_random_state(
                "employee_competencies",
                employee_index,
                min(STARTER_SCALE.employees, self.scale.employees),
            )

        for goal_index, goal in enumerate(self.dataset.tables["goals"]):
            self.dataset.tables["goal_competencies"].append(
                {
                    "goal_id": goal["id"],
                    "competency_id": competency_ids[goal_index % len(competency_ids)],
                }
            )
        self._restore_random_state("employee_competencies")

    def _generate_feedback(self) -> None:
        competency_ids = [row["id"] for row in self.dataset.tables["competencies"]]
        for index in range(self.scale.employees * 2):
            starter_feedback_count = STARTER_SCALE.employees * 2
            employee_count = (
                min(STARTER_SCALE.employees, self.scale.employees)
                if index < starter_feedback_count
                else self.scale.employees
            )
            subject_id = self.employee_ids[index % employee_count]
            author_id = self.employee_ids[
                (index + 1 + index // employee_count) % employee_count
            ]
            if author_id == subject_id:
                author_id = self.employee_ids[(index + 2) % employee_count]
            feedback_id = self.ids.feedback_id()
            cycle_id = self.cycle_ids[index % len(self.cycle_ids)]
            self.dataset.append(
                "feedback",
                id=feedback_id,
                author_employee_id=author_id,
                subject_employee_id=subject_id,
                review_cycle_id=cycle_id,
                content=_FEEDBACK[index % len(_FEEDBACK)],
                visibility=("private", "manager", "review_cycle")[index % 3],
                status="submitted",
            )
            self.dataset.tables["feedback_competencies"].append(
                {
                    "feedback_id": feedback_id,
                    "competency_id": competency_ids[index % len(competency_ids)],
                }
            )

    def _generate_reviews(self) -> None:
        competency_ids = [row["id"] for row in self.dataset.tables["competencies"]]
        cycle = self.dataset.cycles_by_id[self.open_cycle_id]
        for index, employee_id in enumerate(self.employee_ids):
            reviewer_id = self.manager_for_employee[employee_id]
            status = "approved" if index % 4 == 0 else "submitted"
            review_id = self.ids.review_id(cycle["year"])
            self.dataset.append(
                "reviews",
                id=review_id,
                year=cycle["year"],
                employee_id=employee_id,
                reviewer_manager_id=reviewer_id,
                review_cycle_id=self.open_cycle_id,
                summary="Performance review summarizing outcomes, collaboration, and growth.",
                rating=Decimal(self.random.randint(3, 5)),
                effective_from=cycle["starts_on"],
                effective_to=None,
                status=status,
            )
            self.dataset.tables["review_competencies"].append(
                {
                    "review_id": review_id,
                    "competency_id": competency_ids[index % len(competency_ids)],
                }
            )
            if index % 5 == 0:
                evidence_id = self.ids.evidence_id()
                uri = f"synthetic-evidence://{evidence_id}/review-summary.txt"
                self.dataset.append(
                    "evidence",
                    id=evidence_id,
                    employee_id=employee_id,
                    key_result_id=None,
                    checkin_id=None,
                    feedback_id=None,
                    review_id=review_id,
                    uri=uri,
                    media_type="text/plain",
                    sha256=hashlib.sha256(uri.encode("utf-8")).hexdigest(),
                    description="Supporting summary for the performance review.",
                )

    def _generate_development_plans(self) -> None:
        competency_ids = [row["id"] for row in self.dataset.tables["competencies"]]
        goals_by_employee: dict[str, list[dict[str, Any]]] = {}
        for goal in self.dataset.tables["goals"]:
            goals_by_employee.setdefault(goal["employee_id"], []).append(goal)
        starter_goals_by_employee: dict[str, list[dict[str, Any]]] = {}
        for goal in self.dataset.tables["goals"][:STARTER_SCALE.goals]:
            starter_goals_by_employee.setdefault(goal["employee_id"], []).append(goal)
        for index, employee_id in enumerate(self.employee_ids):
            plan_id = self.ids.development_plan_id()
            self.dataset.append(
                "development_plans",
                id=plan_id,
                employee_id=employee_id,
                owner_manager_id=self.manager_for_employee[employee_id],
                review_cycle_id=self.open_cycle_id,
                title="Individual growth and development plan",
                description="Build targeted skills through practice, feedback, and mentoring.",
                effective_from=self.dataset.cycles_by_id[self.open_cycle_id]["starts_on"],
                effective_to=None,
                status="active",
            )
            employee_goals = (
                starter_goals_by_employee.get(employee_id, [])
                if index < STARTER_SCALE.employees
                else goals_by_employee.get(employee_id, [])
            )
            if employee_goals:
                goal = employee_goals[index % len(employee_goals)]
                self.dataset.tables["development_plan_goals"].append(
                    {"development_plan_id": plan_id, "goal_id": goal["id"]}
                )
            self.dataset.tables["development_plan_competencies"].append(
                {
                    "development_plan_id": plan_id,
                    "competency_id": competency_ids[index % len(competency_ids)],
                }
            )

    def _generate_approvals(self) -> None:
        for index, review in enumerate(self.dataset.tables["reviews"]):
            approved = review["status"] == "approved"
            self.dataset.tables["review_approvals"].append(
                {
                    "review_id": review["id"],
                    "approver_manager_id": review["reviewer_manager_id"],
                    "status": "approved" if approved else "pending",
                    "decided_at": datetime(2026, 11, 5, tzinfo=timezone.utc) if approved else None,
                    "comments": "Approved following review." if approved else None,
                    "created_at": FIXED_TIMESTAMP,
                    "updated_at": FIXED_TIMESTAMP,
                }
            )
        for plan in self.dataset.tables["development_plans"]:
            self.dataset.tables["development_plan_approvals"].append(
                {
                    "development_plan_id": plan["id"],
                    "approver_manager_id": plan["owner_manager_id"],
                    "status": "approved",
                    "decided_at": datetime(2026, 11, 5, tzinfo=timezone.utc),
                    "comments": "Development plan approved.",
                    "created_at": FIXED_TIMESTAMP,
                    "updated_at": FIXED_TIMESTAMP,
                }
            )

    def _checkpoint_random_state(self, stage: str, index: int, prefix_size: int) -> None:
        if index + 1 == prefix_size:
            self._random_states[stage] = self.random.getstate()

    def _restore_random_state(self, stage: str) -> None:
        state = self._random_states.get(stage)
        if state is not None:
            self.random.setstate(state)


def generate_dataset(scale: DatasetScale = STARTER_SCALE, seed: int = ID_GENERATION_SEED) -> GeneratedDataset:
    return SyntheticDataGenerator(scale=scale, seed=seed).generate()
