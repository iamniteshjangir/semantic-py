from pysemantic.modeling import Dimension


def test_dimension_initialization():
    """Test Dimension initialization with name and optional dtype."""
    # Test with default dtype
    dim = Dimension("user_id", "user_id")
    assert dim.name == "user_id"
    assert dim.column == "user_id"
    assert dim.dtype == "string"

    # Test with explicit dtype
    dim_date = Dimension("created_at", "created_at_col", dtype="date")
    assert dim_date.name == "created_at"
    assert dim_date.column == "created_at_col"
    assert dim_date.dtype == "date"


def test_dimension_repr():
    """Test string representation of Dimension."""
    dim = Dimension("product_id", "pid", dtype="integer")
    assert repr(dim) == "Dimension(name='product_id', column='pid', dtype='integer')"
