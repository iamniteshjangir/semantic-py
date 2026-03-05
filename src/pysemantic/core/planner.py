from pysemantic.core.ast import QueryAST
from pysemantic.core.plan import JoinNode, QueryPlan
from pysemantic.exceptions import PlannerError, format_error
from pysemantic.modeling import Model
from pysemantic.registry import Registry


class QueryPlanningError(PlannerError):
    """Custom exception for Query Planner errors."""

    DOMAIN = "planning.query"

    def __init__(self, summary: str, **context):
        super().__init__(format_error(self.DOMAIN, summary, **context))


class QueryPlanner:
    def __init__(self, registry: Registry):
        self.registry = registry

    def plan(self, ast: QueryAST) -> QueryPlan:
        """
        Converts a raw AST (Abstract Syntax Tree) into a comprehensive Query Plan (DST).
        """
        if not ast.measures:
            raise QueryPlanningError("Query must contain at least one metric.")

        # 1. Resolve Root Model from the first metric
        first_metric_name = ast.measures[0]
        try:
            root_model = self.registry.get_model_by_metric(first_metric_name)
        except Exception as e:  # Catch generic if PlannerError doesn't wrap it yet
            raise QueryPlanningError(
                summary="Could not resolve root model",
                details=f"Metric '{first_metric_name}' does not belong to any registered model.",
            ) from e

        # 2. Resolve all measures (and ensure they belong to Root)
        resolved_measures = []
        for metric_name in ast.measures:
            try:
                model = self.registry.get_model_by_metric(metric_name)
            except Exception as e:
                raise QueryPlanningError(summary=f"Metric '{metric_name}' not found.") from e

            # Validation: Fan Trap Prevention
            if model.name != root_model.name:
                raise QueryPlanningError(
                    summary="Multi-Fact Query Error",
                    details=(
                        f"All measures must belong to the same model. "
                        f"Metric '{metric_name}' is in '{model.name}', "
                        f"but root is '{root_model.name}'."
                    ),
                )

            # FIX 1: Find the Measure object in the list
            try:
                measure_obj = next(m for m in model.measures if m.name == metric_name)
                resolved_measures.append(measure_obj)
            except StopIteration as e:
                # Should not happen if get_model_by_metric works, but safety first
                raise QueryPlanningError(
                    summary=f"Measure '{metric_name}' definition missing in model '{model.name}'."
                ) from e

        # 3. Resolve Dimensions and Calculate Joins
        resolved_dimensions = []
        joins_needed = []

        # Combine explicit dimensions and filter fields to find all required models
        required_dimension_names = set(ast.dimensions)

        for filter_obj in ast.filters:
            try:
                self.registry.get_model_by_metric(filter_obj.field)
            except Exception:
                required_dimension_names.add(filter_obj.field)

        for dimension_name in required_dimension_names:
            # Find which model owns this dimension
            target_model = self._find_dimension_owner(dimension_name, root_model)

            # If it was an explicitly requested dimension, save the object for the SELECT clause
            if dimension_name in ast.dimensions:
                # Find Dimension object
                try:
                    dim = next(d for d in target_model.dimensions if d.name == dimension_name)
                    resolved_dimensions.append(dim)
                except StopIteration as e:
                    raise QueryPlanningError(
                        summary=f"Dimension '{dimension_name}' definition missing in '{target_model.name}'."
                    ) from e

            # Calculate Join Path if needed
            if target_model.name != root_model.name:
                try:
                    # Returns list of edges: [('orders', 'customers', {metadata}), ('customers', 'regions', {metadata})]
                    join_chain = self.registry.get_join_path(root_model.name, target_model.name)
                except Exception as e:
                    raise QueryPlanningError(
                        summary="Join path not found",
                        details=f"Could not find join path between '{root_model.name}' and '{target_model.name}'.",
                    ) from e

                if not join_chain:
                    raise QueryPlanningError(
                        summary="Unreachable Dimension",
                        details=f"Path found but empty between '{root_model.name}' and '{target_model.name}'.",
                    )
                for source, target, _ in join_chain:
                    join_node = JoinNode(source_model=source, target_model=target)

                    # Deduping: Don't add the same join twice
                    if join_node not in joins_needed:
                        joins_needed.append(join_node)

        # 4. Validate Filters
        # Ensure filter fields are valid dimensions or measures (or at least exist in the model graph)
        # For V1, we simply check if they are resolvable dimensions or measures.
        # Note: We don't strictly require them to be in the SELECT list, but they must be in the model.
        # We can reuse _find_dimension_owner or check if it's a measure.

        for filter_obj in ast.filters:
            # Check if it's a measure
            is_measure = False
            try:
                # Check if it is a metric in the registry
                measure_model = self.registry.get_model_by_metric(filter_obj.field)
                is_measure = True

                # Enforce Fan-Out protection for measures inside filters
                if measure_model.name != root_model.name:
                    raise QueryPlanningError(
                        summary="Multi-Fact Query Error in Filter",
                        details=(
                            f"Cannot filter on metric '{filter_obj.field}' from '{measure_model.name}' "
                            f"because the query root is '{root_model.name}'. V1 does not support cross-fact filtering."
                        ),
                    )
            except Exception as e:
                # Re-raise custom error if we just triggered it
                if isinstance(e, QueryPlanningError):
                    raise e
                pass

            if not is_measure:
                # If not a measure, it must be a dimension
                try:
                    self._find_dimension_owner(filter_obj.field, root_model)
                except Exception as e:
                    raise QueryPlanningError(
                        summary=f"Invalid filter field: '{filter_obj.field}'",
                        details="Field must be a valid dimension or measure.",
                    ) from e

        # 5. Validate Order By
        for order_field in ast.order_by:
            # Order by field can be 'field' or 'field DESC'
            clean_field = order_field.split()[0]

            # Check if it's a measure
            is_measure = False
            try:
                self.registry.get_model_by_metric(clean_field)
                is_measure = True
            except Exception:
                pass

            if not is_measure:
                # If not a measure, it must be a dimension
                try:
                    self._find_dimension_owner(clean_field, root_model)
                except Exception as e:
                    raise QueryPlanningError(
                        summary=f"Invalid order_by field: '{clean_field}'",
                        details="Field must be a valid dimension or measure.",
                    ) from e

        return QueryPlan(
            root_model_name=root_model.name,
            root_table_name=root_model.table,
            measures=resolved_measures,
            dimensions=resolved_dimensions,
            joins=joins_needed,
            filters=ast.filters,
            order_by=ast.order_by,
            limit=ast.limit,
        )

    def _find_dimension_owner(self, dim_name, root_model) -> Model:
        """Helper: Find which model owns a dimension, prioritizing the root."""
        # Check root first
        for d in root_model.dimensions:
            if d.name == dim_name:
                return root_model

        # Check other models
        for model in self.registry.models.values():
            for d in model.dimensions:
                if d.name == dim_name:
                    return model

        raise QueryPlanningError(
            summary="Dimension not found",
            details=f"Dimension '{dim_name}' is not defined in any model.",
        )
