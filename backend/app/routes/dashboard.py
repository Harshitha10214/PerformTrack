from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.dashboard import DashboardAnalyticsResponse
from app.services.dashboard import get_dashboard_analytics

router = APIRouter(tags=["dashboard"])


@router.get("/dashboard/analytics", response_model=DashboardAnalyticsResponse)
def dashboard_analytics(db: Session = Depends(get_db)) -> DashboardAnalyticsResponse:
    try:
        return get_dashboard_analytics(db)
    except SQLAlchemyError:
        raise HTTPException(
            status_code=503,
            detail="Dashboard analytics are unavailable because the database query failed.",
        ) from None
