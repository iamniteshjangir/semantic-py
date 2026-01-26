"""Time column validation module for semantic modeling.

This module provides validation rules for time columns in a semantic model,
ensuring data integrity and correctness of time column definitions.
"""

from typing import TYPE_CHECKING

from pysemantic.exceptions import (
    NamingCollisionError,
    ValidationError,
    format_error,
)

from .common.validation_constants import ALL_RESERVED_WORDS, VALID_IDENTIFIER_PATTERN

if TYPE_CHECKING:
    from pysemantic.modeling.model import Model


class TimeColumnValidationError(ValidationError):
    """Custom exception for time column validation errors."""

    DOMAIN = "validation.time_columns"

    def __init__(self, summary: str, **context):
        super().__init__(format_error(self.DOMAIN, summary, **context))


class TimeColumnValidation:
    """Validates time columns in a semantic model according to business rules.

    Validation Rules:
        1. Time column names must be valid identifiers (no spaces, no symbols,
           no Python reserved words, no SQL keywords).
           Example Good: "created_date", "order_timestamp"
           Example Bad: "created date", "select", "from"

        2. Time columns must be unique (no duplicate time column names within a model).

        3. A time column cannot collide with:
           - Dimension names
           - Entity names
           - Measure names
           - Primary key
           Example Bad: "region" time column (if "region" is already a dimension,
           entity, measure, or the primary key)

    Args:
        model: The Model instance to validate
    """

    def __init__(self, model: "Model"):
        self.model = model

    def _is_valid_identifier(self, name: str) -> bool:
        """Check if a name is a valid Python identifier and not a reserved word.

        Args:
            name: The name to validate

        Returns:
            True if the name is a valid identifier, False otherwise
        """
        if not name:
            return False
        if name in ALL_RESERVED_WORDS:
            return False
        return bool(VALID_IDENTIFIER_PATTERN.match(name))

    def _get_dimension_names(self) -> set[str]:
        """Get all dimension names from the model.

        Returns:
            Set of dimension names
        """
        return {dimension.name for dimension in self.model.dimensions}

    def _get_entity_names(self) -> set[str]:
        """Get all entity names from the model.

        Returns:
            Set of entity names
        """
        return {entity.name for entity in self.model.entities}

    def _get_measure_names(self) -> set[str]:
        """Get all measure names from the model.

        Returns:
            Set of measure names
        """
        return {measure.name for measure in self.model.measures}

    def _validate_time_column_name_is_valid_identifier(self, time_column: str) -> None:
        """Rule 1: Time column names must be valid identifiers.

        Validates that the time column name follows Python identifier rules and
        is not a Python reserved word or SQL keyword:
        - No spaces
        - No special symbols (except underscore)
        - Not a Python reserved word
        - Not a SQL keyword
        - Starts with letter or underscore

        Args:
            time_column: The time column name to validate

        Raises:
            TimeColumnValidationError: If the time column name is not a valid identifier
        """
        if not self._is_valid_identifier(time_column):
            # Check if it's a reserved word to provide better error message
            if time_column in ALL_RESERVED_WORDS:
                message = f"Time column name cannot be a reserved word or SQL keyword. Invalid name: '{time_column}'"
                raise TimeColumnValidationError(
                    message,
                    model=self.model.name,
                    time_column=time_column,
                )
            message = (
                "Time column name must be a valid identifier (no spaces, no symbols, "
                "no reserved words, no SQL keywords). "
                f"Invalid name: '{time_column}'"
            )
            raise TimeColumnValidationError(
                message,
                model=self.model.name,
                time_column=time_column,
            )

    def _validate_no_duplicate_time_columns(self) -> None:
        """Rule 2: Time columns must be unique.

        Ensures that each time column has a unique name within the model.
        Duplicate names would cause ambiguity in queries.

        Raises:
            TimeColumnValidationError: If there are duplicate time column names
        """
        time_columns = self.model.time_columns
        seen = set()
        duplicates = []

        for time_column in time_columns:
            if time_column in seen:
                duplicates.append(time_column)
            seen.add(time_column)

        if duplicates:
            unique_duplicates = list(set(duplicates))
            message = f"A Model cannot define duplicate time column names. Duplicate names: {unique_duplicates}"
            raise NamingCollisionError(
                message,
                model=self.model.name,
                duplicate_time_columns=unique_duplicates,
            )

    def _validate_time_column_name_collisions(self, time_column: str) -> None:
        """Rule 3: A time column cannot collide with dimensions, entities, measures, or primary key.

        Ensures that time column names don't conflict with:
        - Dimension names
        - Entity names
        - Measure names
        - Primary key column name

        This prevents ambiguity when referencing fields in queries.

        Args:
            time_column: The time column name to validate

        Raises:
            TimeColumnValidationError: If time column name conflicts with dimension,
            entity, measure, or primary key
        """
        dimension_names = self._get_dimension_names()
        entity_names = self._get_entity_names()
        measure_names = self._get_measure_names()
        primary_key = self.model.primary_key

        if time_column in dimension_names:
            raise NamingCollisionError(
                "Time column name cannot conflict with dimension names.",
                model=self.model.name,
                time_column=time_column,
                conflict="dimension",
            )

        if time_column in entity_names:
            raise NamingCollisionError(
                "Time column name cannot conflict with entity names.",
                model=self.model.name,
                time_column=time_column,
                conflict="entity",
            )

        if time_column in measure_names:
            raise NamingCollisionError(
                "Time column name cannot conflict with measure names.",
                model=self.model.name,
                time_column=time_column,
                conflict="measure",
            )

        if time_column == primary_key:
            raise NamingCollisionError(
                "Time column name cannot conflict with the primary key.",
                model=self.model.name,
                time_column=time_column,
                conflict="primary_key",
            )

    def validate(self) -> None:
        """Run all validation rules on the model's time columns.

        Validates all time columns in the model according to the 3 validation rules:
        1. Time column names must be valid identifiers
        2. Time columns must be unique
        3. A time column cannot collide with (dimension names, entity names,
           measure names, primary key)

        Raises:
            TimeColumnValidationError: If any validation rule fails
        """
        if not self.model.time_columns:
            # No time columns to validate
            return

        # Rule 2: Check for duplicates first (applies to all time columns)
        self._validate_no_duplicate_time_columns()

        # Validate each time column individually
        for time_column in self.model.time_columns:
            # Rule 1: Name must be valid identifier
            self._validate_time_column_name_is_valid_identifier(time_column)

            # Rule 3: No collision with dimensions/entities/measures/primary key
            self._validate_time_column_name_collisions(time_column)
