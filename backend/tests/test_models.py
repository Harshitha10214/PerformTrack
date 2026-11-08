from sqlalchemy import String
from sqlalchemy.orm import configure_mappers

from app.models import (
    Base,
    CheckIn,
    Competency,
    DevelopmentPlan,
    Employee,
    Feedback,
    Goal,
    KeyResult,
    Manager,
    Review,
    ReviewCycle,
)


def test_all_core_model_imports_and_string_primary_keys() -> None:
    configure_mappers()
    models = (
        Employee,
        Manager,
        ReviewCycle,
        Goal,
        KeyResult,
        CheckIn,
        Competency,
        Feedback,
        Review,
        DevelopmentPlan,
    )
    assert len(Base.metadata.tables) == 21
    for model in models:
        primary_key = model.__table__.c.id
        assert primary_key.primary_key
        assert isinstance(primary_key.type, String)
        assert primary_key.default is None
        assert primary_key.server_default is None


def test_foreign_keys_resolve_and_many_to_many_relationships_are_mapped() -> None:
    configure_mappers()
    for table in Base.metadata.tables.values():
        for foreign_key in table.foreign_keys:
            assert foreign_key.column.table in Base.metadata.tables.values()

    assert Goal.__mapper__.relationships.key_results.direction.name == "ONETOMANY"
    assert CheckIn.__mapper__.relationships.key_results.secondary.name == "checkin_key_results"
    assert Employee.__mapper__.relationships.competencies.secondary.name == "employee_competencies"
    assert Goal.__mapper__.relationships.competencies.secondary.name == "goal_competencies"
    assert Feedback.__mapper__.relationships.competencies.secondary.name == "feedback_competencies"
    assert Review.__mapper__.relationships.competencies.secondary.name == "review_competencies"
    assert DevelopmentPlan.__mapper__.relationships.goals.secondary.name == "development_plan_goals"


def test_key_result_metadata_supports_weighting_and_incomplete_progress() -> None:
    key_result = KeyResult.__table__
    assert key_result.c.current_value.nullable
    assert key_result.c.weight.nullable
    assert any("weight" in str(constraint.sqltext) for constraint in key_result.constraints if hasattr(constraint, "sqltext"))


def test_audit_history_metadata_can_reference_deleted_entity_ids() -> None:
    history = Base.metadata.tables["entity_history"]
    assert {"entity_id", "entity_type", "actor_employee_id", "action", "before_data", "after_data"} <= set(history.c.keys())
    assert not any(foreign_key.column.table is not Base.metadata.tables["employees"] for foreign_key in history.foreign_keys)
