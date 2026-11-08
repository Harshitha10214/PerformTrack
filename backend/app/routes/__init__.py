from app.routes.dashboard import router as dashboard_router
from app.routes.data_exports import router as data_exports_router
from app.routes.audit_history import router as audit_history_router
from app.routes.evidence import router as evidence_router
from app.routes.health import router as health_router
from app.routes.people import router as people_router
from app.routes.goals import router as goals_router
from app.routes.checkins import router as checkins_router
from app.routes.feedback import router as feedback_router
from app.routes.development_plans import router as development_plans_router
from app.routes.reviews import router as reviews_router

__all__ = [
    "dashboard_router",
    "data_exports_router",
    "audit_history_router",
    "evidence_router",
    "health_router",
    "people_router",
    "goals_router",
    "checkins_router",
    "feedback_router",
    "development_plans_router",
    "reviews_router",
]
