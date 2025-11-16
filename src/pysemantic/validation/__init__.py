"""Validation module for semantic modeling.

This module provides validation classes and utilities for ensuring
data integrity and correctness of semantic model definitions.
"""

from pysemantic.exceptions import NamingCollisionError

from .dimension_validation import DimensionValidation, DimensionValidationError
from .entity_validation import EntityValidation, EntityValidationError
from .measure_validation import MeasureValidation, MeasureValidationError
from .time_column_validation import TimeColumnValidation, TimeColumnValidationError

__all__ = [
    "DimensionValidation",
    "DimensionValidationError",
    "EntityValidation",
    "EntityValidationError",
    "MeasureValidation",
    "MeasureValidationError",
    "NamingCollisionError",
    "TimeColumnValidation",
    "TimeColumnValidationError",
]
