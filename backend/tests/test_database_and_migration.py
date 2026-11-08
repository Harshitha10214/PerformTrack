import os
import re
import subprocess
import sys
from pathlib import Path

from sqlalchemy import text

from app.core.config import settings
from app.database import engine


BACKEND_DIR = Path(__file__).resolve().parents[1]


def test_database_connection_executes_select_one() -> None:
    with engine.connect() as connection:
        assert connection.execute(text("SELECT 1")).scalar_one() == 1


def test_alembic_online_environment_can_connect_without_applying_migration() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "current"],
        cwd=BACKEND_DIR,
        env=os.environ.copy(),
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, "Alembic online connection check failed"
    output = result.stdout + result.stderr
    if settings.postgres_password:
        assert settings.postgres_password not in output


def test_alembic_offline_sql_has_create_only_schema_and_audit_triggers() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "--sql", "head"],
        cwd=BACKEND_DIR,
        env=os.environ.copy(),
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, "offline Alembic SQL generation failed"
    generated_sql = result.stdout
    if settings.postgres_password:
        assert settings.postgres_password not in generated_sql
    assert generated_sql.upper().count("CREATE TABLE") >= 21
    assert generated_sql.upper().count("CREATE TRIGGER") == 31
    assert "performtrack_record_entity_history" in generated_sql
    assert "performtrack_record_evidence_history" in generated_sql
    assert "CREATE TRIGGER evidence_history" in generated_sql
    assert "performtrack_record_relationship_history" in generated_sql
    assert "performtrack_prevent_history_change" in generated_sql
    assert "performtrack_prevent_id_change" in generated_sql
    assert "DELETE" in generated_sql
    assert re.search(
        r"(?im)^\s*(DROP\s+TABLE|DROP\s+SEQUENCE|TRUNCATE\s+(?:TABLE\s+)?[A-Z_])",
        generated_sql,
    ) is None
