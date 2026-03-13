from dataclasses import dataclass, field

from pysemantic.core.ast import Filter
from pysemantic.modeling import Dimension, Measure


@dataclass
class JoinNode:
    source_model: str
    target_model: str
    join_type: str = "LEFT"
    # In V2, this would be a full SQL on clause object
    # For now, we assume the SQL Generator knows how to build it from Entity Graph


@dataclass
class QueryPlan:
    """
    The Domain Specific Tree (DST) / Query Plan for single-fact queries.
    This is the 'Output' of the Planner and 'Input' to the SQL Generator.
    """

    # The Root (Fact) Table info
    root_model_name: str
    root_table_name: str

    # Resolved Objects (Rich Metadata)
    measures: list[Measure]
    dimensions: list[Dimension]

    # The Execution Logic
    joins: list[JoinNode] = field(default_factory=list)

    # Post-Processing
    filters: list[Filter] = field(default_factory=list)
    order_by: list[str] = field(default_factory=list)
    limit: int | None = None

    def describe(self) -> str:
        """Helper to print a human-readable summary of the Plan."""
        return (
            f"QueryPlan(root={self.root_model_name}, "
            f"measures={[m.name for m in self.measures]}, "
            f"dimensions={[d.name for d in self.dimensions]}, "
            f"joins={[j.source_model + '->' + j.target_model for j in self.joins]}, "
            f"filters={self.filters}, "
            f"order_by={self.order_by}, "
            f"limit={self.limit})"
        )


@dataclass
class SharedDimensionKey:
    """Join key derived from a shared dimension model's primary key.

    Used to join CTEs in multi-fact queries on the dimension's natural key,
    ensuring each CTE can be stitched back together at the correct grain
    without producing a chasm trap.
    """

    dimension_model_name: str
    table_name: str
    primary_key_column: str
    alias: str


@dataclass
class SubPlan:
    """Represents a single CTE in a multi-fact query plan.

    Each SubPlan pre-aggregates one fact table's measures alongside shared
    dimensions, preventing the chasm trap by isolating each fact's grain.
    """

    cte_alias: str
    fact_model_name: str
    fact_table_name: str
    measures: list[Measure]
    dimensions: list[Dimension]
    joins: list[JoinNode]
    shared_keys: list[SharedDimensionKey]
    filters: list[Filter] = field(default_factory=list)


@dataclass
class MultiFactPlan:
    """Multi-fact query plan using CTEs to avoid the chasm trap.

    Each SubPlan becomes an independent CTE that pre-aggregates measures
    with shared dimensions. The final query joins CTEs on shared dimension
    primary keys via FULL OUTER JOIN, preventing fan-out between fact tables.
    """

    sub_plans: list[SubPlan]
    shared_dimensions: list[Dimension]
    shared_keys: list[SharedDimensionKey]
    # Dimension names used as join keys when the dimension's owner model is
    # also a fact table in this query.  We cannot use that model's PK here:
    # including it in GROUP BY would make each CTE row one-per-entity, so
    # COUNT(primary_key) would always be 1.  We group by dimension values
    # only and join CTEs on those values.
    #
    # Example: measures=[total_order_price, total_customers],
    #          dimensions=[customer_state, customer_city]
    # - order_items CTE: GROUP BY customer_state, customer_city (no customer_id)
    # - customers CTE:   GROUP BY customer_state, customer_city; COUNT(customer_id)
    # - Outer join: ON cte_oi.customer_state = cte_cust.customer_state
    #               AND cte_oi.customer_city = cte_cust.customer_city
    dimension_value_keys: list[str] = field(default_factory=list)
    measure_filters: list[Filter] = field(default_factory=list)
    order_by: list[str] = field(default_factory=list)
    limit: int | None = None

    def describe(self) -> str:
        """Helper to print a human-readable summary of the Plan."""
        return (
            f"MultiFactPlan(sub_plans={[sp.fact_model_name for sp in self.sub_plans]}, "
            f"shared_dimensions={[d.name for d in self.shared_dimensions]}, "
            f"shared_keys={[sk.alias for sk in self.shared_keys]}, "
            f"dimension_value_keys={self.dimension_value_keys}, "
            f"measure_filters={self.measure_filters}, "
            f"order_by={self.order_by}, "
            f"limit={self.limit})"
        )
