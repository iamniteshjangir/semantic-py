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


def test_circular_dependency_direct():
    """Test Rule 3: Circular entities (A -> B -> A)."""
    # Model A references B
    model_a = Model(
        name="model_a",
        table="table_a",
        primary_key="id",
        entities=[
            Entity("entity_a", EntityType.PRIMARY, "id"),
            Entity("entity_b", EntityType.FOREIGN, "b_id"),
        ],
    )

    # Model B references A
    model_b = Model(
        name="model_b",
        table="table_b",
        primary_key="id",
        entities=[
            Entity("entity_b", EntityType.PRIMARY, "id"),
            Entity("entity_a", EntityType.FOREIGN, "a_id"),
        ],
    )

    validator = RegistryValidation(
        models={"model_a": model_a, "model_b": model_b}, entities={}, dimensions={}, measures={}
    )

    with pytest.raises(RegistryValidationError) as exc:
        validator.validate()

    assert "Circular entity references detected" in str(exc.value)
    # The cycle path check depends on implementation order, but should contain both
    assert "model_a" in str(exc.value)
    assert "model_b" in str(exc.value)


def test_circular_dependency_self_reference_ignored():
    """
    Test Rule 3: Self-references (A -> A) should NOT be considered circular dependency errors.
    We use mocks because Model() validation prevents creating a model with self-referencing
    foreign/primary entity naming collision, but we want to test the Registry logic specifically.
    """
    mock_model = MagicMock()
    mock_model.name = "model_a"
    mock_model.entities = [
        MagicMock(name="entity_a", entity_type=EntityType.PRIMARY),
        MagicMock(name="entity_a", entity_type=EntityType.FOREIGN),
    ]
    # Configure mocks to return name correctly when accessed as attribute
    mock_model.entities[0].name = "entity_a"
    mock_model.entities[1].name = "entity_a"

    validator = RegistryValidation(models={"model_a": mock_model}, entities={}, dimensions={}, measures={})

    # Should pass without circular dependency error
    # We only care about _validate_no_circular_entities passing
    validator._validate_no_circular_entities()


def test_identical_models():
    """Test Rule 4: Two identical models pointing to the same table."""
    model1 = Model(
        name="model1",
        table="common_table",
        primary_key="id",
        dimensions=[Dimension("dim1", "string")],
        entities=[Entity("ent1", EntityType.PRIMARY, "id")],
    )

    model2 = Model(
        name="model2",
        table="common_table",
        primary_key="id",
        dimensions=[Dimension("dim1", "string")],
        entities=[Entity("ent1", EntityType.PRIMARY, "id")],
    )

    validator = RegistryValidation(models={"model1": model1, "model2": model2}, entities={}, dimensions={}, measures={})

    with pytest.raises(RegistryValidationError) as exc:
        validator.validate()

    assert "Two identical models pointing to the same table" in str(exc.value)


def test_identical_models_subtle_difference():
    """Test that subtly different models on the same table are not ALLOWED (not identical)."""
    model1 = Model(
        name="model1",
        table="common_table",
        primary_key="id",
        dimensions=[Dimension("dim1", "string")],
        entities=[Entity("ent1", EntityType.PRIMARY, "id")],
    )

    # Different dimension name
    model2 = Model(
        name="model2",
        table="common_table",
        primary_key="id",
        dimensions=[Dimension("dim2", "string")],
        entities=[Entity("ent1", EntityType.PRIMARY, "id")],
    )

    validator = RegistryValidation(models={"model1": model1, "model2": model2}, entities={}, dimensions={}, measures={})

    with pytest.raises(RegistryValidationError) as exc:
        validator.validate()
    assert "Two PRIMARY entities with same name" in str(exc.value)


def test_same_table_different_grains():
    """Test Rule 5: Same table but different grains (hourly vs daily)."""
    # Both point to same table but imply different aggregation grains
    sales_daily = Model(
        name="sales_daily",
        table="sales_data",
        primary_key="id",
        entities=[Entity("sales_daily_ent", EntityType.PRIMARY, "id")],
    )

    sales_hourly = Model(
        name="sales_hourly",
        table="sales_data",
        primary_key="id",
        entities=[Entity("sales_hourly_ent", EntityType.PRIMARY, "id")],
    )

    validator = RegistryValidation(
        models={"sales_daily": sales_daily, "sales_hourly": sales_hourly},
        entities={},
        dimensions={},
        measures={},
    )

    with pytest.raises(RegistryValidationError) as exc:
        validator.validate()

    assert "different grains" in str(exc.value)
    assert "sales_data" in str(exc.value)


def test_duplicate_primary_entities_same_table():
    """Test Rule 6: Duplicate primary entity definitions for same table."""
    # Two models on same table, defining the same primary entity
    # Make them non-identical (Rule 4) by adding a measure to one
    model_a = Model(
        name="model_a",
        table="users_table",
        primary_key="id",
        entities=[Entity("user", EntityType.PRIMARY, "id")],
    )

    model_b = Model(
        name="model_b",
        table="users_table",
        primary_key="id",
        entities=[Entity("user", EntityType.PRIMARY, "id")],
        measures=[Measure("some_measure", "sum", "col")],
    )

    validator = RegistryValidation(
        models={"model_a": model_a, "model_b": model_b}, entities={}, dimensions={}, measures={}
    )

    with pytest.raises(RegistryValidationError) as exc:
        validator.validate()

    assert "Two PRIMARY entities with same name 'user' across two models with same table" in str(exc.value)


def test_duplicate_metrics():
    """Test Rule 7: Same metric name not allowed in multiple models."""
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

    assert "Same metric name not allowed in multiple models" in str(exc.value)
    assert "total_revenue" in str(exc.value)
