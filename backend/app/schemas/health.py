from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = Field(..., example="ok")
    app: str = Field(..., example="PerformTrack")
    version: str = Field(..., example="0.1.0")
    database: str = Field(..., example="configured")
