<div align="center">

# PySemantic

**A lightweight, graph-based Semantic Layer for Python and SQL.**


Define metrics once. Generate SQL everywhere.

[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Poetry](https://img.shields.io/badge/packaging-poetry-cyan.svg)](https://python-poetry.org/)
[![Typer CLI](https://img.shields.io/badge/CLI-Typer-purple.svg)](https://typer.tiangolo.com/)

---

<video src="https://github.com/user-attachments/assets/99704771-497e-45a8-9df0-07a100f7dc84" width="100%" controls>Your browser does not support the video tag. <a href="https://github.com/user-attachments/assets/99704771-497e-45a8-9df0-07a100f7dc84">Watch the demo here</a>.</video>

</div>

---

## What is PySemantic?

PySemantic lets you define your data models as Python objects -- dimensions, measures, and entity relationships -- and generates correct, optimized SQL from simple metric queries. No more hand-writing joins, no more duplicated business logic scattered across dashboards and notebooks.

```python
from pysemantic.client import SemanticLayer

sl = SemanticLayer(model_path="./models")

sql = sl.query(
    measures=["total_order_price", "total_number_of_distinct_orders"],
    dimensions=["customer_state", "customer_city"],
    filters=[{"field": "customer_state", "operator": "IN", "value": "('SP', 'RJ')"}],
    order_by=["total_order_price DESC"],
    limit=10,
)
```
```sql
SELECT
  customers.customer_city AS customer_city,
  customers.customer_state AS customer_state,
  SUM(order_items.price) AS total_order_price,
  COUNT(DISTINCT order_items.order_id) AS total_number_of_distinct_orders
FROM order_items
LEFT JOIN orders
  ON order_items.order_id = orders.order_id
LEFT JOIN customers
  ON orders.customer_id = customers.customer_id
WHERE
  customers.customer_state IN ('SP', 'RJ')
GROUP BY
  1,
  2
ORDER BY
  total_order_price DESC
LIMIT 10
```

CLI Magic:

![pysemantic query](static/terminal_gifs/query.gif)

Joins, table references, WHERE vs HAVING -- all resolved automatically from your model definitions.

---

## Why PySemantic?

| | Feature | Description |
|---|---|---|
| **1** | **Single source of truth** | Define a metric once, use it everywhere |
| **2** | **Automatic join resolution** | Declare entity relationships; PySemantic finds the path |
| **3** | **SQL injection safe** | Structured filters with operator whitelisting and value escaping |
| **4** | **Dialect support** | MySQL, Postgres, and more via [SQLGlot](https://github.com/tobymao/sqlglot) |
| **5** | **Zero infrastructure** | Pure Python, no server required at definition time |
| **6** | **Interactive Studio** | Explore your models, graph, and test queries in the browser |
| **7** | **CLI powered by Typer** | Generate SQL and launch the Studio from the terminal |

---

## Installation

```bash
pip install pysemantic-layer
```

Or with [Poetry](https://python-poetry.org/):

```bash
poetry add pysemantic-layer
```

> **Requires Python 3.11+**

---

## Quick Start

### 1. Define your models

Create a directory (e.g. `models/`) with one Python file per table:

```python
# models/orders.py
from pysemantic.modeling import Model, Dimension, Measure, Entity, EntityType

orders = Model(
    name="orders",
    table="orders",
    primary_key="order_id",
    dimensions=[
        Dimension(name="order_status", column="order_status", dtype="string"),
    ],
    measures=[
        Measure(name="total_orders", agg="count", column="order_id"),
        Measure(name="unique_customers", agg="distinct_count", column="customer_id"),
    ],
    entities=[
        Entity(name="order", entity_type=EntityType.PRIMARY, column="order_id"),
        Entity(name="customer", entity_type=EntityType.FOREIGN, column="customer_id"),
    ],
)
```

```python
# models/customers.py
from pysemantic.modeling import Model, Dimension, Measure, Entity, EntityType

model = Model(
    name="customers",
    table="customers",
    primary_key="customer_id",
    dimensions=[
        Dimension(name="customer_city", column="customer_city", dtype="string"),
        Dimension(name="customer_state", column="customer_state", dtype="string"),
    ],
    measures=[
        Measure(name="total_customers", agg="count", column="customer_id"),
    ],
    entities=[
        Entity(name="customer", entity_type=EntityType.PRIMARY, column="customer_id"),
    ],
)
```

PySemantic automatically discovers the join path: `orders.customer_id` (FOREIGN) links to `customers.customer_id` (PRIMARY) through the shared entity name `customer`.

### 2. Query

```python
from pysemantic.client import SemanticLayer

sl = SemanticLayer(model_path="./models")

sql = sl.query(
    measures=["total_orders"],
    dimensions=["customer_city"],
    filters=[{"field": "customer_state", "operator": "=", "value": "SP"}],
    order_by=["total_orders DESC"],
    limit=10,
)
print(sql)
```

**Generated SQL:**

```sql
SELECT
  customers.customer_city AS customer_city,
  COUNT(orders.order_id) AS total_orders
FROM orders
LEFT JOIN customers
  ON orders.customer_id = customers.customer_id
WHERE
  customers.customer_state = 'SP'
GROUP BY 1
ORDER BY total_orders DESC
LIMIT 10
```

---

## PySemantic Studio

PySemantic ships with a built-in interactive web UI powered by Streamlit.

```bash
pysemantic studio ./models
```

![pysemantic studio](static/terminal_gifs/studio.gif)

The Studio has three tabs:

| Tab | What it does |
|-----|-------------|
| **Entity Graph** | Interactive visualization of your model relationships. Click nodes to isolate, fullscreen mode, drag & zoom. |
| **Data Dictionary** | Browse all registered models with their measures, dimensions, entities, and column mappings. |
| **Query Playground** | Pick measures & dimensions from dropdowns, add filters, click "Generate SQL" and see the output. Invalid combos show your error protections in action. |

```bash
# Custom port and light theme
pysemantic studio ./models --port 8080 --light
```

---

## CLI

PySemantic includes a full command-line interface powered by [Typer](https://typer.tiangolo.com/).

```bash
pysemantic --help
```

### `pysemantic studio` -- Launch the web UI

```bash
pysemantic studio ./models
pysemantic studio ./models --port 8080 --light
```

### `pysemantic query` -- Generate SQL from the terminal

```bash
# Single measure
pysemantic query ./models -m total_orders -d customer_city --limit 10

# Multiple measures (comma-separated or repeated)
pysemantic query ./models -m "total_orders,unique_customers" -d order_status

# With filters
pysemantic query ./models \
  -m total_order_price \
  -d customer_state \
  -f "customer_state IN ('SP', 'RJ')" \
  -f "total_order_price > 100" \
  --order-by "total_order_price DESC" \
  --limit 5
```

**Filter syntax:** `"field OPERATOR value"` -- supports `=`, `!=`, `>`, `<`, `>=`, `<=`, `IN`, `NOT IN`, `LIKE`, `IS`, `IS NOT`.

### `pysemantic graph` -- Export entity graph

```bash
pysemantic graph ./models -o my_graph.html
```

![pysemantic graph](static/terminal_gifs/graph.gif)

Generates a standalone interactive HTML file with your entity graph.

---

## Core Concepts

### Model

A `Model` maps to a database table and defines its semantic metadata:

| Component | Purpose | Example |
|-----------|---------|---------|
| **Dimensions** | Columns to group or filter by | `customer_city`, `order_status` |
| **Measures** | Aggregated metrics | `SUM(price)`, `COUNT(DISTINCT id)` |
| **Entities** | Relationship keys (PRIMARY / FOREIGN) | `order_id`, `customer_id` |

### Entities & Join Resolution

Entities define how models connect. A **PRIMARY** entity declares ownership of a concept; a **FOREIGN** entity references it:

```
order_items  ──(FK: order)──>  orders  ──(FK: customer)──>  customers
     |
     |──(FK: seller)──>  sellers
     |──(FK: product)──>  products
```

When you query a measure from `order_items` with a dimension from `customers`, PySemantic automatically traverses the graph and generates the required `LEFT JOIN` chain.

### Supported Aggregations

| `agg` value | SQL output |
|-------------|------------|
| `sum` | `SUM(column)` |
| `count` | `COUNT(column)` |
| `avg` | `AVG(column)` |
| `min` | `MIN(column)` |
| `max` | `MAX(column)` |
| `distinct_count` | `COUNT(DISTINCT column)` |

### Filters

Filters are passed as dictionaries:

```python
{"field": "customer_state", "operator": "IN", "value": "('SP', 'RJ')"}
{"field": "total_order_price", "operator": ">", "value": "1000"}
{"field": "order_status", "operator": "IS", "value": None}
```

Dimension filters go to `WHERE`; measure filters go to `HAVING` -- automatically.

**Supported operators:** `=`, `!=`, `>`, `<`, `>=`, `<=`, `IN`, `NOT IN`, `LIKE`, `ILIKE`, `IS`, `IS NOT`

---

## Architecture

```
User Query (measures, dimensions, filters)
    |
    v
+----------+     +----------+     +----------+
|   AST    |---->| Planner  |---->|Generator |---> SQL string
| (Parser) |     |(Resolver)|     |(Compiler)|
+----------+     +----------+     +----------+
                      |
                +-----+-----+
                | Registry  |
                | + Entity  |
                |   Graph   |
                +-----------+
```

| Layer | Responsibility |
|-------|---------------|
| **AST** | Parses raw input into a structured, validated syntax tree |
| **Registry** | Loads model files, validates them, builds the entity graph |
| **Planner** | Resolves measures/dimensions to models, calculates join paths |
| **Generator** | Translates the logical plan into dialect-specific SQL |

---

## API Reference

### `SemanticLayer`

```python
from pysemantic.client import SemanticLayer

sl = SemanticLayer(model_path="./models")
```

| Method | Description |
|--------|-------------|
| `query(measures, dimensions, filters, order_by, limit)` | Generate a SQL query string |
| `reload(model_path=None)` | Hot-reload models from disk (useful in notebooks) |
| `generate_graph(output_file)` | Export an interactive entity graph as HTML |

### `query()` Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `measures` | `list[str]` | Yes | Metric names to aggregate |
| `dimensions` | `list[str]` | No | Dimension names to group by |
| `filters` | `list[dict]` | No | Filter conditions as `{field, operator, value}` dicts |
| `order_by` | `list[str]` | No | Sort columns (append `DESC` for descending) |
| `limit` | `int` | No | Maximum rows to return |

---

## License

[MIT](LICENSE)
