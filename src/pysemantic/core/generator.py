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

    def __init__(self, registry: Registry):
        # We need the registry to look up Entity definitions for JOIN ON clauses
        self.registry = registry

    def generate(self, plan: QueryPlan) -> str:
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

        # 6. Build ORDER BY / LIMIT
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

            select_items.append(f"    {measure.agg}({expr}) AS {measure.name}")

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
        """Combines filters with AND."""
        if not plan.filters:
            return ""
        # Simple string concatenation for V1
        return "    " + " AND ".join(plan.filters)

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
        """Handles ORDER BY and LIMIT."""
        parts = []
        if plan.order_by:
            parts.append("ORDER BY " + ", ".join(plan.order_by))

        if plan.limit is not None:
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
