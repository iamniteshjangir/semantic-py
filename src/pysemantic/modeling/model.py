"""Model module for semantic modeling.

This module defines the Model class, which represents a complete semantic
data model. A model defines the structure, dimensions, measures, and entities
for analytical queries and reporting.
"""

from pysemantic import validation

from .dimension import Dimension
from .entity import Entity
from .measure import Measure


class Model:
    """Represents a semantic data model.

    A Model is the central component of a semantic layer, defining the structure
    of analytical data including dimensions for grouping, measures for aggregation,
    entities for relationships, and time columns for temporal analysis.

    Args:
        name: The name of the model (e.g., 'sales', 'inventory')
        table: The database table name this model is based on
        primary_key: The primary key column name
        description: Optional description of the model. Defaults to empty string.
        dimensions: Optional list of Dimension objects for grouping/filtering.
                   Defaults to empty list.
        entities: list of Entity objects for relationships.
                 At least one entity must be provided.
        measures: Optional list of Measure objects for aggregation.
                 Defaults to empty list.
        time_columns: Optional list of time-related column names for temporal
                     analysis. Defaults to empty list.

    Attributes:
        name: The name of the model
        description: Description of the model
        table: The database table name
        primary_key: The primary key column name
        dimensions: List of Dimension objects
        entities: List of entity names
        measures: List of Measure objects
        time_columns: List of time-related column names

    Example:
        >>> from pysemantic.modeling import Model, Dimension, Measure
        >>> dim = Dimension("product_id", dtype="string")
        >>> measure = Measure("total_sales", agg="sum", column="sales_amount")
        >>> model = Model(
        ...     name="sales",
        ...     table="sales_table",
        ...     primary_key="id",
        ...     description="Sales data model",
        ...     dimensions=[dim],
        ...     measures=[measure],
        ... )
        >>> print(model)
        Model(name='sales', table='sales_table', ...)
    """

    def __init__(
        self,
        name: str,
        table: str,
        primary_key: str,
        description: str = "",
        dimensions: list[Dimension] | None = None,
        entities: list[Entity] | None = None,
        measures: list[Measure] | None = None,
        time_columns: list[str] | None = None,
    ) -> None:
        """Initialize a Model instance.

        Args:
            name: The name of the model
            table: The database table name
            primary_key: The primary key column name
            description: Optional description of the model
            dimensions: Optional list of Dimension objects
            entities: list of Entity objects
            measures: Optional list of Measure objects
            time_columns: Optional list of time-related column names

        Raises:
            EntityValidationError: If entities are provided and validation fails
        """
        self.name = name
        self.table = table
        self.primary_key = primary_key
        self.description = description
        self.dimensions = dimensions if dimensions is not None else []
        self.entities = entities
        self.measures = measures if measures is not None else []
        self.time_columns = time_columns if time_columns is not None else []

        self.validate_entities()
        self.validate_dimensions()
        self.validate_measures()
        self.validate_time_columns()

    def validate_entities(self) -> None:
        """Explicitly validate the model's entities.

        This method runs all entity validation rules. It can be called
        after modifying entities to re-validate the model.

        Raises:
            EntityValidationError: If any validation rule fails

        Example:
            >>> model = Model("test", "table", "id", entities=[...])
            >>> # ... modify entities ...
            >>> model.validate()  # Re-validate after changes
        """
        if not self.entities:
            raise validation.EntityValidationError(
                "A Model must declare exactly one primary entity. No entities found.",
                model=self.name,
            )

        validator = validation.EntityValidation(self)
        validator.validate()

    def validate_measures(self) -> None:
        """Explicitly validate the model's measures.

        This method runs all measure validation rules. It can be called
        after modifying measures to re-validate the model.

        Raises:
            MeasureValidationError: If any validation rule fails
        """
        validator = validation.MeasureValidation(self)
        validator.validate()

    def validate_dimensions(self) -> None:
        """Explicitly validate the model's dimensions.

        This method runs all dimension validation rules. It can be called
        after modifying dimensions to re-validate the model.

        Raises:
            DimensionValidationError: If any validation rule fails
        """
        validator = validation.DimensionValidation(self)
        validator.validate()

    def validate_time_columns(self) -> None:
        """Explicitly validate the model's time columns.

        This method runs all time column validation rules. It can be called
        after modifying time columns to re-validate the model.

        Raises:
            TimeColumnValidationError: If any validation rule fails
        """
        validator = validation.TimeColumnValidation(self)
        validator.validate()

    def is_valid(self) -> bool:
        """Check if the model's entities are valid without raising an exception.

        Returns:
            True if all validation rules pass, False otherwise

        Example:
            >>> if model.is_valid():
            ...     print("Model is valid")
            ... else:
            ...     print("Model has validation errors")
        """
        if not self.entities:
            return False

        try:
            self.validate_entities()
            self.validate_dimensions()
            self.validate_measures()
            self.validate_time_columns()
            return True
        except (
            validation.EntityValidationError,
            validation.MeasureValidationError,
            validation.DimensionValidationError,
            validation.TimeColumnValidationError,
            validation.NamingCollisionError,
        ):
            return False

    def __repr__(self) -> str:
        """Return a string representation of the Model.

        Returns:
            A string representation showing the model's key attributes
            including dimensions and measures with their full representations
        """
        dimensions_repr = [dim.__repr__() for dim in self.dimensions]
        measures_repr = [measure.__repr__() for measure in self.measures]
        entities_repr = [entity.__repr__() for entity in self.entities]
        return (
            f"Model(name='{self.name}', table='{self.table}', "
            f"primary_key='{self.primary_key}', description='{self.description}', "
            f"dimensions={dimensions_repr}, entities={entities_repr}, "
            f"measures={measures_repr}, time_columns={self.time_columns})"
        )
