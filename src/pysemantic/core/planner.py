from collections import defaultdict

from pysemantic.core.ast import QueryAST
from pysemantic.core.plan import (
    JoinNode,
    MultiFactPlan,
    QueryPlan,
    SharedDimensionKey,
    SubPlan,
)
from pysemantic.exceptions import PlannerError, format_error
from pysemantic.modeling import Model
from pysemantic.registry import Registry


class QueryPlanningError(PlannerError):
    """Custom exception for Query Planner errors."""

    DOMAIN = "planning.query"

    def __init__(self, summary: str, **context):
        super().__init__(format_error(self.DOMAIN, summary, **context))


class MultiFactPlanningError(PlannerError):
    """Custom exception for multi-fact query planning errors.

    Raised when a query spans multiple fact tables and encounters issues
    such as unreachable dimensions, conflicting grains, or dimension
    ownership violations.
    """

    DOMAIN = "planning.multi_fact"

    def __init__(self, summary: str, **context):
        super().__init__(format_error(self.DOMAIN, summary, **context))


class NonConformedDimensionError(MultiFactPlanningError):
    """Raised when a non-conformed dimension is used in a multi-fact query.

    A conformed dimension is one that is reachable from *every* fact table
    in the query via the entity graph.  Multi-fact queries require all
    dimensions (SELECT and filter) to be conformed so that every CTE can
    be grouped and filtered at the same grain.

    The only exception is a **Grand Total** query — no SELECT dimensions,
    producing scalar aggregates — which uses CROSS JOIN and does not
    require conformed dimensions.
    """

    pass


class QueryPlanner:
    def __init__(self, registry: Registry):
        self.registry = registry

    def plan(self, ast: QueryAST) -> QueryPlan | MultiFactPlan:
        """
        Converts a raw AST (Abstract Syntax Tree) into a Query Plan.

        Automatically detects single-fact vs multi-fact queries. Single-fact
        queries produce a flat QueryPlan; multi-fact queries produce a
        MultiFactPlan backed by CTEs to avoid the chasm trap.
        """
        if not ast.measures:
            raise QueryPlanningError("Query must contain at least one metric.")

        measures_by_model: dict[str, list[str]] = {}
        for metric_name in ast.measures:
            try:
                model = self.registry.get_model_by_metric(metric_name)
            except Exception as e:
                raise QueryPlanningError(
                    summary=f"Metric '{metric_name}' not found.",
                ) from e
            measures_by_model.setdefault(model.name, []).append(metric_name)

        if len(measures_by_model) == 1:
            return self._plan_single_fact(ast)
        return self._plan_multi_fact(ast, measures_by_model)

    # ------------------------------------------------------------------
    # Single-Fact Planning
    # ------------------------------------------------------------------

    def _plan_single_fact(self, ast: QueryAST) -> QueryPlan:
        """Plans a query where all measures belong to a single fact table."""
        first_metric_name = ast.measures[0]
        try:
            root_model = self.registry.get_model_by_metric(first_metric_name)
        except Exception as e:
            raise QueryPlanningError(
                summary="Could not resolve root model",
                details=f"Metric '{first_metric_name}' does not belong to any registered model.",
            ) from e

        # plan() only calls _plan_single_fact when all measures belong to one model
        resolved_measures = []
        for metric_name in ast.measures:
            try:
                model = self.registry.get_model_by_metric(metric_name)
            except Exception as e:
                raise QueryPlanningError(summary=f"Metric '{metric_name}' not found.") from e

            try:
                measure_obj = next(m for m in model.measures if m.name == metric_name)
                resolved_measures.append(measure_obj)
            except StopIteration as e:
                raise QueryPlanningError(
                    summary=f"Measure '{metric_name}' definition missing in model '{model.name}'."
                ) from e

        resolved_dimensions = []
        joins_needed = []

        required_dimension_names = set(ast.dimensions)

        for filter_obj in ast.filters:
            try:
                self.registry.get_model_by_metric(filter_obj.field)
            except Exception:
                required_dimension_names.add(filter_obj.field)

        for dimension_name in required_dimension_names:
            target_model = self._find_dimension_owner(dimension_name, root_model)

            if dimension_name in ast.dimensions:
                try:
                    dim = next(d for d in target_model.dimensions if d.name == dimension_name)
                    resolved_dimensions.append(dim)
                except StopIteration as e:
                    raise QueryPlanningError(
                        summary=f"Dimension '{dimension_name}' definition missing in '{target_model.name}'."
                    ) from e

            if target_model.name != root_model.name:
                try:
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

                    if join_node not in joins_needed:
                        joins_needed.append(join_node)

        for filter_obj in ast.filters:
            is_measure = False
            try:
                measure_model = self.registry.get_model_by_metric(filter_obj.field)
                is_measure = True

                if measure_model.name != root_model.name:
                    raise QueryPlanningError(
                        summary="Multi-Fact Query Error in Filter",
                        details=(
                            f"Cannot filter on metric '{filter_obj.field}' from '{measure_model.name}' "
                            f"because the query root is '{root_model.name}'. V1 does not support cross-fact filtering."
                        ),
                    )
            except Exception as e:
                if isinstance(e, QueryPlanningError):
                    raise e
                pass

            if not is_measure:
                try:
                    self._find_dimension_owner(filter_obj.field, root_model)
                except Exception as e:
                    raise QueryPlanningError(
                        summary=f"Invalid filter field: '{filter_obj.field}'",
                        details="Field must be a valid dimension or measure.",
                    ) from e

        for order_field in ast.order_by:
            clean_field = order_field.split()[0]

            is_measure = False
            try:
                self.registry.get_model_by_metric(clean_field)
                is_measure = True
            except Exception:
                pass

            if not is_measure:
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

    # ------------------------------------------------------------------
    # Multi-Fact Planning (CTE-based chasm trap avoidance)
    # ------------------------------------------------------------------

    def _plan_multi_fact(
        self,
        ast: QueryAST,
        measures_by_model: dict[str, list[str]],
    ) -> MultiFactPlan:
        """Plans a conformed multi-fact query.

        All requested dimensions (SELECT *and* filter) must be
        **conformed** — reachable from every fact table via the entity
        graph.  Non-conformed dimensions raise ``NonConformedDimensionError``.

        **Grand Total exception**: when no SELECT dimensions are
        requested the query produces scalar aggregates; each CTE returns
        one row and the final query uses CROSS JOIN.  Non-conformed
        dimension filters are allowed in this mode and routed only to the
        CTEs that can access them.
        """
        fact_model_names = set(measures_by_model.keys())

        # 1. Resolve measures per fact model
        resolved_measures_by_model: dict[str, list] = {}
        for model_name, metric_names in measures_by_model.items():
            model = self.registry.models[model_name]
            resolved = []
            for metric_name in metric_names:
                try:
                    measure_obj = next(m for m in model.measures if m.name == metric_name)
                    resolved.append(measure_obj)
                except StopIteration as e:
                    raise MultiFactPlanningError(
                        summary=f"Measure '{metric_name}' definition missing in model '{model_name}'."
                    ) from e
            resolved_measures_by_model[model_name] = resolved

        # 2. Resolve & validate conformed SELECT dimensions
        # Every SELECT dimension must be conformed — reachable from ALL
        # fact tables.  A model can serve a *dual role* (it owns requested
        # measures AND provides dimensions); dual-role models are valid
        # dimension providers.  We skip PK-based shared keys for them
        # (PK in GROUP BY would break count-type aggregates) and join
        # CTEs on the dimension values instead.

        all_dim_owners: dict[str, Model] = {}

        for dim_name in ast.dimensions:
            owner = self._find_shared_dimension_owner(dim_name, fact_model_names)
            self._validate_dimension_conformity(dim_name, owner, fact_model_names)
            all_dim_owners[dim_name] = owner

        # 3. Classify filters
        # Conformed mode (dimensions present):
        #   All dimension filters must also be conformed → pushed to every CTE.
        #   Non-conformed dimension filters are rejected.
        #
        # Grand Total mode (no dimensions):
        #   Dimension filters are routed by accessibility — shared when
        #   conformed, fact-specific when not.

        dim_filters_shared: list = []
        dim_filters_per_fact: dict[str, list] = defaultdict(list)
        measure_filters: list = []
        is_grand_total = not ast.dimensions

        for filter_obj in ast.filters:
            if self._is_measure(filter_obj.field):
                measure_model = self.registry.get_model_by_metric(filter_obj.field)
                if measure_model.name not in fact_model_names:
                    raise MultiFactPlanningError(
                        summary="Invalid measure filter in multi-fact query",
                        details=(
                            f"Filter on metric '{filter_obj.field}' from model "
                            f"'{measure_model.name}' which is not a fact table in this query."
                        ),
                    )
                measure_filters.append(filter_obj)
                continue

            owner = self._find_shared_dimension_owner(filter_obj.field, fact_model_names)
            all_dim_owners[filter_obj.field] = owner

            if is_grand_total:
                # Grand Total: best-effort routing by accessibility
                if self._is_reachable_from_all(owner, fact_model_names):
                    dim_filters_shared.append(filter_obj)
                else:
                    for fact_name in fact_model_names:
                        if self._can_reach(fact_name, owner):
                            dim_filters_per_fact[fact_name].append(filter_obj)
            else:
                # Conformed mode: filter dimension must be conformed
                self._validate_dimension_conformity(
                    filter_obj.field, owner, fact_model_names
                )
                dim_filters_shared.append(filter_obj)

        # 4. Build shared keys & dimension-value keys
        # Pure dimension models → SharedDimensionKey (PK-based join)
        # Dual-role models      → dimension_value_keys (join on dim values)

        seen_key_models: set[str] = set()
        shared_keys: list[SharedDimensionKey] = []
        dimension_value_keys: list[str] = []

        for dim_name in ast.dimensions:
            owner = all_dim_owners[dim_name]

            if owner.name in fact_model_names:
                dimension_value_keys.append(dim_name)
            elif owner.name not in seen_key_models:
                seen_key_models.add(owner.name)
                shared_keys.append(
                    SharedDimensionKey(
                        dimension_model_name=owner.name,
                        table_name=owner.table,
                        primary_key_column=owner.primary_key,
                        alias=f"__pk_{owner.name}",
                    )
                )

        # 5. Resolve SELECT dimensions
        resolved_dimensions = []
        for dim_name in ast.dimensions:
            owner = all_dim_owners[dim_name]
            try:
                dim_obj = next(d for d in owner.dimensions if d.name == dim_name)
                resolved_dimensions.append(dim_obj)
            except StopIteration as e:
                raise MultiFactPlanningError(
                    summary=f"Dimension '{dim_name}' definition missing in '{owner.name}'."
                ) from e

        # 6. Validate ORDER BY fields
        for order_field in ast.order_by:
            clean_field = order_field.split()[0]
            if not self._is_measure(clean_field) and clean_field not in all_dim_owners:
                try:
                    self._find_shared_dimension_owner(clean_field, fact_model_names)
                except Exception as e:
                    raise MultiFactPlanningError(
                        summary=f"Invalid order_by field: '{clean_field}'",
                        details="Field must be a valid shared dimension or measure.",
                    ) from e

        # 7. Build SubPlans (one per fact table)
        sub_plans: list[SubPlan] = []

        for model_name in measures_by_model:
            fact_model = self.registry.models[model_name]

            cte_filters = list(dim_filters_shared) + dim_filters_per_fact.get(model_name, [])

            dims_needed_for_cte = set(ast.dimensions)
            for f in cte_filters:
                dims_needed_for_cte.add(f.field)

            joins: list[JoinNode] = []
            for dim_name in dims_needed_for_cte:
                owner = all_dim_owners[dim_name]
                if owner.name == model_name:
                    continue
                try:
                    join_chain = self.registry.get_join_path(model_name, owner.name)
                except Exception as e:
                    raise MultiFactPlanningError(
                        summary="Join path not found for CTE",
                        details=(
                            f"Cannot join fact '{model_name}' to dimension model "
                            f"'{owner.name}' for dimension '{dim_name}'."
                        ),
                    ) from e

                for source, target, _ in join_chain:
                    join_node = JoinNode(source_model=source, target_model=target)
                    if join_node not in joins:
                        joins.append(join_node)

            sub_plans.append(
                SubPlan(
                    cte_alias=f"cte_{model_name}",
                    fact_model_name=model_name,
                    fact_table_name=fact_model.table,
                    measures=resolved_measures_by_model[model_name],
                    dimensions=resolved_dimensions,
                    joins=joins,
                    shared_keys=shared_keys,
                    filters=cte_filters,
                )
            )

        return MultiFactPlan(
            sub_plans=sub_plans,
            shared_dimensions=resolved_dimensions,
            shared_keys=shared_keys,
            dimension_value_keys=dimension_value_keys,
            measure_filters=measure_filters,
            order_by=ast.order_by,
            limit=ast.limit,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _find_dimension_owner(self, dim_name: str, root_model: Model) -> Model:
        """Helper: Find which model owns a dimension, prioritizing the root."""
        for d in root_model.dimensions:
            if d.name == dim_name:
                return root_model

        for model in self.registry.models.values():
            for d in model.dimensions:
                if d.name == dim_name:
                    return model

        raise QueryPlanningError(
            summary="Dimension not found",
            details=f"Dimension '{dim_name}' is not defined in any model.",
        )

    def _find_shared_dimension_owner(
        self, dim_name: str, fact_model_names: set[str]
    ) -> Model:
        """Find which model owns a dimension for multi-fact queries.

        Prefer a model that is *not* a fact in this query (a dedicated
        dimension table).  If the dimension only exists on a fact model,
        return that model.

        Example: facts = {order_items, customers}, dim = customer_state
        - If customer_state exists only on customers → return customers.
        - If customer_state exists on both "customer_demographics" (dim table)
          and "customers" (fact) → return customer_demographics so we use the
          dedicated dimension and PK-based joins.
        """
        for model in self.registry.models.values():
            if model.name not in fact_model_names:
                if any(d.name == dim_name for d in model.dimensions):
                    return model

        for model_name in fact_model_names:
            model = self.registry.models[model_name]
            if any(d.name == dim_name for d in model.dimensions):
                return model

        raise MultiFactPlanningError(
            summary="Dimension not found",
            details=f"Dimension '{dim_name}' is not defined in any registered model.",
        )

    def _validate_dimension_conformity(
        self,
        dim_name: str,
        owner: Model,
        fact_model_names: set[str],
    ) -> None:
        """Validate that a dimension is conformed across all fact tables.

        A conformed dimension must be reachable from every fact table in
        the query via the entity graph.  Dual-role models (owner is
        itself a fact) have local access, so the self-check is skipped.
        """
        for fact_name in fact_model_names:
            if fact_name == owner.name:
                continue
            try:
                self.registry.get_join_path(fact_name, owner.name)
            except Exception as e:
                raise NonConformedDimensionError(
                    summary="Non-conformed Dimension requested",
                    details=(
                        f"Dimension '{dim_name}' (model '{owner.name}') is not "
                        f"reachable from fact model '{fact_name}'. In multi-fact "
                        f"queries all dimensions must be conformed — joinable from "
                        f"every fact table. For unrelated facts with no shared "
                        f"dimensions, use a Grand Total query (no dimensions)."
                    ),
                ) from e

    def _is_reachable_from_all(self, owner: Model, fact_model_names: set[str]) -> bool:
        """True if *owner* is reachable from every fact (self counts)."""
        for fact_name in fact_model_names:
            if fact_name == owner.name:
                continue
            if not self._can_reach(fact_name, owner):
                return False
        return True

    def _can_reach(self, from_model: str, to_model: Model) -> bool:
        """True if *from_model* can reach *to_model* via the entity graph."""
        if from_model == to_model.name:
            return True
        try:
            self.registry.get_join_path(from_model, to_model.name)
            return True
        except Exception:
            return False

    def _is_measure(self, field_name: str) -> bool:
        """Check if a field name corresponds to a registered measure."""
        try:
            self.registry.get_model_by_metric(field_name)
            return True
        except Exception:
            return False
