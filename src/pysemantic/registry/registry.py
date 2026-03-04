from __future__ import annotations

from pathlib import Path

from pysemantic.exceptions import RegistryError, format_error
from pysemantic.modeling import Dimension, Entity, EntityType, Measure, Model
from pysemantic.registry.entity_graph import EntityGraph
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

        # LOAD
        loader = self._load_objects(resolved_source)

        # VALIDATE
        self._validate_models(loader.models, loader.entities, loader.dimensions, loader.measures)

        # REGISTER MODELS
        self._register_models(loader.models)

        # BUILD ENTITY GRAPH
        self._build_entity_graph()

        self._source_paths.append(str(resolved_source))

    def _reset_state(self) -> None:
        self.models: dict[str, Model] = {}
        # Keeping these for now, we can remove them later, because models dict is enough
        self.entities: dict[str, dict[str, Entity]] = {}
        self.dimensions: dict[str, dict[str, Dimension]] = {}
        self.measures: dict[str, dict[str, Measure]] = {}
        # Metric Index for O(1) Lookup & Uniqueness Check
        self.metric_index: dict[str, str] = {}
        # Key: Primary Entity Name (e.g. 'region')
        # Value: Model Name (e.g. 'regions')
        self.primary_entity_map: dict[str, str] = {}
        # Entity Graph for join path
        self.graph = EntityGraph()

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
        for model in models.values():
            if model.name in self.models:
                raise RegistryError(
                    format_error(
                        "registry.registry",
                        "Duplicate model detected during registration",
                        model=model.name,
                    )
                )

            self.models[model.name] = model

            # Populate Metric Index (Crucial for parsing)
            for measure in model.measures:
                if measure.name in self.metric_index:
                    existing_model = self.metric_index[measure.name]
                    raise RegistryError(
                        format_error(
                            "registry",
                            f"Ambiguous Metric '{measure.name}'",
                            details=f"Defined in both '{existing_model}' and '{model.name}'",
                        )
                    )
                self.metric_index[measure.name] = model.name

            for entity in model.entities:
                if entity.entity_type == EntityType.PRIMARY:
                    if entity.name in self.primary_entity_map:
                        existing_model = self.primary_entity_map[entity.name]
                        raise RegistryError(
                            f"Duplicate Primary Entity: '{entity.name}' is defined as PRIMARY in both "
                            f"'{existing_model}' and '{model.name}'. A concept can only have one owner."
                        )
                    self.primary_entity_map[entity.name] = model.name

            self.entities[model.name] = {}
            self.dimensions[model.name] = {}
            self.measures[model.name] = {}

            for entity in model.entities or []:
                self.entities[model.name][entity.name] = entity

            for dimension in model.dimensions:
                self.dimensions[model.name][dimension.name] = dimension

            for measure in model.measures:
                self.measures[model.name][measure.name] = measure

    def _build_entity_graph(self):
        """
        Constructs the join graph from the registered models.
        """
        # Add all models as nodes
        for model_name in self.models:
            self.graph.add_node(model_name)

        # Add all relationships as edges
        for model in self.models.values():
            for entity in model.entities:
                if entity.entity_type == EntityType.FOREIGN:
                    # 1. Get the name of the foreign entity (e.g., 'region')
                    foreign_entity_name = entity.name

                    # 2. Lookup which model owns 'region' as a PRIMARY entity
                    target_model_name = self.primary_entity_map.get(foreign_entity_name)

                    if not target_model_name:
                        raise RegistryError(
                            format_error(
                                "registry.graph",
                                f"Broken Reference: Could not find a primary model for foreign key "
                                f"'{foreign_entity_name}' in model '{model.name}'.",
                                details="Ensure the referenced entity is defined as a PRIMARY entity in another model.",
                            )
                        )

                    target_model = self.models[target_model_name]

                    # Add Edge: Child (Foreign) -> Parent (Primary)
                    self.graph.add_edge(
                        from_model=model.name,
                        to_model=target_model_name,
                        join_on={"left": entity.column, "right": target_model.primary_key},
                    )
        self.graph.validate()

    def get_model_by_metric(self, metric_name: str) -> Model:
        if metric_name not in self.metric_index:
            raise RegistryError(
                format_error(
                    "registry.registry",
                    "Metric not found",
                    metric=metric_name,
                )
            )
        model_name = self.metric_index[metric_name]
        return self.models[model_name]

    def get_join_path(self, start_model: str, end_model: str):
        return self.graph.get_join_path(start_model, end_model)

    def generate_graph(self, output_file: str = "entity_graph.html", dark_mode: bool = True) -> None:
        self.graph.visualize_graph(output_file=output_file, dark_mode=dark_mode, models=self.models)
