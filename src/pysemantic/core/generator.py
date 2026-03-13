import re

import sqlglot

from pysemantic.core.plan import JoinNode, MultiFactPlan, QueryPlan, SubPlan
from pysemantic.exceptions import GeneratorError, format_error
from pysemantic.modeling import EntityType
from pysemantic.registry import Registry


class SQLGenerationError(GeneratorError):
    """Custom exception for SQL Generation errors."""

    DOMAIN = "generation.sql"

    def __init__(self, summary: str, **context):
        super().__init__(format_error(self.DOMAIN, summary, **context))


class MultiFactGenerationError(GeneratorError):
    """Custom exception for multi-fact SQL generation errors.

    Raised when CTE construction, cross-CTE joining, or outer query
    assembly encounters an unresolvable condition.
    """

    DOMAIN = "generation.multi_fact"

    def __init__(self, summary: str, **context):
        super().__init__(format_error(self.DOMAIN, summary, **context))


class SQLGenerator:
    """
    The Translator. Converts a logical QueryPlan into an executable SQL string.
    Currently supports ANSI/Postgres SQL dialect.
    """

    def __init__(self, registry: Registry, dialect: str = "mysql"):
        self.registry = registry
        self.dialect = dialect

    def generate(self, plan: QueryPlan | MultiFactPlan) -> str:
        """
        Generate SQL for the specific target dialect.

        Accepts both single-fact QueryPlan and multi-fact MultiFactPlan.
        Multi-fact plans are rendered as WITH/CTE queries that pre-aggregate
        each fact independently before joining, avoiding the chasm trap.
        """
        if isinstance(plan, MultiFactPlan):
            ansi_sql = self._build_multi_fact_sql(plan)
        else:
            ansi_sql = self._build_ansi_sql(plan)

        try:
            transpiled = sqlglot.transpile(ansi_sql, read=None, write=self.dialect, pretty=True)[0]
            return transpiled
        except Exception as e:
            raise SQLGenerationError(
                summary="Failed to transpile SQL",
                dialect=self.dialect,
                sql=ansi_sql,
                error=str(e),
            ) from e

    # ==================================================================
    # Single-Fact SQL Generation
    # ==================================================================

    def _build_ansi_sql(self, plan: QueryPlan) -> str:
        """
        Main entry point. Orchestrates the construction of the SQL query.
        """
        select_clause = self._build_select(plan)
        from_clause = self._build_from(plan)
        join_clause = self._build_joins(plan)
        where_clause = self._build_where(plan)
        group_by_clause = self._build_group_by(plan)
        having_clause = self._build_having(plan)
        order_limit_clause = self._build_order_limit(plan)

        parts = [
            "SELECT",
            select_clause,
            "FROM",
            from_clause,
        ]

        if join_clause:
            parts.append(join_clause)

        if where_clause:
            parts.append("WHERE")
            parts.append(where_clause)

        if group_by_clause:
            parts.append(group_by_clause)

        if having_clause:
            parts.append("HAVING\n" + having_clause)

        if order_limit_clause:
            parts.append(order_limit_clause)

        return "\n".join(parts) + ";"

    def _build_select(self, plan: QueryPlan) -> str:
        """Constructs 'col AS name, SUM(col) AS name'."""
        select_items = []

        for dim in plan.dimensions:
            owner_model = self._find_owner_model(dim.name, plan)
            table_alias = owner_model.table
            select_items.append(f"    {table_alias}.{dim.column} AS {dim.name}")

        for measure in plan.measures:
            table_alias = plan.root_table_name
            if measure.column in ("1", "*"):
                expr = f"{measure.column}"
            else:
                expr = f"{table_alias}.{measure.column}"
            select_items.append(f"    {self._format_agg(measure.agg, expr)} AS {measure.name}")

        return ",\n".join(select_items)

    def _build_from(self, plan: QueryPlan) -> str:
        """Constructs 'FROM table_name'."""
        return f"    {plan.root_table_name}"

    def _build_joins(self, plan: QueryPlan) -> str:
        """
        Constructs 'LEFT JOIN target ON source.key = target.key'.
        Critical: This resolves the semantic 'Entity' link into a physical SQL 'ON' clause.
        """
        joins = []
        for join in plan.joins:
            sql_join = self._resolve_join_sql(join)
            joins.append(sql_join)

        return "\n".join(joins)

    def _resolve_join_sql(self, join: JoinNode) -> str:
        """
        Helper to write the specific SQL for a JoinNode.
        """
        source_model = self.registry.models[join.source_model]
        target_model = self.registry.models[join.target_model]

        join_key_source = None
        join_key_target = None

        for entity in source_model.entities or []:
            if entity.entity_type == EntityType.FOREIGN:
                target_primary = next(
                    (
                        e
                        for e in (target_model.entities or [])
                        if e.entity_type == EntityType.PRIMARY and e.name == entity.name
                    ),
                    None,
                )
                if target_primary:
                    join_key_source = f"{source_model.table}.{entity.column}"
                    join_key_target = f"{target_model.table}.{target_primary.column}"
                    break

        if not join_key_source:
            for entity in target_model.entities or []:
                if entity.entity_type == EntityType.FOREIGN:
                    source_primary = next(
                        (
                            e
                            for e in (source_model.entities or [])
                            if e.entity_type == EntityType.PRIMARY and e.name == entity.name
                        ),
                        None,
                    )
                    if source_primary:
                        join_key_target = f"{target_model.table}.{entity.column}"
                        join_key_source = f"{source_model.table}.{source_primary.column}"
                        break

        if not join_key_source or not join_key_target:
            raise SQLGenerationError(
                summary="Could not resolve join condition",
                source=source_model.name,
                target=target_model.name,
                details="Ensure one has a FOREIGN entity matching the other's PRIMARY entity.",
            )

        return f"LEFT JOIN {target_model.table} ON {join_key_source} = {join_key_target}"

    def _build_where(self, plan: QueryPlan) -> str:
        """Combines filters with AND using safe interpolation."""
        if not plan.filters:
            return ""

        conditions = []
        for filter_obj in plan.filters:
            try:
                self.registry.get_model_by_metric(filter_obj.field)
                continue
            except Exception:
                pass

            try:
                owner_model = self._find_owner_model(filter_obj.field, plan)
                physcical_column = self._find_column_name(owner_model, filter_obj.field)
                col_expr = f"{owner_model.table}.{physcical_column}"
            except SQLGenerationError:
                col_expr = filter_obj.field

            safe_val = self._format_filter_value(filter_obj.operator, filter_obj.value)
            conditions.append(f"{col_expr} {filter_obj.operator.upper()} {safe_val}")

        return "    " + " AND ".join(conditions) if conditions else ""

    def _build_having(self, plan: QueryPlan) -> str:
        if not plan.filters:
            return ""

        conditions = []
        for filter_obj in plan.filters:
            try:
                measure_model = self.registry.get_model_by_metric(filter_obj.field)
                measure_obj = next(m for m in measure_model.measures if m.name == filter_obj.field)
            except Exception:
                continue

            table_alias = measure_model.table
            if measure_obj.column in ("1", "*"):
                expr = f"{measure_obj.column}"
            else:
                expr = f"{table_alias}.{measure_obj.column}"

            col_expr = self._format_agg(measure_obj.agg, expr)
            safe_val = self._format_filter_value(filter_obj.operator, filter_obj.value)
            conditions.append(f"{col_expr} {filter_obj.operator.upper()} {safe_val}")

        return "    " + " AND ".join(conditions) if conditions else ""

    def _build_group_by(self, plan: QueryPlan) -> str:
        """
        Calculates group by indices (1, 2, 3...).
        Required if there are measures.
        """
        if not plan.measures or not plan.dimensions:
            return ""

        indices = [str(i + 1) for i in range(len(plan.dimensions))]
        return "GROUP BY " + ", ".join(indices)

    def _build_order_limit(self, plan: QueryPlan) -> str:
        """Handles ORDER BY and LIMIT with validation."""
        parts = []
        if plan.order_by:
            safe_orders = []
            for item in plan.order_by:
                if not re.match(r"^[\w\.]+(\s+(ASC|DESC))?$", item, re.IGNORECASE):
                    raise SQLGenerationError(f"Invalid ORDER BY clause: {item}")
                safe_orders.append(item)

            parts.append("ORDER BY " + ", ".join(safe_orders))

        if plan.limit is not None:
            if not isinstance(plan.limit, int):
                raise SQLGenerationError("LIMIT must be an integer.")
            parts.append(f"LIMIT {plan.limit}")

        return "\n".join(parts)

    # ==================================================================
    # Multi-Fact SQL Generation (CTE-based)
    # ==================================================================

    def _build_multi_fact_sql(self, plan: MultiFactPlan) -> str:
        """Builds a WITH/CTE query for multi-fact plans.

        Structure:
            WITH cte_fact_a AS (pre-aggregated fact A),
                 cte_fact_b AS (pre-aggregated fact B)
            SELECT COALESCE'd dimensions, measures from each CTE
            FROM cte_fact_a
            FULL OUTER JOIN cte_fact_b ON shared keys
            WHERE measure filters
            ORDER BY / LIMIT
        """
        if not plan.sub_plans:
            raise MultiFactGenerationError(
                summary="MultiFactPlan has no sub-plans",
                details="At least two sub-plans are required for a multi-fact query.",
            )

        # 1. Build CTE definitions
        cte_parts = []
        for sub_plan in plan.sub_plans:
            cte_body = self._build_cte_body(sub_plan)
            cte_parts.append(f"{sub_plan.cte_alias} AS (\n{cte_body}\n)")

        with_clause = "WITH " + ",\n".join(cte_parts)

        # 2. Build outer SELECT
        select_items = []

        for dim in plan.shared_dimensions:
            coalesce_refs = [f"{sp.cte_alias}.{dim.name}" for sp in plan.sub_plans]
            select_items.append(f"    COALESCE({', '.join(coalesce_refs)}) AS {dim.name}")

        for sub_plan in plan.sub_plans:
            for measure in sub_plan.measures:
                select_items.append(f"    {sub_plan.cte_alias}.{measure.name}")

        if not select_items:
            raise MultiFactGenerationError(
                summary="Empty SELECT clause",
                details="Multi-fact query must produce at least one output column.",
            )

        select_clause = "SELECT\n" + ",\n".join(select_items)

        # 3. Build FROM + FULL OUTER JOIN between CTEs
        from_clause = self._build_cte_joins(plan)

        # 4. Build outer WHERE for measure filters
        where_clause = self._build_measure_filter_where(plan)

        # 5. Build ORDER BY / LIMIT
        order_limit = self._build_order_limit_raw(plan.order_by, plan.limit)

        # Assemble
        parts = [with_clause, select_clause, from_clause]

        if where_clause:
            parts.append(where_clause)

        if order_limit:
            parts.append(order_limit)

        return "\n".join(parts) + ";"

    def _build_cte_body(self, sub_plan: SubPlan) -> str:
        """Build the inner SQL for a single CTE (sub-plan).

        SELECT shared_keys, dimensions, aggregated measures
        FROM fact_table
        LEFT JOIN dimension_tables
        WHERE dimension filters
        GROUP BY non-aggregate columns
        """
        select_items = []

        # Shared keys (dimension model PKs for outer-query joining)
        for key in sub_plan.shared_keys:
            select_items.append(
                f"    {key.table_name}.{key.primary_key_column} AS {key.alias}"
            )

        # Dimension columns
        for dim in sub_plan.dimensions:
            owner = self._find_owner_model_in_subplan(dim.name, sub_plan)
            select_items.append(f"    {owner.table}.{dim.column} AS {dim.name}")

        # Aggregated measures
        for measure in sub_plan.measures:
            if measure.column in ("1", "*"):
                expr = measure.column
            else:
                expr = f"{sub_plan.fact_table_name}.{measure.column}"
            select_items.append(
                f"    {self._format_agg(measure.agg, expr)} AS {measure.name}"
            )

        if not select_items:
            raise MultiFactGenerationError(
                summary="Empty CTE SELECT",
                details=f"CTE '{sub_plan.cte_alias}' produces no columns.",
            )

        # FROM
        from_part = f"    {sub_plan.fact_table_name}"

        # JOINs (fact → dimension tables)
        join_parts = []
        for join_node in sub_plan.joins:
            join_parts.append(self._resolve_join_sql(join_node))

        # WHERE (dimension filters pushed into the CTE)
        where_conditions = []
        for filter_obj in sub_plan.filters:
            try:
                owner = self._find_owner_model_in_subplan(filter_obj.field, sub_plan)
                physical_col = self._find_column_name(owner, filter_obj.field)
                col_expr = f"{owner.table}.{physical_col}"
            except (SQLGenerationError, MultiFactGenerationError):
                col_expr = filter_obj.field

            safe_val = self._format_filter_value(filter_obj.operator, filter_obj.value)
            where_conditions.append(f"{col_expr} {filter_obj.operator.upper()} {safe_val}")

        # GROUP BY (indices covering shared_keys + dimensions)
        group_count = len(sub_plan.shared_keys) + len(sub_plan.dimensions)

        # Assemble
        parts = ["SELECT", ",\n".join(select_items), "FROM", from_part]

        if join_parts:
            parts.append("\n".join(join_parts))

        if where_conditions:
            parts.append("WHERE " + " AND ".join(where_conditions))

        if group_count > 0 and sub_plan.measures:
            indices = [str(i + 1) for i in range(group_count)]
            parts.append("GROUP BY " + ", ".join(indices))

        return "\n".join(parts)

    def _build_cte_joins(self, plan: MultiFactPlan) -> str:
        """Build FROM + FULL OUTER JOIN (or CROSS JOIN) between CTEs.

        Join conditions combine two strategies:
        - PK-based keys (``shared_keys``) for pure dimension models
        - Dimension-value keys (``dimension_value_keys``) for dual-role
          models whose PK must stay out of GROUP BY
        """
        first = plan.sub_plans[0]

        if len(plan.sub_plans) == 1:
            return f"FROM {first.cte_alias}"

        has_join_keys = bool(plan.shared_keys) or bool(plan.dimension_value_keys)

        if not has_join_keys:
            parts = [f"FROM {first.cte_alias}"]
            for sp in plan.sub_plans[1:]:
                parts.append(f"CROSS JOIN {sp.cte_alias}")
            return "\n".join(parts)

        # FULL OUTER JOIN with COALESCE'd keys for 3+ CTEs
        parts = [f"FROM {first.cte_alias}"]
        for i, sp in enumerate(plan.sub_plans[1:], start=1):
            on_conditions = []

            # PK-based conditions (pure dimension models)
            for key in plan.shared_keys:
                if i == 1:
                    left_ref = f"{first.cte_alias}.{key.alias}"
                else:
                    prev_refs = [
                        f"{plan.sub_plans[j].cte_alias}.{key.alias}"
                        for j in range(i)
                    ]
                    left_ref = f"COALESCE({', '.join(prev_refs)})"
                on_conditions.append(f"{left_ref} = {sp.cte_alias}.{key.alias}")

            # Dimension-value conditions (dual-role models)
            for dim_name in plan.dimension_value_keys:
                if i == 1:
                    left_ref = f"{first.cte_alias}.{dim_name}"
                else:
                    prev_refs = [
                        f"{plan.sub_plans[j].cte_alias}.{dim_name}"
                        for j in range(i)
                    ]
                    left_ref = f"COALESCE({', '.join(prev_refs)})"
                on_conditions.append(f"{left_ref} = {sp.cte_alias}.{dim_name}")

            parts.append(
                f"FULL OUTER JOIN {sp.cte_alias}\n"
                f"    ON {' AND '.join(on_conditions)}"
            )

        return "\n".join(parts)

    def _build_measure_filter_where(self, plan: MultiFactPlan) -> str:
        """Build WHERE clause for measure filters on the outer query.

        Since CTEs already compute aggregates, measure filters become
        simple column comparisons on the outer query.
        """
        if not plan.measure_filters:
            return ""

        conditions = []
        for filter_obj in plan.measure_filters:
            cte_alias = self._find_measure_cte(filter_obj.field, plan)
            if not cte_alias:
                raise MultiFactGenerationError(
                    summary="Measure not found in any CTE",
                    details=f"Filter field '{filter_obj.field}' doesn't match any CTE measure.",
                )
            safe_val = self._format_filter_value(filter_obj.operator, filter_obj.value)
            conditions.append(
                f"{cte_alias}.{filter_obj.field} {filter_obj.operator.upper()} {safe_val}"
            )

        return "WHERE " + " AND ".join(conditions)

    # ==================================================================
    # Shared helpers
    # ==================================================================

    def _find_owner_model(self, dim_name: str, plan: QueryPlan):
        """Locates the model object for a given dimension name (single-fact)."""
        root = self.registry.models[plan.root_model_name]

        for d in root.dimensions:
            if d.name == dim_name:
                return root

        for join in plan.joins:
            model = self.registry.models[join.target_model]
            for d in model.dimensions:
                if d.name == dim_name:
                    return model

        raise SQLGenerationError(
            summary="Dimension lost during planning",
            details=f"Dimension '{dim_name}' not found in any plan model.",
        )

    def _find_owner_model_in_subplan(self, dim_name: str, sub_plan: SubPlan):
        """Locates the model object for a dimension within a SubPlan's scope."""
        fact_model = self.registry.models[sub_plan.fact_model_name]
        for d in fact_model.dimensions:
            if d.name == dim_name:
                return fact_model

        for join_node in sub_plan.joins:
            model = self.registry.models[join_node.target_model]
            for d in model.dimensions:
                if d.name == dim_name:
                    return model

        raise MultiFactGenerationError(
            summary="Dimension not found in CTE context",
            details=(
                f"Dimension '{dim_name}' not found in models accessible "
                f"from CTE '{sub_plan.cte_alias}'."
            ),
        )

    @staticmethod
    def _find_measure_cte(measure_name: str, plan: MultiFactPlan) -> str | None:
        """Find which CTE alias owns a given measure."""
        for sp in plan.sub_plans:
            if any(m.name == measure_name for m in sp.measures):
                return sp.cte_alias
        return None

    @staticmethod
    def _format_agg(agg: str, expr: str) -> str:
        """Translate semantic agg types into valid SQL aggregate expressions."""
        agg_lower = agg.lower()
        if agg_lower in ("distinct_count", "count_distinct"):
            return f"COUNT(DISTINCT {expr})"
        return f"{agg}({expr})"

    def _find_column_name(self, model, dim_name):
        for d in model.dimensions:
            if d.name == dim_name:
                return d.column
        return dim_name

    def _build_order_limit_raw(self, order_by: list[str], limit: int | None) -> str:
        """Shared ORDER BY / LIMIT builder for any plan type."""
        parts = []
        if order_by:
            safe_orders = []
            for item in order_by:
                if not re.match(r"^[\w\.]+(\s+(ASC|DESC))?$", item, re.IGNORECASE):
                    raise SQLGenerationError(f"Invalid ORDER BY clause: {item}")
                safe_orders.append(item)
            parts.append("ORDER BY " + ", ".join(safe_orders))

        if limit is not None:
            if not isinstance(limit, int):
                raise SQLGenerationError("LIMIT must be an integer.")
            parts.append(f"LIMIT {limit}")

        return "\n".join(parts)

    def _format_filter_value(self, operator: str, value) -> str:
        """Intelligently formats and escapes values based on the SQL operator."""
        op_lower = operator.lower()

        if op_lower in ("is", "is not"):
            if value is None or str(value).upper() == "NULL":
                return "NULL"
            if isinstance(value, bool) or str(value).upper() in ("TRUE", "FALSE"):
                return str(value).upper()
            return f"'{value}'"

        if op_lower in ("in", "not in"):
            if isinstance(value, (list, tuple)):
                safe_vals = [
                    "'{}'".format(str(v).replace("'", "''")) if isinstance(v, str) else str(v)
                    for v in value
                ]
                return f"({', '.join(safe_vals)})"
            elif isinstance(value, str):
                return value

        if value is None or str(value).upper() == "NULL":
            return "NULL"

        if isinstance(value, bool):
            return "TRUE" if value else "FALSE"
        if isinstance(value, (int, float)):
            return str(value)

        str_val = str(value)
        try:
            float(str_val)
            return str_val
        except ValueError:
            pass

        escaped_val = str_val.replace("'", "''")
        return f"'{escaped_val}'"
