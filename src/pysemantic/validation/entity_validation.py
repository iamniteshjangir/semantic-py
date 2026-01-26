"""Entity validation module for semantic modeling.

This module provides validation rules for entities in a semantic model,
ensuring data integrity and correctness of entity definitions.
"""

from typing import TYPE_CHECKING

from pysemantic.exceptions import (
    NamingCollisionError,
    ValidationError,
    format_error,
)
from pysemantic.modeling.entity import Entity, EntityType

from .common.validation_constants import RESERVED_WORDS, VALID_IDENTIFIER_PATTERN

if TYPE_CHECKING:
    from pysemantic.modeling.model import Model


class EntityValidationError(ValidationError):
    """Custom exception for entity validation errors."""

    DOMAIN = "validation.entities"

    def __init__(self, summary: str, **context):
        super().__init__(format_error(self.DOMAIN, summary, **context))


class EntityValidation:
    """Validates entities in a semantic model according to business rules.

    Validation Rules:
        1. A Model must declare exactly one primary entity.
        2. Primary entity column must match the model's primary key.
        3. Entity name must be a valid identifier (no spaces, no symbols, no reserved words).
        4. A model cannot have a foreign entity with the same name as its primary entity.
        5. A model cannot define duplicate entity names.
        6. No conflict with dimensions/entities/measures/time columns/primary key.
    Args:
        model: The Model instance to validate
    """

    def __init__(self, model: "Model"):
        self.model = model

    def _get_primary_entity(self) -> Entity | None:
        """Get the primary entity from the model.

        Returns:
            The primary entity if found, None otherwise
        """
        primary_entities = [entity for entity in self.model.entities if entity.entity_type == EntityType.PRIMARY]
        return primary_entities[0] if primary_entities else None

    def _validate_exactly_one_primary_entity(self) -> None:
        """Rule 1: A Model must declare exactly one primary entity.

        Raises:
            EntityValidationError: If there is not exactly one primary entity
        """
        primary_entities = [entity for entity in self.model.entities if entity.entity_type == EntityType.PRIMARY]

        count = len(primary_entities)
        if count == 0:
            raise EntityValidationError(
                "A Model must declare exactly one primary entity. Found 0 primary entities.",
                model=self.model.name,
                found_primary=count,
            )
        if count > 1:
            primary_names = [e.name for e in primary_entities]
            raise EntityValidationError(
                f"A Model must declare exactly one primary entity. Found {count} primary entities: {primary_names}",
                model=self.model.name,
                primary_entities=primary_names,
            )

    def _validate_primary_entity_column_matches_primary_key(self) -> None:
        """Rule 2: Primary entity column must match the model's primary key.

        Raises:
            EntityValidationError: If the primary entity column doesn't match the primary key
        """
        primary_entity = self._get_primary_entity()
        if primary_entity is None:
            return  # This will be caught by rule 1

        if primary_entity.column != self.model.primary_key:
            raise EntityValidationError(
                f"Primary entity column '{primary_entity.column}' must match "
                f"the model's primary key '{self.model.primary_key}'.",
                model=self.model.name,
                column=primary_entity.column,
                primary_key=self.model.primary_key,
            )

    def _is_valid_identifier(self, name: str) -> bool:
        """Check if a name is a valid Python identifier.

        Args:
            name: The name to validate

        Returns:
            True if the name is a valid identifier, False otherwise
        """
        if not name:
            return False
        if name in RESERVED_WORDS:
            return False
        return bool(VALID_IDENTIFIER_PATTERN.match(name))

    def _validate_entity_names_are_valid_identifiers(self) -> None:
        """Rule 3: Entity name must be a valid identifier.

        Raises:
            EntityValidationError: If any entity name is invalid
        """
        invalid_entities = []
        for entity in self.model.entities:
            if not self._is_valid_identifier(entity.name):
                invalid_entities.append(entity.name)

        if invalid_entities:
            raise EntityValidationError(
                "Entity names must be valid identifiers (no spaces, no symbols, "
                "no reserved words). "
                f"Invalid names: {invalid_entities}",
                model=self.model.name,
                invalid_entities=invalid_entities,
            )

    def _validate_no_foreign_entity_same_name_as_primary(self) -> None:
        """Rule 4: A model cannot have a foreign entity with the same name as its primary entity.

        Raises:
            EntityValidationError: If a foreign entity has the same name as the primary entity
        """
        primary_entity = self._get_primary_entity()
        if primary_entity is None:
            return  # This will be caught by rule 1

        conflicting_entities = [
            entity
            for entity in self.model.entities
            if entity.entity_type == EntityType.FOREIGN and entity.name == primary_entity.name
        ]

        if conflicting_entities:
            raise EntityValidationError(
                "A Model cannot have a foreign entity with the same name as its primary entity.",
                model=self.model.name,
                primary_entity=primary_entity.name,
            )

    def _validate_no_duplicate_entity_names(self) -> None:
        """Rule 5: A model cannot define duplicate entity names.

        Raises:
            EntityValidationError: If there are duplicate entity names
        """
        entity_names = [entity.name for entity in self.model.entities]
        seen = set()
        duplicates = []

        for name in entity_names:
            if name in seen:
                duplicates.append(name)
            seen.add(name)

        if duplicates:
            unique_duplicates = list(set(duplicates))
            message = f"A Model cannot define duplicate entity names. Duplicate names: {unique_duplicates}"
            raise NamingCollisionError(
                message,
                model=self.model.name,
                duplicate_entities=unique_duplicates,
            )

    def _validate_entity_name_collisions(self) -> None:
        """Ensure entity names do not collide with other semantic objects."""
        dimension_names = {dimension.name for dimension in self.model.dimensions}
        measure_names = {measure.name for measure in self.model.measures}
        time_columns = set(self.model.time_columns)
        primary_key = self.model.primary_key

        for entity in self.model.entities:
            name = entity.name
            if name in dimension_names:
                raise NamingCollisionError(
                    "Entity name cannot match a dimension name.",
                    model=self.model.name,
                    entity=name,
                    conflict="dimension",
                )
            if name in measure_names:
                raise NamingCollisionError(
                    "Entity name cannot match a measure name.",
                    model=self.model.name,
                    entity=name,
                    conflict="measure",
                )
            if name in time_columns:
                raise NamingCollisionError(
                    "Entity name cannot match a time column name.",
                    model=self.model.name,
                    entity=name,
                    conflict="time_column",
                )
            if name == primary_key:
                raise NamingCollisionError(
                    "Entity name cannot match the model's primary key.",
                    model=self.model.name,
                    entity=name,
                    conflict="primary_key",
                )

    def validate(self) -> None:
        """Run all validation rules on the model's entities.

        Raises:
            EntityValidationError: If any validation rule fails
        """
        # Only validate if there are entities
        if not self.model.entities:
            raise EntityValidationError(
                "A Model must declare exactly one primary entity. No entities found.",
                model=self.model.name,
            )

        # Run all validation rules
        self._validate_exactly_one_primary_entity()
        self._validate_primary_entity_column_matches_primary_key()
        self._validate_entity_names_are_valid_identifiers()
        self._validate_no_foreign_entity_same_name_as_primary()
        self._validate_no_duplicate_entity_names()
        self._validate_entity_name_collisions()
