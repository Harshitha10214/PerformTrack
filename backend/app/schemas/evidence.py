from datetime import datetime
from typing import Literal

from pydantic import BaseModel


EvidenceTargetType = Literal["key_result", "checkin", "feedback", "review"]


class EvidenceResponse(BaseModel):
    id: str
    employee_id: str
    employee_name: str
    target_type: EvidenceTargetType
    linked_record_id: str
    linked_record_label: str
    file_name: str
    uri: str
    media_type: str
    size_bytes: int | None
    sha256: str | None
    description: str
    downloadable: bool
    created_at: datetime
    updated_at: datetime


class PaginatedEvidence(BaseModel):
    items: list[EvidenceResponse]
    total: int
    page: int
    page_size: int
