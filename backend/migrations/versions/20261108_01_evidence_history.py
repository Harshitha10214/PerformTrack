"""Include Evidence records in the existing immutable entity history.

Revision ID: 20261108_01
Revises: 20261106_01
Create Date: 2026-11-08
"""
from alembic import op
from sqlalchemy import text

revision = "20261108_01"
down_revision = "20261106_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("ck_entity_history_type", "entity_history", type_="check")
    op.create_check_constraint(
        "ck_entity_history_type",
        "entity_history",
        "entity_type IN ('Employee', 'Manager', 'ReviewCycle', 'Goal', 'KeyResult', "
        "'CheckIn', 'Competency', 'Feedback', 'Review', 'DevelopmentPlan', 'Evidence')",
    )
    op.execute(
        text(
            """
            CREATE OR REPLACE FUNCTION performtrack_record_evidence_history()
            RETURNS trigger
            LANGUAGE plpgsql
            AS $$
            DECLARE
                old_row jsonb;
                new_row jsonb;
                history_action text;
                actor_employee text;
            BEGIN
                IF TG_OP = 'INSERT' THEN
                    new_row := to_jsonb(NEW);
                    history_action := 'INSERT';
                ELSIF TG_OP = 'UPDATE' THEN
                    old_row := to_jsonb(OLD);
                    new_row := to_jsonb(NEW);
                    history_action := 'UPDATE';
                ELSE
                    old_row := to_jsonb(OLD);
                    history_action := 'DELETE';
                END IF;

                actor_employee := nullif(current_setting('performtrack.actor_employee_id', true), '');
                INSERT INTO entity_history
                    (event_id, entity_type, entity_id, actor_id, actor_employee_id,
                     action, before_data, after_data)
                VALUES
                    (gen_random_uuid()::text, 'Evidence',
                     CASE WHEN TG_OP = 'DELETE' THEN OLD.id ELSE NEW.id END,
                     coalesce(actor_employee, 'SYSTEM'), actor_employee,
                     history_action, old_row, new_row);

                IF TG_OP = 'DELETE' THEN
                    RETURN OLD;
                END IF;
                RETURN NEW;
            END;
            $$;
            """
        )
    )
    op.execute(
        text(
            """
            CREATE TRIGGER evidence_id_immutable
            BEFORE UPDATE OF id ON evidence
            FOR EACH ROW EXECUTE FUNCTION performtrack_prevent_id_change();
            """
        )
    )
    op.execute(
        text(
            """
            CREATE TRIGGER evidence_history
            AFTER INSERT OR UPDATE OR DELETE ON evidence
            FOR EACH ROW EXECUTE FUNCTION performtrack_record_evidence_history();
            """
        )
    )


def downgrade() -> None:
    raise RuntimeError(
        "Evidence history is retained permanently; this migration is intentionally irreversible."
    )
