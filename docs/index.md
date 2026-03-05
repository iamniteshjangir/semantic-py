---
hide:
  - toc
---

<div class="hero" markdown>

# PySemantic

<p class="tagline">A lightweight, graph-based Semantic Layer for Python and SQL.<br>
<strong>Define metrics once. Generate SQL everywhere.</strong></p>

<div class="badges">
<a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/python-3.11%2B-blue.svg" alt="Python 3.11+"></a>
<a href="https://github.com/iamniteshjangir/semantic-py/blob/main/LICENSE"><img src="https://img.shields.io/badge/License-MIT-green.svg" alt="MIT License"></a>
<a href="https://pypi.org/project/pysemantic-layer/"><img src="https://img.shields.io/pypi/v/pysemantic-layer?color=purple&label=PyPI" alt="PyPI"></a>
<a href="https://typer.tiangolo.com/"><img src="https://img.shields.io/badge/CLI-Typer-purple.svg" alt="Typer CLI"></a>
</div>

<div class="cta-buttons">
<a href="getting-started/" class="cta-primary">&#x1F680; Get Started</a>
<a href="cli-studio/" class="cta-secondary">&#x1F4BB; CLI &amp; Studio</a>
</div>

</div>

---

## See It in Action

<div class="video-container">
<video src="https://github.com/user-attachments/assets/99704771-497e-45a8-9df0-07a100f7dc84" width="100%" controls>
Your browser does not support the video tag.
</video>
</div>

Write a Python query — get production-ready SQL:

=== "Python"

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

=== "Generated SQL"

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
      1, 2
    ORDER BY
      total_order_price DESC
    LIMIT 10
    ```

=== "CLI"

    ```bash
    pysemantic query ./models \
      -m "total_order_price,total_number_of_distinct_orders" \
      -d customer_state,customer_city \
      -f "customer_state IN ('SP', 'RJ')" \
      --order-by "total_order_price DESC" \
      --limit 10
    ```

<div class="gif-container" markdown>

![pysemantic query demo](assets/gifs/query.gif)

</div>

<hr class="section-divider">

## Why PySemantic?

<div class="feature-grid">

<div class="feature-card">
<div class="feature-icon">🎯</div>
<h3>Single Source of Truth</h3>
<p>Define a metric once — use it across dashboards, notebooks, and APIs. No more scattered business logic.</p>
</div>

<div class="feature-card">
<div class="feature-icon">🔗</div>
<h3>Automatic Join Resolution</h3>
<p>Declare entity relationships in your models. PySemantic finds the shortest join path automatically.</p>
</div>

<div class="feature-card">
<div class="feature-icon">🛡️</div>
<h3>SQL Injection Safe</h3>
<p>Structured filters with operator whitelisting and value escaping. No raw string interpolation.</p>
</div>

<div class="feature-card">
<div class="feature-icon">🌐</div>
<h3>Multi-Dialect Support</h3>
<p>MySQL, Postgres, and more via <a href="https://github.com/tobymao/sqlglot">SQLGlot</a>. One model, any database.</p>
</div>

<div class="feature-card">
<div class="feature-icon">⚡</div>
<h3>Zero Infrastructure</h3>
<p>Pure Python library. No server, no daemon, no Docker. Install and query.</p>
</div>

<div class="feature-card">
<div class="feature-icon">🔮</div>
<h3>Interactive Studio</h3>
<p>Explore models, visualize the entity graph, and test queries in the browser — powered by Streamlit.</p>
</div>

</div>

<hr class="section-divider">

## Architecture

PySemantic processes queries through a clean, four-stage pipeline:

<div class="architecture-block">

```
User Query (measures, dimensions, filters)
    │
    ▼
┌──────────┐     ┌──────────┐     ┌──────────┐
│   AST    │────▶│ Planner  │────▶│Generator │───▶ SQL string
│ (Parser) │     │(Resolver)│     │(Compiler)│
└──────────┘     └──────────┘     └──────────┘
                      │
                ┌─────┴─────┐
                │ Registry  │
                │ + Entity  │
                │   Graph   │
                └───────────┘
```

</div>

| Layer | Responsibility |
|-------|---------------|
| **AST** | Parses raw input into a structured, validated syntax tree |
| **Registry** | Loads model files, validates them, builds the entity graph |
| **Planner** | Resolves measures/dimensions to models, calculates join paths |
| **Generator** | Translates the logical plan into dialect-specific SQL |

<hr class="section-divider">

<div style="text-align: center; padding: 2rem 0;" markdown>

**Ready to define your first semantic model?**

<div class="cta-buttons">
<a href="getting-started/" class="cta-primary">&#x1F680; Get Started</a>
<a href="https://github.com/iamniteshjangir/semantic-py/" class="cta-secondary">&#x2B50; View on GitHub</a>
</div>
</div>
