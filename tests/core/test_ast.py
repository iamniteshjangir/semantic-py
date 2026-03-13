"""Tests for QueryAST and Filter (core/ast.py)."""

import pytest

from pysemantic.core.ast import ASTValidationError, Filter, QueryAST


class TestFilter:
    def test_valid_operators(self):
        Filter(field="x", operator="=", value=1)
        Filter(field="x", operator="!=", value="a")
        Filter(field="x", operator="in", value="(1,2)")
        Filter(field="x", operator="IS", value=None)

    def test_invalid_operator_raises(self):
        with pytest.raises(ASTValidationError, match="Invalid filter operator"):
            Filter(field="x", operator="<>", value=1)


class TestQueryASTFromRequest:
    def test_minimal_measures_only(self):
        ast = QueryAST.from_request(measures=["m1"])
        assert ast.measures == ["m1"]
        assert ast.dimensions == []
        assert ast.filters == []
        assert ast.order_by == []
        assert ast.limit is None

    def test_with_dimensions_and_order_limit(self):
        ast = QueryAST.from_request(
            measures=["m1"],
            dimensions=["d1"],
            order_by=["m1 DESC"],
            limit=10,
        )
        assert ast.dimensions == ["d1"]
        assert ast.order_by == ["m1 DESC"]
        assert ast.limit == 10

    def test_filter_dict(self):
        ast = QueryAST.from_request(
            measures=["m1"],
            filters=[{"field": "dim_a", "operator": "=", "value": "x"}],
        )
        assert len(ast.filters) == 1
        assert ast.filters[0].field == "dim_a"
        assert ast.filters[0].operator == "="
        assert ast.filters[0].value == "x"

    def test_filter_dict_op_alias(self):
        ast = QueryAST.from_request(
            measures=["m1"],
            filters=[{"field": "dim_a", "op": "=", "value": 5}],
        )
        assert ast.filters[0].operator == "="

    def test_filter_invalid_dict_missing_field_raises(self):
        with pytest.raises(ASTValidationError, match="Invalid filter dictionary"):
            QueryAST.from_request(
                measures=["m1"],
                filters=[{"operator": "=", "value": 1}],
            )

    def test_filter_string_parsed(self):
        ast = QueryAST.from_request(
            measures=["m1"],
            filters=["status = delivered"],
        )
        assert len(ast.filters) == 1
        assert ast.filters[0].field == "status"
        assert ast.filters[0].value == "delivered"

    def test_filter_string_invalid_raises(self):
        with pytest.raises(ASTValidationError, match="Invalid filter string"):
            QueryAST.from_request(measures=["m1"], filters=["not valid"])

    def test_empty_measures_and_dimensions_raises_in_post_init(self):
        with pytest.raises(ASTValidationError, match="at least one metric or dimension"):
            QueryAST(measures=[], dimensions=[], filters=[], order_by=[], limit=None)
