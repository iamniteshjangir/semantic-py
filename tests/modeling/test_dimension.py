from pysemantic.modeling import Dimension


def test_dimension_initialization():
    """Test Dimension initialization with name and optional dtype."""
    # Test with default dtype
    dim = Dimension("user_id")
    assert dim.name == "user_id"
    assert dim.dtype == "string"

    # Test with explicit dtype
    dim_date = Dimension("created_at", dtype="date")
    assert dim_date.name == "created_at"
    assert dim_date.dtype == "date"


def test_dimension_repr():
    """Test string representation of Dimension."""
    dim = Dimension("product_id", dtype="integer")
    assert repr(dim) == "Dimension(name='product_id', dtype='integer')"
