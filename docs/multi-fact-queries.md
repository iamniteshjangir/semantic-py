# Multi-Fact Queries

## Overview

Multi-fact queries allow you to combine measures from **multiple fact tables** in a single query. PySemantic automatically detects when requested measures span different models and generates CTE-based SQL that avoids the **chasm trap** — a common pitfall where naive joins between fact tables produce inflated aggregates due to fan-out.

> **Conformed-Only Rule**: Multi-fact queries require all dimensions to be **conformed** — reachable from every fact table in the query. Non-conformed dimensions raise `NonConformedDimensionError`. The only exception is **Grand Total** queries (no dimensions), which produce scalar aggregates via `CROSS JOIN`.

<div class="gif-container" markdown>

![multi-fact query demo](assets/gifs/multi-fact-queries.gif)

</div>

### The Problem: Chasm Trap

Consider two fact tables — `orders` and `web_events` — both connected to a shared `customers` dimension:

```
orders ──FK──▶ customers ◀──FK── web_events
```

A naive join produces a Cartesian product between the two fact tables for each customer:

```sql
-- WRONG: Chasm trap — aggregates are inflated
SELECT
  c.name,
  SUM(o.revenue) AS total_revenue,
  COUNT(w.id) AS total_clicks
FROM customers c
LEFT JOIN orders o ON c.id = o.customer_id
LEFT JOIN web_events w ON c.id = w.customer_id
GROUP BY c.name;
```

If a customer has 3 orders and 5 web events, the join produces 15 rows per customer. `SUM(revenue)` is inflated 5x and `COUNT(clicks)` is inflated 3x.

### The Solution: CTE-Based Pre-Aggregation

PySemantic solves this by pre-aggregating each fact table independently in a CTE, then joining the results on the shared conformed dimension:

```sql
WITH cte_orders AS (
  SELECT
    customers.id AS __pk_customers,
    customers.name AS customer_name,
    SUM(orders.revenue) AS total_revenue
  FROM orders
  LEFT JOIN customers ON orders.customer_id = customers.id
  GROUP BY 1, 2
),
cte_web_events AS (
  SELECT
    customers.id AS __pk_customers,
    customers.name AS customer_name,
    COUNT(web_events.id) AS total_clicks
  FROM web_events
  LEFT JOIN customers ON web_events.customer_id = customers.id
  GROUP BY 1, 2
)
SELECT
  COALESCE(cte_orders.customer_name, cte_web_events.customer_name) AS customer_name,
  cte_orders.total_revenue,
  cte_web_events.total_clicks
FROM cte_orders
FULL OUTER JOIN cte_web_events
  ON cte_orders.__pk_customers = cte_web_events.__pk_customers;
```

Each CTE aggregates at the correct grain. The `FULL OUTER JOIN` ensures customers that appear in only one fact table are still included.

### How PySemantic Handles It

1. **Detection** — When you pass measures from more than one model, the planner switches to the multi-fact path instead of a single flat query.
2. **Conformed dimensions** — Every dimension you use (in SELECT or filters) must be reachable from *every* fact table in the query; otherwise PySemantic raises `NonConformedDimensionError`.
3. **CTE per fact** — Each fact table becomes one CTE that pre-aggregates its measures and joins to the shared dimension(s). No fact table is joined directly to another fact table, so there is no fan-out.
4. **Outer join** — The final query joins the CTEs on the shared dimension (by primary key or by dimension values) using `FULL OUTER JOIN`, so rows that exist in only one fact are still returned.
5. **Intelligent Filter Pushdown** — Filters are automatically routed to the right place: conformed dimension filters are pushed into *every* CTE's `WHERE` clause; non-conformed dimension filters (Grand Total only) are pushed into *only* the CTEs that can reach them; measure filters are applied to the outer query after CTE aggregation. No manual filter routing required.
6. **Grand Total exception** — If you request no dimensions at all, you get one row per CTE and a `CROSS JOIN`; non-conformed dimension filters are then allowed and applied only where reachable.

The same `query()` API is used for both single-fact and multi-fact; no extra configuration is required.

### Conformed Dimensions

A **conformed dimension** is one that is reachable from *every* fact table in the query via the entity graph. Only conformed dimensions may appear in the SELECT or filter clauses of a multi-fact query. This ensures all CTEs group and filter at the same grain, producing correct aggregates.

PySemantic automatically detects how to reach each dimension from each fact table. If a model provides both measures and dimensions (e.g. `customers` has `total_customers` *and* `customer_state`), PySemantic handles this transparently — the model's own CTE uses local dimensions directly, while other CTEs join to it through the entity graph.

```python
sl.query(
    measures=["total_order_price", "total_customers"],  # order_items + customers
    dimensions=["customer_state", "customer_city"],       # conformed: reachable from both facts
    filters=[{"field": "customer_state", "operator": "IN", "value": "('SP', 'RJ')"}],
)
```

Generates:
```sql
WITH cte_order_items AS (
  SELECT customer_state, customer_city, SUM(price) AS total_order_price
  FROM order_items
  LEFT JOIN orders ON ...
  LEFT JOIN customers ON ...
  WHERE customer_state IN ('SP', 'RJ')
  GROUP BY 1, 2
),
cte_customers AS (
  SELECT customer_state, customer_city, COUNT(customer_id) AS total_customers
  FROM customers
  WHERE customer_state IN ('SP', 'RJ')
  GROUP BY 1, 2
)
SELECT
  COALESCE(cte_order_items.customer_state, cte_customers.customer_state) AS customer_state,
  COALESCE(cte_order_items.customer_city, cte_customers.customer_city) AS customer_city,
  cte_order_items.total_order_price,
  cte_customers.total_customers
FROM cte_order_items
FULL OUTER JOIN cte_customers
  ON cte_order_items.customer_state = cte_customers.customer_state
  AND cte_order_items.customer_city = cte_customers.customer_city;
```

A non-conformed dimension — one that only some fact tables can reach — is **rejected**:

```python
sl.query(
    measures=["total_order_price", "total_customers"],
    dimensions=["order_status"],  # only reachable from order_items, NOT from customers
)
# → raises NonConformedDimensionError
```

---

## Usage

Multi-fact queries require **no API changes**. The existing `SemanticLayer.query()` method automatically detects and handles them. Both initialization styles work identically:

=== "From model directory"

    ```python
    from pysemantic.client import SemanticLayer

    sl = SemanticLayer(model_path="./models", dialect="postgres")

    # Single-fact query (unchanged behavior)
    sql = sl.query(
        measures=["total_revenue", "order_count"],
        dimensions=["customer_name"],
    )

    # Multi-fact query (automatic CTE generation)
    sql = sl.query(
        measures=["total_revenue", "total_clicks"],  # from different fact tables
        dimensions=["customer_name"],                 # conformed dimension
    )
    ```

=== "From explicit model list"

    ```python
    from pysemantic.client import SemanticLayer
    from pysemantic.modeling import Model, Dimension, Measure, Entity, EntityType

    orders = Model(
        name="orders", table="orders", primary_key="order_id",
        measures=[Measure(name="total_revenue", agg="sum", column="revenue")],
        entities=[Entity(name="order", entity_type=EntityType.PRIMARY, column="order_id"),
                  Entity(name="customer", entity_type=EntityType.FOREIGN, column="customer_id")],
    )
    web_events = Model(
        name="web_events", table="web_events", primary_key="event_id",
        measures=[Measure(name="total_clicks", agg="count", column="id")],
        entities=[Entity(name="event", entity_type=EntityType.PRIMARY, column="event_id"),
                  Entity(name="customer", entity_type=EntityType.FOREIGN, column="customer_id")],
    )
    customers = Model(
        name="customers", table="customers", primary_key="customer_id",
        dimensions=[Dimension(name="customer_name", column="name", dtype="string")],
        entities=[Entity(name="customer", entity_type=EntityType.PRIMARY, column="customer_id")],
    )

    sl = SemanticLayer(models=[orders, web_events, customers], dialect="postgres")

    sql = sl.query(
        measures=["total_revenue", "total_clicks"],
        dimensions=["customer_name"],
    )
    ```

### With Filters

In **Conformed mode** (dimensions present), all filter dimensions must also be conformed — reachable from every fact. Non-conformed filter dimensions raise `NonConformedDimensionError`.

```python
# Conformed dimension filter — pushed into BOTH CTEs
sql = sl.query(
    measures=["total_revenue", "total_clicks"],
    dimensions=["customer_name"],
    filters=[{"field": "customer_name", "operator": "=", "value": "Alice"}],
)

# Non-conformed filter dimension — REJECTED
# order_date is only reachable from orders, not web_events
sl.query(
    measures=["total_revenue", "total_clicks"],
    dimensions=["customer_name"],
    filters=[{"field": "order_date", "operator": ">", "value": "2024-01-01"}],
)
# → raises NonConformedDimensionError

# Measure filter — applied to the outer query WHERE clause (always allowed)
sql = sl.query(
    measures=["total_revenue", "total_clicks"],
    dimensions=["customer_name"],
    filters=[{"field": "total_revenue", "operator": ">", "value": 100}],
)
```

### Grand Total (No Dimensions)

When no dimensions are specified, each CTE produces a single aggregated row and the final query uses `CROSS JOIN`. This is the **only** way to query unrelated fact tables that share no conformed dimensions.

```python
sql = sl.query(measures=["total_revenue", "total_clicks"])
# Produces:
# WITH cte_orders AS (SELECT SUM(revenue) AS total_revenue FROM orders),
#      cte_web_events AS (SELECT COUNT(id) AS total_clicks FROM web_events)
# SELECT cte_orders.total_revenue, cte_web_events.total_clicks
# FROM cte_orders CROSS JOIN cte_web_events;
```

In Grand Total mode, non-conformed filter dimensions are **allowed** and routed only to the CTEs that can access them:

```python
# Grand Total with fact-specific filter — allowed
sql = sl.query(
    measures=["total_order_price", "total_customers"],
    dimensions=[],
    filters=[{"field": "order_status", "operator": "=", "value": "delivered"}],
)
# → order_status filter pushed only to order_items CTE
#   customers CTE produces unfiltered total
```

### 3+ Fact Tables

Multi-fact queries support any number of fact tables. Subsequent CTEs are joined using `COALESCE`d keys:

```python
sql = sl.query(
    measures=["total_revenue", "total_clicks", "return_count"],
    dimensions=["customer_name"],
)
```

Produces chained `FULL OUTER JOIN`:

```sql
FROM cte_orders
FULL OUTER JOIN cte_web_events
  ON cte_orders.__pk_customers = cte_web_events.__pk_customers
FULL OUTER JOIN cte_returns
  ON COALESCE(cte_orders.__pk_customers, cte_web_events.__pk_customers)
     = cte_returns.__pk_customers
```

---

## Architecture

### How It Works Internally

The multi-fact feature extends the existing three-stage pipeline:

```
QueryAST  ──▶  QueryPlanner  ──▶  SQLGenerator
                    │                    │
              ┌─────┴─────┐        ┌────┴────┐
              │ QueryPlan │        │ Flat SQL │   (single-fact)
              └───────────┘        └─────────┘
              ┌───────────────┐    ┌──────────┐
              │ MultiFactPlan │    │ CTE SQL  │   (multi-fact)
              └───────────────┘    └──────────┘
```

**Detection**: The planner groups requested measures by their owning model. If all measures belong to one model, the existing `QueryPlan` path is used. If measures span 2+ models, the `MultiFactPlan` path activates — validating that all dimensions are conformed before generating SQL.

### Data Structures

#### `SharedDimensionKey`
Represents a join key derived from a conformed dimension model's primary key. Used to join CTEs in the outer query when the dimension model is a dedicated dimension table (not also a fact in the query).

| Field | Description |
|-------|-------------|
| `dimension_model_name` | Name of the dimension model (e.g., `"customers"`) |
| `table_name` | Physical table name (e.g., `"customers"`) |
| `primary_key_column` | PK column name (e.g., `"id"`) |
| `alias` | Internal alias for CTE output (e.g., `"__pk_customers"`) |

#### `SubPlan`
Represents a single CTE in the multi-fact query. One per fact table.

| Field | Description |
|-------|-------------|
| `cte_alias` | CTE name (e.g., `"cte_orders"`) |
| `fact_model_name` | Semantic model name |
| `fact_table_name` | Physical table name |
| `measures` | Measures from this fact |
| `dimensions` | Conformed dimensions to include |
| `joins` | Join path from fact to dimension tables |
| `shared_keys` | Dimension PKs for outer-query joining |
| `filters` | Dimension filters pushed into this CTE |

#### `MultiFactPlan`
The top-level plan containing all CTEs and outer-query metadata.

| Field | Description |
|-------|-------------|
| `sub_plans` | List of `SubPlan` instances |
| `shared_dimensions` | Conformed dimensions in the final SELECT |
| `shared_keys` | PK-based join keys (dedicated dimension models) |
| `dimension_value_keys` | Dimension names used as join keys (when the dimension model also provides measures in this query) |
| `measure_filters` | Filters applied to the outer query |
| `order_by` | ORDER BY fields for the outer query |
| `limit` | LIMIT for the outer query |

---

## Intelligent Filter Pushdown

PySemantic automatically routes every filter to the correct SQL location — no manual intervention needed. The routing strategy depends on the filter type and whether the query has dimensions.

```
┌─────────────────────────────────────────────────────┐
│                 Filter Pushdown                     │
│                                                     │
│  Dimension filter ─┬─ Conformed ──▶ ALL CTEs WHERE  │
│                    └─ Non-conformed                  │
│                       ├─ Conformed mode ──▶ ERROR    │
│                       └─ Grand Total ──▶ Reachable   │
│                                          CTEs only   │
│                                                     │
│  Measure filter ──────────────▶ Outer query WHERE   │
└─────────────────────────────────────────────────────┘
```

### Conformed Mode (dimensions present)

| Filter Type | Routing | Non-conformed? |
|-------------|---------|----------------|
| **Conformed dimension filter** | Pushed into ALL CTEs' WHERE | Must be conformed — **error** if not |
| **Measure filter** | Applied to outer query WHERE | N/A |

All dimension filters must be conformed (reachable from every fact). This guarantees **symmetric filtering** — every CTE applies the same dimension constraints, so aggregates remain comparable across fact tables.

```python
# customer_city is conformed (reachable from both order_items and customers)
# → pushed into BOTH CTEs' WHERE clause
sql = sl.query(
    measures=["total_order_price", "total_customers"],
    dimensions=["customer_state"],
    filters=[{"field": "customer_city", "operator": "=", "value": "São Paulo"}],
)
```

### Grand Total Mode (no dimensions)

| Filter Type | Routing | Non-conformed? |
|-------------|---------|----------------|
| **Conformed dimension filter** | Pushed into ALL CTEs' WHERE | Allowed |
| **Fact-specific dimension filter** | Pushed into ONLY accessible CTEs | Allowed |
| **Measure filter** | Applied to outer query WHERE | N/A |

In Grand Total mode, non-conformed dimension filters are permitted. They're routed **only to CTEs that can reach** the dimension's model, producing asymmetric but semantically valid scalar aggregates.

```python
# order_status is only reachable from order_items (via orders), NOT from customers
# → filter pushed ONLY to cte_order_items; cte_customers runs unfiltered
sql = sl.query(
    measures=["total_order_price", "total_customers"],
    dimensions=[],
    filters=[{"field": "order_status", "operator": "=", "value": "delivered"}],
)
```

```sql
WITH cte_order_items AS (
  SELECT SUM(order_items.price) AS total_order_price
  FROM order_items
  LEFT JOIN orders ON order_items.order_id = orders.order_id
  WHERE orders.order_status = 'delivered'   -- ← filter pushed here only
),
cte_customers AS (
  SELECT COUNT(customers.customer_id) AS total_customers
  FROM customers                            -- ← no filter (can't reach orders)
)
SELECT
  cte_order_items.total_order_price,
  cte_customers.total_customers
FROM cte_order_items
CROSS JOIN cte_customers;
```

### Measure Filters

Measure filters are always applied to the **outer query's WHERE** clause (after CTE aggregation). Since CTEs already compute the aggregated values, these become simple column comparisons like `cte_orders.total_revenue > 100`.

---

## Error Handling

Multi-fact queries introduce three exception classes following the existing exception hierarchy:

### `NonConformedDimensionError` (inherits from `MultiFactPlanningError`)

The primary guard for multi-fact queries. Raised when a dimension (SELECT or filter) is **not conformed** — not reachable from every fact table in the query.

```python
from pysemantic.core.planner import NonConformedDimensionError

try:
    sql = sl.query(
        measures=["total_order_price", "total_customers"],
        dimensions=["order_status"],  # only reachable from order_items, not customers
    )
except NonConformedDimensionError as e:
    print(e)
    # planning.multi_fact: Non-conformed Dimension requested
    # (details="Dimension 'order_status' (model 'orders') is not reachable
    #  from fact model 'customers'. In multi-fact queries all dimensions must
    #  be conformed — joinable from every fact table. For unrelated facts with
    #  no shared dimensions, use a Grand Total query (no dimensions).")
```

### `MultiFactPlanningError` (inherits from `PlannerError`)

Raised for general multi-fact planning issues:

- **Invalid measure filter**: A filter references a measure from a model that isn't a fact table in the query
- **Missing dimension/measure definitions**: A referenced field doesn't exist in any model
- **Join path not found**: A CTE can't join to a required dimension model

### `MultiFactGenerationError` (inherits from `GeneratorError`)

Raised during SQL generation when:

- **Empty sub-plans**: MultiFactPlan has no CTEs to generate
- **Empty CTE SELECT**: A CTE produces no output columns
- **Unresolvable dimension in CTE**: A dimension can't be found in the CTE's accessible models
- **Unresolvable measure in outer query**: A measure filter references a field not in any CTE

---

## Constraints and Limitations

### Conformed Dimension Requirement

1. **All dimensions must be conformed** — reachable from every fact table in the query via the entity graph. Non-conformed dimensions in either SELECT or filter clauses raise `NonConformedDimensionError`.

2. **Grand Total exception**: the only way to query unrelated fact tables is with no SELECT dimensions, producing scalar aggregates via CROSS JOIN. Non-conformed filter dimensions are permitted in this mode.

3. **Models providing both measures and dimensions** are fully supported. When a model contributes both measures and conformed dimensions to a query, PySemantic uses dimension-value joins instead of PK-based joins to preserve correct aggregate semantics.

### Dialect Support

PySemantic defaults to **MySQL** and supports all dialects via [SQLGlot](https://github.com/tobymao/sqlglot). Pass the `dialect` parameter when initializing `SemanticLayer`:

```python
sl = SemanticLayer(model_path="./models", dialect="postgres")
```

| Dialect | Value | Multi-Fact Notes |
|---------|-------|-----------------|
| MySQL | `"mysql"` (default) | 2-fact supported (SQLGlot transpiles `FULL OUTER JOIN` to `LEFT + RIGHT + UNION ALL`). 3+ facts may need native `FULL OUTER JOIN`. |
| PostgreSQL | `"postgres"` | Full support (native `FULL OUTER JOIN`) |
| BigQuery | `"bigquery"` | Full support |
| Snowflake | `"snowflake"` | Full support |
| DuckDB | `"duckdb"` | Full support |
| Databricks | `"databricks"` | Full support |
| Redshift | `"redshift"` | Full support |
| ClickHouse | `"clickhouse"` | Full support |
| Trino / Presto | `"trino"` / `"presto"` | Full support |
| SQLite | `"sqlite"` | Limited (`FULL OUTER JOIN` not natively supported) |
| ... and more | See [SQLGlot dialect list](https://github.com/tobymao/sqlglot/blob/main/sqlglot/dialects/__init__.py) | |

### Impact on Existing System

| Component | Impact |
|-----------|--------|
| `plan.py` | Added `SharedDimensionKey`, `SubPlan`, `MultiFactPlan` (with `dimension_value_keys` for dimension-value joins) |
| `planner.py` | Added `MultiFactPlanningError`, `NonConformedDimensionError`, `_plan_multi_fact()`, `_find_shared_dimension_owner()`, `_validate_dimension_conformity()`, `_is_reachable_from_all()`, `_can_reach()`. Conformed-only enforcement with Grand Total exception. Existing single-fact logic in `_plan_single_fact()` — **no behavioral change** |
| `generator.py` | Added `MultiFactGenerationError`, `_build_multi_fact_sql()`, `_build_cte_body()`, `_build_cte_joins()` (supports both PK-based and dimension-value joins), `_build_measure_filter_where()`, `_find_owner_model_in_subplan()`. Existing single-fact methods **unchanged** |
| `client.py` | **No changes** — polymorphic flow handles both plan types |
| `exceptions.py` | **No changes** — new exceptions inherit from existing base classes |
| `registry.py` | **No changes** |
| `ast.py` | **No changes** |

The feature is **fully backward-compatible**. Single-fact queries follow the exact same code path as before.
