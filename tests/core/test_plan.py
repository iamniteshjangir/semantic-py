"""Tests for plan dataclasses (core/plan.py)."""

from pysemantic.core.plan import JoinNode, MultiFactPlan, QueryPlan, SharedDimensionKey, SubPlan
from pysemantic.modeling import Dimension, Measure


def test_join_node():
    j = JoinNode(source_model="a", target_model="b")
    assert j.source_model == "a"
    assert j.target_model == "b"
    assert j.join_type == "LEFT"


def test_query_plan_describe():
    plan = QueryPlan(
        root_model_name="orders",
        root_table_name="orders",
        measures=[Measure(name="m1", agg="sum", column="amt")],
        dimensions=[Dimension(name="d1", column="d1", dtype="string")],
        joins=[],
        filters=[],
        order_by=[],
        limit=5,
    )
    desc = plan.describe()
    assert "orders" in desc
    assert "m1" in desc
    assert "d1" in desc
    assert "5" in desc


def test_shared_dimension_key():
    sk = SharedDimensionKey(
        dimension_model_name="customers",
        table_name="customers",
        primary_key_column="customer_id",
        alias="__pk_customers",
    )
    assert sk.alias == "__pk_customers"


def test_sub_plan():
    sp = SubPlan(
        cte_alias="cte_oi",
        fact_model_name="order_items",
        fact_table_name="order_items",
        measures=[],
        dimensions=[],
        joins=[],
        shared_keys=[],
        filters=[],
    )
    assert sp.cte_alias == "cte_oi"


def test_multi_fact_plan_describe():
    plan = MultiFactPlan(
        sub_plans=[],
        shared_dimensions=[],
        shared_keys=[],
        dimension_value_keys=["customer_state"],
        measure_filters=[],
        order_by=[],
        limit=None,
    )
    desc = plan.describe()
    assert "dimension_value_keys" in desc
    assert "customer_state" in desc
