import pytest

from pysemantic.exceptions import RegistryError
from pysemantic.registry.entity_graph import EntityGraph


@pytest.fixture
def empty_graph():
    return EntityGraph()


def test_add_node(empty_graph):
    """Test adding nodes to the graph."""
    empty_graph.add_node("model_a")
    assert "model_a" in empty_graph.graph

    # Adding same node again should be idempotent
    empty_graph.add_node("model_a")
    assert "model_a" in empty_graph.graph


def test_add_edge_and_path(empty_graph):
    """Test adding edges and retrieving join path."""
    empty_graph.add_node("orders")
    empty_graph.add_node("customers")

    join_condition = {"left": "customer_id", "right": "id"}
    empty_graph.add_edge("orders", "customers", join_condition)

    path = empty_graph.get_join_path("orders", "customers")

    assert len(path) == 1
    assert path[0] == ("orders", "customers", join_condition)


def test_join_path_validation_no_node(empty_graph):
    """Test validation when nodes don't exist."""
    with pytest.raises(RegistryError) as exc:
        empty_graph.get_join_path("non_existent", "other")
    assert "Model not found" in str(exc.value)


def test_join_path_no_path(empty_graph):
    """Test validation when no path exists between disconnected nodes."""
    empty_graph.add_node("A")
    empty_graph.add_node("B")

    with pytest.raises(RegistryError) as exc:
        empty_graph.get_join_path("A", "B")
    assert "No path found" in str(exc.value)


def test_ambiguous_join_path(empty_graph):
    """Test validation when multiple paths exist."""
    # A -> B -> D
    # A -> C -> D
    empty_graph.add_node("A")
    empty_graph.add_node("B")
    empty_graph.add_node("C")
    empty_graph.add_node("D")

    empty_graph.add_edge("A", "B", {"j": "1"})
    empty_graph.add_edge("B", "D", {"j": "2"})

    empty_graph.add_edge("A", "C", {"j": "3"})
    empty_graph.add_edge("C", "D", {"j": "4"})

    with pytest.raises(RegistryError) as exc:
        empty_graph.get_join_path("A", "D")
    assert "Multiple paths found" in str(exc.value)


def test_validate_acyclic(empty_graph):
    """Test cycle detection."""
    # A -> B -> A
    empty_graph.add_node("A")
    empty_graph.add_node("B")

    empty_graph.add_edge("A", "B", {})
    empty_graph.add_edge("B", "A", {})

    with pytest.raises(RegistryError) as exc:
        empty_graph.validate()
    assert "Circular dependency detected" in str(exc.value)


def test_visualize_graph_error_handling(empty_graph):
    """Verify that verify_graph raises RegistryError on failure (e.g. invalid path)."""
    empty_graph.add_node("A")

    # We provoke an error by trying to save to a non-existent directory
    with pytest.raises(RegistryError) as exc:
        empty_graph.visualize_graph("/non_existent_folder/graph.png")

    assert "Failed to visualize graph" in str(exc.value)
