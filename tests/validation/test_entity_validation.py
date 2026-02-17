"""Tests for entity validation rules.

This module contains comprehensive tests for all entity validation rules:
1. A Model must declare exactly one primary entity
2. Primary entity column must match the model's primary key
3. Entity name must be a valid identifier
4. A model cannot have a foreign entity with the same name as its primary entity
5. A model cannot define duplicate entity names
"""

import pytest

from pysemantic.modeling import Dimension, Entity, EntityType, Measure, Model
from pysemantic.validation import (
    EntityValidation,
    EntityValidationError,
    NamingCollisionError,
)


def _entity(name: str, entity_type: EntityType, column: str | None = None) -> Entity:
    if column is None:
        column = "id" if entity_type == EntityType.PRIMARY else f"{name}_id"
    return Entity(name, entity_type, column)


def _model_with(**overrides) -> Model:
    params = {
        "name": overrides.pop("name", "test"),
        "table": overrides.pop("table", "test_table"),
        "primary_key": overrides.pop("primary_key", "id"),
    }
    params.update(overrides)
    return Model(**params)


class TestPrimaryEntityRequirement:
    """Test Rule 1: A Model must declare exactly one primary entity."""

    def test_valid_single_primary_entity(self):
        """Test that a model with exactly one primary entity is valid."""
        entity = _entity("customer", EntityType.PRIMARY)
        model = _model_with(entities=[entity])
        assert len([e for e in model.entities if e.entity_type == EntityType.PRIMARY]) == 1

    def test_no_primary_entity_raises_error(self):
        """Test that a model with no primary entity raises EntityValidationError."""
        entity = _entity("customer", EntityType.FOREIGN)
        with pytest.raises(EntityValidationError) as exc_info:
            _model_with(entities=[entity])

        assert "exactly one primary entity" in str(exc_info.value)
        assert "Found 0 primary entities" in str(exc_info.value)

    def test_multiple_primary_entities_raises_error(self):
        """Test that a model with multiple primary entities raises EntityValidationError."""
        entity1 = _entity("customer", EntityType.PRIMARY)
        entity2 = _entity("order", EntityType.PRIMARY)

        with pytest.raises(EntityValidationError) as exc_info:
            _model_with(entities=[entity1, entity2])

        assert "exactly one primary entity" in str(exc_info.value)
        assert "Found 2 primary entities" in str(exc_info.value)
        assert "customer" in str(exc_info.value)
        assert "order" in str(exc_info.value)

    def test_empty_entities_list_raises_error(self):
        """Test that a model with empty entities list raises EntityValidationError."""
        # Entities are required, so empty list should raise error during __init__
        with pytest.raises(EntityValidationError) as exc_info:
            _model_with(entities=[])

        assert "exactly one primary entity" in str(exc_info.value)
        assert "No entities found" in str(exc_info.value)


class TestPrimaryEntityColumnValidation:
    """Test Rule 2: Primary entity column must match the model's primary key."""

    def test_valid_primary_entity_column_matches_primary_key(self):
        """Test that a primary entity with matching column is valid."""
        entity = _entity("customer", EntityType.PRIMARY)
        model = _model_with(entities=[entity])
        assert model.primary_key == entity.column

    def test_primary_entity_column_mismatch_raises_error(self):
        """Test that a primary entity with mismatched column raises EntityValidationError."""
        entity = _entity("customer", EntityType.PRIMARY, column="customer_id")

        with pytest.raises(EntityValidationError) as exc_info:
            _model_with(entities=[entity])

        assert "Primary entity column" in str(exc_info.value)
        assert "must match" in str(exc_info.value)
        assert "customer_id" in str(exc_info.value)
        assert "id" in str(exc_info.value)


class TestEntityNameIdentifierRules:
    """Test Rule 3: Entity name must be a valid identifier."""

    def test_valid_entity_name(self):
        """Test that valid entity names are accepted."""
        valid_names = ["customer", "order_id", "product_name", "_private", "CamelCase"]

        for name in valid_names:
            entity = _entity(name, EntityType.PRIMARY)
            model = _model_with(entities=[entity])
            assert model.entities[0].name == name

    def test_entity_name_with_space_raises_error(self):
        """Test that entity names with spaces raise EntityValidationError."""
        entity = _entity("customer id", EntityType.PRIMARY)

        with pytest.raises(EntityValidationError) as exc_info:
            _model_with(entities=[entity])

        assert "valid identifiers" in str(exc_info.value)
        assert "customer id" in str(exc_info.value)

    def test_entity_name_with_symbols_raises_error(self):
        """Test that entity names with symbols raise EntityValidationError."""
        invalid_names = ["customer-id", "order@id", "product#name", "user.name"]

        for name in invalid_names:
            entity = _entity(name, EntityType.PRIMARY)
            with pytest.raises(EntityValidationError) as exc_info:
                _model_with(entities=[entity])

            assert "valid identifiers" in str(exc_info.value)
            assert name in str(exc_info.value)

    def test_entity_name_reserved_word_raises_error(self):
        """Test that Python reserved words as entity names raise EntityValidationError."""
        reserved_words = ["class", "def", "if", "for", "import", "return"]

        for word in reserved_words:
            entity = _entity(word, EntityType.PRIMARY)
            with pytest.raises(EntityValidationError) as exc_info:
                _model_with(entities=[entity])

            assert "valid identifiers" in str(exc_info.value)
            assert word in str(exc_info.value)

    def test_entity_name_starting_with_number_raises_error(self):
        """Test that entity names starting with numbers raise EntityValidationError."""
        entity = _entity("123customer", EntityType.PRIMARY)

        with pytest.raises(EntityValidationError) as exc_info:
            _model_with(entities=[entity])

        assert "valid identifiers" in str(exc_info.value)
        assert "123customer" in str(exc_info.value)

    def test_empty_entity_name_raises_error(self):
        """Test that empty entity names raise EntityValidationError."""
        entity = _entity("", EntityType.PRIMARY)

        with pytest.raises(EntityValidationError) as exc_info:
            _model_with(entities=[entity])

        assert "valid identifiers" in str(exc_info.value)


class TestPrimaryForeignNameConflicts:
    """Test Rule 4: Foreign entity names cannot match the primary entity name."""

    def test_valid_primary_and_foreign_with_different_names(self):
        """Test that primary and foreign entities with different names are valid."""
        primary = _entity("customer", EntityType.PRIMARY)
        foreign = _entity("order", EntityType.FOREIGN)
        model = _model_with(entities=[primary, foreign])
        assert len(model.entities) == 2

    def test_foreign_entity_same_name_as_primary_raises_error(self):
        """Test that a foreign entity with the same name as primary raises EntityValidationError."""
        primary = _entity("customer", EntityType.PRIMARY)
        foreign = _entity("customer", EntityType.FOREIGN)

        with pytest.raises(EntityValidationError) as exc_info:
            _model_with(entities=[primary, foreign])

        assert "foreign entity with the same name as its primary entity" in str(exc_info.value)
        assert "customer" in str(exc_info.value)

    def test_multiple_foreign_entities_with_primary_name_raises_error(self):
        """Test that multiple foreign entities with primary name raise EntityValidationError."""
        primary = _entity("customer", EntityType.PRIMARY)
        foreign1 = _entity("customer", EntityType.FOREIGN)
        foreign2 = _entity("customer", EntityType.FOREIGN, column="customer_id_2")

        with pytest.raises(EntityValidationError) as exc_info:
            _model_with(entities=[primary, foreign1, foreign2])

        assert "foreign entity with the same name as its primary entity" in str(exc_info.value)


class TestEntityNameUniqueness:
    """Test Rule 5: A model cannot define duplicate entity names."""

    def test_valid_unique_entity_names(self):
        """Test that entities with unique names are valid."""
        entity1 = _entity("customer", EntityType.PRIMARY)
        entity2 = _entity("order", EntityType.FOREIGN)
        entity3 = _entity("product", EntityType.FOREIGN)
        model = _model_with(entities=[entity1, entity2, entity3])
        assert len(model.entities) == 3

    def test_duplicate_entity_names_raises_error(self):
        """Test that duplicate entity names raise EntityValidationError."""
        # Note: If primary and foreign have same name, Rule 4 catches it first
        # So we test with two foreign entities with same name
        primary = _entity("customer", EntityType.PRIMARY)
        foreign1 = _entity("order", EntityType.FOREIGN)
        foreign2 = _entity("order", EntityType.FOREIGN, column="order_id_2")

        with pytest.raises(NamingCollisionError) as exc_info:
            _model_with(entities=[primary, foreign1, foreign2])

        assert "duplicate entity names" in str(exc_info.value)
        assert "order" in str(exc_info.value)

    def test_multiple_duplicate_entity_names_raises_error(self):
        """Test that multiple duplicate entity names raise EntityValidationError."""
        # Test with FOREIGN entities to avoid Rule 4 conflicts
        primary = _entity("customer", EntityType.PRIMARY)
        foreign1 = _entity("product", EntityType.FOREIGN)
        foreign2 = _entity("product", EntityType.FOREIGN, column="product_id_2")

        with pytest.raises(NamingCollisionError) as exc_info:
            _model_with(entities=[primary, foreign1, foreign2])

        assert "duplicate entity names" in str(exc_info.value)
        assert "product" in str(exc_info.value)

        # Test with multiple duplicates
        foreign3 = _entity("order", EntityType.FOREIGN)
        foreign4 = _entity("order", EntityType.FOREIGN, column="order_id_2")
        foreign5 = _entity("shipment", EntityType.FOREIGN)
        foreign6 = _entity("shipment", EntityType.FOREIGN, column="shipment_id_2")

        with pytest.raises(NamingCollisionError) as exc_info:
            _model_with(entities=[primary, foreign3, foreign4, foreign5, foreign6])

        assert "duplicate entity names" in str(exc_info.value)


class TestEntityValidationClass:
    """Test the EntityValidation class directly."""

    def test_validate_valid_model(self):
        """Test that EntityValidation.validate() passes for valid models."""
        entity = _entity("customer", EntityType.PRIMARY)
        model = _model_with(entities=[entity])
        validator = EntityValidation(model)
        validator.validate()  # Should not raise

    def test_validate_invalid_model_raises_error(self):
        """Test that EntityValidation.validate() raises error for invalid models."""
        # Create a model with invalid entity (no primary entity)
        entity = _entity("customer", EntityType.FOREIGN)

        with pytest.raises(EntityValidationError):
            _model_with(entities=[entity])

    def test_is_valid_method(self):
        """Test the is_valid() method on Model."""
        # Valid model
        entity1 = _entity("customer", EntityType.PRIMARY)
        model1 = _model_with(entities=[entity1])
        assert model1.is_valid() is True

        # Invalid model - create with invalid entity (no primary)
        # We need to create it in a way that bypasses validation, then test is_valid
        # Since entities are required, we'll create a valid model first, then modify it
        entity2 = _entity("customer", EntityType.PRIMARY)
        model2 = _model_with(entities=[entity2])
        # Now modify to invalid state
        model2.entities[0].entity_type = EntityType.FOREIGN
        assert model2.is_valid() is False


class TestEntityNamingCollisions:
    """Tests for entity naming collision rules."""

    def test_entity_name_conflicts_with_dimension(self):
        primary = _entity("customer", EntityType.PRIMARY, column="pk")
        dimension = Dimension("customer", "col")

        with pytest.raises(NamingCollisionError):
            _model_with(
                entities=[primary],
                dimensions=[dimension],
                primary_key="pk",
                name="sales",
                table="sales_table",
            )

    def test_entity_name_conflicts_with_measure(self):
        primary = _entity("revenue", EntityType.PRIMARY, column="pk")
        measure = Measure("revenue", "sum", "amount")

        with pytest.raises(NamingCollisionError):
            _model_with(
                entities=[primary],
                measures=[measure],
                primary_key="pk",
                name="sales",
                table="sales_table",
            )

    def test_entity_name_conflicts_with_time_column(self):
        primary = _entity("created_at", EntityType.PRIMARY, column="pk")

        with pytest.raises(NamingCollisionError):
            _model_with(
                entities=[primary],
                time_columns=["created_at"],
                primary_key="pk",
                name="sales",
                table="sales_table",
            )

    def test_entity_name_conflicts_with_primary_key(self):
        primary = _entity("id", EntityType.PRIMARY, column="id")

        with pytest.raises(NamingCollisionError):
            _model_with(
                entities=[primary],
                primary_key="id",
                name="sales",
                table="sales_table",
            )


class TestComplexScenarios:
    """Test complex scenarios with multiple entities."""

    def test_valid_complex_model(self):
        """Test a valid model with primary and multiple foreign entities."""
        primary = _entity("customer", EntityType.PRIMARY)
        foreign1 = _entity("order", EntityType.FOREIGN)
        foreign2 = _entity("product", EntityType.FOREIGN)
        foreign3 = _entity("email", EntityType.FOREIGN)

        model = _model_with(
            name="sales",
            table="sales_table",
            primary_key="id",
            entities=[primary, foreign1, foreign2, foreign3],
        )

        assert len(model.entities) == 4
        assert model.is_valid() is True

    def test_all_validation_rules_fail(self):
        """Test a model that violates multiple rules."""
        # This will fail on rule 1 (no primary entity)
        entity = _entity("customer", EntityType.FOREIGN)

        with pytest.raises(EntityValidationError) as exc_info:
            _model_with(entities=[entity])

        # Should catch the first rule violation
        assert "exactly one primary entity" in str(exc_info.value)

    def test_validate_entities_method(self):
        """Test the validate_entities() method on Model."""
        entity = _entity("customer", EntityType.PRIMARY)
        model = _model_with(entities=[entity])

        # Should not raise
        model.validate_entities()

        # Modify to invalid state
        model.entities[0].entity_type = EntityType.FOREIGN

        # Should raise on re-validation
        with pytest.raises(EntityValidationError):
            model.validate_entities()
