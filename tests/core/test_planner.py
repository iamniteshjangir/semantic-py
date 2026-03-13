"""Tests for QueryPlanner: single-fact, multi-fact, conformed, Grand Total, errors."""

import pytest

from pysemantic.core.ast import Filter, QueryAST
from pysemantic.core.plan import MultiFactPlan, QueryPlan
from pysemantic.core.planner import (
    MultiFactPlanningError,
    NonConformedDimensionError,
    QueryPlanner,
    QueryPlanningError,
)

# ── Single-Fact Planning ────────────────────────────────────────────


class TestPlannerSingleFact:
    """Single-fact path: all measures from one model."""

    def test_plan_single_fact_returns_query_plan(self, registry_with_three_models):
        planner = QueryPlanner(registry_with_three_models)
        ast = QueryAST(measures=["total_order_price"], dimensions=["customer_state"], filters=[], order_by=[], limit=5)
        plan = planner.plan(ast)
        assert isinstance(plan, QueryPlan)
        assert plan.root_model_name == "order_items"
        assert plan.root_table_name == "order_items"
        assert len(plan.measures) == 1
        assert plan.measures[0].name == "total_order_price"
        assert len(plan.dimensions) == 1
        assert plan.dimensions[0].name == "customer_state"
        assert plan.limit == 5

    def test_plan_single_fact_with_joins(self, registry_with_three_models):
        planner = QueryPlanner(registry_with_three_models)
        ast = QueryAST(
            measures=["total_order_price"], dimensions=["customer_state"], filters=[], order_by=[], limit=None
        )
        plan = planner.plan(ast)
        assert len(plan.joins) == 2
        join_targets = [j.target_model for j in plan.joins]
        assert "orders" in join_targets
        assert "customers" in join_targets

    def test_plan_single_fact_no_dimensions(self, registry_with_three_models):
        planner = QueryPlanner(registry_with_three_models)
        ast = QueryAST(measures=["total_order_price"], dimensions=[], filters=[], order_by=[], limit=None)
        plan = planner.plan(ast)
        assert plan.dimensions == []
        assert plan.joins == []

    def test_plan_single_fact_with_dimension_filter(self, registry_with_three_models):
        planner = QueryPlanner(registry_with_three_models)
        ast = QueryAST(
            measures=["total_order_price"],
            dimensions=["customer_state"],
            filters=[Filter(field="customer_city", operator="=", value="SP")],
            order_by=[],
            limit=None,
        )
        plan = planner.plan(ast)
        assert len(plan.filters) == 1
        assert plan.filters[0].field == "customer_city"

    def test_plan_single_fact_with_measure_filter(self, registry_with_three_models):
        planner = QueryPlanner(registry_with_three_models)
        ast = QueryAST(
            measures=["total_order_price"],
            dimensions=["customer_state"],
            filters=[Filter(field="total_order_price", operator=">", value="100")],
            order_by=[],
            limit=None,
        )
        plan = planner.plan(ast)
        assert len(plan.filters) == 1

    def test_plan_single_fact_with_order_by(self, registry_with_three_models):
        planner = QueryPlanner(registry_with_three_models)
        ast = QueryAST(
            measures=["total_order_price"],
            dimensions=["customer_state"],
            filters=[],
            order_by=["total_order_price DESC"],
            limit=None,
        )
        plan = planner.plan(ast)
        assert plan.order_by == ["total_order_price DESC"]

    def test_plan_single_fact_metric_not_found_raises(self, registry_with_three_models):
        planner = QueryPlanner(registry_with_three_models)
        ast = QueryAST(measures=["nonexistent_measure"], dimensions=[], filters=[], order_by=[], limit=None)
        with pytest.raises(QueryPlanningError, match="not found"):
            planner.plan(ast)

    def test_plan_empty_measures_raises(self, registry_with_three_models):
        planner = QueryPlanner(registry_with_three_models)
        ast = QueryAST(measures=[], dimensions=["d1"], filters=[], order_by=[], limit=None)
        with pytest.raises(QueryPlanningError, match="at least one metric"):
            planner.plan(ast)

    def test_plan_single_fact_invalid_filter_field_raises(self, registry_with_three_models):
        planner = QueryPlanner(registry_with_three_models)
        ast = QueryAST(
            measures=["total_order_price"],
            dimensions=[],
            filters=[Filter(field="nonexistent_dim", operator="=", value="x")],
            order_by=[],
            limit=None,
        )
        with pytest.raises(QueryPlanningError):
            planner.plan(ast)

    def test_plan_single_fact_invalid_order_by_raises(self, registry_with_three_models):
        planner = QueryPlanner(registry_with_three_models)
        ast = QueryAST(
            measures=["total_order_price"],
            dimensions=[],
            filters=[],
            order_by=["nonexistent_field DESC"],
            limit=None,
        )
        with pytest.raises(QueryPlanningError, match="Invalid order_by"):
            planner.plan(ast)

    def test_plan_single_fact_dimension_not_found_raises(self, registry_with_three_models):
        planner = QueryPlanner(registry_with_three_models)
        ast = QueryAST(
            measures=["total_order_price"],
            dimensions=["nonexistent_dim"],
            filters=[],
            order_by=[],
            limit=None,
        )
        with pytest.raises(QueryPlanningError, match="Dimension not found"):
            planner.plan(ast)

    def test_plan_single_fact_multiple_measures(self, registry_with_three_models):
        planner = QueryPlanner(registry_with_three_models)
        ast = QueryAST(
            measures=["total_order_price", "item_count"],
            dimensions=[],
            filters=[],
            order_by=[],
            limit=None,
        )
        plan = planner.plan(ast)
        assert isinstance(plan, QueryPlan)
        assert len(plan.measures) == 2


# ── Multi-Fact Planning ─────────────────────────────────────────────


class TestPlannerMultiFact:
    """Multi-fact path: measures from 2+ models -> MultiFactPlan."""

    def test_plan_multi_fact_conformed_returns_multi_fact_plan(self, registry_with_three_models):
        planner = QueryPlanner(registry_with_three_models)
        ast = QueryAST(
            measures=["total_order_price", "total_customers"],
            dimensions=["customer_state"],
            filters=[],
            order_by=[],
            limit=None,
        )
        plan = planner.plan(ast)
        assert isinstance(plan, MultiFactPlan)
        assert len(plan.sub_plans) == 2
        assert plan.shared_dimensions
        assert any(d.name == "customer_state" for d in plan.shared_dimensions)

    def test_plan_multi_fact_grand_total_no_dimensions(self, registry_with_three_models):
        planner = QueryPlanner(registry_with_three_models)
        ast = QueryAST(
            measures=["total_order_price", "total_customers"],
            dimensions=[],
            filters=[],
            order_by=[],
            limit=None,
        )
        plan = planner.plan(ast)
        assert isinstance(plan, MultiFactPlan)
        assert len(plan.sub_plans) == 2
        assert plan.shared_dimensions == []
        assert plan.shared_keys == []
        assert plan.dimension_value_keys == []

    def test_plan_multi_fact_non_conformed_dimension_raises(self, registry_with_three_models):
        """order_status is only on orders; customers cannot reach it."""
        planner = QueryPlanner(registry_with_three_models)
        ast = QueryAST(
            measures=["total_order_price", "total_customers"],
            dimensions=["order_status"],
            filters=[],
            order_by=[],
            limit=None,
        )
        with pytest.raises(NonConformedDimensionError, match="Non-conformed Dimension"):
            planner.plan(ast)

    def test_plan_multi_fact_non_conformed_filter_raises(self, registry_with_three_models):
        """In conformed mode, a filter on order_status (non-conformed) must be rejected."""
        planner = QueryPlanner(registry_with_three_models)
        ast = QueryAST.from_request(
            measures=["total_order_price", "total_customers"],
            dimensions=["customer_state"],
            filters=[{"field": "order_status", "operator": "=", "value": "delivered"}],
        )
        with pytest.raises(NonConformedDimensionError, match="Non-conformed Dimension"):
            planner.plan(ast)

    def test_plan_multi_fact_conformed_filter_ok(self, registry_with_three_models):
        """Conformed filter (customer_city) should be pushed into all CTEs."""
        planner = QueryPlanner(registry_with_three_models)
        ast = QueryAST.from_request(
            measures=["total_order_price", "total_customers"],
            dimensions=["customer_state"],
            filters=[{"field": "customer_city", "operator": "=", "value": "SP"}],
        )
        plan = planner.plan(ast)
        assert isinstance(plan, MultiFactPlan)
        assert len(plan.sub_plans) == 2
        for sp in plan.sub_plans:
            assert any(f.field == "customer_city" for f in sp.filters)

    def test_plan_multi_fact_with_measure_filter(self, registry_with_three_models):
        planner = QueryPlanner(registry_with_three_models)
        ast = QueryAST.from_request(
            measures=["total_order_price", "total_customers"],
            dimensions=["customer_state"],
            filters=[{"field": "total_order_price", "operator": ">", "value": "100"}],
        )
        plan = planner.plan(ast)
        assert len(plan.measure_filters) == 1
        assert plan.measure_filters[0].field == "total_order_price"

    def test_plan_multi_fact_invalid_measure_filter_model_raises(self, registry_with_three_models):
        """Filter on a measure that's not a fact model in this query."""
        planner = QueryPlanner(registry_with_three_models)
        ast = QueryAST.from_request(
            measures=["total_order_price", "total_customers"],
            dimensions=["customer_state"],
            filters=[{"field": "total_orders", "operator": ">", "value": "5"}],
        )
        with pytest.raises(MultiFactPlanningError, match="Invalid measure filter"):
            planner.plan(ast)

    def test_plan_multi_fact_with_order_by(self, registry_with_three_models):
        planner = QueryPlanner(registry_with_three_models)
        ast = QueryAST(
            measures=["total_order_price", "total_customers"],
            dimensions=["customer_state"],
            filters=[],
            order_by=["total_order_price DESC"],
            limit=10,
        )
        plan = planner.plan(ast)
        assert plan.order_by == ["total_order_price DESC"]
        assert plan.limit == 10

    def test_plan_multi_fact_invalid_order_by_raises(self, registry_with_three_models):
        planner = QueryPlanner(registry_with_three_models)
        ast = QueryAST(
            measures=["total_order_price", "total_customers"],
            dimensions=["customer_state"],
            filters=[],
            order_by=["nonexistent DESC"],
            limit=None,
        )
        with pytest.raises(MultiFactPlanningError, match="Invalid order_by"):
            planner.plan(ast)

    def test_plan_multi_fact_dimension_value_keys(self, registry_with_three_models):
        """customer_state belongs to customers (also a fact) → dimension_value_keys."""
        planner = QueryPlanner(registry_with_three_models)
        ast = QueryAST(
            measures=["total_order_price", "total_customers"],
            dimensions=["customer_state"],
            filters=[],
            order_by=[],
            limit=None,
        )
        plan = planner.plan(ast)
        assert "customer_state" in plan.dimension_value_keys

    def test_plan_multi_fact_grand_total_with_non_conformed_filter(self, registry_with_three_models):
        """Grand Total mode allows non-conformed filter dims, routed to accessible CTEs."""
        planner = QueryPlanner(registry_with_three_models)
        ast = QueryAST.from_request(
            measures=["total_order_price", "total_customers"],
            dimensions=[],
            filters=[{"field": "order_status", "operator": "=", "value": "delivered"}],
        )
        plan = planner.plan(ast)
        assert isinstance(plan, MultiFactPlan)
        assert plan.shared_dimensions == []

    def test_plan_multi_fact_dimension_not_found_raises(self, registry_with_three_models):
        planner = QueryPlanner(registry_with_three_models)
        ast = QueryAST(
            measures=["total_order_price", "total_customers"],
            dimensions=["nonexistent_dim"],
            filters=[],
            order_by=[],
            limit=None,
        )
        with pytest.raises(MultiFactPlanningError, match="Dimension not found"):
            planner.plan(ast)

    def test_plan_multi_fact_subplan_structure(self, registry_with_three_models):
        planner = QueryPlanner(registry_with_three_models)
        ast = QueryAST(
            measures=["total_order_price", "total_customers"],
            dimensions=["customer_state"],
            filters=[],
            order_by=[],
            limit=None,
        )
        plan = planner.plan(ast)
        fact_names = {sp.fact_model_name for sp in plan.sub_plans}
        assert fact_names == {"order_items", "customers"}
        for sp in plan.sub_plans:
            assert sp.cte_alias.startswith("cte_")
            assert len(sp.measures) >= 1
            assert len(sp.dimensions) >= 1


# ── Helper Methods ──────────────────────────────────────────────────


class TestFindSharedDimensionOwner:
    """_find_shared_dimension_owner: prefer non-fact model."""

    def test_returns_fact_model_when_only_option(self, registry_with_three_models):
        planner = QueryPlanner(registry_with_three_models)
        fact_names = {"order_items", "customers"}
        owner = planner._find_shared_dimension_owner("customer_state", fact_names)
        assert owner.name == "customers"

    def test_dimension_not_found_raises(self, registry_with_three_models):
        planner = QueryPlanner(registry_with_three_models)
        with pytest.raises(MultiFactPlanningError, match="Dimension not found"):
            planner._find_shared_dimension_owner("nonexistent_dim", {"order_items", "customers"})


class TestHelperMethods:
    def test_is_measure_true(self, registry_with_three_models):
        planner = QueryPlanner(registry_with_three_models)
        assert planner._is_measure("total_order_price") is True

    def test_is_measure_false(self, registry_with_three_models):
        planner = QueryPlanner(registry_with_three_models)
        assert planner._is_measure("customer_state") is False

    def test_can_reach_self(self, registry_with_three_models):
        planner = QueryPlanner(registry_with_three_models)
        model = registry_with_three_models.models["customers"]
        assert planner._can_reach("customers", model) is True

    def test_can_reach_via_graph(self, registry_with_three_models):
        planner = QueryPlanner(registry_with_three_models)
        model = registry_with_three_models.models["customers"]
        assert planner._can_reach("order_items", model) is True

    def test_can_reach_false(self, registry_with_three_models):
        planner = QueryPlanner(registry_with_three_models)
        model = registry_with_three_models.models["order_items"]
        assert planner._can_reach("customers", model) is False

    def test_is_reachable_from_all(self, registry_with_three_models):
        planner = QueryPlanner(registry_with_three_models)
        owner = registry_with_three_models.models["customers"]
        assert planner._is_reachable_from_all(owner, {"order_items", "customers"}) is True
