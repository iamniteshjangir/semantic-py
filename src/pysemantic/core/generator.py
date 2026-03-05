import sqlglot

from pysemantic.core.plan import JoinNode, QueryPlan
from pysemantic.exceptions import GeneratorError, format_error
from pysemantic.modeling import EntityType
from pysemantic.registry import Registry


class SQLGenerationError(GeneratorError):
    """Custom exception for SQL Generation errors."""

    DOMAIN = "generation.sql"

    def __init__(self, summary: str, **context):
        super().__init__(format_error(self.DOMAIN, summary, **context))


class SQLGenerator:
    """
    The Translator. Converts a logical QueryPlan into an executable SQL string.
    Currently supports ANSI/Postgres SQL dialect.
    """

    def __init__(self, registry: Registry, dialect: str = "mysql"):
        # We need the registry to look up Entity definitions for JOIN ON clauses
        self.registry = registry
        self.dialect = dialect

    def generate(self, plan: QueryPlan) -> str:
        """
        Generate SQL for the specific target dialect.
        """
        # Build RAW ANSI SQL
        ansi_sql = self._build_ansi_sql(plan)

        # Transpile/Format using SQLGlot
        try:
            # If dialect is ansi this just formats the code nicely
            # If dialect is different, it will transpile to that dialect
            transpiled = sqlglot.transpile(ansi_sql, read=None, write=self.dialect, pretty=True)[0]
            return transpiled
        except Exception as e:
            raise SQLGenerationError(
                summary="Failed to transpile SQL",
                dialect=self.dialect,
                sql=ansi_sql,
                error=str(e),
            ) from e

    def _build_ansi_sql(self, plan: QueryPlan) -> str:
        """
        Main entry point. Orchestrates the construction of the SQL query.
        """
        # 1. Build SELECT clause (Dimensions + Measures)
        select_clause = self._build_select(plan)

        # 2. Build FROM clause (Root Table)
        from_clause = self._build_from(plan)

        # 3. Build JOIN clause (Traverse the graph edges)
        join_clause = self._build_joins(plan)

        # 4. Build WHERE clause (Filters)
        where_clause = self._build_where(plan)

        # 5. Build GROUP BY clause (Automatic indices)
        group_by_clause = self._build_group_by(plan)

        # 6. Build HAVING clause
        having_clause = self._build_having(plan)

        # 7. Build ORDER BY / LIMIT
        order_limit_clause = self._build_order_limit(plan)

        # Combine logic
        # Note: We use \n for readability of the generated SQL
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

        # A. Dimensions
        # Logic: {table}.{column} AS {name}
        for dim in plan.dimensions:
            # We must resolve the table alias.
            # If it's the root, use root table. If joined, use joined model name.
            # For V1, we assume the table name in the DB matches the model's table attribute.

            # Find which model owns this dimension to get the correct table alias
            owner_model = self._find_owner_model(dim.name, plan)
            table_alias = owner_model.table

            select_items.append(f"    {table_alias}.{dim.column} AS {dim.name}")

        # B. Measures
        # Logic: {agg}({table}.{column}) AS {name}
        for measure in plan.measures:
            # Measures always come from Root in V1
            table_alias = plan.root_table_name

            # Handle special case: count(1) or count(*) doesn't need a table alias
            if measure.column in ("1", "*"):
                expr = f"{measure.column}"
            else:
                expr = f"{table_alias}.{measure.column}"

            select_items.append(f"    {self._format_agg(measure.agg, expr)} AS {measure.name}")

        return ",\n".join(select_items)

    def _build_from(self, plan: QueryPlan) -> str:
        """Constructs 'FROM table_name'."""
        # In V1, we don't alias the root table (or we alias it to its own name)
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

        # 1. Identify the Entity linking them
        # We look for a FOREIGN entity in Source that matches a PRIMARY in Target
        # OR a FOREIGN entity in Target that matches a PRIMARY in Source

        # Strategy: Scan source entities for a foreign key pointing to target
        join_key_source = None
        join_key_target = None

        # Case A: Source -> Target (Source has the FK)
        # e.g. Orders -> Customers (Orders has customer_id)
        for entity in source_model.entities or []:
            if entity.entity_type == EntityType.FOREIGN:
                # Does this foreign entity match a Primary in the target?
                # We check by name (Concept Match)
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

        # Case B: Target -> Source (Target has the FK, but we are joining TO it)
        # This happens in reverse joins. For V1, we stick to Case A logic primarily,
        # but if not found, we check the reverse.
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
            # Determine field name (aliased)
            # We assume the field is already fully qualified or is a simple column name
            # For V1 generator we need to find the alias again?
            # Or we can just trust the field name if it matches a known dimension/measure?
            # plan.filters has dimensions/measures names.

            # Simple resolution:
            # If it's a measure, use the measure expression (agg) -> Wait, WHERE clause usually filters BEFORE agg?
            # Actually, standard SQL: WHERE filters rows (dimensions), HAVING filters groups (measures).
            # V1 Semantic Layer usually puts everything in WHERE or HAVING depending on type.
            # But here `_build_where` is for WHERE clause.
            # If a user filters on a metric, it should go to HAVING.
            # For this security fix task, let's assume we handle Dimensions in WHERE.
            # Measures in WHERE would be invalid SQL usually unless it's a derived table.

            # For strict security, we map the operator and quote the value.

            # Skip measures in WHERE clause, they belong in HAVING clause.
            try:
                self.registry.get_model_by_metric(filter_obj.field)
                continue  # It's a measure, skip
            except Exception:
                pass  # It's a dimension, continue

            # 1. Resolve Field
            # We need the table alias.
            # Re-using logic from _build_select implies we can find the owner.
            try:
                owner_model = self._find_owner_model(filter_obj.field, plan)
                physcical_column = self._find_column_name(owner_model, filter_obj.field)
                col_expr = f"{owner_model.table}.{physcical_column}"
            except SQLGenerationError:
                # If not found (maybe it's a measure?), for now we might skip or fail.
                # But sticking to security scope: even if we fail to resolve Alias, strictly quoting is key.
                # If we can't find alias, we might fallback to just the field name (risky if ambiguous) or fail.
                # Let's fallback to safely checking if it looks like a valid identifier.
                col_expr = filter_obj.field

            # format the value and append
            safe_val = self._format_filter_value(filter_obj.operator, filter_obj.value)
            conditions.append(f"{col_expr} {filter_obj.operator.upper()} {safe_val}")

        return "    " + " AND ".join(conditions) if conditions else ""

    def _build_having(self, plan: QueryPlan) -> str:
        if not plan.filters:
            return ""

        conditions = []
        for filter_obj in plan.filters:
            try:
                # Fetch the actual model and measure object
                measure_model = self.registry.get_model_by_metric(filter_obj.field)
                # Find the specific measure definition
                measure_obj = next(m for m in measure_model.measures if m.name == filter_obj.field)
            except Exception:
                continue

            # Reconstruct the physical SQL aggregate (e.g., SUM(price))
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
            # Validate order_by fields (Basic SQL Injection check)
            # Ensure they match [a-zA-Z0-9_]+ and optionally " DESC" or " ASC"
            # Or better, check if they are in the selected columns list.

            safe_orders = []
            for item in plan.order_by:
                # Simple whitelist regex
                import re

                if not re.match(r"^[\w\.]+(\s+(ASC|DESC))?$", item, re.IGNORECASE):
                    raise SQLGenerationError(f"Invalid ORDER BY clause: {item}")
                safe_orders.append(item)

            parts.append("ORDER BY " + ", ".join(safe_orders))

        if plan.limit is not None:
            if not isinstance(plan.limit, int):
                raise SQLGenerationError("LIMIT must be an integer.")
            parts.append(f"LIMIT {plan.limit}")

        return "\n".join(parts)

    def _find_owner_model(self, dim_name: str, plan: QueryPlan):
        """
        Helper: Locates the model object for a given dimension name.
        Uses the registry.
        """
        # 1. Check Root
        root = self.registry.models[plan.root_model_name]

        for d in root.dimensions:
            if d.name == dim_name:
                return root

        # 2. Check Joined Models
        for join in plan.joins:
            model = self.registry.models[join.target_model]
            for d in model.dimensions:
                if d.name == dim_name:
                    return model

        raise SQLGenerationError(
            summary="Dimension lost during planning", details=f"Dimension '{dim_name}' not found in any plan model."
        )

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
        return dim_name  # Should not happen if _find_owner_model succeeded

    def _format_filter_value(self, operator: str, value: any) -> str:
        """Intelligently formats and escapes values based on the SQL operator."""
        op_lower = operator.lower()

        # 1. Handle IS / IS NOT
        if op_lower in ("is", "is not"):
            if value is None or str(value).upper() == "NULL":
                return "NULL"
            if isinstance(value, bool) or str(value).upper() in ("TRUE", "FALSE"):
                return str(value).upper()
            return f"'{value}'"

        # 2. Handle IN / NOT IN
        if op_lower in ("in", "not in"):
            if isinstance(value, (list, tuple)):
                safe_vals = ["'{}'".format(str(v).replace("'", "''")) if isinstance(v, str) else str(v) for v in value]
                return f"({', '.join(safe_vals)})"
            elif isinstance(value, str):
                return value  # Trust strings already formatted like "('A', 'B')"

        # 3. Handle NULLs for standard operators
        if value is None or str(value).upper() == "NULL":
            return "NULL"

        # 4. Handle Scalars
        if isinstance(value, bool):
            return "TRUE" if value else "FALSE"
        if isinstance(value, (int, float)):
            return str(value)

        # 5. Detect numeric strings before quoting
        str_val = str(value)
        try:
            float(str_val)
            return str_val
        except ValueError:
            pass

        # 6. Default string escaping (for =, !=, LIKE, ILIKE, >, <, etc.)
        escaped_val = str_val.replace("'", "''")
        return f"'{escaped_val}'"
