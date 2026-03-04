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
    The Domain Specific Tree (DST) / Query Plan.
    This is the 'Ouptut' of the Planner and 'Input' to the SQL Generator.
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
