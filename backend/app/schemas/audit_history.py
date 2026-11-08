from datetime import datetime
from typing import Literal

from pydantic import BaseModel


AuditEntityType = Literal[
    "Employee",
    "Manager",
    "ReviewCycle",
    "Goal",
    "KeyResult",
    "CheckIn",
    "Competency",
    "Feedback",
    "Review",
    "DevelopmentPlan",
    "Evidence",
]

AuditOperation = Literal[
    "INSERT",
    "UPDATE",
    "DELETE",
    "RELATIONSHIP_INSERTED",
    "RELATIONSHIP_UPDATED",
    "RELATIONSHIP_DELETED",
]


class AuditHistoryResponse(BaseModel):
    event_id: str
    entity_type: AuditEntityType
    entity_id: str
    actor_id: str
    actor_employee_id: str | None
    actor_name: str | None
    actor_attribution_available: bool
    operation: AuditOperation
    recorded_at: datetime
    before_data: dict | None
    after_data: dict | None


class PaginatedAuditHistory(BaseModel):
    items: list[AuditHistoryResponse]
    total: int
    page: int
    page_size: int
