from unittest.mock import patch

import pytest

from pysemantic.exceptions import RegistryError
from pysemantic.modeling import Entity, EntityType, Model
from pysemantic.registry.registry import Registry


@pytest.fixture
def mock_loader():
    start_patch = patch("pysemantic.registry.registry.ModuleLoader")
    mock_class = start_patch.start()
    mock_instance = mock_class.return_value

    # Setup default return values for the loader
    mock_instance.models = {}
    mock_instance.entities = {}
    mock_instance.dimensions = {}
    mock_instance.measures = {}

    yield mock_instance
    start_patch.stop()


@pytest.fixture
def registry():
    return Registry()


def test_registry_initialization(registry):
    """Test standard initialization."""
    assert registry.models == {}
    assert registry.entities == {}
    assert registry.dimensions == {}
    assert registry.measures == {}


def test_initialize_loads_and_validates(registry, mock_loader):
    """Test initialize method calls loader and validation."""
    # Setup mock data
    model = Model("test_model", "test_table", "id", entities=[Entity("e", EntityType.PRIMARY, "id")])
    mock_loader.models = {"test_model": model}
    mock_loader.entities = {}  # Simplified

    with patch("pysemantic.registry.registry.RegistryValidation") as mock_validator_class:
        mock_validator = mock_validator_class.return_value

        registry.initialize("some/path")

        # Verify loader was called
        mock_loader.load_objects.assert_called_once()

        # Verify validation was run
        mock_validator_class.assert_called_once()
        mock_validator.validate.assert_called_once()


def test_register_model_populates_dicts(registry):
    """Test internal _register_model logic."""
    # Note: _register_model is commented out in initialize() currently,
    # but we should test it as it's part of the class API invoked presumably after validation?
    # Actually based on the code provided:
    # # self._register_models(validated_models)
    # It is commented out in initialize().
    # But let's test the method itself in case it's used elsewhere or enabled later.

    model = Model(
        name="test_model",
        table="test_table",
        primary_key="id",
        entities=[Entity("user", EntityType.PRIMARY, "id")],
    )

    registry._register_model(model)

    assert "test_model" in registry.models
    assert registry.models["test_model"] == model
    assert "user" in registry.entities["test_model"]


def test_register_duplicate_model_raises_error(registry):
    """Test that registering duplicate model names raises RegistryError."""
    model = Model(
        name="test_model",
        table="test_table",
        primary_key="id",
        entities=[Entity("user", EntityType.PRIMARY, "id")],
    )

    registry._register_model(model)

    with pytest.raises(RegistryError) as exc:
        registry._register_model(model)

    assert "Duplicate model detected" in str(exc.value)


def test_reset_state(registry):
    """Test _reset_state clears all dicts."""
    registry.models["foo"] = "bar"
    registry._reset_state()
    assert registry.models == {}
