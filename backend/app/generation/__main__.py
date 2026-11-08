from __future__ import annotations

import argparse
from pathlib import Path

from sqlalchemy import text

from app.core.config import settings
from app.database import engine
from app.generation.export import dataset_checksum, export_dataset
from app.generation.generator import available_scales, generate_dataset
from app.generation.persistence import persist_dataset
from app.generation.prepare import prepare_against_database
from app.generation.validation import validate_dataset
from app.models.ids import ID_GENERATION_SEED


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate PerformTrack baseline data.")
    parser.add_argument("--scale", choices=available_scales(), default="starter")
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="Output directory for CSV, JSON, SQL, and separate anomaly ground truth.",
    )
    parser.add_argument(
        "--load-db",
        action="store_true",
        help="Append baseline rows to the configured PostgreSQL database.",
    )
    parser.add_argument(
        "--prepare-from-db",
        action="store_true",
        help="Read existing rows and prepare a merged export without changing PostgreSQL.",
    )
    parser.add_argument(
        "--confirm-full-load",
        action="store_true",
        help="Explicitly approve insert-only loading of the full baseline.",
    )
    args = parser.parse_args()

    if args.load_db and args.prepare_from_db:
        parser.error("--load-db and --prepare-from-db cannot be used together")
    if args.prepare_from_db and args.scale != "full":
        parser.error("--prepare-from-db is intended for the full-scale baseline")
    if args.confirm_full_load and (not args.load_db or args.scale != "full"):
        parser.error("--confirm-full-load requires --scale full and --load-db")
    if args.load_db and args.scale == "full" and not args.confirm_full_load:
        parser.error(
            "full-scale loading is approval-gated; pass --confirm-full-load to approve inserts"
        )

    dataset = generate_dataset(available_scales()[args.scale], seed=ID_GENERATION_SEED)
    preparation_report = None
    if args.prepare_from_db or (args.load_db and args.scale == "full"):
        dataset, preparation_report = prepare_against_database(dataset)
    if args.load_db:
        with engine.connect() as connection:
            database_name = connection.execute(text("SELECT current_database()")).scalar_one()
        if database_name != "performtrack_db" or settings.postgres_db != "performtrack_db":
            raise RuntimeError(
                "Refusing to load synthetic records: active database is not performtrack_db."
            )
    validation = validate_dataset(dataset)
    output_dir = args.output_dir or Path("generated") / args.scale
    export_result = export_dataset(dataset, output_dir, preparation_report)
    if args.load_db:
        inserted = persist_dataset(dataset)
        print(f"Database: {database_name}")
        print(f"Inserted rows: {sum(inserted.values())}")
        print(f"Already present rows: {sum(validation['tables'].values()) - sum(inserted.values())}")

    print(f"Scale: {dataset.scale.name}; seed: {dataset.seed}")
    print(f"Dataset SHA-256: {dataset_checksum(dataset)}")
    print(f"Validated rows: {validation['total_rows']}")
    print(f"Export: {export_result['output_dir']}")


if __name__ == "__main__":
    main()
