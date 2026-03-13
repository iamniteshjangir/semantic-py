"""Shared fixtures for tests: minimal models and registry for core/client tests."""

import pytest

from pysemantic.modeling import Dimension, Entity, EntityType, Measure, Model
from pysemantic.registry import Registry


@pytest.fixture
def orders_model():
    """Orders table: links order_items to customers."""
    return Model(
        name="orders",
        table="orders",
        primary_key="order_id",
        dimensions=[Dimension(name="order_status", column="order_status", dtype="string")],
        measures=[Measure(name="total_orders", agg="count", column="order_id")],
        entities=[
            Entity(name="order", entity_type=EntityType.PRIMARY, column="order_id"),
            Entity(name="customer", entity_type=EntityType.FOREIGN, column="customer_id"),
        ],
    )


@pytest.fixture
def customers_model():
    """Customers: has measures and dimensions (conformed from order_items via orders)."""
    return Model(
        name="customers",
        table="customers",
        primary_key="customer_id",
        dimensions=[
            Dimension(name="customer_state", column="customer_state", dtype="string"),
            Dimension(name="customer_city", column="customer_city", dtype="string"),
        ],
        measures=[Measure(name="total_customers", agg="count", column="customer_id")],
        entities=[Entity(name="customer", entity_type=EntityType.PRIMARY, column="customer_id")],
    )


@pytest.fixture
def order_items_model():
    """Order items: fact table with FK to orders."""
    return Model(
        name="order_items",
        table="order_items",
        primary_key="order_item_id",
        dimensions=[],
        measures=[
            Measure(name="total_order_price", agg="sum", column="price"),
            Measure(name="item_count", agg="count", column="order_item_id"),
        ],
        entities=[
            Entity(name="order_item", entity_type=EntityType.PRIMARY, column="order_item_id"),
            Entity(name="order", entity_type=EntityType.FOREIGN, column="order_id"),
        ],
    )


@pytest.fixture
def registry_with_three_models(order_items_model, orders_model, customers_model):
    """Registry with order_items -> orders -> customers (single path to customers)."""
    reg = Registry()
    reg.initialize_from_models([order_items_model, orders_model, customers_model])
    return reg
