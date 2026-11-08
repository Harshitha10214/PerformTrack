from decimal import Decimal

import pytest

from app.services.goal_progress import (
    KeyResultProgressInput,
    calculate_goal_progress,
    calculate_key_result_progress,
)


def test_key_result_progress_normal_and_boundary_values() -> None:
    assert calculate_key_result_progress(25, 100) == Decimal("25.00")
    assert calculate_key_result_progress(100, 100) == Decimal("100.00")
    assert calculate_key_result_progress(150, 100) == Decimal("100.00")
    assert calculate_key_result_progress(None, 100) == Decimal("0")


def test_goal_progress_averages_unweighted_and_incomplete_results() -> None:
    key_results = [
        KeyResultProgressInput(target_value=100, actual_value=50),
        KeyResultProgressInput(target_value=20, actual_value=None),
        KeyResultProgressInput(target_value=10, actual_value=20),
    ]
    assert calculate_goal_progress(key_results) == Decimal("50.00")


def test_goal_progress_uses_validated_weights() -> None:
    key_results = [
        KeyResultProgressInput(target_value=100, actual_value=50, weight=75),
        KeyResultProgressInput(target_value=100, actual_value=100, weight=25),
    ]
    assert calculate_goal_progress(key_results) == Decimal("62.50")


@pytest.mark.parametrize(
    "key_results",
    [
        [],
        [
            KeyResultProgressInput(target_value=10, actual_value=5, weight=50),
            KeyResultProgressInput(target_value=10, actual_value=5, weight=25),
        ],
        [
            KeyResultProgressInput(target_value=10, actual_value=5, weight=100),
            KeyResultProgressInput(target_value=10, actual_value=5),
        ],
        [
            KeyResultProgressInput(target_value=10, actual_value=5, weight=101),
        ],
        [
            KeyResultProgressInput(target_value=10, actual_value=5, weight=-1),
        ],
    ],
)
def test_invalid_goal_weight_inputs_are_rejected(key_results) -> None:
    with pytest.raises(ValueError):
        calculate_goal_progress(key_results)


@pytest.mark.parametrize(
    ("actual", "target"),
    [(1, 0), (1, -1), (-1, 10), (float("nan"), 10), (float("inf"), 10)],
)
def test_invalid_key_result_values_are_rejected(actual, target) -> None:
    with pytest.raises(ValueError):
        calculate_key_result_progress(actual, target)
