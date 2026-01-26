"""Measure validation module for semantic modeling.

This module provides validation rules for measures in a semantic model,
ensuring data integrity and correctness of measure definitions.
"""

from typing import TYPE_CHECKING

from pysemantic.exceptions import (
    NamingCollisionError,
    ValidationError,
    format_error,
)
from pysemantic.modeling.entity import EntityType
from pysemantic.modeling.measure import Measure

from .common.validation_constants import (
    RESERVED_WORDS,
    VALID_IDENTIFIER_PATTERN,
    VALID_MEASURE_AGGS,
)

if TYPE_CHECKING:
    from pysemantic.modeling.model import Model


class MeasureValidationError(ValidationError):
    """Custom exception for measure validation errors."""

    DOMAIN = "validation.measures"

    def __init__(self, summary: str, **context):
        super().__init__(format_error(self.DOMAIN, summary, **context))


class MeasureValidation:
    """Validates measures in a semantic model according to business rules.

    Validation Rules:
        1. Name must be valid identifier (no spaces, no symbols, no reserved words).
           Example Good: "total_sales"
           Example Bad: "total sales"

        2. agg must be a known aggregation function.
           Example Good: "sum", "count"
           Example Bad: "totalsum"

        3. column must be valid identifier (format validation only).
           Example Good: "amount"
           Example Bad: "total amount"
           Note: column DOES NOT need to exist in model semantic fields.

        4. Measures cannot reference foreign-entity columns (prevents double-counting).
           Example Bad: column="customer_id" (if customer_id is a foreign entity column)

        5. Derived measures must reference valid measure/dimension names.
           Example Good: "revenue / orders" (if revenue and orders are valid)
           Example Bad: "revenue / foo" (if foo doesn't exist)

        6. No duplicate measure names.

        7. No conflict with dimensions/entities/time columns/primary key.
           (A measure name cannot match a dimension, entity, time column, or the primary key.)
           Example Bad: "region" measure (if "region" is already a dimension or entity)

    Args:
        model: The Model instance to validate
    """

    def __init__(self, model: "Model"):
        self.model = model

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

    def _is_valid_agg(self, agg: str) -> bool:
        """Check if an aggregation function is valid.

        Args:
            agg: The aggregation function to validate

        Returns:
            True if the aggregation is valid, False otherwise
        """
        if not agg:
            return False
        return agg in VALID_MEASURE_AGGS

    def _get_foreign_entity_columns(self) -> set[str]:
        """Get all column names from foreign entities in the model.

        Returns:
            Set of column names from foreign entities
        """
        foreign_columns = set()
        for entity in self.model.entities:
            if entity.entity_type == EntityType.FOREIGN:
                foreign_columns.add(entity.column)
        return foreign_columns

    def _get_dimension_names(self) -> set[str]:
        """Get all dimension names from the model.

        Returns:
            Set of dimension names
        """
        return {dim.name for dim in self.model.dimensions}

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

    def _validate_name_is_valid_identifier(self, measure: Measure) -> None:
        """Rule 1: Name must be valid identifier.

        Validates that the measure name follows Python identifier rules:
        - No spaces
        - No special symbols (except underscore)
        - Not a reserved word
        - Starts with letter or underscore

        Args:
            measure: The Measure instance to validate

        Raises:
            MeasureValidationError: If the measure name is not a valid identifier
        """
        if not self._is_valid_identifier(measure.name):
            message = (
                "Measure name must be a valid identifier "
                "(no spaces, no symbols, no reserved words). "
                f"Invalid name: '{measure.name}'"
            )
            raise MeasureValidationError(
                message,
                model=self.model.name,
                measure=measure.name,
            )

    def _validate_agg_is_known_aggregation(self, measure: Measure) -> None:
        """Rule 2: agg must be a known aggregation function.

        Validates that the aggregation function is one of the supported types:
        sum, avg, mean, count, count_distinct, min, max

        Args:
            measure: The Measure instance to validate

        Raises:
            MeasureValidationError: If the aggregation function is not recognized
        """
        if not self._is_valid_agg(measure.agg):
            raise MeasureValidationError(
                "Measure aggregation must be a known aggregation function. "
                f"Invalid aggregation: '{measure.agg}'. "
                f"Valid aggregations: {VALID_MEASURE_AGGS}",
                model=self.model.name,
                measure=measure.name,
                aggregation=measure.agg,
            )

    def _validate_column_is_valid_identifier(self, measure: Measure) -> None:
        """Rule 3: column must be valid identifier (format validation only).

        Validates that the column name follows Python identifier format rules.
        Note: This only validates the format, not whether the column exists
        in the model's semantic fields.

        Args:
            measure: The Measure instance to validate

        Raises:
            MeasureValidationError: If the column name is not a valid identifier format
        """
        if not self._is_valid_identifier(measure.column):
            message = (
                "Measure column must be a valid identifier format "
                "(no spaces, no symbols, no reserved words). "
                f"Invalid column: '{measure.column}'"
            )
            raise MeasureValidationError(
                message,
                model=self.model.name,
                measure=measure.name,
                column=measure.column,
            )

    def _validate_measure_does_not_reference_foreign_entity_columns(self, measure: Measure) -> None:
        """Rule 4: Measures cannot reference foreign-entity columns.

        Prevents double-counting by ensuring measures don't aggregate foreign key columns.
        Foreign entity columns are typically used for joins and relationships,
        not for direct aggregation.

        Args:
            measure: The Measure instance to validate

        Raises:
            MeasureValidationError: If the measure column matches a foreign entity column
        """
        foreign_columns = self._get_foreign_entity_columns()
        if measure.column in foreign_columns:
            raise MeasureValidationError(
                "Measures cannot reference foreign-entity columns (prevents double-counting). "
                f"Measure '{measure.name}' references foreign entity column: '{measure.column}'",
                model=self.model.name,
                measure=measure.name,
                column=measure.column,
            )

    def _validate_derived_measure_references_valid_names(self, measure: Measure) -> None:
        """Rule 5: Derived measures must reference valid measure/dimension names.

        For derived measures (those that reference other measures or dimensions),
        validates that all referenced names exist in the model.

        Note: This is a placeholder for future derived measure support.
        Currently, this rule checks if the measure name or column references
        existing dimensions or measures.

        Args:
            measure: The Measure instance to validate

        Raises:
            MeasureValidationError: If derived measure references invalid names
        """
        # Get all valid reference names (dimensions, measures, entities)
        valid_names = self._get_dimension_names() | self._get_measure_names() | self._get_entity_names()

        # Check if measure column references a valid name (for derived measures)
        # This is a simplified check - full derived measure parsing would be more complex
        # For now, we check if column matches a dimension/measure/entity name
        # This indicates it might be a derived measure reference
        if measure.column in valid_names:
            # This is acceptable - column can reference a dimension/measure
            pass
        # Additional derived measure validation would go here
        # For example, parsing expressions like "revenue / orders"

    def _validate_no_duplicate_measure_names(self) -> None:
        """Rule 6: No duplicate measure names.

        Ensures that each measure has a unique name within the model.
        Duplicate names would cause ambiguity in queries.

        Raises:
            MeasureValidationError: If there are duplicate measure names
        """
        measure_names = [measure.name for measure in self.model.measures]
        seen = set()
        duplicates = []

        for name in measure_names:
            if name in seen:
                duplicates.append(name)
            seen.add(name)

        if duplicates:
            unique_duplicates = list(set(duplicates))
            message = f"A Model cannot define duplicate measure names. Duplicate names: {unique_duplicates}"
            raise NamingCollisionError(
                message,
                model=self.model.name,
                duplicate_measures=unique_duplicates,
            )

    def _validate_measure_name_collisions(self, measure: Measure) -> None:
        """Rule 7: No conflict with dimensions/entities.

        Ensures that measure names don't conflict with dimension or entity names.
        This prevents ambiguity when referencing fields in queries.

        Example Bad: A measure named "region" when "region" is already a dimension.

        Args:
            measure: The Measure instance to validate

        Raises:
            MeasureValidationError: If measure name conflicts with dimension or entity name
        """
        dimension_names = self._get_dimension_names()
        entity_names = self._get_entity_names()
        time_columns = set(self.model.time_columns)
        primary_key = self.model.primary_key

        if measure.name in dimension_names:
            raise NamingCollisionError(
                "Measure name cannot conflict with dimension names.",
                model=self.model.name,
                measure=measure.name,
                conflict="dimension",
            )

        if measure.name in entity_names:
            raise NamingCollisionError(
                "Measure name cannot conflict with entity names.",
                model=self.model.name,
                measure=measure.name,
                conflict="entity",
            )

        if measure.name in time_columns:
            raise NamingCollisionError(
                "Measure name cannot conflict with time column names.",
                model=self.model.name,
                measure=measure.name,
                conflict="time_column",
            )

        if measure.name == primary_key:
            raise NamingCollisionError(
                "Measure name cannot conflict with the primary key.",
                model=self.model.name,
                measure=measure.name,
                conflict="primary_key",
            )

    def validate(self) -> None:
        """Run all validation rules on the model's measures.

        Validates all measures in the model according to the 7 validation rules:
        1. Name must be valid identifier
        2. agg must be a known aggregation
        3. column must be valid identifier (format)
        4. Measures cannot reference foreign-entity columns
        5. Derived measures must reference valid measure/dim names
        6. No duplicate measure names
        7. No conflict with dimensions/entities/time columns/primary key

        Raises:
            MeasureValidationError: If any validation rule fails
        """
        if not self.model.measures:
            # No measures to validate
            return

        # Rule 6: Check for duplicates first (applies to all measures)
        self._validate_no_duplicate_measure_names()

        # Validate each measure individually
        for measure in self.model.measures:
            # Rule 1: Name must be valid identifier
            self._validate_name_is_valid_identifier(measure)

            # Rule 2: agg must be a known aggregation
            self._validate_agg_is_known_aggregation(measure)

            # Rule 3: column must be valid identifier (format)
            self._validate_column_is_valid_identifier(measure)

            # Rule 4: Measures cannot reference foreign-entity columns
            self._validate_measure_does_not_reference_foreign_entity_columns(measure)

            # Rule 5: Derived measures must reference valid measure/dim names
            self._validate_derived_measure_references_valid_names(measure)

            # Rule 7: No conflict with dimensions/entities/time columns/primary key
            self._validate_measure_name_collisions(measure)
