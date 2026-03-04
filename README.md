# PySemantic

**Python lightweight semantic layer for data engineers.**

PySemantic lets you define your data models as Python objects -- dimensions, measures, and entity relationships -- and generates correct, optimized SQL from simple metric queries. No more hand-writing joins, no more duplicated business logic across dashboards.

## Why PySemantic?

- **Single source of truth** -- Define a metric once, use it everywhere.
- **Automatic join resolution** -- Declare entity relationships; PySemantic finds the join path.
- **SQL injection safe** -- Structured filters with operator whitelisting and value escaping.
- **Dialect support** -- Generates SQL for MySQL, Postgres, and more via [SQLGlot](https://github.com/tobymao/sqlglot).
- **Zero infrastructure** -- Pure Python, no server, no database required at definition time.
- **Interactive graph visualization** -- Inspect your entity graph in the browser.

## Installation

```bash
pip install pysemantic
```

Or with [Poetry](https://python-poetry.org/):

```bash
poetry add pysemantic
```

**Requires Python 3.11+**

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
        Measure(name="total_number_of_orders", agg="count", column="order_id"),
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
    measures=["total_number_of_orders"],
    dimensions=["customer_city"],
    filters=[{"field": "customer_state", "operator": "=", "value": "SP"}],
    order_by=["total_number_of_orders DESC"],
    limit=10,
)

print(sql)
```

**Generated SQL:**

```sql
SELECT
  customers.customer_city AS customer_city,
  COUNT(orders.order_id) AS total_number_of_orders
FROM orders
LEFT JOIN customers
  ON orders.customer_id = customers.customer_id
WHERE
  customers.customer_state = 'SP'
GROUP BY
  1
ORDER BY
  total_number_of_orders DESC
LIMIT 10
```

### 3. Visualize the entity graph

```python
sl.generate_graph(output_file="entity_graph.html")
```

Opens an interactive HTML graph showing all models, their relationships, and metadata.

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
     │
     ├──(FK: seller)──>  sellers
     └──(FK: product)──>  products
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

Filters can be passed as dictionaries or strings:

```python
# Dictionary (recommended)
{"field": "customer_state", "operator": "IN", "value": ["SP", "RJ"]}
{"field": "total_order_price", "operator": ">", "value": 1000}
{"field": "order_status", "operator": "IS", "value": None}

# String (simple cases)
"order_status = 'delivered'"
```

Dimension filters go to `WHERE`; measure filters go to `HAVING` -- automatically.

**Supported operators:** `=`, `!=`, `>`, `<`, `>=`, `<=`, `IN`, `NOT IN`, `LIKE`, `ILIKE`, `IS`, `IS NOT`

## Architecture

```
User Query (measures, dimensions, filters)
    │
    ▼
┌──────────┐     ┌──────────┐     ┌──────────┐
│   AST    │────>│ Planner  │────>│Generator │───> SQL string
│ (Parser) │     │(Resolver)│     │(Compiler)│
└──────────┘     └──────────┘     └──────────┘
                       │
                 ┌─────┴─────┐
                 │ Registry  │
                 │  + Entity │
                 │   Graph   │
                 └───────────┘
```

| Layer | Responsibility |
|-------|---------------|
| **AST** | Parses raw input into a structured, validated syntax tree |
| **Registry** | Loads model files, validates them, builds the entity graph |
| **Planner** | Resolves measures/dimensions to models, calculates join paths |
| **Generator** | Translates the logical plan into dialect-specific SQL |

## API Reference

### `SemanticLayer`

```python
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
| `filters` | `list[dict \| str]` | No | Filter conditions |
| `order_by` | `list[str]` | No | Sort columns (append `DESC` for descending) |
| `limit` | `int` | No | Maximum rows to return |

## Development

```bash
git clone https://github.com/user/pysemantic.git
cd pysemantic
poetry install
```

Run tests:

```bash
poetry run pytest
```

Run linting:

```bash
poetry run pre-commit run --all-files
```

## License

[MIT](LICENSE)
