"""Dimension validation module for semantic modeling.

This module provides validation rules for dimensions in a semantic model,
ensuring data integrity and correctness of dimension definitions.
"""

from typing import TYPE_CHECKING

from pysemantic.exceptions import (
    NamingCollisionError,
    ValidationError,
    format_error,
)
from pysemantic.modeling.dimension import Dimension

from .common.validation_constants import (
    ALL_RESERVED_WORDS,
    VALID_DIMENSION_DTYPES,
    VALID_IDENTIFIER_PATTERN,
)

if TYPE_CHECKING:
    from pysemantic.modeling.model import Model


class DimensionValidationError(ValidationError):
    """Custom exception for dimension validation errors."""

    DOMAIN = "validation.dimensions"

    def __init__(self, summary: str, **context):
        super().__init__(format_error(self.DOMAIN, summary, **context))


class DimensionValidation:
    """Validates dimensions in a semantic model according to business rules.

    Validation Rules:
        1. Dimension names must be valid identifiers (no spaces, no symbols,
           no Python reserved words, no SQL keywords).
           Example Good: "product_id", "region"
           Example Bad: "product id", "select", "from"

        2. Unique dimension names (no duplicate dimension names within a model).

        3. dtype must be a supported data type.
           Supported types: string, int, float, boolean, date, datetime
           Example Good: "string", "int", "date"
           Example Bad: "text", "number", "timestamp"

        4. No naming collisions with entities, measures, or time columns.
           Example Bad: "region" dimension (if "region" is already an entity,
           measure, or time column)

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

    def _get_dimension_names(self) -> set[str]:
        """Get all dimension names from the model.

        Returns:
            Set of dimension names
        """
        return {dimension.name for dimension in self.model.dimensions}

    def _validate_name_is_valid_identifier(self, dimension: Dimension) -> None:
        """Rule 1: Dimension names must be valid identifiers.

        Validates that the dimension name follows Python identifier rules and
        is not a Python reserved word or SQL keyword:
        - No spaces
        - No special symbols (except underscore)
        - Not a Python reserved word
        - Not a SQL keyword
        - Starts with letter or underscore

        Args:
            dimension: The Dimension instance to validate

        Raises:
            DimensionValidationError: If the dimension name is not a valid identifier
        """
        if not self._is_valid_identifier(dimension.name):
            # Check if it's a reserved word to provide better error message
            if dimension.name in ALL_RESERVED_WORDS:
                message = (
                    "Dimension name cannot be a reserved word or SQL keyword. "
                    f"Invalid name: '{dimension.name}'"
                )
                raise DimensionValidationError(
                    message,
                    model=self.model.name,
                    dimension=dimension.name,
                )
            message = (
                "Dimension name must be a valid identifier (no spaces, no symbols, "
                "no reserved words, no SQL keywords). "
                f"Invalid name: '{dimension.name}'"
            )
            raise DimensionValidationError(
                message,
                model=self.model.name,
                dimension=dimension.name,
            )

    def _validate_no_duplicate_dimension_names(self) -> None:
        """Rule 2: No duplicate dimension names.

        Ensures that each dimension has a unique name within the model.
        Duplicate names would cause ambiguity in queries.

        Raises:
            DimensionValidationError: If there are duplicate dimension names
        """
        dimension_names = [dimension.name for dimension in self.model.dimensions]
        seen = set()
        duplicates = []

        for name in dimension_names:
            if name in seen:
                duplicates.append(name)
            seen.add(name)

        if duplicates:
            unique_duplicates = list(set(duplicates))
            message = (
                "A Model cannot define duplicate dimension names. "
                f"Duplicate names: {unique_duplicates}"
            )
            raise NamingCollisionError(
                message,
                model=self.model.name,
                duplicate_dimensions=unique_duplicates,
            )

    def _validate_dtype_is_supported(self, dimension: Dimension) -> None:
        """Rule 3: dtype must be a supported data type.

        Validates that the dimension's data type is one of the supported types:
        string, int, float, boolean, date, datetime

        Args:
            dimension: The Dimension instance to validate

        Raises:
            DimensionValidationError: If the data type is not supported
        """
        if dimension.dtype not in VALID_DIMENSION_DTYPES:
            raise DimensionValidationError(
                "Dimension dtype must be a supported data type. "
                f"Invalid dtype: '{dimension.dtype}'. "
                f"Valid dtypes: {VALID_DIMENSION_DTYPES}",
                model=self.model.name,
                dimension=dimension.name,
                dtype=dimension.dtype,
            )

    def _validate_dimension_name_collisions(self, dimension: Dimension) -> None:
        """Rule 4: No naming collisions with entities, measures, or time columns.

        Ensures that dimension names don't conflict with entity names, measure names,
        or time column names. This prevents ambiguity when referencing fields in queries.

        Example Bad: A dimension named "region" when "region" is already an entity,
        measure, or time column.

        Args:
            dimension: The Dimension instance to validate

        Raises:
            DimensionValidationError: If dimension name conflicts with entity,
            measure, or time column
        """
        entity_names = self._get_entity_names()
        measure_names = self._get_measure_names()
        time_columns = set(self.model.time_columns)
        primary_key = self.model.primary_key

        if dimension.name in entity_names:
            raise NamingCollisionError(
                "Dimension name cannot conflict with entity names.",
                model=self.model.name,
                dimension=dimension.name,
                conflict="entity",
            )

        if dimension.name in measure_names:
            raise NamingCollisionError(
                "Dimension name cannot conflict with measure names.",
                model=self.model.name,
                dimension=dimension.name,
                conflict="measure",
            )

        if dimension.name in time_columns:
            raise NamingCollisionError(
                "Dimension name cannot conflict with time column names.",
                model=self.model.name,
                dimension=dimension.name,
                conflict="time_column",
            )

        if dimension.name == primary_key:
            raise NamingCollisionError(
                "Dimension name cannot conflict with the primary key.",
                model=self.model.name,
                dimension=dimension.name,
                conflict="primary_key",
            )

    def validate(self) -> None:
        """Run all validation rules on the model's dimensions.

        Validates all dimensions in the model according to the 4 validation rules:
        1. Dimension names must be valid identifiers (no space, symbols, SQL keywords)
        2. Unique dimension names
        3. dtype supported (allow: string, int, float, boolean, date, datetime)
        4. No naming collisions (entities/measures/time columns)

        Raises:
            DimensionValidationError: If any validation rule fails
        """
        if not self.model.dimensions:
            # No dimensions to validate
            return

        # Rule 2: Check for duplicates first (applies to all dimensions)
        self._validate_no_duplicate_dimension_names()

        # Validate each dimension individually
        for dimension in self.model.dimensions:
            # Rule 1: Name must be valid identifier
            self._validate_name_is_valid_identifier(dimension)

            # Rule 3: dtype must be supported
            self._validate_dtype_is_supported(dimension)

            # Rule 4: No conflict with entities/measures/time columns
            self._validate_dimension_name_collisions(dimension)
