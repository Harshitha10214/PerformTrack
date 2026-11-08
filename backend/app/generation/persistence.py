from __future__ import annotations

from typing import Any

from sqlalchemy import select, text, tuple_
from sqlalchemy.orm import Session, sessionmaker

from app.database import SessionLocal
from app.generation.types import EXPORT_TABLES, GeneratedDataset
from app.models import Base


def _existing_matches(existing: dict[str, Any], generated: dict[str, Any]) -> bool:
    return all(existing.get(column) == value for column, value in generated.items())


def persist_dataset(dataset: GeneratedDataset, session_factory: sessionmaker[Session] = SessionLocal) -> dict[str, int]:
    """Append missing baseline rows; reject conflicting IDs and never update/delete records."""
    inserted: dict[str, int] = {}
    with session_factory.begin() as session:
        session.execute(text("SET CONSTRAINTS ALL DEFERRED"))
        for table_name in EXPORT_TABLES:
            table = Base.metadata.tables[table_name]
            primary_key = tuple(column.name for column in table.primary_key.columns)
            rows = dataset.tables[table_name]
            existing_by_key: dict[tuple[Any, ...], dict[str, Any]] = {}
            for offset in range(0, len(rows), 500):
                batch = rows[offset : offset + 500]
                keys = [tuple(row[column] for column in primary_key) for row in batch]
                if len(primary_key) == 1:
                    condition = table.c[primary_key[0]].in_([key[0] for key in keys])
                else:
                    condition = tuple_(*(table.c[column] for column in primary_key)).in_(keys)
                for existing in session.execute(select(table).where(condition)).mappings():
                    record = dict(existing)
                    key = tuple(record[column] for column in primary_key)
                    existing_by_key[key] = record

            new_rows: list[dict[str, Any]] = []
            for row in rows:
                key = tuple(row[column] for column in primary_key)
                existing = existing_by_key.get(key)
                if existing is None:
                    new_rows.append(row)
                elif _existing_matches(dict(existing), row):
                    continue
                else:
                    raise ValueError(
                        f"existing {table_name} row conflicts with generated baseline ID {key}; "
                        "no existing records were changed"
                    )
            if new_rows:
                session.execute(table.insert(), new_rows)
            inserted[table_name] = len(new_rows)
    return inserted
