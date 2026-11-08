from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import sys

import pytest

from app.generation import __main__ as generation_cli
from app.generation.anomalies import (
    build_anomaly_fixtures,
    build_ground_truth,
    detect_anomaly,
)
from app.generation.export import _export_contents, dataset_checksum, export_dataset
from app.generation.generator import generate_dataset
from app.generation.merge import merge_existing_rows
from app.generation.types import EXPORT_TABLES, FULL_SCALE, STARTER_SCALE
from app.generation.validation import validate_dataset
from app.models import Base
from app.services.goal_progress import KeyResultProgressInput, calculate_goal_progress


def test_starter_generation_counts_and_validation() -> None:
    dataset = generate_dataset()

    assert len(dataset.tables["employees"]) == 30
    assert len(dataset.tables["managers"]) == 5
    assert len(dataset.tables["goals"]) == 100
    assert len(dataset.tables["checkins"]) == 200
    assert len(dataset.tables["key_results"]) == 200
    result = validate_dataset(dataset)
    assert result["total_rows"] == sum(map(len, dataset.tables.values()))
    assert result["duplicate_primary_keys"] == 0
    assert result["goal_progress_count"] == 100
    assert set(dataset.tables) == set(EXPORT_TABLES)


def test_ids_are_unique_and_follow_required_formats() -> None:
    dataset = generate_dataset()
    id_patterns = {
        "employees": r"EMP-\d{6}\Z",
        "managers": r"MGR-\d{6}\Z",
        "review_cycles": r"CYCLE-\d{4}-H[12]\Z",
        "goals": r"GOAL-EMP-\d{6}-\d{3}\Z",
        "key_results": r"KR-GOAL-EMP-\d{6}-\d{3}-\d{2}\Z",
        "checkins": r"CHK-\d{6}\Z",
        "competencies": r"COMP-\d{6}\Z",
        "feedback": r"FB-\d{6}\Z",
        "reviews": r"REV-\d{4}-\d{6}\Z",
        "development_plans": r"DEV-\d{6}\Z",
        "evidence": r"EVD-\d{6}\Z",
    }
    for table_name, pattern in id_patterns.items():
        ids = [row["id"] for row in dataset.tables[table_name]]
        assert len(ids) == len(set(ids))
        assert all(re.fullmatch(pattern, record_id) for record_id in ids)


def test_generated_foreign_keys_and_manager_relationships_are_valid() -> None:
    assert validate_dataset(generate_dataset())["foreign_key_columns_validated"] > 0


def test_goal_progress_is_derived_from_weighted_key_results() -> None:
    dataset = generate_dataset()
    key_results_by_goal: dict[str, list[dict]] = {}
    for result in dataset.tables["key_results"]:
        key_results_by_goal.setdefault(result["goal_id"], []).append(result)
    for goal_id, results in key_results_by_goal.items():
        calculated = calculate_goal_progress(
            [
                KeyResultProgressInput(
                    target_value=result["target_value"],
                    actual_value=result["current_value"],
                    weight=result["weight"],
                )
                for result in results
            ]
        )
        assert dataset.goal_progress[goal_id] == calculated
        assert calculated <= 100


def test_anomaly_fixtures_are_isolated_and_match_ground_truth() -> None:
    dataset = generate_dataset()
    fixtures = build_anomaly_fixtures(dataset)
    truth = build_ground_truth(fixtures)
    owner_mismatch = next(row for row in fixtures if row["issue_type"] == "goal_owner_mismatch")
    owner_goal = next(
        goal for goal in dataset.tables["goals"] if goal["id"] == owner_mismatch["record_id"]
    )
    owner_manager = next(
        manager
        for manager in dataset.tables["managers"]
        if manager["id"] == owner_goal["owner_manager_id"]
    )

    assert len(fixtures) == len(truth) == 5
    assert owner_mismatch["observed"]["owner_employee_id"] == owner_manager["employee_id"]
    assert owner_mismatch["observed"]["employee_id"] != owner_manager["employee_id"]
    assert {row["issue_type"] for row in fixtures} == {
        "goal_owner_mismatch",
        "unjustified_progress_over_100",
        "invalid_reviewer_relationship",
        "silent_edit_in_closed_cycle",
        "untraceable_feedback",
    }
    assert all(detect_anomaly(fixture) == expected["expected_decision"] for fixture, expected in zip(fixtures, truth, strict=True))
    assert all(set(row) == {"issue_type", "ground_truth_label", "expected_decision", "record_id"} for row in truth)
    assert not any("ground_truth" in table_name for table_name in dataset.tables)


def test_repeated_generation_has_identical_data_and_exports() -> None:
    first = generate_dataset()
    second = generate_dataset()

    assert first.tables == second.tables
    assert first.goal_progress == second.goal_progress
    assert dataset_checksum(first) == dataset_checksum(second)
    first_exports = _export_contents(first)
    second_exports = _export_contents(second)
    assert first_exports == second_exports
    assert hashlib.sha256(first_exports["dataset.json"]).digest() == hashlib.sha256(
        second_exports["dataset.json"]
    ).digest()


def test_full_scale_generation_is_reproducible_and_valid_without_writing_files() -> None:
    first = generate_dataset(FULL_SCALE)
    second = generate_dataset(FULL_SCALE)

    assert first.seed == second.seed == 20261022
    assert first.tables == second.tables
    assert first.goal_progress == second.goal_progress
    assert dataset_checksum(first) == dataset_checksum(second)

    validation = validate_dataset(first)
    assert validation["duplicate_primary_keys"] == 0
    assert validation["foreign_key_columns_validated"] == 292500
    assert validation["goal_progress_count"] == 10000
    assert validation["total_rows"] == 130126

    first_fixtures = build_anomaly_fixtures(first)
    second_fixtures = build_anomaly_fixtures(second)
    first_truth = build_ground_truth(first_fixtures)
    second_truth = build_ground_truth(second_fixtures)
    assert first_fixtures == second_fixtures
    assert first_truth == second_truth
    assert len(first_fixtures) == len(first_truth) == 5
    assert all(
        detect_anomaly(fixture) == truth["expected_decision"]
        for fixture, truth in zip(first_fixtures, first_truth, strict=True)
    )


def test_export_refuses_to_replace_different_existing_files(tmp_path) -> None:
    output_dir = tmp_path / "starter"
    dataset = generate_dataset()
    export_dataset(dataset, output_dir)
    assert export_dataset(dataset, output_dir)["already_identical"] is True
    (output_dir / "employees.json").write_text("not the generated data", encoding="utf-8")
    with pytest.raises(FileExistsError):
        export_dataset(dataset, output_dir)


def test_exports_keep_ground_truth_out_of_normal_data_and_seed_sql() -> None:
    dataset = generate_dataset()
    files = _export_contents(dataset)
    assert b"ground_truth" not in files["dataset.json"]
    assert b"ground_truth" not in files["seed.sql"]
    assert b"ground_truth_label" in files["ground_truth.csv"]
    assert b"ground_truth_label" in files["ground_truth.json"]
    assert b"issue_type" in files["anomaly_fixtures.json"]
    assert json.loads(files["validation_report.json"])["goal_progress_count"] == 100
    assert re.search(rb"(?im)^\s*(DROP|TRUNCATE|UPDATE|DELETE)\b", files["seed.sql"]) is None
    assert files["seed.sql"].index(b'INSERT INTO "reviews"') < files["seed.sql"].index(
        b'INSERT INTO "evidence"'
    )
    for table_name in EXPORT_TABLES:
        assert len(json.loads(files[f"{table_name}.json"])) == len(dataset.tables[table_name])
        assert len(list(csv.DictReader(io.StringIO(files[f"{table_name}.csv"].decode())))) == len(
            dataset.tables[table_name]
        )


def test_full_scale_merge_preserves_starter_rows_and_validates_exact_counts() -> None:
    starter = generate_dataset(STARTER_SCALE)
    full = generate_dataset(FULL_SCALE)
    merged = merge_existing_rows(full, starter.tables)

    for table_name in EXPORT_TABLES:
        primary_key = tuple(
            column.name
            for column in Base.metadata.tables[table_name].primary_key.columns
        )
        merged_by_key = {
            tuple(row[column] for column in primary_key): row
            for row in merged.tables[table_name]
        }
        assert len(merged.tables[table_name]) == len(full.tables[table_name])
        for existing in starter.tables[table_name]:
            key = tuple(existing[column] for column in primary_key)
            assert merged_by_key[key] == existing

    assert len(merged.tables["employees"]) == 3000
    assert len(merged.tables["managers"]) == 500
    assert len(merged.tables["goals"]) == 10000
    assert len(merged.tables["checkins"]) == 20000
    assert validate_dataset(merged)["total_rows"] == validate_dataset(full)["total_rows"]


def test_starter_records_match_full_scale_for_every_overlapping_primary_key() -> None:
    starter = generate_dataset(STARTER_SCALE, seed=20261022)
    full = generate_dataset(FULL_SCALE, seed=20261022)

    assert starter.seed == full.seed == 20261022
    assert full.tables["employees"][:30] == starter.tables["employees"]
    assert full.tables["managers"][:5] == starter.tables["managers"]

    for table_name in EXPORT_TABLES:
        primary_key = tuple(
            column.name
            for column in Base.metadata.tables[table_name].primary_key.columns
        )
        starter_by_key = {
            tuple(row[column] for column in primary_key): row
            for row in starter.tables[table_name]
        }
        full_by_key = {
            tuple(row[column] for column in primary_key): row
            for row in full.tables[table_name]
        }
        assert starter_by_key.keys() <= full_by_key.keys(), table_name
        assert all(
            full_by_key[key] == row for key, row in starter_by_key.items()
        ), table_name

    assert validate_dataset(starter)["duplicate_primary_keys"] == 0
    assert validate_dataset(full)["duplicate_primary_keys"] == 0


def test_full_scale_database_load_requires_explicit_approval(monkeypatch) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        ["performtrack-generation", "--scale", "full", "--load-db"],
    )

    with pytest.raises(SystemExit) as error:
        generation_cli.main()

    assert error.value.code == 2
