from sqlalchemy import text
from sqlalchemy.orm import Session


def set_audit_actor(session: Session, employee_id: str | None) -> None:
    """Set the actor recorded by audit triggers for the current transaction."""
    session.execute(
        text("SELECT set_config('performtrack.actor_employee_id', :employee_id, true)"),
        {"employee_id": employee_id or ""},
    )
