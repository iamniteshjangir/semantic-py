from __future__ import annotations

from pathlib import Path

from pysemantic.exceptions import RegistryError, format_error
from pysemantic.modeling import Dimension, Entity, Measure, Model
from pysemantic.registry.loader import ModuleLoader
from pysemantic.validation.registry.validation import RegistryValidation


class Registry:
    """
    Centralized registry for semantic layer objects. Loads raw metadata, validates it, and populates stores.
    Acts as the single source of truth for:
    - Parser
    - Entity Graph
    - Grain Graph
    - Query Builder
    """

    def __init__(self) -> None:
        self._reset_state()
        self._source_paths: list[str] = []

    def initialize(self, source_path: str | Path) -> None:
        """
        Initialize the registry by loading the raw metadata from the source path.

        Args:
            source_path: Directory that contains semantic model definitions.
        """
        resolved_source = Path(source_path).resolve()
        self._reset_state()
        self._source_paths = []

        loader = self._load_objects(resolved_source)
        self._validate_models(loader.models, loader.entities, loader.dimensions, loader.measures)
        print("loader.models", loader.models)
        print("--------------------------------")
        for model in loader.models.values():
            print(f"Model: {model.name}")
            print(f"Entities: {model.entities}")
            print(f"Dimensions: {model.dimensions}")
            print(f"Measures: {model.measures}")
            print(f"Time Columns: {model.time_columns}")
            print("--------------------------------")
        print("loader.entities", loader.entities)
        print("--------------------------------")
        print("loader.dimensions", loader.dimensions)
        print("--------------------------------")
        print("loader.measures", loader.measures)
        print("--------------------------------")
        # self._register_models(validated_models)
        # self._source_paths.append(str(resolved_source))

    def _reset_state(self) -> None:
        self.models: dict[str, Model] = {}
        self.entities: dict[str, dict[str, Entity]] = {}
        self.dimensions: dict[str, dict[str, Dimension]] = {}
        self.measures: dict[str, dict[str, Measure]] = {}

    def _load_objects(self, source_path: Path) -> ModuleLoader:
        """Load and return semantic objects from the provided source path."""
        loader = ModuleLoader(source_path)
        loader.load_objects()
        return loader

    def _validate_models(
        self,
        models: dict[str, Model],
        entities: dict[str, Entity],
        dimensions: dict[str, Dimension],
        measures: dict[str, Measure],
    ) -> None:
        """
        Validate all models.

        Args:
            models: Dictionary of Model instances to validate.
            entities: Dictionary of Entity instances to validate.
            dimensions: Dictionary of Dimension instances to validate.
            measures: Dictionary of Measure instances to validate.
        """
        validator = RegistryValidation(models, entities, dimensions, measures)
        validator.validate()

    def _register_models(self, models: dict[str, Model]) -> None:
        """
        Register models and extract their dimensions, measures, and entities.

        Indexes all models, dimensions, measures, and entities in the registry.

        Args:
            models: List of validated Model instances to register.
        """
        for model in models:
            self._register_model(model)

    def _register_model(self, model: Model) -> None:
        if model.name in self.models:
            raise RegistryError(
                format_error(
                    "registry.registry",
                    "Duplicate model detected during registration",
                    model=model.name,
                )
            )

        self.models[model.name] = model
        self.entities[model.name] = {}
        self.dimensions[model.name] = {}
        self.measures[model.name] = {}

        for entity in model.entities or []:
            self.entities[model.name][entity.name] = entity

        for dimension in model.dimensions:
            self.dimensions[model.name][dimension.name] = dimension

        for measure in model.measures:
            self.measures[model.name][measure.name] = measure
