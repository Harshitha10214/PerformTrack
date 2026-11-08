"""Create the initial PerformTrack schema without modifying existing data.

Revision ID: 20261106_01
Revises:
Create Date: 2026-11-06
"""
from alembic import op
from sqlalchemy import text

from app.models import Base

revision = "20261106_01"
down_revision = None
branch_labels = None
depends_on = None

_ENTITY_TABLES = (
    "employees",
    "managers",
    "review_cycles",
    "goals",
    "key_results",
    "checkins",
    "competencies",
    "feedback",
    "reviews",
    "development_plans",
)

_BRIDGE_TABLES = (
    ("employee_competencies", "Employee", "employee_id"),
    ("goal_competencies", "Goal", "goal_id"),
    ("checkin_key_results", "CheckIn", "checkin_id"),
    ("feedback_competencies", "Feedback", "feedback_id"),
    ("review_competencies", "Review", "review_id"),
    ("development_plan_goals", "DevelopmentPlan", "development_plan_id"),
    ("development_plan_competencies", "DevelopmentPlan", "development_plan_id"),
)


def upgrade() -> None:
    Base.metadata.create_all(bind=op.get_bind(), checkfirst=True)

    op.execute(
        text(
            """
            CREATE OR REPLACE FUNCTION performtrack_prevent_id_change()
            RETURNS trigger
            LANGUAGE plpgsql
            AS $$
            BEGIN
                IF NEW.id IS DISTINCT FROM OLD.id THEN
                    RAISE EXCEPTION 'Primary key IDs are immutable for table %', TG_TABLE_NAME
                        USING ERRCODE = 'check_violation';
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
            CREATE OR REPLACE FUNCTION performtrack_prevent_history_change()
            RETURNS trigger
            LANGUAGE plpgsql
            AS $$
            BEGIN
                RAISE EXCEPTION 'Audit history rows are immutable'
                    USING ERRCODE = 'check_violation';
            END;
            $$;
            """
        )
    )
    op.execute(
        text(
            """
            CREATE OR REPLACE FUNCTION performtrack_record_entity_history()
            RETURNS trigger
            LANGUAGE plpgsql
            AS $$
            DECLARE
                entity_label text;
                entity_id text;
                old_row jsonb;
                new_row jsonb;
                history_action text;
            BEGIN
                CASE TG_TABLE_NAME
                    WHEN 'employees' THEN entity_label := 'Employee';
                    WHEN 'managers' THEN entity_label := 'Manager';
                    WHEN 'review_cycles' THEN entity_label := 'ReviewCycle';
                    WHEN 'goals' THEN entity_label := 'Goal';
                    WHEN 'key_results' THEN entity_label := 'KeyResult';
                    WHEN 'checkins' THEN entity_label := 'CheckIn';
                    WHEN 'competencies' THEN entity_label := 'Competency';
                    WHEN 'feedback' THEN entity_label := 'Feedback';
                    WHEN 'reviews' THEN entity_label := 'Review';
                    WHEN 'development_plans' THEN entity_label := 'DevelopmentPlan';
                    ELSE RAISE EXCEPTION 'Unsupported history table %', TG_TABLE_NAME;
                END CASE;

                IF TG_OP = 'INSERT' THEN
                    new_row := to_jsonb(NEW);
                    entity_id := NEW.id;
                    history_action := 'INSERT';
                ELSIF TG_OP = 'UPDATE' THEN
                    old_row := to_jsonb(OLD);
                    new_row := to_jsonb(NEW);
                    entity_id := NEW.id;
                    history_action := 'UPDATE';
                ELSE
                    old_row := to_jsonb(OLD);
                    entity_id := OLD.id;
                    history_action := 'DELETE';
                END IF;

                INSERT INTO entity_history
                    (event_id, entity_type, entity_id, actor_id, actor_employee_id,
                     action, before_data, after_data)
                VALUES
                    (gen_random_uuid()::text, entity_label, entity_id,
                     coalesce(nullif(current_setting('performtrack.actor_employee_id', true), ''), 'SYSTEM'),
                     nullif(current_setting('performtrack.actor_employee_id', true), ''),
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
            CREATE OR REPLACE FUNCTION performtrack_record_relationship_history()
            RETURNS trigger
            LANGUAGE plpgsql
            AS $$
            DECLARE
                target_column text;
                entity_label text;
                target_row jsonb;
                old_row jsonb;
                new_row jsonb;
                entity_id text;
                history_action text;
            BEGIN
                CASE TG_TABLE_NAME
                    WHEN 'employee_competencies' THEN target_column := 'employee_id'; entity_label := 'Employee';
                    WHEN 'goal_competencies' THEN target_column := 'goal_id'; entity_label := 'Goal';
                    WHEN 'checkin_key_results' THEN target_column := 'checkin_id'; entity_label := 'CheckIn';
                    WHEN 'feedback_competencies' THEN target_column := 'feedback_id'; entity_label := 'Feedback';
                    WHEN 'review_competencies' THEN target_column := 'review_id'; entity_label := 'Review';
                    WHEN 'development_plan_goals' THEN target_column := 'development_plan_id'; entity_label := 'DevelopmentPlan';
                    WHEN 'development_plan_competencies' THEN target_column := 'development_plan_id'; entity_label := 'DevelopmentPlan';
                    ELSE RAISE EXCEPTION 'Unsupported relationship table %', TG_TABLE_NAME;
                END CASE;

                IF TG_OP = 'INSERT' THEN
                    new_row := to_jsonb(NEW);
                    target_row := new_row;
                    history_action := 'RELATIONSHIP_INSERTED';
                ELSIF TG_OP = 'UPDATE' THEN
                    old_row := to_jsonb(OLD);
                    new_row := to_jsonb(NEW);
                    target_row := new_row;
                    history_action := 'RELATIONSHIP_UPDATED';
                ELSE
                    old_row := to_jsonb(OLD);
                    target_row := old_row;
                    history_action := 'RELATIONSHIP_DELETED';
                END IF;
                entity_id := target_row ->> target_column;

                INSERT INTO entity_history
                    (event_id, entity_type, entity_id, actor_id, actor_employee_id,
                     action, before_data, after_data)
                VALUES
                    (gen_random_uuid()::text, entity_label, entity_id,
                     coalesce(nullif(current_setting('performtrack.actor_employee_id', true), ''), 'SYSTEM'),
                     nullif(current_setting('performtrack.actor_employee_id', true), ''),
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

    for table_name in _ENTITY_TABLES:
        op.execute(
            text(
                f"""
                CREATE TRIGGER {table_name}_id_immutable
                BEFORE UPDATE OF id ON {table_name}
                FOR EACH ROW EXECUTE FUNCTION performtrack_prevent_id_change();
                """
            )
        )
        op.execute(
            text(
                f"""
                CREATE TRIGGER {table_name}_history
                AFTER INSERT OR UPDATE OR DELETE ON {table_name}
                FOR EACH ROW EXECUTE FUNCTION performtrack_record_entity_history();
                """
            )
        )

    for table_name, _, _ in _BRIDGE_TABLES:
        op.execute(
            text(
                f"""
                CREATE TRIGGER {table_name}_history
                AFTER INSERT OR UPDATE OR DELETE ON {table_name}
                FOR EACH ROW EXECUTE FUNCTION performtrack_record_relationship_history();
                """
            )
        )

    op.execute(
        text(
            """
            CREATE TRIGGER entity_history_immutable
            BEFORE UPDATE OR DELETE ON entity_history
            FOR EACH ROW EXECUTE FUNCTION performtrack_prevent_history_change();
            """
        )
    )
    op.execute(
        text(
            """
            CREATE TRIGGER entity_history_no_truncate
            BEFORE TRUNCATE ON entity_history
            FOR EACH STATEMENT EXECUTE FUNCTION performtrack_prevent_history_change();
            """
        )
    )


def downgrade() -> None:
    raise RuntimeError(
        "This initial schema migration is intentionally irreversible to protect existing data. "
        "Create a reviewed forward migration for schema changes."
    )
