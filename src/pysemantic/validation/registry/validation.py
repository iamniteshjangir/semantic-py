from pysemantic.modeling import Model, Entity, Dimension, Measure
from pysemantic.exceptions import RegistryError, format_error
from pysemantic.modeling.entity import EntityType
from pysemantic.validation.common.validation_constants import GRAIN_KEYWORDS

class RegistryValidationError(RegistryError):
    """Custom exception for registry validation errors."""

    DOMAIN = "validation.registry"

    def __init__(self, summary: str, **context):
        super().__init__(format_error(self.DOMAIN, summary, **context))

class RegistryValidation:
    """Validates the registry according to business rules.
    Validation Rules:
        1. No duplicate model names.
        2. Foreign entity must reference an existing model. Foreign Entity Must Match Primary Entity name in other models.
        3. No circular entities like A→B and B→A.
        4. Two identical models pointing to the same tables with same model definitions are not allowed.
        5. Two models using same table name but for different grains (hourly, daily, monthly, yearly) not allowed.
        6. Two PRIMARY entities with same name across two models with same table are not allowed. for eg. Same entity name "customer" defined as PRIMARY in two models not allowed
    """

    def __init__(self, models: dict[str, Model], entities: dict[str, Entity], dimensions: dict[str, Dimension], measures: dict[str, Measure]) -> None:
        self.models = models
        self.entities = entities
        self.dimensions = dimensions
        self.measures = measures
    
    def _validate_no_duplicate_model_names(self) -> None:
        """Rule 1: No duplicate model names."""
        model_names = list(self.models.keys())
        seen = set()
        for name in model_names:
            if name in seen:
                message = (
                    "A Model cannot have duplicate names. "
                    f"Duplicate names: {name}"
                )
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
    
    def _validate_no_circular_entities(self) -> None:
        """Rule 3: No circular entities like A→B and B→A."""
        # Build a graph: model_name -> set of models it references via foreign entities
        model_references: dict[str, set[str]] = {}
        primary_entity_to_model: dict[str, str] = {}
        
        # First, build map of primary entity names to their models
        for model_name, model in self.models.items():
            if model.entities:
                for entity in model.entities:
                    if entity.entity_type == EntityType.PRIMARY:
                        primary_entity_to_model[entity.name] = model_name
        
        # Build the reference graph
        for model_name, model in self.models.items():
            model_references[model_name] = set()
            if model.entities:
                for entity in model.entities:
                    if entity.entity_type == EntityType.FOREIGN:
                        if entity.name in primary_entity_to_model:
                            referenced_model = primary_entity_to_model[entity.name]
                            if referenced_model != model_name:  # Don't count self-references
                                model_references[model_name].add(referenced_model)

        # Check for cycles using DFS
        def has_cycle(node: str, visited: set[str], rec_stack: set[str]) -> bool:
            visited.add(node)
            rec_stack.add(node)
            
            for neighbor in model_references.get(node, set()):
                if neighbor not in visited:
                    if has_cycle(neighbor, visited, rec_stack):
                        return True
                elif neighbor in rec_stack:
                    # Found a back edge, cycle detected
                    return True
            
            rec_stack.remove(node)
            return False
        
        visited = set()
        for model_name in self.models.keys():
            if model_name not in visited:
                if has_cycle(model_name, visited, set()):
                    # Find the cycle path for better error message
                    cycle_path = self._find_cycle_path(model_references)
                    message = (
                        f"Circular entity references detected. "
                        f"Models form a cycle: {' → '.join(cycle_path)}"
                    )
                    raise RegistryValidationError(
                        message,
                        cycle_path=cycle_path,
                    )
    
    def _find_cycle_path(self, model_references: dict[str, set[str]]) -> list[str]:
        """Helper to find a cycle path for error reporting."""
        visited = set()
        
        def dfs(node: str, path: list[str]) -> tuple[bool, list[str]]:
            if node in path:
                # Found cycle, extract the cycle portion
                cycle_start = path.index(node)
                cycle = path[cycle_start:] + [node]
                return True, cycle
            if node in visited:
                return False, []
            
            visited.add(node)
            path.append(node)
            
            for neighbor in model_references.get(node, set()):
                found, cycle = dfs(neighbor, path)
                if found:
                    return True, cycle
            
            path.pop()
            return False, []
        
        for model_name in self.models.keys():
            if model_name not in visited:
                found, cycle = dfs(model_name, [])
                if found:
                    return cycle
        
        return []
    
    def _validate_no_identical_models(self) -> None:
        """Rule 4: Two identical models pointing to the same tables with same model definitions are not allowed."""
        model_list = list(self.models.values())
        
        for i, model1 in enumerate(model_list):
            for model2 in model_list[i + 1:]:
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
    
    def _validate_no_same_table_different_grains(self) -> None:
        """Rule 5: Two models using same table name but for different grains (hourly, daily, monthly, yearly) not allowed."""
        table_to_models: dict[str, list[Model]] = {}
        
        # Group models by table name
        for model in self.models.values():
            if model.table not in table_to_models:
                table_to_models[model.table] = []
            table_to_models[model.table].append(model)
        
        # Check for same table with different grains
        for table, models in table_to_models.items():
            if len(models) > 1:
                # Extract grain from model names
                model_grains = {}
                for model in models:
                    grain = None
                    model_name_lower = model.name.lower()
                    for g in GRAIN_KEYWORDS:
                        if g in model_name_lower:
                            grain = g
                            break
                    model_grains[model.name] = grain
                
                # Check if there are different grains
                grains_found = [g for g in model_grains.values() if g is not None]
                if len(set(grains_found)) > 1:
                    message = (
                        f"Two models using same table name '{table}' but for different grains "
                        f"are not allowed. Models: {[m.name for m in models]}"
                    )
                    raise RegistryValidationError(
                        message,
                        table=table,
                        models=[m.name for m in models],
                        grains=grains_found,
                    )
    
    def _validate_no_duplicate_primary_entities_same_table(self) -> None:
        """Rule 6: Two PRIMARY entities with same name across two models with same table are not allowed."""
        # Group models by table name
        table_to_models: dict[str, list[Model]] = {}
        for model in self.models.values():
            if model.table not in table_to_models:
                table_to_models[model.table] = []
            table_to_models[model.table].append(model)
        
        # Check for duplicate primary entities in models with same table
        for table, models in table_to_models.items():
            if len(models) > 1:
                primary_entities_by_name: dict[str, list[str]] = {}
                for model in models:
                    if model.entities:
                        for entity in model.entities:
                            if entity.entity_type == EntityType.PRIMARY:
                                if entity.name not in primary_entities_by_name:
                                    primary_entities_by_name[entity.name] = []
                                primary_entities_by_name[entity.name].append(model.name)
                
                # Check for duplicates
                for entity_name, model_names in primary_entities_by_name.items():
                    if len(model_names) > 1:
                        message = (
                            f"Two PRIMARY entities with same name '{entity_name}' across "
                            f"two models with same table '{table}' are not allowed. "
                            f"Models: {model_names}"
                        )
                        raise RegistryValidationError(
                            message,
                            table=table,
                            entity_name=entity_name,
                            models=model_names,
                        )
    
    def validate(self) -> None:
        self._validate_no_duplicate_model_names()
        self._validate_foreign_entities_cross_model()
        self._validate_no_circular_entities()
        self._validate_no_identical_models()
        self._validate_no_same_table_different_grains()
        self._validate_no_duplicate_primary_entities_same_table()