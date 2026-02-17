"""Semantic modeling package.

This package provides classes for building semantic data models, including:
- Model: The central semantic model definition
- Dimension: Categorical attributes for grouping and filtering
- Measure: Aggregated measures and calculations
- Entity: Relationship definitions and key constraints

Example:
    >>> from pysemantic.modeling import Model, Dimension, Measure, Entity, EntityType
    >>> dim = Dimension("product_id", dtype="string")
    >>> measure = Measure("total_sales", agg="sum", column="sales_amount")
    >>> entity = Entity("customer", EntityType.PRIMARY, "id")
    >>> model = Model(
    ...     name="sales",
    ...     table="sales_table",
    ...     primary_key="id",
    ...     dimensions=[dim],
    ...     measures=[measure],
    ...     entities=[entity],
    ... )
"""

from pysemantic.validation import (
    DimensionValidationError,
    EntityValidationError,
    MeasureValidationError,
    TimeColumnValidationError,
)

from .dimension import Dimension
from .entity import Entity, EntityType
from .measure import Measure
from .model import Model

__all__ = [
    "Dimension",
    "DimensionValidationError",
    "Entity",
    "EntityType",
    "EntityValidationError",
    "Measure",
    "MeasureValidationError",
    "Model",
    "TimeColumnValidationError",
]
