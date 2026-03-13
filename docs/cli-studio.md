# CLI & Studio

PySemantic ships with a powerful CLI (powered by [Typer](https://typer.tiangolo.com/)) and an interactive web-based Studio (powered by [Streamlit](https://streamlit.io/)).

```bash
pysemantic --help
```

---

## `pysemantic query` — Generate SQL from the Terminal

Turn metric queries into SQL without writing a single line of Python.

### Basic usage

```bash
pysemantic query ./models -m total_orders -d customer_city --limit 10
```

### Multiple measures

```bash
pysemantic query ./models -m "total_orders,unique_customers" -d order_status
```

### With filters and ordering

```bash
pysemantic query ./models \
  -m total_order_price \
  -d customer_state \
  -f "customer_state IN ('SP', 'RJ')" \
  -f "total_order_price > 100" \
  --order-by "total_order_price DESC" \
  --limit 5
```

<div class="gif-container" markdown>

![pysemantic query demo](assets/gifs/query.gif)

</div>

### Filter syntax

Filters follow the format `"field OPERATOR value"`.

| Operator | Example |
|----------|---------|
| `=` | `"order_status = delivered"` |
| `!=` | `"order_status != cancelled"` |
| `>`, `<`, `>=`, `<=` | `"total_order_price > 100"` |
| `IN` | `"customer_state IN ('SP', 'RJ')"` |
| `NOT IN` | `"customer_state NOT IN ('MG')"` |
| `LIKE` / `ILIKE` | `"customer_city LIKE 'São%'"` |
| `IS` / `IS NOT` | `"order_status IS NULL"` |

### Command options

| Option | Short | Description |
|--------|-------|-------------|
| `--measure` | `-m` | Measure(s) — repeat or comma-separate |
| `--dimension` | `-d` | Dimension(s) — repeat or comma-separate |
| `--filter` | `-f` | Filter expression — repeatable |
| `--order-by` | | Sort columns |
| `--limit` | `-l` | Max rows to return |

---

## `pysemantic studio` — Interactive Web UI

Launch a full-featured browser-based interface to explore your semantic layer.

```bash
pysemantic studio ./models
```

<div class="gif-container" markdown>

![pysemantic studio launch](assets/gifs/studio.gif)

</div>

### Options

```bash
pysemantic studio ./models --port 8080 --light
```

| Option | Short | Default | Description |
|--------|-------|---------|-------------|
| `--port` | `-p` | `8501` | Port for the Streamlit server |
| `--dark/--light` | | `--dark` | Theme toggle |

### Studio Tabs

The Studio provides three tabs for exploring your data layer:

=== ":material-graph: Entity Graph"

    Interactive visualization of your model relationships.

    - Click nodes to isolate a model and its connections
    - Fullscreen mode for presentations
    - Drag, zoom, and explore the join topology

=== ":material-book-open-variant: Data Dictionary"

    Browse all registered models with their:

    - Measures and aggregation types
    - Dimensions and data types
    - Entities and relationship direction (PRIMARY / FOREIGN)
    - Column mappings and table references

=== ":material-console: Query Playground"

    Build queries interactively:

    - Pick measures and dimensions from dropdowns
    - Add filters with point-and-click
    - Click **"Generate SQL"** and see the result
    - **Multi-fact supported:** combining measures from multiple models (e.g. order_items + customers) produces CTE-based SQL; dimensions must be [conformed](multi-fact-queries.md#conformed-dimensions) or the query runs as a Grand Total (no dimensions)
    - Invalid combinations surface your error protections in real-time

---

## `pysemantic graph` — Export Entity Graph

Generate a standalone interactive HTML file showing your entity graph.

```bash
pysemantic graph ./models
```

<div class="gif-container" markdown>

![pysemantic graph demo](assets/gifs/graph.gif)

</div>

### Options

| Option | Short | Default | Description |
|--------|-------|---------|-------------|
| `--output` | `-o` | `entity_graph.html` | Output HTML file path |

### Example

```bash
pysemantic graph ./models -o my_graph.html
```

Output:

```
✅ Entity Graph generated: my_graph.html
Graph saved to: my_graph.html
```

Open the HTML file in any browser — it's fully interactive with drag, zoom, node isolation, and a metadata sidebar.

---

## Quick Reference

| Command | What it does |
|---------|-------------|
| `pysemantic query ./models -m <measures>` | Generate SQL |
| `pysemantic studio ./models` | Launch web UI |
| `pysemantic graph ./models` | Export entity graph |
| `pysemantic --help` | Show help |

---

## SQL Dialect

The CLI generates SQL using the **MySQL** dialect by default (matching the `SemanticLayer` default). PySemantic supports all [SQLGlot dialects](https://github.com/tobymao/sqlglot/blob/main/sqlglot/dialects/__init__.py) — MySQL, PostgreSQL, BigQuery, Snowflake, DuckDB, Databricks, Redshift, ClickHouse, Trino, SQLite, and more.

To use a different dialect, initialize `SemanticLayer` programmatically with the `dialect` parameter:

```python
sl = SemanticLayer(model_path="./models", dialect="postgres")
```

See [Getting Started — Supported Dialects](getting-started.md#supported-dialects) for the full list.

---

<div style="text-align: center; padding: 1rem 0;" markdown>
**New to PySemantic?** [Getting Started](getting-started.md) · **Multi-model metrics?** [Multi-Fact Queries](multi-fact-queries.md)
</div>
