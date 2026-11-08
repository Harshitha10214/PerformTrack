from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Sequence


_ZERO = Decimal("0")
_ONE_HUNDRED = Decimal("100")
_TWO_PLACES = Decimal("0.01")


@dataclass(frozen=True)
class KeyResultProgressInput:
    target_value: Decimal | int | float | str
    actual_value: Decimal | int | float | str | None
    weight: Decimal | int | float | str | None = None


def _decimal(value: Decimal | int | float | str, name: str) -> Decimal:
    try:
        result = value if isinstance(value, Decimal) else Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise ValueError(f"{name} must be a finite number") from None
    if not result.is_finite():
        raise ValueError(f"{name} must be a finite number")
    return result


def calculate_key_result_progress(
    actual_value: Decimal | int | float | str | None,
    target_value: Decimal | int | float | str,
) -> Decimal:
    """Return key-result progress as a percentage, capped at 100."""
    target = _decimal(target_value, "target_value")
    if target <= 0:
        raise ValueError("target_value must be greater than zero")
    if actual_value is None:
        return _ZERO
    actual = _decimal(actual_value, "actual_value")
    if actual < 0:
        raise ValueError("actual_value cannot be negative")
    return min(actual * _ONE_HUNDRED / target, _ONE_HUNDRED).quantize(
        _TWO_PLACES, rounding=ROUND_HALF_UP
    )


def calculate_goal_progress(key_results: Sequence[KeyResultProgressInput]) -> Decimal:
    """Calculate goal progress from its key results; incomplete results count as zero."""
    if not key_results:
        raise ValueError("at least one key result is required to calculate goal progress")

    progresses = [
        calculate_key_result_progress(item.actual_value, item.target_value)
        for item in key_results
    ]
    weights = [None if item.weight is None else _decimal(item.weight, "weight") for item in key_results]

    if all(weight is None for weight in weights):
        return (sum(progresses, _ZERO) / Decimal(len(progresses))).quantize(
            _TWO_PLACES, rounding=ROUND_HALF_UP
        )
    if any(weight is None for weight in weights):
        raise ValueError("either provide weights for every key result or for none")

    concrete_weights = [weight for weight in weights if weight is not None]
    if any(weight < 0 or weight > _ONE_HUNDRED for weight in concrete_weights):
        raise ValueError("weights must be between 0 and 100")
    if sum(concrete_weights, _ZERO) != _ONE_HUNDRED:
        raise ValueError("key result weights must sum to 100")

    weighted_progress = sum(
        (progress * weight for progress, weight in zip(progresses, concrete_weights, strict=True)),
        _ZERO,
    ) / _ONE_HUNDRED
    return weighted_progress.quantize(_TWO_PLACES, rounding=ROUND_HALF_UP)
