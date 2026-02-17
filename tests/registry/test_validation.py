from unittest.mock import MagicMock

import pytest

from pysemantic.exceptions import RegistryError
from pysemantic.modeling import Dimension, Entity, EntityType, Measure, Model
from pysemantic.validation.registry.validation import RegistryValidation, RegistryValidationError


@pytest.fixture
def empty_registry():
    return RegistryValidation(models={}, entities={}, dimensions={}, measures={})


def create_model(
    name,
    table="table_1",
    grain="daily",
    measures=None,
    dimensions=None,
    entities=None,
    time_columns=None,
):
    if measures is None:
        measures = []
    if dimensions is None:
        dimensions = []
    if entities is None:
        # Default to one primary entity to satisfy Model internal validation if not testing specific entity issues
        entities = [Entity(f"{name}_id", EntityType.PRIMARY, "id_col")]

    return Model(
        name=name,
        table=table,
        primary_key="id_col",
        measures=measures,
        dimensions=dimensions,
        entities=entities,
        time_columns=time_columns,
    )


def test_valid_registry():
    """Test a perfectly valid registry with cross-model references."""
    # Model A: Users
    users = Model(
        name="users",
        table="dim_users",
        primary_key="user_id",
        entities=[Entity("user", EntityType.PRIMARY, "user_id")],
    )

    # Model B: Orders (references Users)
    orders = Model(
        name="orders",
        table="fct_orders",
        primary_key="order_id",
        entities=[
            Entity("order", EntityType.PRIMARY, "order_id"),
            Entity("user", EntityType.FOREIGN, "user_id_fk"),
        ],
    )

    validator = RegistryValidation(models={"users": users, "orders": orders}, entities={}, dimensions={}, measures={})
    # Should not raise any exception
    validator.validate()


def test_duplicate_model_names_logic():
    """
    Test Rule 1: No duplicate model names.
    Since standard dicts cannot have duplicate keys, we mock the models object
    to verify the logic inside _validate_no_duplicate_model_names.
    """
    validator = RegistryValidation(models={}, entities={}, dimensions={}, measures={})

    # Mock models.keys() to return duplicates
    mock_models = MagicMock()
    mock_models.keys.return_value = ["model_a", "model_b", "model_a"]
    validator.models = mock_models

    with pytest.raises(RegistryValidationError) as exc:
        validator._validate_no_duplicate_model_names()

    assert "Duplicate names: model_a" in str(exc.value)


def test_foreign_entity_missing_reference():
    """Test Rule 2: Foreign entity must reference an existing primary entity."""
    # Model with a foreign key pointing to nowhere
    orders = Model(
        name="orders",
        table="orders_tbl",
        primary_key="id",
        entities=[
            Entity("order", EntityType.PRIMARY, "id"),
            Entity("non_existent_customer", EntityType.FOREIGN, "cust_id"),
        ],
    )

    validator = RegistryValidation(models={"orders": orders}, entities={}, dimensions={}, measures={})

    with pytest.raises(RegistryValidationError) as exc:
        validator.validate()

    assert "must reference an existing primary entity" in str(exc.value)
    assert "non_existent_customer" in str(exc.value)


def test_identical_models():
    """Test Rule 4: Two identical models pointing to the same table."""
    model1 = Model(
        name="model1",
        table="common_table",
        primary_key="id",
        dimensions=[Dimension("dim1", "col1", "string")],
        entities=[Entity("ent1", EntityType.PRIMARY, "id")],
    )

    model2 = Model(
        name="model2",
        table="common_table",
        primary_key="id",
        dimensions=[Dimension("dim1", "col1", "string")],
        entities=[Entity("ent1", EntityType.PRIMARY, "id")],
    )

    validator = RegistryValidation(models={"model1": model1, "model2": model2}, entities={}, dimensions={}, measures={})

    with pytest.raises(RegistryValidationError) as exc:
        validator.validate()

    assert "Two identical models pointing to the same table" in str(exc.value)


def test_duplicate_primary_entities_global():
    """Test Rule 5: A Primary Entity Name must be globally unique."""
    # Two models (can be same or different table) defining the same primary entity name
    model_a = Model(
        name="model_a",
        table="users_table_a",
        primary_key="id",
        entities=[Entity("user", EntityType.PRIMARY, "id")],
    )

    model_b = Model(
        name="model_b",
        table="users_table_b",
        primary_key="id",
        entities=[Entity("user", EntityType.PRIMARY, "id")],
        measures=[Measure("some_measure", "sum", "col")],
    )

    validator = RegistryValidation(
        models={"model_a": model_a, "model_b": model_b}, entities={}, dimensions={}, measures={}
    )

    with pytest.raises(RegistryValidationError) as exc:
        validator.validate()

    assert "Ambiguous Concept Ownership" in str(exc.value)
    assert "user" in str(exc.value)


def test_duplicate_measures():
    """Test Rule 7: Same measure name not allowed in multiple models."""
    model_a = Model(
        name="sales_na",
        table="sales_na",
        primary_key="id",
        entities=[Entity("sales_na", EntityType.PRIMARY, "id")],
        measures=[Measure("total_revenue", "sum", "rev")],
    )

    model_b = Model(
        name="sales_eu",
        table="sales_eu",
        primary_key="id",
        entities=[Entity("sales_eu", EntityType.PRIMARY, "id")],
        measures=[Measure("total_revenue", "sum", "rev")],  # Duplicate metric name
    )

    validator = RegistryValidation(
        models={"model_a": model_a, "model_b": model_b}, entities={}, dimensions={}, measures={}
    )

    # Note: The code raises RegistryError, not RegistryValidationError specifically for this rule
    with pytest.raises(RegistryError) as exc:
        validator.validate()

    assert "Same measure name not allowed" in str(exc.value)
    assert "total_revenue" in str(exc.value)


def test_duplicate_dimensions():
    """Test Rule 8: Same dimension name not allowed in multiple models."""
    model_a = Model(
        name="sales_na",
        table="sales_na",
        primary_key="id",
        entities=[Entity("sales_na", EntityType.PRIMARY, "id")],
        dimensions=[Dimension("country", "country_col", "string")],
    )

    model_b = Model(
        name="sales_eu",
        table="sales_eu",
        primary_key="id",
        entities=[Entity("sales_eu", EntityType.PRIMARY, "id")],
        dimensions=[Dimension("country", "country_col", "string")],  # Duplicate dimension name
    )

    validator = RegistryValidation(
        models={"model_a": model_a, "model_b": model_b}, entities={}, dimensions={}, measures={}
    )

    with pytest.raises(RegistryValidationError) as exc:
        validator.validate()

    assert "Same dimension name not allowed" in str(exc.value)
    assert "country" in str(exc.value)
