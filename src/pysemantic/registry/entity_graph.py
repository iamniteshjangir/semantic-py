import json

import networkx as nx
from pyvis.network import Network

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

    def visualize_graph(
        self,
        output_file: str = "entity_graph.html",
        dark_mode: bool = True,
        models: dict | None = None,
    ) -> None:
        """
        Visualizes the entity graph with interactive features.
        Fixed to prevent 'Black Screen' / JavaScript race conditions
        and PyVis 'dict' AttributeErrors. Includes Node Isolation.
        """
        try:
            # 1. Setup Canvas
            bg_color = "#111111" if dark_mode else "#ffffff"
            text_color = "#e0e0e0" if dark_mode else "#333333"

            # Obsidian Palette
            node_base = "#7c4dff" if dark_mode else "#45B7D1"
            node_root = "#9b59b6" if dark_mode else "#FF6B6B"
            node_highlight = "#b388ff"
            edge_color = "#444444" if dark_mode else "#cccccc"

            net = Network(height="100vh", width="100%", bgcolor=bg_color, font_color=text_color, directed=True)

            # 2. Add Nodes
            model_metadata = {}
            for node in self.graph.nodes():
                is_root = self.graph.in_degree(node) == 0

                # Metadata for Sidebar
                if models and node in models:
                    m = models[node]
                    model_metadata[node] = {
                        "type": "Fact Table" if is_root else "Dimension",
                        "table": m.table,
                        "measures": [meas.name for meas in m.measures],
                        "dimensions": [dim.name for dim in m.dimensions],
                    }
                else:
                    model_metadata[node] = {"type": "Unknown", "measures": [], "dimensions": []}

                # Clean Title
                hover_text = f"Table: {node}\nType: {'Root Model' if is_root else 'Dimension'}"

                net.add_node(
                    node,
                    label=node,
                    title=hover_text,
                    color={
                        "background": node_root if is_root else node_base,
                        "border": bg_color,
                        "highlight": {"background": node_highlight, "border": "#ffffff"},
                    },
                    size=25 if is_root else 15,
                    shape="dot",
                    borderWidth=2,
                    font={"size": 14, "face": "Inter, sans-serif", "color": text_color},
                )

            # 3. Add Edges
            for source, target, data in self.graph.edges(data=True):
                join_meta = data.get("join_condition", {})
                join_label = f"{join_meta.get('left')} → {join_meta.get('right')}"

                net.add_edge(
                    source,
                    target,
                    title=f"Join: {join_label}",
                    color={"color": edge_color, "highlight": node_highlight, "hover": node_highlight},
                    width=0.5,
                    selectionWidth=2,
                    hoverWidth=1.5,
                    arrowStrikethrough=False,
                )

            # 4. Save & Inject
            net.save_graph(output_file)
            json_data = json.dumps(model_metadata)
            self._inject_interactive_features(output_file, json_data, dark_mode)

            print(f"✅ Entity Graph generated: {output_file}")

        except ImportError as e:
            raise RegistryError("PyVis is required. Run 'poetry add pyvis'.") from e
        except Exception as e:
            raise RegistryError(f"Failed to visualize graph: {e!s}") from e

    def _inject_interactive_features(self, file_path: str, json_metadata: str, dark_mode: bool):
        """
        Injects CSS/JS for Node Isolation, Reset Button, Sidebar, and Stable Physics.
        """
        # Colors for Reset Logic
        reset_bg = "#7c4dff" if dark_mode else "#45B7D1"
        reset_border = "#111111" if dark_mode else "#ffffff"
        reset_font = "#e0e0e0" if dark_mode else "#333333"

        # Panel Colors
        bg_panel = "rgba(30, 30, 30, 0.95)" if dark_mode else "rgba(255, 255, 255, 0.95)"
        text_panel = "#fff" if dark_mode else "#333"
        border_panel = "#7c4dff" if dark_mode else "#45B7D1"

        with open(file_path) as f:
            html = f.read()

        css = f"""
        <style>
            #reset-btn {{
                position: absolute; top: 20px; left: 20px;
                padding: 10px 20px; background: {border_panel}; color: #fff;
                border: none; border-radius: 5px; cursor: pointer;
                font-family: 'Segoe UI', sans-serif; font-weight: bold;
                box-shadow: 0 4px 6px rgba(0,0,0,0.3);
                z-index: 1000; display: none; transition: background 0.2s;
            }}
            #reset-btn:hover {{ filter: brightness(1.2); }}

            #detail-panel {{
                position: absolute; top: 20px; right: -400px;
                width: 350px; max-height: 80vh;
                background: {bg_panel}; color: {text_panel};
                border-left: 4px solid {border_panel};
                padding: 20px; font-family: 'Segoe UI', sans-serif;
                box-shadow: -5px 0 15px rgba(0,0,0,0.5);
                transition: right 0.3s ease-in-out;
                z-index: 1000; overflow-y: auto; border-radius: 8px 0 0 8px;
            }}
            #detail-panel.active {{ right: 0; }}
            #detail-panel h2 {{ margin-top: 0; border-bottom: 1px solid #555; padding-bottom: 10px; }}
            .meta-section {{ margin-top: 15px; }}
            .meta-tag {{ display: inline-block; padding: 4px 8px; margin: 2px;
                border-radius: 4px; font-size: 12px; font-weight: bold; }}
            .tag-meas {{ background: #2e7d32; color: #fff; }}
            .tag-dim {{ background: #1565c0; color: #fff; }}
            .close-btn {{ position: absolute; top: 10px; right: 15px; cursor: pointer; font-size: 20px; }}
        </style>

        <button id="reset-btn" onclick="resetGraph()">⟲ Reset View</button>

        <div id="detail-panel">
            <span class="close-btn" onclick="closePanel()">&times;</span>
            <h2 id="panel-title">Details</h2>
            <p><strong>Table:</strong> <span id="panel-table"></span></p>
            <p><strong>Type:</strong> <span id="panel-type"></span></p>
            <div class="meta-section"><h4>📐 Measures</h4><div id="panel-measures"></div></div>
            <div class="meta-section"><h4>🗂 Dimensions</h4><div id="panel-dimensions"></div></div>
        </div>
        """

        js = f"""
        <script type="text/javascript">
            var modelData = {json_metadata};

            function closePanel() {{
                var p = document.getElementById('detail-panel');
                if(p) p.classList.remove('active');
            }}

            // GLOBAL RESET FUNCTION
            function resetGraph() {{
                // Show all nodes
                var allNodeIds = nodes.getIds();
                var nodeUpdates = allNodeIds.map(id => ({{id: id, hidden: false}}));
                nodes.update(nodeUpdates);

                // Show all edges
                var allEdgeIds = edges.getIds();
                var edgeUpdates = allEdgeIds.map(id => ({{id: id, hidden: false}}));
                edges.update(edgeUpdates);

                document.getElementById('reset-btn').style.display = 'none';
                closePanel();

                // Fit view to all nodes
                network.fit({{ animation: {{ duration: 500 }} }});
            }}

            // SAFE LOADER
            window.addEventListener("load", function() {{
                var checkInterval = setInterval(function() {{
                    try {{
                        if (typeof network !== 'undefined' && network !== null) {{
                            console.log("PySemantic: Graph detected. Initializing UI...");
                            clearInterval(checkInterval);
                            initInteractivity();
                        }}
                    }} catch(e) {{
                        // Ignore until loaded
                    }}
                }}, 200);
            }});

            function initInteractivity() {{
                // Apply straight edges and rigid physics natively
                network.setOptions({{
                    nodes: {{ font: {{ strokeWidth: 0 }} }},
                    edges: {{ smooth: false }}, // <--- Straight Edges
                    physics: {{
                        solver: "barnesHut",    // <--- Rigid/Stable Solver
                        barnesHut: {{
                            gravitationalConstant: -3000,
                            centralGravity: 0.8,
                            springLength: 150,
                            springConstant: 0.05,
                            damping: 0.9       // <--- High damping stops the bouncing
                        }},
                        stabilization: {{ enabled: true, iterations: 150 }}
                    }},
                    interaction: {{
                        hover: true,
                        tooltipDelay: 200,
                        zoomView: true
                    }}
                }});

                // CLICK EVENT (ISOLATE NODE)
                network.on("click", function (params) {{
                    if (params.nodes.length > 0) {{
                        var nodeId = params.nodes[0];

                        // 1. Show Reset Button
                        document.getElementById('reset-btn').style.display = 'block';

                        // 2. Hide unrelated nodes
                        var connectedNodes = network.getConnectedNodes(nodeId);
                        connectedNodes.push(nodeId); // Include clicked node

                        var allNodeIds = nodes.getIds();
                        var nodeUpdates = allNodeIds.map(id => ({{
                            id: id,
                            hidden: !connectedNodes.includes(id)
                        }}));
                        nodes.update(nodeUpdates);

                        // 3. Hide unrelated edges
                        var allEdgeIds = edges.getIds();
                        var edgeUpdates = allEdgeIds.map(edgeId => {{
                            var edge = edges.get(edgeId);
                            var isConnected = connectedNodes.includes(edge.from) && connectedNodes.includes(edge.to);
                            return {{ id: edgeId, hidden: !isConnected }};
                        }});
                        edges.update(edgeUpdates);

                        // 4. Populate Sidebar
                        var data = modelData[nodeId];
                        if (data) {{
                            document.getElementById('panel-title').innerText = nodeId;
                            document.getElementById('panel-table').innerText = data.table || "N/A";
                            document.getElementById('panel-type').innerText = data.type;

                            var mDiv = document.getElementById('panel-measures');
                            mDiv.innerHTML = data.measures.length ? "" : "<em>None</em>";
                            data.measures.forEach(function(m) {{
                                mDiv.innerHTML += '<span class="meta-tag tag-meas">' + m + '</span>';
                            }});

                            var dDiv = document.getElementById('panel-dimensions');
                            dDiv.innerHTML = data.dimensions.length ? "" : "<em>None</em>";
                            data.dimensions.forEach(function(d) {{
                                dDiv.innerHTML += '<span class="meta-tag tag-dim">' + d + '</span>';
                            }});

                            document.getElementById('detail-panel').classList.add('active');
                        }}

                        // 5. Zoom into the isolated cluster
                        network.focus(nodeId, {{ scale: 1.0, animation: {{ duration: 400 }} }});

                    }} else {{
                        // Clicked empty space -> reset
                        resetGraph();
                    }}
                }});

                // HOVER ON EVENT (Subtle glow, since isolation handles main focus)
                network.on("hoverNode", function (params) {{
                    var nodeId = params.node;
                    var connectedNodes = network.getConnectedNodes(nodeId);
                    var allNodes = nodes.getIds();
                    var updates = [];
                    for (var i = 0; i < allNodes.length; i++) {{
                        var id = allNodes[i];
                        if (id !== nodeId && !connectedNodes.includes(id)) {{
                            updates.push({{
                                id: id,
                                color: {{background: 'rgba(124, 77, 255, 0.2)',
                                    border: 'rgba(124, 77, 255, 0.1)'}},
                                font: {{color: 'rgba(255,255,255,0.2)'}}
                            }});
                        }}
                    }}
                    nodes.update(updates);
                }});

                // HOVER OFF EVENT
                network.on("blurNode", function (params) {{
                    var allNodes = nodes.getIds();
                    var updates = [];
                    for (var i = 0; i < allNodes.length; i++) {{
                        var id = allNodes[i];
                        updates.push({{
                            id: id,
                            color: {{background: '{reset_bg}',
                                border: '{reset_border}'}},
                            font: {{color: '{reset_font}'}}
                        }});
                    }}
                    nodes.update(updates);
                }});
            }}
        </script>
        </body>
        """

        new_html = html.replace("</body>", css + js)
        with open(file_path, "w") as f:
            f.write(new_html)
