"""Tests for dimension validation rules."""

import pytest

from pysemantic.exceptions import NamingCollisionError
from pysemantic.modeling import Dimension, Entity, EntityType, Measure, Model
from pysemantic.validation.dimension_validation import (
    DimensionValidation,
    DimensionValidationError,
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


class TestDimensionNameIdentifierRules:
    """Rule 1: Dimension names must be valid identifiers."""

    def test_valid_dimension_names(self):
        valid_names = ["region", "product_id", "_category", "CamelCase"]
        for name in valid_names:
            _model_with(dimensions=[Dimension(name, "col", "string")])

    def test_dimension_name_with_space_raises_error(self):
        with pytest.raises(DimensionValidationError) as exc_info:
            _model_with(dimensions=[Dimension("product category", "col", "string")])

        assert "valid identifier" in str(exc_info.value)

    def test_dimension_name_with_symbols_raises_error(self):
        with pytest.raises(DimensionValidationError) as exc_info:
            _model_with(dimensions=[Dimension("product-id", "col", "string")])

        assert "valid identifier" in str(exc_info.value)

    def test_dimension_name_reserved_word_raises_error(self):
        with pytest.raises(DimensionValidationError) as exc_info:
            _model_with(dimensions=[Dimension("select", "col", "string")])

        assert "reserved word" in str(exc_info.value)

    def test_dimension_name_starting_with_number_raises_error(self):
        with pytest.raises(DimensionValidationError):
            _model_with(dimensions=[Dimension("123category", "col", "string")])

    def test_empty_dimension_name_raises_error(self):
        with pytest.raises(DimensionValidationError):
            _model_with(dimensions=[Dimension("", "col", "string")])


class TestDimensionNameUniqueness:
    """Rule 2: No duplicate dimension names."""

    def test_unique_dimension_names(self):
        dims = [Dimension("region", "r", "string"), Dimension("product", "p", "string")]
        _model_with(dimensions=dims)

    def test_duplicate_dimension_names_raise_error(self):
        dims = [Dimension("region", "r", "string"), Dimension("region", "r", "int")]

        with pytest.raises(NamingCollisionError) as exc_info:
            _model_with(dimensions=dims)

        assert "duplicate dimension names" in str(exc_info.value)

    def test_multiple_duplicate_dimension_names_raise_error(self):
        dims = [
            Dimension("region", "r", "string"),
            Dimension("region", "r", "int"),
            Dimension("country", "c", "string"),
            Dimension("country", "c", "string"),
        ]

        with pytest.raises(NamingCollisionError):
            _model_with(dimensions=dims)


class TestDimensionDtypeValidation:
    """Rule 3: Dimension dtype must be supported."""

    def test_valid_dimension_dtypes(self):
        for dtype in ["string", "int", "float", "boolean", "date", "datetime"]:
            _model_with(dimensions=[Dimension("region", "r", dtype)])

    def test_invalid_dimension_dtype_raises_error(self):
        with pytest.raises(DimensionValidationError) as exc_info:
            _model_with(dimensions=[Dimension("region", "r", "text")])

        assert "supported data type" in str(exc_info.value)


class TestDimensionNameCollisions:
    """Rule 4: No naming collisions between dimensions and other entities."""

    def test_dimension_name_conflicts_with_entity(self):
        entity = Entity("customer", EntityType.PRIMARY, "id")

        with pytest.raises(NamingCollisionError):
            _model_with(
                entities=[entity],
                dimensions=[Dimension("customer", "c", "string")],
            )

    def test_dimension_name_conflicts_with_measure(self):
        measure = Measure("region", "sum", "amount")

        with pytest.raises(NamingCollisionError):
            _model_with(measures=[measure], dimensions=[Dimension("region", "r", "string")])

    def test_dimension_name_conflicts_with_time_column(self):
        with pytest.raises(NamingCollisionError):
            _model_with(
                dimensions=[Dimension("created_at", "c", "datetime")],
                time_columns=["created_at"],
            )

    def test_dimension_name_conflicts_with_primary_key(self):
        with pytest.raises(NamingCollisionError):
            _model_with(
                primary_key="region_id",
                dimensions=[Dimension("region_id", "r", "string")],
            )


class TestDimensionValidationClass:
    """Direct tests for DimensionValidation."""

    def test_validate_valid_model(self):
        dims = [Dimension("region", "r", "string")]
        model = _model_with(dimensions=dims)
        validator = DimensionValidation(model)
        validator.validate()

    def test_validate_invalid_model_raises_error(self):
        dimension = Dimension("region", "r", "string")
        model = _model_with(dimensions=[dimension])
        dimension.name = "region name"  # mutate after model creation

        validator = DimensionValidation(model)
        with pytest.raises(DimensionValidationError):
            validator.validate()
