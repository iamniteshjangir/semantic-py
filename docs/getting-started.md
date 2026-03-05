# Getting Started

Get PySemantic running in under 5 minutes.

---

## Installation

=== "pip"

    ```bash
    pip install pysemantic-layer
    ```

=== "Poetry"

    ```bash
    poetry add pysemantic-layer
    ```

!!! info "Requirements"
    Python **3.11** or higher is required.

---

## Step 1 — Define Your Models

Create a directory (e.g. `models/`) with **one Python file per table**. Each file declares a `Model` with its dimensions, measures, and entities.

### `models/order_items.py`

```python
from pysemantic.modeling import Model, Dimension, Measure, Entity, EntityType

model = Model(
    name="order_items",
    table="order_items",
    primary_key="order_item_id",
    dimensions=[
        Dimension(name="product_category", column="product_category", dtype="string"),
    ],
    measures=[
        Measure(name="total_order_price", agg="sum", column="price"),
        Measure(
            name="total_number_of_distinct_orders",
            agg="distinct_count",
            column="order_id",
        ),
    ],
    entities=[
        Entity(name="order_item", entity_type=EntityType.PRIMARY, column="order_item_id"),
        Entity(name="order", entity_type=EntityType.FOREIGN, column="order_id"),
        Entity(name="product", entity_type=EntityType.FOREIGN, column="product_id"),
        Entity(name="seller", entity_type=EntityType.FOREIGN, column="seller_id"),
    ],
)
```

### `models/orders.py`

```python
from pysemantic.modeling import Model, Dimension, Measure, Entity, EntityType

model = Model(
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

### `models/customers.py`

```python
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

!!! tip "How joins work"
    PySemantic resolves joins automatically through **shared entity names**.
    `orders` declares a FOREIGN entity `customer` → links to `customers` which declares a PRIMARY entity `customer`.
    No manual join configuration needed.

---

## Step 2 — Query

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

??? success "Generated SQL"
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

Joins, table references, `WHERE` vs `HAVING` — all resolved automatically from your model definitions.

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
order_items ──(FK: order)──▶ orders ──(FK: customer)──▶ customers
     │
     ├──(FK: seller)──▶ sellers
     └──(FK: product)──▶ products
```

When you query a measure from `order_items` with a dimension from `customers`, PySemantic traverses the entity graph and generates the full `LEFT JOIN` chain automatically.

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

Filters can be passed as dictionaries:

```python
{"field": "customer_state", "operator": "IN", "value": "('SP', 'RJ')"}
{"field": "total_order_price", "operator": ">", "value": "1000"}
{"field": "order_status", "operator": "IS", "value": None}
```

!!! note "Automatic WHERE vs HAVING"
    Dimension filters go to `WHERE`. Measure filters go to `HAVING`. PySemantic handles this automatically.

**Supported operators:** `=`, `!=`, `>`, `<`, `>=`, `<=`, `IN`, `NOT IN`, `LIKE`, `ILIKE`, `IS`, `IS NOT`

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

<div style="text-align: center; padding: 1rem 0;" markdown>
**Next:** explore the full CLI and interactive Studio →  [CLI & Studio](cli-studio.md)
</div>
