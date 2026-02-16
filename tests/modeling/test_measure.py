from pysemantic.modeling import Measure


def test_measure_initialization():
    """Test Measure initialization with all arguments."""
    measure = Measure("total_sales", "sum", "sales_amount")
    assert measure.name == "total_sales"
    assert measure.agg == "sum"
    assert measure.column == "sales_amount"


def test_measure_repr():
    """Test string representation of Measure."""
    measure = Measure("count_orders", "count", "order_id")
    assert repr(measure) == "Measure(name='count_orders', agg='count', column='order_id')"
