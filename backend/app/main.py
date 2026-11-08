from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.routes import (
    checkins_router,
    dashboard_router,
    data_exports_router,
    development_plans_router,
    audit_history_router,
    evidence_router,
    feedback_router,
    goals_router,
    health_router,
    people_router,
    reviews_router,
)

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Employee performance and goal management system API",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router, prefix="/api/v1")
app.include_router(dashboard_router, prefix="/api/v1")
app.include_router(data_exports_router, prefix="/api/v1")
app.include_router(people_router, prefix="/api/v1")
app.include_router(goals_router, prefix="/api/v1")
app.include_router(checkins_router, prefix="/api/v1")
app.include_router(feedback_router, prefix="/api/v1")
app.include_router(development_plans_router, prefix="/api/v1")
app.include_router(audit_history_router, prefix="/api/v1")
app.include_router(evidence_router, prefix="/api/v1")
app.include_router(reviews_router, prefix="/api/v1")


@app.get("/")
async def root() -> dict[str, str]:
    return {"message": "PerformTrack API is running."}
