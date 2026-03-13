"""Tests for pysemantic CLI (cli.py)."""

import pytest
from typer.testing import CliRunner

from pysemantic.cli import _parse_filter, _split_csv, app

runner = CliRunner()


class TestSplitCsv:
    def test_none_returns_none(self):
        assert _split_csv(None) is None

    def test_single_value(self):
        assert _split_csv(["abc"]) == ["abc"]

    def test_comma_separated(self):
        assert _split_csv(["a,b,c"]) == ["a", "b", "c"]

    def test_mixed_repeat_and_comma(self):
        assert _split_csv(["a,b", "c"]) == ["a", "b", "c"]

    def test_strips_brackets_and_quotes(self):
        result = _split_csv(["['a', 'b']"])
        assert "a" in result
        assert "b" in result

    def test_empty_after_clean_returns_none(self):
        assert _split_csv([""]) is None


class TestParseFilter:
    def test_parse_equals(self):
        result = _parse_filter("order_status = delivered")
        assert result["field"] == "order_status"
        assert result["operator"] == "="
        assert result["value"] == "delivered"

    def test_parse_greater_than(self):
        result = _parse_filter("total_order_price > 100")
        assert result["operator"] == ">"
        assert result["value"] == "100"

    def test_parse_in_operator(self):
        result = _parse_filter("customer_state IN ('SP', 'RJ')")
        assert result["operator"] == "IN"
        assert "SP" in result["value"]

    def test_parse_is_null(self):
        result = _parse_filter("order_status IS NULL")
        assert result["operator"] == "IS"
        assert result["value"] is None

    def test_parse_not_in(self):
        result = _parse_filter("customer_state NOT IN ('MG')")
        assert result["operator"] == "NOT IN"

    def test_parse_like(self):
        result = _parse_filter("customer_city LIKE São%")
        assert result["operator"] == "LIKE"

    def test_parse_invalid_raises(self):
        with pytest.raises(Exception, match="Could not parse"):
            _parse_filter("badfilterstring")


class TestQueryCommand:
    def test_query_generates_sql(self, tmp_path):
        model_file = tmp_path / "orders.py"
        model_file.write_text(
            "from pysemantic.modeling import Model, Dimension, Measure, Entity, EntityType\n"
            "model = Model(\n"
            "    name='orders', table='orders', primary_key='order_id',\n"
            "    dimensions=[Dimension(name='order_status', column='order_status', dtype='string')],\n"
            "    measures=[Measure(name='total_orders', agg='count', column='order_id')],\n"
            "    entities=[Entity(name='order', entity_type=EntityType.PRIMARY, column='order_id')],\n"
            ")\n"
        )
        result = runner.invoke(
            app,
            [
                "query",
                str(tmp_path),
                "-m",
                "total_orders",
                "-d",
                "order_status",
                "--limit",
                "5",
            ],
        )
        assert result.exit_code == 0
        assert "SELECT" in result.stdout

    def test_query_invalid_model_path(self):
        result = runner.invoke(app, ["query", "/nonexistent/path", "-m", "x"])
        assert result.exit_code == 1
        assert "Error" in result.stdout

    def test_query_no_measures(self, tmp_path):
        model_file = tmp_path / "orders.py"
        model_file.write_text(
            "from pysemantic.modeling import Model, Dimension, Measure, Entity, EntityType\n"
            "model = Model(\n"
            "    name='orders', table='orders', primary_key='order_id',\n"
            "    dimensions=[Dimension(name='order_status', column='order_status', dtype='string')],\n"
            "    measures=[Measure(name='total_orders', agg='count', column='order_id')],\n"
            "    entities=[Entity(name='order', entity_type=EntityType.PRIMARY, column='order_id')],\n"
            ")\n"
        )
        result = runner.invoke(app, ["query", str(tmp_path)])
        assert result.exit_code != 0

    def test_query_with_filter(self, tmp_path):
        model_file = tmp_path / "orders.py"
        model_file.write_text(
            "from pysemantic.modeling import Model, Dimension, Measure, Entity, EntityType\n"
            "model = Model(\n"
            "    name='orders', table='orders', primary_key='order_id',\n"
            "    dimensions=[Dimension(name='order_status', column='order_status', dtype='string')],\n"
            "    measures=[Measure(name='total_orders', agg='count', column='order_id')],\n"
            "    entities=[Entity(name='order', entity_type=EntityType.PRIMARY, column='order_id')],\n"
            ")\n"
        )
        result = runner.invoke(
            app,
            [
                "query",
                str(tmp_path),
                "-m",
                "total_orders",
                "-d",
                "order_status",
                "-f",
                "order_status = delivered",
            ],
        )
        assert result.exit_code == 0
        assert "SELECT" in result.stdout

    def test_query_error_prints_message(self, tmp_path):
        model_file = tmp_path / "orders.py"
        model_file.write_text(
            "from pysemantic.modeling import Model, Dimension, Measure, Entity, EntityType\n"
            "model = Model(\n"
            "    name='orders', table='orders', primary_key='order_id',\n"
            "    dimensions=[Dimension(name='order_status', column='order_status', dtype='string')],\n"
            "    measures=[Measure(name='total_orders', agg='count', column='order_id')],\n"
            "    entities=[Entity(name='order', entity_type=EntityType.PRIMARY, column='order_id')],\n"
            ")\n"
        )
        result = runner.invoke(
            app,
            [
                "query",
                str(tmp_path),
                "-m",
                "nonexistent_measure",
            ],
        )
        assert result.exit_code == 1
        assert "Error" in result.stdout


class TestGraphCommand:
    def test_graph_invalid_model_path(self):
        result = runner.invoke(app, ["graph", "/nonexistent/path"])
        assert result.exit_code == 1
        assert "Error" in result.stdout

    def test_graph_generates_file(self, tmp_path):
        model_file = tmp_path / "orders.py"
        model_file.write_text(
            "from pysemantic.modeling import Model, Dimension, Measure, Entity, EntityType\n"
            "model = Model(\n"
            "    name='orders', table='orders', primary_key='order_id',\n"
            "    dimensions=[Dimension(name='order_status', column='order_status', dtype='string')],\n"
            "    measures=[Measure(name='total_orders', agg='count', column='order_id')],\n"
            "    entities=[Entity(name='order', entity_type=EntityType.PRIMARY, column='order_id')],\n"
            ")\n"
        )
        out_file = tmp_path / "graph.html"
        result = runner.invoke(app, ["graph", str(tmp_path), "-o", str(out_file)])
        assert result.exit_code == 0
        assert "Graph saved" in result.stdout


class TestStudioCommand:
    def test_studio_invalid_model_path(self):
        result = runner.invoke(app, ["studio", "/nonexistent/path"])
        assert result.exit_code == 1
        assert "Error" in result.stdout
