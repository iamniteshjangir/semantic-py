"""Tests for SemanticLayer (client.py)."""

import pytest

from pysemantic.client import SemanticLayer
from pysemantic.core.planner import NonConformedDimensionError


@pytest.fixture
def client_from_models(order_items_model, orders_model, customers_model):
    """SemanticLayer initialized from in-memory models."""
    return SemanticLayer(models=[order_items_model, orders_model, customers_model])


class TestSemanticLayerInit:
    def test_init_requires_model_path_or_models(self):
        with pytest.raises(ValueError, match=r"model_path.*models"):
            SemanticLayer()

    def test_init_rejects_both_model_path_and_models(self, order_items_model):
        with pytest.raises(ValueError, match="not both"):
            SemanticLayer(model_path="/tmp", models=[order_items_model])

    def test_init_invalid_dialect_raises(self, order_items_model):
        with pytest.raises(ValueError, match="Unsupported dialect"):
            SemanticLayer(models=[order_items_model], dialect="invalid_dialect")

    def test_init_from_models(self, client_from_models):
        assert client_from_models.registry is not None
        assert len(client_from_models.registry.models) == 3


class TestSemanticLayerQuery:
    def test_query_single_fact_returns_sql(self, client_from_models):
        sql = client_from_models.query(
            measures=["total_order_price"],
            dimensions=["customer_state"],
            limit=5,
        )
        assert "SELECT" in sql
        assert "order_items" in sql
        assert "customer_state" in sql
        assert "LIMIT 5" in sql

    def test_query_multi_fact_conformed_returns_cte_sql(self, client_from_models):
        sql = client_from_models.query(
            measures=["total_order_price", "total_customers"],
            dimensions=["customer_state"],
        )
        assert "WITH" in sql
        assert "cte_" in sql
        assert "total_order_price" in sql
        assert "total_customers" in sql

    def test_query_grand_total_cross_join(self, client_from_models):
        sql = client_from_models.query(
            measures=["total_order_price", "total_customers"],
            dimensions=[],
        )
        assert "CROSS JOIN" in sql

    def test_query_multi_fact_non_conformed_raises(self, client_from_models):
        with pytest.raises(NonConformedDimensionError, match="Non-conformed"):
            client_from_models.query(
                measures=["total_order_price", "total_customers"],
                dimensions=["order_status"],
            )

    def test_query_with_filter_dict(self, client_from_models):
        sql = client_from_models.query(
            measures=["total_order_price"],
            dimensions=["customer_state"],
            filters=[{"field": "customer_state", "operator": "=", "value": "SP"}],
        )
        assert "SP" in sql
        assert "customer_state" in sql

    def test_query_with_order_by_and_limit(self, client_from_models):
        sql = client_from_models.query(
            measures=["total_order_price"],
            dimensions=["customer_state"],
            order_by=["total_order_price DESC"],
            limit=10,
        )
        assert "ORDER BY" in sql
        assert "LIMIT 10" in sql

    def test_query_reload(self, client_from_models):
        client_from_models.reload(models=list(client_from_models.registry.models.values()))
        sql = client_from_models.query(measures=["total_customers"], dimensions=[])
        assert "customers" in sql

    def test_query_multi_fact_with_measure_filter(self, client_from_models):
        sql = client_from_models.query(
            measures=["total_order_price", "total_customers"],
            dimensions=["customer_state"],
            filters=[{"field": "total_order_price", "operator": ">", "value": "100"}],
        )
        assert "total_order_price" in sql
        assert "WHERE" in sql
