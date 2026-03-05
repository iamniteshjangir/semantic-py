import sys
import tempfile

import streamlit as st
import streamlit.components.v1 as components

from pysemantic.client import SemanticLayer
from pysemantic.exceptions import PySemanticError

st.set_page_config(
    page_title="PySemantic Explorer",
    page_icon="🔮",
    layout="wide",
    initial_sidebar_state="collapsed",
)

FILTER_OPERATORS = ["=", "!=", ">", "<", ">=", "<=", "IN", "NOT IN", "LIKE", "IS", "IS NOT"]


def _get_model_path() -> str:
    if len(sys.argv) > 1:
        return sys.argv[-1]
    return "./test_things/models"


@st.cache_resource
def load_semantic_layer():
    return SemanticLayer(model_path=_get_model_path())


@st.cache_resource
def get_graph_html():
    sl = load_semantic_layer()
    with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as tmp:
        sl.generate_graph(output_file=tmp.name)
        tmp_path = tmp.name
    with open(tmp_path) as f:
        html = f.read()
    return _inject_fullscreen_button(html)


def _inject_fullscreen_button(html: str) -> str:
    fullscreen_assets = """
    <style>
        html, body {
            margin: 0 !important;
            padding: 0 !important;
            overflow: hidden;
            background: #111111;
        }
        #mynetwork {
            border: none !important;
        }
        #fs-btn {
            position: absolute; top: 12px; right: 12px;
            width: 36px; height: 36px;
            background: rgba(124, 77, 255, 0.85); color: #fff;
            border: none; border-radius: 8px; cursor: pointer;
            font-size: 18px; display: flex; align-items: center;
            justify-content: center; z-index: 1002;
            box-shadow: 0 2px 8px rgba(0,0,0,0.4);
            transition: all 0.3s ease;
            backdrop-filter: blur(4px);
        }
        #fs-btn:hover {
            background: rgba(124, 77, 255, 1);
            transform: scale(1.08);
            box-shadow: 0 4px 16px rgba(124, 77, 255, 0.5);
        }
        /* Shift fullscreen button left when detail panel is open */
        #detail-panel.active ~ #fs-btn {
            right: 370px;
        }
        :fullscreen { background: #111; }
        :-webkit-full-screen { background: #111; }

        #graph-legend {
            position: absolute; bottom: 12px; left: 12px;
            background: rgba(30, 30, 30, 0.85);
            backdrop-filter: blur(8px);
            padding: 10px 14px; border-radius: 8px;
            font-family: 'Segoe UI', system-ui, sans-serif;
            font-size: 11px; color: #ccc; z-index: 1001;
            display: flex; gap: 14px; align-items: center;
        }
        .legend-item {
            display: flex; align-items: center; gap: 6px;
        }
        .legend-dot {
            width: 10px; height: 10px; border-radius: 50%;
            display: inline-block; flex-shrink: 0;
        }
    </style>

    <button id="fs-btn" onclick="toggleFullscreen()" title="Toggle Fullscreen">
        <svg id="fs-icon-expand" width="18" height="18" viewBox="0 0 24 24"
             fill="none" stroke="currentColor" stroke-width="2.5"
             stroke-linecap="round" stroke-linejoin="round">
            <polyline points="15 3 21 3 21 9"></polyline>
            <polyline points="9 21 3 21 3 15"></polyline>
            <line x1="21" y1="3" x2="14" y2="10"></line>
            <line x1="3" y1="21" x2="10" y2="14"></line>
        </svg>
        <svg id="fs-icon-collapse" width="18" height="18" viewBox="0 0 24 24"
             fill="none" stroke="currentColor" stroke-width="2.5"
             stroke-linecap="round" stroke-linejoin="round"
             style="display:none">
            <polyline points="4 14 10 14 10 20"></polyline>
            <polyline points="20 10 14 10 14 4"></polyline>
            <line x1="14" y1="10" x2="21" y2="3"></line>
            <line x1="3" y1="21" x2="10" y2="14"></line>
        </svg>
    </button>

    <div id="graph-legend">
        <div class="legend-item">
            <span class="legend-dot" style="background:#9b59b6"></span> Fact Table
        </div>
        <div class="legend-item">
            <span class="legend-dot" style="background:#7c4dff"></span> Dimension
        </div>
        <div class="legend-item">
            <span class="legend-dot" style="background:#444; width:20px; height:2px;
                  border-radius:1px"></span> Join Path
        </div>
    </div>

    <script type="text/javascript">
        function toggleFullscreen() {
            var doc = document.documentElement;
            if (!document.fullscreenElement && !document.webkitFullscreenElement) {
                if (doc.requestFullscreen) doc.requestFullscreen();
                else if (doc.webkitRequestFullscreen) doc.webkitRequestFullscreen();
            } else {
                if (document.exitFullscreen) document.exitFullscreen();
                else if (document.webkitExitFullscreen) document.webkitExitFullscreen();
            }
        }

        function onFSChange() {
            var isFS = !!document.fullscreenElement || !!document.webkitFullscreenElement;
            document.getElementById('fs-icon-expand').style.display = isFS ? 'none' : 'block';
            document.getElementById('fs-icon-collapse').style.display = isFS ? 'block' : 'none';
        }

        document.addEventListener('fullscreenchange', onFSChange);
        document.addEventListener('webkitfullscreenchange', onFSChange);
    </script>
    </body>
    """
    return html.replace("</body>", fullscreen_assets)


def get_all_measures(sl: SemanticLayer) -> list[str]:
    measures = []
    for model in sl.registry.models.values():
        for m in model.measures:
            measures.append(m.name)
    return sorted(measures)


def get_all_dimensions(sl: SemanticLayer) -> list[str]:
    dims = []
    for model in sl.registry.models.values():
        for d in model.dimensions:
            dims.append(d.name)
    return sorted(dims)


def get_all_filterable_fields(sl: SemanticLayer) -> list[str]:
    return sorted(set(get_all_dimensions(sl) + get_all_measures(sl)))


def get_graph_stats(sl: SemanticLayer) -> dict:
    graph = sl.registry.graph.graph
    total_measures = sum(len(m.measures) for m in sl.registry.models.values())
    total_dims = sum(len(m.dimensions) for m in sl.registry.models.values())
    fact_count = sum(1 for n in graph.nodes() if graph.in_degree(n) == 0)
    return {
        "models": graph.number_of_nodes(),
        "joins": graph.number_of_edges(),
        "measures": total_measures,
        "dimensions": total_dims,
        "facts": fact_count,
        "dims": graph.number_of_nodes() - fact_count,
    }


def render_entity_graph(sl: SemanticLayer):
    stats = get_graph_stats(sl)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Models", stats["models"], help=f"{stats['facts']} fact, {stats['dims']} dimension")
    c2.metric("Join Paths", stats["joins"])
    c3.metric("Measures", stats["measures"])
    c4.metric("Dimensions", stats["dimensions"])

    st.markdown(
        """<style>
        iframe[title="streamlit_components_v1.html"] {
            border: none !important;
        }
        .stHtml, [data-testid="stHtml"] {
            border: none !important;
            outline: none !important;
            box-shadow: none !important;
        }
        .element-container:has(iframe[title="streamlit_components_v1.html"]) {
            border: none !important;
            padding: 0 !important;
        }
        </style>""",
        unsafe_allow_html=True,
    )

    graph_html = get_graph_html()
    components.html(graph_html, height=600, scrolling=False)

    st.caption("Click a node to isolate its connections. Use the ⛶ button (top-right) for fullscreen.")


def render_data_dictionary(sl: SemanticLayer):
    for model_name, model in sorted(sl.registry.models.items()):
        is_root = sl.registry.graph.graph.in_degree(model_name) == 0
        badge = "🟣 Fact" if is_root else "🔵 Dim"

        with st.expander(f"{badge}  **{model_name}** — `{model.table}`", expanded=False):
            col1, col2, col3 = st.columns(3)

            with col1:
                st.markdown("##### Measures")
                if model.measures:
                    rows = [
                        {"Name": m.name, "Agg": m.agg.upper(), "Column": m.column}
                        for m in model.measures
                    ]
                    st.dataframe(rows, use_container_width=True, hide_index=True)
                else:
                    st.caption("No measures defined.")

            with col2:
                st.markdown("##### Dimensions")
                if model.dimensions:
                    rows = [
                        {"Name": d.name, "Column": d.column, "Type": d.dtype}
                        for d in model.dimensions
                    ]
                    st.dataframe(rows, use_container_width=True, hide_index=True)
                else:
                    st.caption("No dimensions defined.")

            with col3:
                st.markdown("##### Entities")
                if model.entities:
                    rows = [
                        {"Name": e.name, "Type": e.entity_type.value.upper(), "Column": e.column}
                        for e in model.entities
                    ]
                    st.dataframe(rows, use_container_width=True, hide_index=True)
                else:
                    st.caption("No entities defined.")


def render_query_playground(sl: SemanticLayer):
    all_measures = get_all_measures(sl)
    all_dimensions = get_all_dimensions(sl)
    all_fields = get_all_filterable_fields(sl)

    col_left, col_right = st.columns([1, 2])

    with col_left:
        st.markdown("#### Select Fields")

        selected_measures = st.multiselect(
            "Measures",
            options=all_measures,
            placeholder="Pick one or more measures...",
        )
        selected_dimensions = st.multiselect(
            "Dimensions",
            options=all_dimensions,
            placeholder="Pick dimensions to group by...",
        )

        st.divider()
        st.markdown("#### Filters")

        if "filters" not in st.session_state:
            st.session_state.filters = []

        for i, f in enumerate(st.session_state.filters):
            fc1, fc2, fc3, fc4 = st.columns([3, 2, 3, 1])
            with fc1:
                field_idx = all_fields.index(f["field"]) if f["field"] in all_fields else 0
                f["field"] = st.selectbox("Field", all_fields, key=f"ff_{i}", index=field_idx)
            with fc2:
                op_idx = (
                    FILTER_OPERATORS.index(f["operator"])
                    if f["operator"] in FILTER_OPERATORS
                    else 0
                )
                f["operator"] = st.selectbox("Op", FILTER_OPERATORS, key=f"fo_{i}", index=op_idx)
            with fc3:
                raw = st.text_input(
                    "Value",
                    value=str(f["value"]) if f["value"] is not None else "",
                    key=f"fv_{i}",
                )
                if f["operator"] in ("IS", "IS NOT"):
                    f["value"] = None
                else:
                    f["value"] = raw
            with fc4:
                st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
                if st.button("✕", key=f"fd_{i}"):
                    st.session_state.filters.pop(i)
                    st.rerun()

        if st.button("+ Add Filter"):
            st.session_state.filters.append(
                {"field": all_fields[0] if all_fields else "", "operator": "=", "value": ""}
            )
            st.rerun()

        st.divider()
        st.markdown("#### Options")

        order_col, limit_col = st.columns(2)
        with order_col:
            order_by_input = st.text_input(
                "Order By", placeholder="e.g. total_order_price DESC"
            )
        with limit_col:
            limit_val = st.number_input("Limit", min_value=0, value=0, step=1)

        generate = st.button(
            "Generate SQL",
            type="primary",
            use_container_width=True,
            disabled=not selected_measures,
        )

    with col_right:
        if generate:
            filters_for_query = [
                {
                    "field": f["field"],
                    "operator": f["operator"],
                    "value": f["value"],
                }
                for f in st.session_state.filters
            ]

            order_by = (
                [o.strip() for o in order_by_input.split(",") if o.strip()]
                if order_by_input
                else None
            )
            limit = limit_val if limit_val > 0 else None

            try:
                sql = sl.query(
                    measures=selected_measures,
                    dimensions=selected_dimensions or None,
                    filters=filters_for_query or None,
                    order_by=order_by,
                    limit=limit,
                )
                st.markdown("#### Generated SQL")
                st.code(sql, language="sql")
            except PySemanticError as e:
                st.error(f"**Query Error**\n\n{e}")
            except Exception as e:
                st.error(f"**Unexpected Error**\n\n{e}")
        else:
            st.markdown(
                "<div style='display:flex;align-items:center;justify-content:center;"
                "height:400px;color:#888;font-size:1.1em'>"
                "Select measures and click <b>Generate SQL</b> to see the output."
                "</div>",
                unsafe_allow_html=True,
            )


def main():
    st.markdown(
        "<h1 style='text-align:center;margin-bottom:0'>🔮 PySemantic Explorer</h1>"
        "<p style='text-align:center;color:#888;margin-top:4px'>"
        "A lightweight semantic layer for data engineers</p>",
        unsafe_allow_html=True,
    )

    sl = load_semantic_layer()

    tab_graph, tab_dict, tab_playground = st.tabs([
        "🕸️  Entity Graph",
        "📖  Data Dictionary",
        "🧪  Query Playground",
    ])

    with tab_graph:
        render_entity_graph(sl)

    with tab_dict:
        st.markdown("#### Registered Models")
        st.caption(f"{len(sl.registry.models)} models loaded from `{_get_model_path()}`")
        render_data_dictionary(sl)

    with tab_playground:
        render_query_playground(sl)


if __name__ == "__main__":
    main()
