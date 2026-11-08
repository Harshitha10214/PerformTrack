from pathlib import Path

from app.models import Base


def test_audit_schema_has_immutable_history_and_entity_identity() -> None:
    history = Base.metadata.tables["entity_history"]
    assert "event_id" in history.c
    assert "entity_id" in history.c
    assert "entity_type" in history.c
    assert "action" in history.c
    assert "actor_id" in history.c
    assert "actor_employee_id" in history.c
    assert "recorded_at" in history.c
    assert "before_data" in history.c
    assert "after_data" in history.c


def test_initial_migration_tracks_core_deletes_and_protects_history_rows() -> None:
    migration_path = (
        Path(__file__).resolve().parents[1]
        / "migrations"
        / "versions"
        / "20261106_01_initial_schema.py"
    )
    migration = migration_path.read_text(encoding="utf-8")
    assert "AFTER INSERT OR UPDATE OR DELETE ON {table_name}" in migration
    assert "BEFORE UPDATE OR DELETE ON entity_history" in migration
    assert "BEFORE TRUNCATE ON entity_history" in migration
    assert "history_action := 'DELETE'" in migration
    assert "before_data, after_data" in migration
