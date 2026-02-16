import pytest

from pysemantic.modeling import Dimension, Entity, EntityType, Measure, Model
from pysemantic.validation.entity_validation import EntityValidationError


def test_model_initialization_defaults():
    """Test Model initialization with minimal arguments and default values."""
    # Must provide at least one entity to pass validation
    entity = Entity("user", EntityType.PRIMARY, "id")
    model = Model(name="test_model", table="test_table", primary_key="id", entities=[entity])

    assert model.name == "test_model"
    assert model.table == "test_table"
    assert model.primary_key == "id"
    assert model.description == ""
    assert model.dimensions == []
    assert model.measures == []
    assert model.time_columns == []
    assert model.entities == [entity]


def test_model_initialization_full():
    """Test Model initialization with all fields populated."""
    dim = Dimension("dim1")
    measure = Measure("m1", "sum", "col")
    entity = Entity("e1", EntityType.PRIMARY, "id")

    model = Model(
        name="full_model",
        table="full_table",
        primary_key="id",
        description="A full model",
        dimensions=[dim],
        measures=[measure],
        entities=[entity],
        time_columns=["created_at"],
    )

    assert model.description == "A full model"
    assert len(model.dimensions) == 1
    assert model.dimensions[0] == dim
    assert len(model.measures) == 1
    assert model.measures[0] == measure
    assert len(model.entities) == 1
    assert model.entities[0] == entity
    assert model.time_columns == ["created_at"]


def test_model_repr():
    """Test string representation of Model."""
    entity = Entity("e", EntityType.PRIMARY, "id")
    dim = Dimension("d")
    model = Model("m", "t", "id", entities=[entity], dimensions=[dim])

    repr_str = repr(model)
    assert "Model(name='m'" in repr_str
    assert "table='t'" in repr_str
    assert "Dimension(name='d'" in repr_str
    assert "Entity(name='e'" in repr_str


def test_model_validation_empty_entities():
    """Test validation raises error if entities are missing."""
    with pytest.raises(EntityValidationError) as exc:
        Model(
            name="invalid",
            table="tbl",
            primary_key="id",
            entities=[],  # Empty entities should fail
        )
    assert "A Model must declare exactly one primary entity" in str(exc.value)


def test_is_valid_method():
    """Test is_valid() boolean check."""
    entity = Entity("user", EntityType.PRIMARY, "id")
    # Valid model
    model = Model("valid", "t", "id", entities=[entity])
    assert model.is_valid() is True

    # Invalid model (manually constructing or modifying state to bypass init checks if possible,
    # or just checking cases where it returns false)
    # Since init runs validation, constructing an invalid model raises exception.
    # We can check is_valid by modifying attributes after init.

    model.entities = []  # Make it invalid
    assert model.is_valid() is False
