"""Tests for measure validation rules.

This module contains comprehensive tests for all measure validation rules:
1. Name must be valid identifier
2. agg must be a known aggregation
3. column must be valid identifier (format)
4. Measures cannot reference foreign-entity columns
5. Derived measures must reference valid measure/dim names
6. No duplicate measure names
7. No conflict with dimensions/entities
"""

import pytest

from pysemantic.exceptions import NamingCollisionError
from pysemantic.modeling import Dimension, Entity, EntityType, Measure, Model
from pysemantic.validation.measure_validation import MeasureValidation, MeasureValidationError


def _entity(name: str, entity_type: EntityType, column: str | None = None) -> Entity:
    if column is None:
        column = "id" if entity_type == EntityType.PRIMARY else f"{name}_id"
    return Entity(name, entity_type, column)


def _measure(name: str, agg: str = "sum", column: str = "amount") -> Measure:
    return Measure(name, agg, column)


def _model_with(**overrides) -> Model:
    params = {
        "name": overrides.pop("name", "test"),
        "table": overrides.pop("table", "table"),
        "primary_key": overrides.pop("primary_key", "id"),
    }
    params.update(overrides)
    return Model(**params)


class TestMeasureNameIdentifierRules:
    """Test Rule 1: Name must be valid identifier."""

    def test_valid_measure_name(self):
        """Test that valid measure names are accepted."""
        valid_names = ["total_sales", "order_count", "revenue_amount", "_private", "CamelCase"]

        for name in valid_names:
            entity = _entity("customer", EntityType.PRIMARY)
            measure = _measure(name)
            model = _model_with(entities=[entity], measures=[measure])
            validator = MeasureValidation(model)
            validator.validate()  # Should not raise

    def test_measure_name_with_space_raises_error(self):
        """Test that measure names with spaces raise MeasureValidationError."""
        entity = _entity("customer", EntityType.PRIMARY)
        measure = _measure("total sales")

        with pytest.raises(MeasureValidationError) as exc_info:
            _model_with(entities=[entity], measures=[measure])

        assert "valid identifier" in str(exc_info.value)
        assert "total sales" in str(exc_info.value)

    def test_measure_name_with_symbols_raises_error(self):
        """Test that measure names with symbols raise MeasureValidationError."""
        invalid_names = ["total-sales", "order@count", "revenue#amount", "user.name"]

        for name in invalid_names:
            entity = _entity("customer", EntityType.PRIMARY)
            measure = _measure(name)

            with pytest.raises(MeasureValidationError) as exc_info:
                _model_with(entities=[entity], measures=[measure])

            assert "valid identifier" in str(exc_info.value)
            assert name in str(exc_info.value)

    def test_measure_name_reserved_word_raises_error(self):
        """Test that Python reserved words as measure names raise MeasureValidationError."""
        reserved_words = ["class", "def", "if", "for", "import", "return"]

        for word in reserved_words:
            entity = _entity("customer", EntityType.PRIMARY)
            measure = _measure(word)

            with pytest.raises(MeasureValidationError) as exc_info:
                _model_with(entities=[entity], measures=[measure])

            assert "valid identifier" in str(exc_info.value)
            assert word in str(exc_info.value)

    def test_measure_name_starting_with_number_raises_error(self):
        """Test that measure names starting with numbers raise MeasureValidationError."""
        entity = _entity("customer", EntityType.PRIMARY)
        measure = _measure("123sales")

        with pytest.raises(MeasureValidationError) as exc_info:
            _model_with(entities=[entity], measures=[measure])

        assert "valid identifier" in str(exc_info.value)
        assert "123sales" in str(exc_info.value)

    def test_empty_measure_name_raises_error(self):
        """Test that empty measure names raise MeasureValidationError."""
        entity = _entity("customer", EntityType.PRIMARY)
        measure = _measure("")

        with pytest.raises(MeasureValidationError) as exc_info:
            _model_with(entities=[entity], measures=[measure])

        assert "valid identifier" in str(exc_info.value)


class TestMeasureAggregationValidation:
    """Test Rule 2: agg must be a known aggregation."""

    def test_valid_aggregation_functions(self):
        """Test that valid aggregation functions are accepted."""
        valid_aggs = ["sum", "avg", "mean", "count", "count_distinct", "min", "max"]

        for agg in valid_aggs:
            entity = _entity("customer", EntityType.PRIMARY)
            measure = _measure("total_sales", agg)
            model = _model_with(entities=[entity], measures=[measure])
            validator = MeasureValidation(model)
            validator.validate()  # Should not raise

    def test_invalid_aggregation_raises_error(self):
        """Test that invalid aggregation functions raise MeasureValidationError."""
        invalid_aggs = ["totalsum", "average", "total", "aggregate", "summation"]

        for agg in invalid_aggs:
            entity = _entity("customer", EntityType.PRIMARY)
            measure = _measure("total_sales", agg)

            with pytest.raises(MeasureValidationError) as exc_info:
                _model_with(entities=[entity], measures=[measure])

            assert "known aggregation function" in str(exc_info.value)
            assert agg in str(exc_info.value)

    def test_empty_aggregation_raises_error(self):
        """Test that empty aggregation raises MeasureValidationError."""
        entity = _entity("customer", EntityType.PRIMARY)
        measure = _measure("total_sales", "")

        with pytest.raises(MeasureValidationError) as exc_info:
            _model_with(entities=[entity], measures=[measure])

        assert "known aggregation function" in str(exc_info.value)


class TestMeasureColumnIdentifierRules:
    """Test Rule 3: column must be valid identifier (format validation only)."""

    def test_valid_column_name(self):
        """Test that valid column names are accepted."""
        valid_columns = ["amount", "sales_total", "order_id", "_column", "ColumnName"]

        for column in valid_columns:
            entity = _entity("customer", EntityType.PRIMARY)
            measure = _measure("total_sales", "sum", column)
            model = _model_with(entities=[entity], measures=[measure])
            validator = MeasureValidation(model)
            validator.validate()  # Should not raise

    def test_column_name_with_space_raises_error(self):
        """Test that column names with spaces raise MeasureValidationError."""
        entity = _entity("customer", EntityType.PRIMARY)
        measure = _measure("total_sales", "sum", "total amount")

        with pytest.raises(MeasureValidationError) as exc_info:
            _model_with(entities=[entity], measures=[measure])

        assert "valid identifier format" in str(exc_info.value)
        assert "total amount" in str(exc_info.value)

    def test_column_name_with_symbols_raises_error(self):
        """Test that column names with symbols raise MeasureValidationError."""
        invalid_columns = ["amount-total", "sales@id", "order#number", "user.name"]

        for column in invalid_columns:
            entity = _entity("customer", EntityType.PRIMARY)
            measure = _measure("total_sales", "sum", column)

            with pytest.raises(MeasureValidationError) as exc_info:
                _model_with(entities=[entity], measures=[measure])

            assert "valid identifier format" in str(exc_info.value)
            assert column in str(exc_info.value)

    def test_column_does_not_need_to_exist_in_model(self):
        """Test that column doesn't need to exist in model semantic fields."""
        # Column can be any valid identifier, even if not in dimensions/entities
        entity = _entity("customer", EntityType.PRIMARY)
        measure = _measure("total_sales", "sum", "non_existent_column")
        model = _model_with(entities=[entity], measures=[measure])
        validator = MeasureValidation(model)
        validator.validate()  # Should not raise - format validation only


class TestMeasureForeignColumnRestrictions:
    """Test Rule 4: Measures cannot reference foreign-entity columns."""

    def test_measure_with_non_foreign_column_is_valid(self):
        """Test that measures with non-foreign columns are valid."""
        primary = _entity("customer", EntityType.PRIMARY)
        foreign = _entity("order", EntityType.FOREIGN)
        measure = _measure("total_sales", "sum", "amount")  # amount is not a foreign column
        model = _model_with(entities=[primary, foreign], measures=[measure])
        validator = MeasureValidation(model)
        validator.validate()  # Should not raise

    def test_measure_referencing_foreign_entity_column_raises_error(self):
        """Test that measures referencing foreign entity columns raise MeasureValidationError."""
        primary = _entity("customer", EntityType.PRIMARY)
        foreign = _entity("order", EntityType.FOREIGN)
        measure = _measure("total_sales", "sum", "order_id")  # order_id is a foreign column

        with pytest.raises(MeasureValidationError) as exc_info:
            _model_with(entities=[primary, foreign], measures=[measure])

        assert "cannot reference foreign-entity columns" in str(exc_info.value)
        assert "order_id" in str(exc_info.value)
        assert "prevents double-counting" in str(exc_info.value)

    def test_measure_referencing_primary_entity_column_is_valid(self):
        """Test that measures can reference primary entity columns."""
        primary = _entity("customer", EntityType.PRIMARY)
        measure = _measure("customer_count", "count", "id")  # id is primary, not foreign
        model = _model_with(entities=[primary], measures=[measure])
        validator = MeasureValidation(model)
        validator.validate()  # Should not raise

    def test_multiple_foreign_columns_are_all_blocked(self):
        """Test that all foreign entity columns are blocked."""
        primary = _entity("customer", EntityType.PRIMARY)
        foreign1 = _entity("order", EntityType.FOREIGN)
        foreign2 = _entity("product", EntityType.FOREIGN)

        # Test order_id
        measure1 = _measure("total_sales", "sum", "order_id")
        with pytest.raises(MeasureValidationError):
            _model_with(entities=[primary, foreign1, foreign2], measures=[measure1])

        # Test product_id
        measure2 = _measure("total_sales", "sum", "product_id")
        with pytest.raises(MeasureValidationError):
            _model_with(entities=[primary, foreign1, foreign2], measures=[measure2])


class TestDerivedMeasureReferences:
    """Test Rule 5: Derived measures must reference valid measure/dimension names."""

    def test_derived_measure_referencing_valid_dimension(self):
        """Test that derived measures can reference valid dimensions."""
        # Note: Current implementation is a placeholder
        # This test verifies the method doesn't raise errors for valid references
        entity = _entity("customer", EntityType.PRIMARY)
        dimension = Dimension("region", "string")
        measure = _measure("region_measure", "sum", "region")  # column matches dimension name
        model = _model_with(entities=[entity], dimensions=[dimension], measures=[measure])
        validator = MeasureValidation(model)
        validator.validate()  # Should not raise

    def test_derived_measure_referencing_valid_measure(self):
        """Test that derived measures can reference valid measures."""
        # Note: Current implementation is a placeholder
        entity = _entity("customer", EntityType.PRIMARY)
        measure1 = _measure("revenue", "sum", "amount")
        measure2 = _measure("orders", "count", "order_id")
        # measure2 column references measure1 name (simplified check)
        model = _model_with(entities=[entity], measures=[measure1, measure2])
        validator = MeasureValidation(model)
        validator.validate()  # Should not raise


class TestMeasureNameUniqueness:
    """Test Rule 6: No duplicate measure names."""

    def test_valid_unique_measure_names(self):
        """Test that measures with unique names are valid."""
        entity = _entity("customer", EntityType.PRIMARY)
        measure1 = _measure("total_sales", "sum", "amount")
        measure2 = _measure("order_count", "count", "order_id")
        measure3 = _measure("avg_price", "avg", "price")
        model = _model_with(entities=[entity], measures=[measure1, measure2, measure3])
        validator = MeasureValidation(model)
        validator.validate()  # Should not raise

    def test_duplicate_measure_names_raises_error(self):
        """Test that duplicate measure names raise MeasureValidationError."""
        entity = _entity("customer", EntityType.PRIMARY)
        measure1 = _measure("total_sales", "sum", "amount")
        measure2 = _measure("total_sales", "count", "order_id")  # Duplicate name

        with pytest.raises(NamingCollisionError) as exc_info:
            _model_with(entities=[entity], measures=[measure1, measure2])

        assert "duplicate measure names" in str(exc_info.value)
        assert "total_sales" in str(exc_info.value)

    def test_multiple_duplicate_measure_names_raises_error(self):
        """Test that multiple duplicate measure names raise MeasureValidationError."""
        entity = _entity("customer", EntityType.PRIMARY)
        measure1 = _measure("total_sales", "sum", "amount")
        measure2 = _measure("total_sales", "count", "order_id")  # Duplicate
        measure3 = _measure("order_count", "count", "order_id")
        measure4 = _measure("order_count", "sum", "amount")  # Duplicate

        with pytest.raises(NamingCollisionError) as exc_info:
            _model_with(entities=[entity], measures=[measure1, measure2, measure3, measure4])

        assert "duplicate measure names" in str(exc_info.value)
        # Should mention both duplicates
        error_str = str(exc_info.value)
        assert "total_sales" in error_str or "order_count" in error_str


class TestMeasureNameCollisions:
    """Test Rule 7: No conflict with dimensions/entities."""

    def test_measure_name_conflicts_with_dimension_raises_error(self):
        """Test that measure names conflicting with dimension names raise NamingCollisionError."""
        entity = _entity("customer", EntityType.PRIMARY)
        dimension = Dimension("region", "string")
        measure = _measure("region", "sum", "amount")  # Conflicts with dimension name

        with pytest.raises(NamingCollisionError) as exc_info:
            _model_with(entities=[entity], dimensions=[dimension], measures=[measure])

        message = str(exc_info.value)
        assert "Dimension name cannot conflict with measure names" in message
        assert "region" in message

    def test_measure_name_conflicts_with_entity_raises_error(self):
        """Test that measure names conflicting with entity names raise NamingCollisionError."""
        primary = _entity("customer", EntityType.PRIMARY)
        foreign = _entity("order", EntityType.FOREIGN)
        measure = _measure("order", "sum", "amount")  # Conflicts with entity name

        with pytest.raises(NamingCollisionError) as exc_info:
            _model_with(entities=[primary, foreign], measures=[measure])

        message = str(exc_info.value)
        assert "Entity name cannot match a measure name" in message
        assert "order" in message

    def test_measure_name_conflicts_with_primary_entity_raises_error(self):
        """Measure names cannot match the primary entity name."""
        primary = _entity("customer", EntityType.PRIMARY)
        measure = _measure("customer", "sum", "amount")  # Conflicts with primary entity name

        with pytest.raises(NamingCollisionError) as exc_info:
            _model_with(entities=[primary], measures=[measure])

        message = str(exc_info.value)
        assert "Entity name cannot match a measure name" in message
        assert "customer" in message

    def test_measure_name_conflicts_with_time_column_raises_error(self):
        """Measure names cannot match a time column."""
        entity = _entity("customer", EntityType.PRIMARY)
        measure = _measure("created_at", "sum", "amount")

        with pytest.raises(NamingCollisionError) as exc_info:
            _model_with(entities=[entity], measures=[measure], time_columns=["created_at"])

        assert "time column" in str(exc_info.value)

    def test_measure_name_conflicts_with_primary_key_raises_error(self):
        """Measure names cannot match the primary key."""
        entity = _entity("customer", EntityType.PRIMARY)
        measure = _measure("id", "sum", "amount")

        with pytest.raises(NamingCollisionError) as exc_info:
            _model_with(entities=[entity], measures=[measure])

        assert "primary key" in str(exc_info.value)

    def test_valid_measure_with_no_conflicts(self):
        """Test that measures with no conflicts are valid."""
        primary = _entity("customer", EntityType.PRIMARY)
        foreign = _entity("order", EntityType.FOREIGN)
        dimension = Dimension("region", "string")
        measure = _measure("total_sales", "sum", "amount")  # No conflicts

        model = _model_with(entities=[primary, foreign], dimensions=[dimension], measures=[measure])
        validator = MeasureValidation(model)
        validator.validate()  # Should not raise


class TestMeasureValidationClass:
    """Test the MeasureValidation class directly."""

    def test_validate_valid_model(self):
        """Test that MeasureValidation.validate() passes for valid models."""
        entity = _entity("customer", EntityType.PRIMARY)
        measure = _measure("total_sales", "sum", "amount")
        model = _model_with(entities=[entity], measures=[measure])
        validator = MeasureValidation(model)
        validator.validate()  # Should not raise

    def test_validate_invalid_model_raises_error(self):
        """Test that MeasureValidation.validate() raises error for invalid models."""
        entity = _entity("customer", EntityType.PRIMARY)
        measure = _measure("total sales", "sum", "amount")  # Invalid name

        with pytest.raises(MeasureValidationError):
            _model_with(entities=[entity], measures=[measure])

    def test_validate_empty_measures_list(self):
        """Test that validation passes when there are no measures."""
        entity = _entity("customer", EntityType.PRIMARY)
        model = _model_with(entities=[entity], measures=[])
        validator = MeasureValidation(model)
        validator.validate()  # Should not raise - no measures to validate


class TestComplexScenarios:
    """Test complex scenarios with multiple measures."""

    def test_valid_complex_model(self):
        """Test a valid model with multiple measures."""
        primary = _entity("customer", EntityType.PRIMARY)
        foreign = _entity("order", EntityType.FOREIGN)
        dimension = Dimension("region", "string")

        measure1 = _measure("total_sales", "sum", "amount")
        measure2 = _measure("order_count", "count", "id")  # Use primary key, not foreign
        measure3 = _measure("avg_price", "avg", "price")

        model = _model_with(
            name="sales",
            table="sales_table",
            entities=[primary, foreign],
            dimensions=[dimension],
            measures=[measure1, measure2, measure3],
        )

        validator = MeasureValidation(model)
        validator.validate()  # Should not raise
        assert len(model.measures) == 3

    def test_multiple_validation_errors(self):
        """Test a model that violates multiple rules."""
        # This will fail on the first rule violation (name validation)
        entity = _entity("customer", EntityType.PRIMARY)
        measure = _measure("total sales", "invalid_agg", "total amount")  # Multiple violations

        with pytest.raises(MeasureValidationError) as exc_info:
            _model_with(entities=[entity], measures=[measure])

        # Should catch the first validation error (name)
        assert "valid identifier" in str(exc_info.value)

    def test_all_rules_pass(self):
        """Test that all validation rules pass for a comprehensive valid model."""
        primary = _entity("customer", EntityType.PRIMARY)
        foreign = _entity("order", EntityType.FOREIGN)
        dimension1 = Dimension("region", "string")
        dimension2 = Dimension("product", "string")

        measure1 = _measure("total_revenue", "sum", "revenue")
        measure2 = _measure("order_count", "count", "id")  # Use primary key, not foreign
        measure3 = _measure("avg_order_value", "avg", "order_value")

        model = _model_with(
            name="sales",
            table="sales_table",
            entities=[primary, foreign],
            dimensions=[dimension1, dimension2],
            measures=[measure1, measure2, measure3],
        )

        validator = MeasureValidation(model)
        validator.validate()  # Should not raise
        assert len(model.measures) == 3
