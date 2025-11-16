"""Tests for time column validation rules."""

import pytest

from pysemantic.exceptions import NamingCollisionError
from pysemantic.modeling import Dimension, Entity, EntityType, Measure, Model
from pysemantic.validation.time_column_validation import (
    TimeColumnValidation,
    TimeColumnValidationError,
)


def _model_with(**overrides) -> Model:
    primary_key = overrides.get("primary_key", "id")
    entities = overrides.get(
        "entities",
        [Entity("customer", EntityType.PRIMARY, primary_key)],
    )

    base = {
        "name": overrides.get("name", "sales"),
        "table": overrides.get("table", "sales_table"),
        "primary_key": primary_key,
        "entities": entities,
        "dimensions": overrides.get("dimensions", []),
        "measures": overrides.get("measures", []),
        "time_columns": overrides.get("time_columns", []),
    }
    return Model(**base)


class TestTimeColumnIdentifierRules:
    """Rule 1: Time column names must be valid identifiers."""

    def test_valid_time_column_names(self):
        for name in ["created_at", "orderDate", "_processed"]:
            _model_with(time_columns=[name])

    def test_time_column_name_with_space_raises_error(self):
        with pytest.raises(TimeColumnValidationError) as exc_info:
            _model_with(time_columns=["created at"])

        assert "valid identifier" in str(exc_info.value)

    def test_time_column_name_with_symbols_raises_error(self):
        with pytest.raises(TimeColumnValidationError):
            _model_with(time_columns=["created-at"])

    def test_time_column_name_reserved_word_raises_error(self):
        with pytest.raises(TimeColumnValidationError):
            _model_with(time_columns=["select"])

    def test_time_column_name_starting_with_number_raises_error(self):
        with pytest.raises(TimeColumnValidationError):
            _model_with(time_columns=["123created"])

    def test_empty_time_column_name_raises_error(self):
        with pytest.raises(TimeColumnValidationError):
            _model_with(time_columns=[""])


class TestTimeColumnUniqueness:
    """Rule 2: No duplicate time column names."""

    def test_unique_time_columns(self):
        _model_with(time_columns=["created_at", "updated_at"])

    def test_duplicate_time_columns_raise_error(self):
        with pytest.raises(NamingCollisionError):
            _model_with(time_columns=["created_at", "created_at"])


class TestTimeColumnNameCollisions:
    """Rule 3: Time column names cannot collide with other semantic objects."""

    def test_time_column_conflicts_with_dimension(self):
        dimension = Dimension("created_at", "datetime")

        with pytest.raises(NamingCollisionError):
            _model_with(dimensions=[dimension], time_columns=["created_at"])

    def test_time_column_conflicts_with_entity(self):
        entity = Entity("created_at", EntityType.PRIMARY, "id")

        with pytest.raises(NamingCollisionError):
            _model_with(entities=[entity], time_columns=["created_at"])

    def test_time_column_conflicts_with_measure(self):
        measure = Measure("created_at", "sum", "amount")

        with pytest.raises(NamingCollisionError):
            _model_with(measures=[measure], time_columns=["created_at"])

    def test_time_column_conflicts_with_primary_key(self):
        with pytest.raises(NamingCollisionError):
            _model_with(primary_key="created_at", time_columns=["created_at"])


class TestTimeColumnValidationClass:
    """Direct tests for TimeColumnValidation."""

    def test_validate_valid_model(self):
        model = _model_with(time_columns=["created_at"])
        validator = TimeColumnValidation(model)
        validator.validate()

    def test_validate_invalid_model_raises_error(self):
        model = _model_with(time_columns=["created_at"])
        model.time_columns[0] = "created at"  # mutate after creation
        validator = TimeColumnValidation(model)

        with pytest.raises(TimeColumnValidationError):
            validator.validate()
