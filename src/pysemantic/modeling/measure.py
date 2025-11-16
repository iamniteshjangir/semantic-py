"""Measure module for semantic modeling.

This module defines the Measure class, which represents a metric or measure
in a semantic data model. Measures are aggregated values like sums, averages,
or counts that are calculated over dimensions.
"""


class Measure:
    """Represents a measure (metric) in a semantic model.

    A measure is a quantitative value that can be aggregated, such as sales
    revenue, order count, or average price. Measures are calculated using
    aggregation functions like sum, count, average, min, or max.

    Args:
        name: The name of the measure (e.g., 'total_sales', 'order_count')
        agg: The aggregation function to apply. Common values:
             'sum', 'count', 'avg', 'average', 'min', 'max', 'distinct_count'
        column: The database column name to aggregate

    Attributes:
        name: The name of the measure
        agg: The aggregation function
        column: The database column name

    Example:
        >>> measure = Measure("total_revenue", agg="sum", column="revenue")
        >>> print(measure)
        Measure(name='total_revenue', agg='sum', column='revenue')
    """

    def __init__(self, name: str, agg: str, column: str) -> None:
        """Initialize a Measure instance.

        Args:
            name: The name of the measure
            agg: The aggregation function to apply
            column: The database column name to aggregate
        """
        self.name = name
        self.agg = agg
        self.column = column

    def __repr__(self) -> str:
        """Return a string representation of the Measure.

        Returns:
            A string representation showing the measure's name, aggregation,
            and column
        """
        return f"Measure(name='{self.name}', agg='{self.agg}', column='{self.column}')"
