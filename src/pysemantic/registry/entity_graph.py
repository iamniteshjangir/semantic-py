import matplotlib.pyplot as plt
import networkx as nx

from pysemantic.exceptions import RegistryError, format_error


class EntityGraph:
    def __init__(self):
        """
        we use a Directed graph, If You need multiple joins between same table (e.g Buyer/Seller)
        You should strictly use distinct Models (Role-Playing Dimensions)
        """
        self.graph = nx.DiGraph()

    def add_node(self, model_name: str):
        """Registers a node in the Graph"""
        if not self.graph.has_node(model_name):
            self.graph.add_node(model_name)

    def add_edge(self, from_model: str, to_model: str, join_on: dict[str, str]):
        """
        Creates a directed edge from Foreign Entity -> Primary Entity

        Args:
            from_model: The model holding the Foreign Key (e.g. 'orders')
            to_model: The model holding the Primary Key (e.g. 'customers')
            join_on: Metadata for SQL generation {'left': 'customer_id', 'right': 'id'}
        """
        self.graph.add_edge(from_model, to_model, join_condition=join_on)

    def validate(self):
        """
        Validations:
        1. Must be Acyclic (DAG)
        2. No isolated islands
        """
        if not nx.is_directed_acyclic_graph(self.graph):
            cycles = list(nx.simple_cycles(self.graph))
            raise RegistryError(
                format_error("registry.entity_graph", "Circular dependency detected! Logic Loop", cycles=cycles)
            )

    def get_join_path(self, start_model: str, end_model: str) -> list[tuple[str, str, dict[str, str]]]:
        """
        Returns the deterministic join path between two models.

        Returns:
            List of steps: [('orders', 'customers', {'left':..., 'right':....}), ...]

        Raises:
            RegistryError: If no path exists or if multiple paths exist (Ambiguity).
        """
        if start_model not in self.graph or end_model not in self.graph:
            raise RegistryError(
                format_error(
                    "registry.entity_graph",
                    "One of the Model not found in the graph",
                    start_model=start_model,
                    end_model=end_model,
                )
            )

        all_paths = list(nx.all_simple_paths(self.graph, source=start_model, target=end_model))

        if len(all_paths) == 0:
            raise RegistryError(
                format_error(
                    "registry.entity_graph",
                    "No path found between these two models",
                    start_model=start_model,
                    end_model=end_model,
                )
            )

        if len(all_paths) > 1:
            raise RegistryError(
                format_error(
                    "registry.entity_graph",
                    "Multiple paths found between these two models",
                    start_model=start_model,
                    end_model=end_model,
                )
            )

        path_nodes = all_paths[0]
        join_chain = []
        for i in range(len(path_nodes) - 1):
            source = path_nodes[i]
            target = path_nodes[i + 1]
            edge_data = self.graph.get_edge_data(source, target)
            join_chain.append((source, target, edge_data["join_condition"]))

        return join_chain

    def visualize_graph(self, output_file: str = "entity_graph.png") -> None:
        """
        Visualizes the entity graph and saves it to a file.

        Args:
            output_file: Path where the graph image will be saved.
        """
        try:
            # Optimize Layout for Hierarchical/DAG structure
            try:
                pos = nx.nx_agraph.graphviz_layout(self.graph, prog="dot")
            except (ImportError, ModuleNotFoundError):
                # Fallback to shell layout
                print("Graphviz not found, using shell layout.")
                pos = nx.shell_layout(self.graph)

            plt.figure(figsize=(10, 8))

            nx.draw(
                self.graph,
                pos,
                with_labels=True,
                node_color="lightblue",
                node_size=2000,
                font_size=10,
                font_weight="bold",
                arrowsize=20,
                arrows=True,
            )

            # Add edge labels (join keys)
            edge_labels = nx.get_edge_attributes(self.graph, "join_condition")
            # Format labels for readability
            formatted_labels = {k: f"{v['left']} -> {v['right']}" for k, v in edge_labels.items()}

            nx.draw_networkx_edge_labels(self.graph, pos, edge_labels=formatted_labels, font_color="red", font_size=8)

            plt.title("Entity Graph")
            plt.axis("off")
            plt.tight_layout()
            plt.savefig(output_file)
            plt.close()
            print(f"Graph visualization saved to {output_file}")
        except Exception as e:
            raise RegistryError(format_error("registry.entity_graph", "Failed to visualize graph", error=str(e))) from e
