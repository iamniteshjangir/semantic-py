"""Dimension module for semantic modeling.

This module defines the Dimension class, which represents a dimension
in a semantic data model. Dimensions are used for grouping and filtering data.
"""


class Dimension:
    """Represents a dimension in a semantic model.

    A dimension is a categorical attribute used for grouping, filtering,
    and organizing data in analytical queries. Examples include product
    categories, geographic regions, or time periods.

    Args:
        name: The name of the dimension (e.g., 'product_id', 'region')
        dtype: The data type of the dimension. Defaults to 'string'.
               Common values: 'string', 'integer', 'date', 'timestamp'

    Attributes:
        name: The name of the dimension
        dtype: The data type of the dimension

    Example:
        >>> dim = Dimension("product_category", dtype="string")
        >>> print(dim)
        Dimension(name='product_category', dtype='string')
    """

    def __init__(self, name: str, dtype: str = "string") -> None:
        """Initialize a Dimension instance.

        Args:
            name: The name of the dimension
            dtype: The data type of the dimension (default: 'string')
        """
        self.name = name
        self.dtype = dtype

    def __repr__(self) -> str:
        """Return a string representation of the Dimension.

        Returns:
            A string representation showing the dimension's name and data type
        """
        return f"Dimension(name='{self.name}', dtype='{self.dtype}')"
