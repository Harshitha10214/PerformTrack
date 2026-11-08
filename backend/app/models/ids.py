import re
from threading import Lock

ID_GENERATION_SEED = 20261022

_EMPLOYEE_ID = re.compile(r"^EMP-\d{6}$")
_GOAL_ID = re.compile(r"^GOAL-(EMP-\d{6})-(\d{3})$")


def _format_counter(counter: int, width: int) -> str:
    if not 1 <= counter <= 10**width - 1:
        raise ValueError(f"counter must be between 1 and {10**width - 1}")
    return f"{counter:0{width}d}"


def format_cycle_id(year: int, half: str) -> str:
    if not 1 <= year <= 9999 or half not in {"H1", "H2"}:
        raise ValueError("review cycle requires a four-digit year and H1 or H2")
    return f"CYCLE-{year:04d}-{half}"


def format_goal_id(employee_id: str, counter: int) -> str:
    if not _EMPLOYEE_ID.fullmatch(employee_id):
        raise ValueError("employee_id must match EMP-000001")
    return f"GOAL-{employee_id}-{_format_counter(counter, 3)}"


def format_key_result_id(goal_id: str, counter: int) -> str:
    if not _GOAL_ID.fullmatch(goal_id):
        raise ValueError("goal_id must match GOAL-EMP-000001-001")
    return f"KR-{goal_id}-{_format_counter(counter, 2)}"


def format_review_id(year: int, counter: int) -> str:
    if not 1 <= year <= 9999:
        raise ValueError("review year must be four digits")
    return f"REV-{year:04d}-{_format_counter(counter, 6)}"


class DeterministicIdAllocator:
    """Allocate reproducible, per-entity IDs for a fixed seed and call order."""

    def __init__(self, seed: int = ID_GENERATION_SEED) -> None:
        if seed != ID_GENERATION_SEED:
            raise ValueError(f"PerformTrack ID generation seed is fixed at {ID_GENERATION_SEED}")
        self.seed = seed
        self._counters: dict[tuple[str, str, str], int] = {}
        self._cycles: set[str] = set()
        self._lock = Lock()

    def _next(self, entity: str, scope: str = "", width: int = 6) -> int:
        key = (str(self.seed), entity, scope)
        with self._lock:
            counter = self._counters.get(key, 0) + 1
            _format_counter(counter, width)
            self._counters[key] = counter
            return counter

    def employee_id(self) -> str:
        return f"EMP-{_format_counter(self._next('employee'), 6)}"

    def manager_id(self) -> str:
        return f"MGR-{_format_counter(self._next('manager'), 6)}"

    def review_cycle_id(self, year: int, half: str) -> str:
        cycle_id = format_cycle_id(year, half)
        with self._lock:
            if cycle_id in self._cycles:
                raise ValueError(f"review cycle ID already allocated: {cycle_id}")
            self._cycles.add(cycle_id)
        return cycle_id

    def goal_id(self, employee_id: str) -> str:
        if not _EMPLOYEE_ID.fullmatch(employee_id):
            raise ValueError("employee_id must match EMP-000001")
        counter = self._next("goal", employee_id, width=3)
        return format_goal_id(employee_id, counter)

    def key_result_id(self, goal_id: str) -> str:
        if not _GOAL_ID.fullmatch(goal_id):
            raise ValueError("goal_id must match GOAL-EMP-000001-001")
        counter = self._next("key_result", goal_id, width=2)
        return format_key_result_id(goal_id, counter)

    def checkin_id(self) -> str:
        return f"CHK-{_format_counter(self._next('checkin'), 6)}"

    def competency_id(self) -> str:
        return f"COMP-{_format_counter(self._next('competency'), 6)}"

    def feedback_id(self) -> str:
        return f"FB-{_format_counter(self._next('feedback'), 6)}"

    def review_id(self, year: int) -> str:
        if not 1 <= year <= 9999:
            raise ValueError("review year must be four digits")
        counter = self._next("review", str(year))
        return format_review_id(year, counter)

    def development_plan_id(self) -> str:
        return f"DEV-{_format_counter(self._next('development_plan'), 6)}"

    def evidence_id(self) -> str:
        return f"EVD-{_format_counter(self._next('evidence'), 6)}"
