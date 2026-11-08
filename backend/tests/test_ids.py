import pytest

from app.models.ids import (
    ID_GENERATION_SEED,
    DeterministicIdAllocator,
)


def allocate_sample_ids() -> list[str]:
    allocator = DeterministicIdAllocator()
    employee_id = allocator.employee_id()
    goal_id = allocator.goal_id(employee_id)
    return [
        employee_id,
        allocator.manager_id(),
        allocator.review_cycle_id(2026, "H1"),
        goal_id,
        allocator.key_result_id(goal_id),
        allocator.checkin_id(),
        allocator.competency_id(),
        allocator.feedback_id(),
        allocator.review_id(2026),
        allocator.development_plan_id(),
    ]


def test_seeded_ids_are_reproducible_and_match_required_formats() -> None:
    assert ID_GENERATION_SEED == 20261022
    expected = [
        "EMP-000001",
        "MGR-000001",
        "CYCLE-2026-H1",
        "GOAL-EMP-000001-001",
        "KR-GOAL-EMP-000001-001-01",
        "CHK-000001",
        "COMP-000001",
        "FB-000001",
        "REV-2026-000001",
        "DEV-000001",
    ]
    assert allocate_sample_ids() == expected
    assert allocate_sample_ids() == expected


def test_entity_counters_are_unique_and_parent_scoped() -> None:
    allocator = DeterministicIdAllocator()
    employee_1 = allocator.employee_id()
    employee_2 = allocator.employee_id()
    goal_1 = allocator.goal_id(employee_1)
    goal_2 = allocator.goal_id(employee_1)
    other_employee_goal = allocator.goal_id(employee_2)

    assert [goal_1, goal_2, other_employee_goal] == [
        "GOAL-EMP-000001-001",
        "GOAL-EMP-000001-002",
        "GOAL-EMP-000002-001",
    ]
    assert allocator.key_result_id(goal_1) == "KR-GOAL-EMP-000001-001-01"
    assert allocator.key_result_id(goal_1) == "KR-GOAL-EMP-000001-001-02"
    assert allocator.key_result_id(goal_2) == "KR-GOAL-EMP-000001-002-01"
    assert allocator.review_id(2026) == "REV-2026-000001"
    assert allocator.review_id(2027) == "REV-2027-000001"


def test_cycle_ids_cannot_be_allocated_twice_and_seed_is_fixed() -> None:
    allocator = DeterministicIdAllocator()
    assert allocator.review_cycle_id(2026, "H2") == "CYCLE-2026-H2"
    with pytest.raises(ValueError, match="already allocated"):
        allocator.review_cycle_id(2026, "H2")
    with pytest.raises(ValueError, match="fixed"):
        DeterministicIdAllocator(seed=1)
