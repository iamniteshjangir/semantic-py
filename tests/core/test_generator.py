"""Tests for SQLGenerator: single-fact SQL and multi-fact CTE SQL."""

import pytest

from pysemantic.core.ast import Filter
from pysemantic.core.generator import MultiFactGenerationError, SQLGenerationError, SQLGenerator
from pysemantic.core.plan import (
    JoinNode,
    MultiFactPlan,
    QueryPlan,
    SharedDimensionKey,
    SubPlan,
)
from pysemantic.modeling import Dimension, Measure


@pytest.fixture
def generator(registry_with_three_models):
    return SQLGenerator(registry_with_three_models, dialect="mysql")


# ── Single-Fact SQL ─────────────────────────────────────────────────


class TestGeneratorSingleFact:
    def test_generate_single_fact_basic(self, generator, registry_with_three_models):
        plan = QueryPlan(
            root_model_name="order_items",
            root_table_name="order_items",
            measures=[
                next(m for m in registry_with_three_models.models["order_items"].measures if m.name == "total_order_price"),
            ],
            dimensions=[
                next(d for d in registry_with_three_models.models["customers"].dimensions if d.name == "customer_state"),
            ],
            joins=[
                JoinNode("order_items", "orders"),
                JoinNode("orders", "customers"),
            ],
            filters=[],
            order_by=[],
            limit=10,
        )
        sql = generator.generate(plan)
        assert "SELECT" in sql
        assert "order_items" in sql
        assert "LEFT JOIN" in sql
        assert "GROUP BY" in sql
        assert "LIMIT 10" in sql

    def test_generate_single_fact_with_where(self, generator, registry_with_three_models):
        plan = QueryPlan(
            root_model_name="customers",
            root_table_name="customers",
            measures=[
                next(m for m in registry_with_three_models.models["customers"].measures if m.name == "total_customers"),
            ],
            dimensions=[],
            joins=[],
            filters=[Filter(field="customer_state", operator="=", value="SP")],
            order_by=[],
            limit=None,
        )
        sql = generator.generate(plan)
        assert "WHERE" in sql
        assert "customer_state" in sql

    def test_generate_single_fact_with_having(self, generator, registry_with_three_models):
        plan = QueryPlan(
            root_model_name="customers",
            root_table_name="customers",
            measures=[
                next(m for m in registry_with_three_models.models["customers"].measures if m.name == "total_customers"),
            ],
            dimensions=[
                next(d for d in registry_with_three_models.models["customers"].dimensions if d.name == "customer_state"),
            ],
            joins=[],
            filters=[Filter(field="total_customers", operator=">", value="5")],
            order_by=[],
            limit=None,
        )
        sql = generator.generate(plan)
        assert "HAVING" in sql

    def test_generate_single_fact_order_by(self, generator, registry_with_three_models):
        plan = QueryPlan(
            root_model_name="customers",
            root_table_name="customers",
            measures=[
                next(m for m in registry_with_three_models.models["customers"].measures if m.name == "total_customers"),
            ],
            dimensions=[
                next(d for d in registry_with_three_models.models["customers"].dimensions if d.name == "customer_state"),
            ],
            joins=[],
            filters=[],
            order_by=["total_customers DESC"],
            limit=None,
        )
        sql = generator.generate(plan)
        assert "ORDER BY" in sql
        assert "total_customers DESC" in sql

    def test_generate_single_fact_invalid_order_by_raises(self, generator):
        plan = QueryPlan(
            root_model_name="customers",
            root_table_name="customers",
            measures=[Measure(name="m", agg="count", column="id")],
            dimensions=[],
            joins=[],
            filters=[],
            order_by=["invalid; DROP TABLE"],
            limit=None,
        )
        with pytest.raises(SQLGenerationError, match="Invalid ORDER BY"):
            generator.generate(plan)

    def test_generate_single_fact_no_measures_no_group_by(self, generator, registry_with_three_models):
        plan = QueryPlan(
            root_model_name="customers",
            root_table_name="customers",
            measures=[],
            dimensions=[
                next(d for d in registry_with_three_models.models["customers"].dimensions if d.name == "customer_state"),
            ],
            joins=[],
            filters=[],
            order_by=[],
            limit=None,
        )
        sql = generator.generate(plan)
        assert "GROUP BY" not in sql


# ── Multi-Fact CTE SQL ──────────────────────────────────────────────


class TestGeneratorMultiFact:
    def test_generate_multi_fact_cte_cross_join(self, generator, registry_with_three_models):
        """Grand Total: no dimensions -> CROSS JOIN."""
        sub1 = SubPlan(
            cte_alias="cte_order_items",
            fact_model_name="order_items",
            fact_table_name="order_items",
            measures=[
                next(m for m in registry_with_three_models.models["order_items"].measures if m.name == "total_order_price"),
            ],
            dimensions=[],
            joins=[],
            shared_keys=[],
            filters=[],
        )
        sub2 = SubPlan(
            cte_alias="cte_customers",
            fact_model_name="customers",
            fact_table_name="customers",
            measures=[
                next(m for m in registry_with_three_models.models["customers"].measures if m.name == "total_customers"),
            ],
            dimensions=[],
            joins=[],
            shared_keys=[],
            filters=[],
        )
        plan = MultiFactPlan(
            sub_plans=[sub1, sub2],
            shared_dimensions=[],
            shared_keys=[],
            dimension_value_keys=[],
            measure_filters=[],
            order_by=[],
            limit=None,
        )
        sql = generator.generate(plan)
        assert "WITH" in sql
        assert "cte_order_items" in sql
        assert "cte_customers" in sql
        assert "CROSS JOIN" in sql

    def test_generate_multi_fact_with_dimension_value_join(self, generator, registry_with_three_models):
        """Conformed dimension from customers (dimension_value_keys)."""
        dim = next(d for d in registry_with_three_models.models["customers"].dimensions if d.name == "customer_state")
        sub1 = SubPlan(
            cte_alias="cte_order_items",
            fact_model_name="order_items",
            fact_table_name="order_items",
            measures=[
                next(m for m in registry_with_three_models.models["order_items"].measures if m.name == "total_order_price"),
            ],
            dimensions=[dim],
            joins=[JoinNode("order_items", "orders"), JoinNode("orders", "customers")],
            shared_keys=[],
            filters=[],
        )
        sub2 = SubPlan(
            cte_alias="cte_customers",
            fact_model_name="customers",
            fact_table_name="customers",
            measures=[
                next(m for m in registry_with_three_models.models["customers"].measures if m.name == "total_customers"),
            ],
            dimensions=[dim],
            joins=[],
            shared_keys=[],
            filters=[],
        )
        plan = MultiFactPlan(
            sub_plans=[sub1, sub2],
            shared_dimensions=[dim],
            shared_keys=[],
            dimension_value_keys=["customer_state"],
            measure_filters=[],
            order_by=[],
            limit=5,
        )
        sql = generator.generate(plan)
        assert "WITH" in sql
        assert "customer_state" in sql
        assert "COALESCE" in sql
        assert "LIMIT 5" in sql

    def test_generate_multi_fact_with_shared_key(self, generator, registry_with_three_models):
        """PK-based shared key join."""
        dim = next(d for d in registry_with_three_models.models["customers"].dimensions if d.name == "customer_state")
        sk = SharedDimensionKey(
            dimension_model_name="customers",
            table_name="customers",
            primary_key_column="customer_id",
            alias="__pk_customers",
        )
        sub1 = SubPlan(
            cte_alias="cte_order_items",
            fact_model_name="order_items",
            fact_table_name="order_items",
            measures=[
                next(m for m in registry_with_three_models.models["order_items"].measures if m.name == "total_order_price"),
            ],
            dimensions=[dim],
            joins=[JoinNode("order_items", "orders"), JoinNode("orders", "customers")],
            shared_keys=[sk],
            filters=[],
        )
        sub2 = SubPlan(
            cte_alias="cte_customers",
            fact_model_name="customers",
            fact_table_name="customers",
            measures=[
                next(m for m in registry_with_three_models.models["customers"].measures if m.name == "total_customers"),
            ],
            dimensions=[dim],
            joins=[],
            shared_keys=[sk],
            filters=[],
        )
        plan = MultiFactPlan(
            sub_plans=[sub1, sub2],
            shared_dimensions=[dim],
            shared_keys=[sk],
            dimension_value_keys=[],
            measure_filters=[],
            order_by=[],
            limit=None,
        )
        sql = generator.generate(plan)
        assert "__pk_customers" in sql
        assert "COALESCE" in sql

    def test_generate_multi_fact_with_measure_filter(self, generator, registry_with_three_models):
        sub1 = SubPlan(
            cte_alias="cte_order_items",
            fact_model_name="order_items",
            fact_table_name="order_items",
            measures=[
                next(m for m in registry_with_three_models.models["order_items"].measures if m.name == "total_order_price"),
            ],
            dimensions=[],
            joins=[],
            shared_keys=[],
            filters=[],
        )
        sub2 = SubPlan(
            cte_alias="cte_customers",
            fact_model_name="customers",
            fact_table_name="customers",
            measures=[
                next(m for m in registry_with_three_models.models["customers"].measures if m.name == "total_customers"),
            ],
            dimensions=[],
            joins=[],
            shared_keys=[],
            filters=[],
        )
        plan = MultiFactPlan(
            sub_plans=[sub1, sub2],
            shared_dimensions=[],
            shared_keys=[],
            dimension_value_keys=[],
            measure_filters=[Filter(field="total_order_price", operator=">", value="100")],
            order_by=[],
            limit=None,
        )
        sql = generator.generate(plan)
        assert "WHERE" in sql
        assert "total_order_price" in sql

    def test_generate_multi_fact_with_cte_filter(self, generator, registry_with_three_models):
        dim = next(d for d in registry_with_three_models.models["customers"].dimensions if d.name == "customer_state")
        sub1 = SubPlan(
            cte_alias="cte_order_items",
            fact_model_name="order_items",
            fact_table_name="order_items",
            measures=[
                next(m for m in registry_with_three_models.models["order_items"].measures if m.name == "total_order_price"),
            ],
            dimensions=[dim],
            joins=[JoinNode("order_items", "orders"), JoinNode("orders", "customers")],
            shared_keys=[],
            filters=[Filter(field="customer_state", operator="=", value="SP")],
        )
        sub2 = SubPlan(
            cte_alias="cte_customers",
            fact_model_name="customers",
            fact_table_name="customers",
            measures=[
                next(m for m in registry_with_three_models.models["customers"].measures if m.name == "total_customers"),
            ],
            dimensions=[dim],
            joins=[],
            shared_keys=[],
            filters=[Filter(field="customer_state", operator="=", value="SP")],
        )
        plan = MultiFactPlan(
            sub_plans=[sub1, sub2],
            shared_dimensions=[dim],
            shared_keys=[],
            dimension_value_keys=["customer_state"],
            measure_filters=[],
            order_by=[],
            limit=None,
        )
        sql = generator.generate(plan)
        assert sql.count("customer_state") >= 4

    def test_generate_multi_fact_empty_sub_plans_raises(self, generator):
        plan = MultiFactPlan(
            sub_plans=[],
            shared_dimensions=[],
            shared_keys=[],
            dimension_value_keys=[],
            measure_filters=[],
            order_by=[],
            limit=None,
        )
        with pytest.raises(MultiFactGenerationError, match="no sub-plans"):
            generator.generate(plan)

    def test_generate_multi_fact_single_sub_plan(self, generator, registry_with_three_models):
        sub = SubPlan(
            cte_alias="cte_order_items",
            fact_model_name="order_items",
            fact_table_name="order_items",
            measures=[
                next(m for m in registry_with_three_models.models["order_items"].measures if m.name == "total_order_price"),
            ],
            dimensions=[],
            joins=[],
            shared_keys=[],
            filters=[],
        )
        plan = MultiFactPlan(
            sub_plans=[sub],
            shared_dimensions=[],
            shared_keys=[],
            dimension_value_keys=[],
            measure_filters=[],
            order_by=[],
            limit=None,
        )
        sql = generator.generate(plan)
        assert "WITH" in sql
        assert "FROM cte_order_items" in sql


# ── Shared Helpers ──────────────────────────────────────────────────


class TestGeneratorHelpers:
    def test_format_agg_sum(self):
        assert SQLGenerator._format_agg("sum", "t.col") == "sum(t.col)"

    def test_format_agg_distinct_count(self):
        assert SQLGenerator._format_agg("distinct_count", "t.col") == "COUNT(DISTINCT t.col)"

    def test_format_agg_count_distinct(self):
        assert SQLGenerator._format_agg("count_distinct", "t.col") == "COUNT(DISTINCT t.col)"

    def test_format_filter_value_null(self, generator):
        assert generator._format_filter_value("IS", None) == "NULL"

    def test_format_filter_value_bool(self, generator):
        assert generator._format_filter_value("=", True) == "TRUE"

    def test_format_filter_value_in_list(self, generator):
        result = generator._format_filter_value("IN", ["a", "b"])
        assert "'a'" in result
        assert "'b'" in result

    def test_format_filter_value_in_string(self, generator):
        result = generator._format_filter_value("IN", "('SP', 'RJ')")
        assert result == "('SP', 'RJ')"

    def test_format_filter_value_number(self, generator):
        assert generator._format_filter_value("=", 42) == "42"

    def test_format_filter_value_numeric_string(self, generator):
        assert generator._format_filter_value("=", "100") == "100"

    def test_format_filter_value_string(self, generator):
        assert generator._format_filter_value("=", "hello") == "'hello'"

    def test_format_filter_value_escapes_quotes(self, generator):
        assert generator._format_filter_value("=", "it's") == "'it''s'"
