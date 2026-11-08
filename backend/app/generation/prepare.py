from __future__ import annotations

from typing import Any

from sqlalchemy import select, text

from app.core.config import settings
from app.database import engine
from app.generation.merge import merge_existing_rows
from app.generation.types import EXPORT_TABLES, GeneratedDataset
from app.generation.validation import validate_dataset
from app.models import Base


def prepare_against_database(generated: GeneratedDataset) -> tuple[GeneratedDataset, dict[str, Any]]:
    """Prepare a merged full snapshot from a consistent, read-only database view."""
    existing_rows: dict[str, list[dict[str, Any]]] = {}
    with engine.connect().execution_options(isolation_level="REPEATABLE READ") as connection:
        with connection.begin():
            connection.execute(text("SET TRANSACTION READ ONLY"))
            database_name = connection.execute(text("SELECT current_database()")).scalar_one()
            if database_name != "performtrack_db" or settings.postgres_db != "performtrack_db":
                raise RuntimeError(
                    "Refusing to prepare the PerformTrack baseline: active database is not performtrack_db."
                )
            for table_name in EXPORT_TABLES:
                table = Base.metadata.tables[table_name]
                existing_rows[table_name] = [
                    dict(row)
                    for row in connection.execute(select(table)).mappings()
                ]

    merged = merge_existing_rows(generated, existing_rows)
    if merged.scale != generated.scale or merged.seed != generated.seed:
        raise ValueError("merged dataset metadata differs from generated dataset")

    row_counts = {
        table_name: len(merged.tables[table_name])
        for table_name in EXPORT_TABLES
    }
    generated_counts = {
        table_name: len(generated.tables[table_name])
        for table_name in EXPORT_TABLES
    }
    mismatched_counts = {
        table_name: (row_counts[table_name], generated_counts[table_name])
        for table_name in EXPORT_TABLES
        if row_counts[table_name] != generated_counts[table_name]
    }
    if mismatched_counts:
        raise ValueError(
            "existing database rows do not form a subset of the full baseline counts: "
            f"{mismatched_counts}"
        )

    preserved_rows = {
        table_name: len(existing_rows[table_name])
        for table_name in EXPORT_TABLES
    }
    conflicting_existing_rows: dict[str, int] = {}
    for table_name in EXPORT_TABLES:
        table = Base.metadata.tables[table_name]
        primary_key = tuple(column.name for column in table.primary_key.columns)
        generated_by_key = {
            tuple(row[column] for column in primary_key): row
            for row in generated.tables[table_name]
        }
        conflicts = 0
        for row in existing_rows[table_name]:
            key = tuple(row[column] for column in primary_key)
            generated_row = generated_by_key.get(key)
            if generated_row is not None and any(
                row.get(column) != value
                for column, value in generated_row.items()
            ):
                conflicts += 1
        if conflicts:
            conflicting_existing_rows[table_name] = conflicts

    validation = validate_dataset(merged)
    report = {
        "mode": "read_only_merge",
        "database": database_name,
        "seed": merged.seed,
        "scale": merged.scale.name,
        "existing_rows_preserved": preserved_rows,
        "existing_rows_with_generated_value_differences": conflicting_existing_rows,
        "rows_that_would_be_inserted": {
            table_name: generated_counts[table_name] - preserved_rows[table_name]
            for table_name in EXPORT_TABLES
        },
        "validation": validation,
    }
    return merged, report
