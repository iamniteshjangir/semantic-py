from pysemantic.exceptions import RegistryError, format_error
from pysemantic.modeling import Dimension, Entity, Measure, Model
from pysemantic.modeling.entity import EntityType


class RegistryValidationError(RegistryError):
    """Custom exception for registry validation errors."""

    DOMAIN = "validation.registry"

    def __init__(self, summary: str, **context):
        super().__init__(format_error(self.DOMAIN, summary, **context))


class RegistryValidation:
    """Validates the registry according to business rules.
    Validation Rules:
        1. No duplicate model names.
        2. Foreign entity must reference an existing model.
           Foreign Entity Must Match Primary Entity name in other models.
        3. Two identical models pointing to the same tables with same model definitions are not allowed.
        4. Two PRIMARY entities with same name across two models.
           for eg. Same entity name "customer" defined as PRIMARY in two models not allowed
        5. Same metric name not allowed in multiple models
        6. Same dimension name not allowed in multiple models
    """

    def __init__(
        self,
        models: dict[str, Model],
        entities: dict[str, Entity],
        dimensions: dict[str, Dimension],
        measures: dict[str, Measure],
    ) -> None:
        self.models = models
        self.entities = entities
        self.dimensions = dimensions
        self.measures = measures

    def _validate_no_duplicate_model_names(self) -> None:
        """Rule 1: No duplicate model names."""
        seen = set()
        for name in self.models.keys():
            if name in seen:
                message = f"A Model cannot have duplicate names. Duplicate names: {name}"
                raise RegistryValidationError(
                    message,
                    model=name,
                    duplicate_models=name,
                )
            seen.add(name)

    def _validate_foreign_entities_cross_model(self) -> None:
        """Rule 2: Foreign entity must reference an existing model.
        Foreign Entity Must Match Primary Entity name in other models."""
        # Build a map of primary entity names to their models
        primary_entity_to_model: dict[str, str] = {}
        for model_name, model in self.models.items():
            if model.entities:
                for entity in model.entities:
                    if entity.entity_type == EntityType.PRIMARY:
                        primary_entity_to_model[entity.name] = model_name

        # Check all foreign entities
        for model_name, model in self.models.items():
            if model.entities:
                for entity in model.entities:
                    if entity.entity_type == EntityType.FOREIGN:
                        if entity.name not in primary_entity_to_model:
                            message = (
                                f"Foreign entity '{entity.name}' in model '{model_name}' "
                                f"must reference an existing primary entity in another model. "
                                f"No model found with a primary entity named '{entity.name}'."
                            )
                            raise RegistryValidationError(
                                message,
                                model=model_name,
                                foreign_entity=entity.name,
                            )

    def _validate_no_identical_models(self) -> None:
        """Rule 3: Two identical models pointing to the same tables with same model definitions are not allowed."""
        model_list = list(self.models.values())

        for i, model1 in enumerate(model_list):
            for model2 in model_list[i + 1 :]:
                if model1.table == model2.table:
                    # Check if they have identical definitions
                    if self._are_models_identical(model1, model2):
                        message = (
                            f"Two identical models pointing to the same table '{model1.table}' "
                            f"with same model definitions are not allowed. "
                            f"Models: '{model1.name}' and '{model2.name}'"
                        )
                        raise RegistryValidationError(
                            message,
                            table=model1.table,
                            model1=model1.name,
                            model2=model2.name,
                        )

    def _are_models_identical(self, model1: Model, model2: Model) -> bool:
        """Check if two models have identical definitions."""
        # Check dimensions
        dim1_sorted = sorted([(d.name, d.dtype) for d in model1.dimensions])
        dim2_sorted = sorted([(d.name, d.dtype) for d in model2.dimensions])
        if dim1_sorted != dim2_sorted:
            return False

        # Check measures
        measure1_sorted = sorted([(m.name, m.agg, m.column) for m in model1.measures])
        measure2_sorted = sorted([(m.name, m.agg, m.column) for m in model2.measures])
        if measure1_sorted != measure2_sorted:
            return False

        # Check entities
        entity1_sorted = sorted([(e.name, e.entity_type, e.column) for e in (model1.entities or [])])
        entity2_sorted = sorted([(e.name, e.entity_type, e.column) for e in (model2.entities or [])])
        if entity1_sorted != entity2_sorted:
            return False

        # Check time columns
        time1_sorted = sorted(model1.time_columns)
        time2_sorted = sorted(model2.time_columns)
        if time1_sorted != time2_sorted:
            return False

        # Check primary key
        if model1.primary_key != model2.primary_key:
            return False

        return True

    def _validate_no_duplicate_primary_entities(self) -> None:
        """
        Rule 4: A Primary Entity Name must be globally unique across the entire registry.

        Why: The Entity Name acts as the 'Node ID' in the Join Graph. If two models
        both claim to be the Primary owner of 'user', the graph becomes ambiguous
        (we don't know which table to join to when someone asks for 'user').
        """
        # Map to track ownership: { 'entity_name': 'model_name_that_owns_it' }
        primary_owner_map: dict[str, str] = {}

        for model_name, model in self.models.items():
            if not model.entities:
                continue

            for entity in model.entities:
                if entity.entity_type == EntityType.PRIMARY:
                    # Check if this concept is already owned by another model
                    if entity.name in primary_owner_map:
                        existing_owner = primary_owner_map[entity.name]

                        message = (
                            f"Ambiguous Concept Ownership: The primary entity '{entity.name}' "
                            f"is claimed by multiple models: ['{existing_owner}', '{model_name}']. "
                            f"A concept can have only one primary owner."
                        )

                        raise RegistryValidationError(
                            message,
                            entity=entity.name,
                            conflicting_models=[existing_owner, model_name],
                            hint=(
                                f"If these are role-playing dimensions (e.g. Buyer vs Seller), "
                                f"rename the entities to unique concepts like "
                                f"'{entity.name}_buyer' and '{entity.name}_seller'."
                            ),
                        )

                    # Register ownership
                    primary_owner_map[entity.name] = model_name

    def _validate_no_duplicate_measures_across_models(self) -> None:
        """Rule 5: Same measure name not allowed in multiple models"""
        visited = set()
        for model in self.models.values():
            for measure in model.measures:
                if measure.name in visited:
                    message = f"Same measure name not allowed in multiple models. Measure: {measure.name}"
                    raise RegistryValidationError(
                        message,
                        measure=measure.name,
                    )
                visited.add(measure.name)

    def _validate_no_duplicate_dimensions_across_models(self) -> None:
        """
        TODO: In V2, Dimensions are attributes of a specific model. Users typically query them with context or
        the Planner finds them attached to the root. The Planner logic should be:
        1. Identify Root Model (from measures).
        2. Check if Dimension exists in Root Model.
        3. If not, check if Dimension exists in any reachable Joined Model.
        4. If found in multiple joined models, raise AmbiguousDimensionError.

        Rule 6: Same dimensions name not allowed in multiple models
        """
        visited = set()
        for model in self.models.values():
            for dimension in model.dimensions:
                if dimension.name in visited:
                    message = f"Same dimension name not allowed in multiple models. Dimension: {dimension.name}"
                    raise RegistryValidationError(
                        message,
                        dimension=dimension.name,
                    )
                visited.add(dimension.name)

    def validate(self) -> None:
        self._validate_no_duplicate_model_names()
        self._validate_foreign_entities_cross_model()
        self._validate_no_identical_models()
        self._validate_no_duplicate_primary_entities()
        self._validate_no_duplicate_measures_across_models()
        self._validate_no_duplicate_dimensions_across_models()
