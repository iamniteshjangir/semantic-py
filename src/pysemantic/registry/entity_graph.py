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

    def visualize_graph(self, output_file: str = "entity_graph.html") -> None:
        """
        Visualizes the entity graph using PyVis for an interactive HTML experience.

        Args:
            output_file: Path where the interactive HTML will be saved.
        """
        try:
            from pyvis.network import Network

            # Initialize the Network
            # directed=True ensures arrows point from Foreign Key -> Primary Key
            net = Network(height="800px", width="100%", bgcolor="#ffffff", font_color="#333333", directed=True)

            # 1. Add Nodes with Semantic Styling
            for node in self.graph.nodes():
                # Heuristic: Nodes with no incoming edges are likely Fact/Root tables
                is_root = self.graph.in_degree(node) == 0

                net.add_node(
                    node,
                    label=node,
                    title=f"Model: {node} ({'Root' if is_root else 'Dimension'})",
                    color="#FF6B6B" if is_root else "#45B7D1",
                    size=35 if is_root else 25,
                    shape="dot",
                    font={"size": 16, "face": "Arial", "weight": "bold"},
                )

            # 2. Add Edges with Join Condition Tooltips
            edge_data = self.graph.edges(data=True)
            for source, target, data in edge_data:
                join_meta = data.get("join_condition", {})
                join_label = f"{join_meta.get('left')} 🔗 {join_meta.get('right')}"

                net.add_edge(
                    source,
                    target,
                    label=join_label,
                    title=f"Join Logic: {join_label}",  # Shown on hover
                    color="#999999",
                    width=2,
                    arrowStrikethrough=False,
                    smooth={"type": "curvedCW", "roundness": 0.2},  # Prevents overlapping straight lines
                )

            # 3. Configure Layout (Hierarchical vs Physics)
            # We use hierarchical UD (Up-Down) to reflect the Snowflake/Star schema flow
            net.set_options("""
            var options = {
              "layout": {
                "hierarchical": {
                  "enabled": true,
                  "levelSeparation": 200,
                  "nodeSpacing": 250,
                  "treeSpacing": 250,
                  "direction": "UD",
                  "sortMethod": "directed"
                }
              },
              "physics": {
                "enabled": false
              },
              "interaction": {
                "hover": true,
                "navigationButtons": true,
                "tooltipDelay": 100
              }
            }
            """)

            # 4. Save the Result
            net.save_graph(output_file)

        except ImportError as e:
            raise RegistryError("PyVis is required for visualization. Run 'poetry add pyvis'.") from e
        except Exception as e:
            raise RegistryError(format_error("registry.entity_graph", "Failed to visualize graph", error=str(e))) from e
