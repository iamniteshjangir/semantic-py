"""PySemantic CLI — powered by Typer."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel

app = typer.Typer(
    name="pysemantic",
    help="Python lightweight semantic layer for data engineers.",
    no_args_is_help=True,
    rich_markup_mode="rich",
)
console = Console()


def _split_csv(values: list[str] | None) -> list[str] | None:
    """Expand comma-separated items so '-m a,b -m c' becomes ['a', 'b', 'c']."""
    if not values:
        return values
    expanded = []
    for v in values:
        for part in v.split(","):
            cleaned = part.strip().strip("[]'\"")
            if cleaned:
                expanded.append(cleaned)
    return expanded or None


_OPERATORS = [
    "NOT IN",
    "IS NOT",
    "!=",
    ">=",
    "<=",
    "ILIKE",
    "LIKE",
    "IN",
    "IS",
    "=",
    ">",
    "<",
]


def _parse_filter(raw: str) -> dict:
    """Parse 'field operator value' into a filter dict.

    Examples:
        "order_status = delivered"        -> {"field":"order_status", "operator":"=", "value":"delivered"}
        "total_order_price > 100"         -> {"field":"total_order_price", "operator":">", "value":"100"}
        "customer_state IN ('SP', 'RJ')"  -> {"field":"customer_state", "operator":"IN", "value":"('SP', 'RJ')"}
        "order_status IS NULL"            -> {"field":"order_status", "operator":"IS", "value":None}
    """
    upper = raw.upper()
    for op in _OPERATORS:
        padded = f" {op} "
        idx = upper.find(padded)
        if idx == -1:
            continue

        field = raw[:idx].strip()
        value_str = raw[idx + len(padded) :].strip()

        if not field:
            continue

        value: str | None = value_str
        if value_str.upper() == "NULL":
            value = None

        return {"field": field, "operator": op, "value": value}

    raise typer.BadParameter(
        f"Could not parse filter: '{raw}'. Expected format: 'field OPERATOR value' (e.g. 'order_status = delivered')"
    )


@app.command()
def studio(
    model_path: str = typer.Argument(
        ...,
        help="Path to the directory containing your semantic model definitions.",
    ),
    port: int = typer.Option(8501, "--port", "-p", help="Port for the Streamlit server."),
    dark: bool = typer.Option(True, "--dark/--light", help="Dark or light theme."),
):
    """Launch the PySemantic Explorer studio in your browser."""
    resolved = Path(model_path).resolve()
    if not resolved.is_dir():
        console.print(f"[red]Error:[/red] Model path '{model_path}' is not a valid directory.")
        raise typer.Exit(code=1)

    console.print(
        Panel.fit(
            f"[bold]Model path:[/bold] {resolved}\n"
            f"[bold]Port:[/bold] {port}\n"
            f"[bold]Theme:[/bold] {'dark' if dark else 'light'}",
            title="🔮 PySemantic Studio",
            border_style="magenta",
        )
    )

    app_path = Path(__file__).parent / "ui" / "app.py"
    theme = "dark" if dark else "light"

    cmd = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        str(app_path),
        "--server.port",
        str(port),
        "--server.headless",
        "true",
        "--theme.base",
        theme,
        "--",
        str(resolved),
    ]

    try:
        subprocess.run(cmd, check=True)
    except KeyboardInterrupt:
        console.print("\n[dim]Studio stopped.[/dim]")


@app.command()
def query(
    model_path: str = typer.Argument(
        ...,
        help="Path to the directory containing your semantic model definitions.",
    ),
    measures: list[str] = typer.Option(..., "--measure", "-m", help="Measure(s) — repeat or comma-separate."),
    dimensions: list[str] | None = typer.Option(
        None, "--dimension", "-d", help="Dimension(s) — repeat or comma-separate."
    ),
    filters: list[str] | None = typer.Option(
        None,
        "--filter",
        "-f",
        help="Filter as 'field OP value', e.g. 'order_status = delivered'. Repeatable.",
    ),
    order_by: list[str] | None = typer.Option(
        None, "--order-by", help="Order by column(s) — repeat or comma-separate."
    ),
    limit: int | None = typer.Option(None, "--limit", "-l", help="Limit rows."),
):
    """Generate a SQL query from the command line."""
    from pysemantic.client import SemanticLayer

    resolved = Path(model_path).resolve()
    if not resolved.is_dir():
        console.print(f"[red]Error:[/red] Model path '{model_path}' is not a valid directory.")
        raise typer.Exit(code=1)

    parsed_measures = _split_csv(measures)
    parsed_dimensions = _split_csv(dimensions)
    parsed_order_by = _split_csv(order_by)
    parsed_filters = [_parse_filter(f) for f in filters] if filters else None

    if not parsed_measures:
        console.print("[red]Error:[/red] At least one measure is required.")
        raise typer.Exit(code=1)

    try:
        sl = SemanticLayer(model_path=str(resolved))
        sql = sl.query(
            measures=parsed_measures,
            dimensions=parsed_dimensions,
            filters=parsed_filters,
            order_by=parsed_order_by,
            limit=limit,
        )
        console.print()
        console.print(Panel(sql, title="Generated SQL", border_style="green", subtitle="pysemantic"))
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(code=1) from e


@app.command()
def graph(
    model_path: str = typer.Argument(
        ...,
        help="Path to the directory containing your semantic model definitions.",
    ),
    output: str = typer.Option("entity_graph.html", "--output", "-o", help="Output HTML file path."),
):
    """Generate an interactive entity-graph HTML file."""
    from pysemantic.client import SemanticLayer

    resolved = Path(model_path).resolve()
    if not resolved.is_dir():
        console.print(f"[red]Error:[/red] Model path '{model_path}' is not a valid directory.")
        raise typer.Exit(code=1)

    try:
        sl = SemanticLayer(model_path=str(resolved))
        sl.generate_graph(output_file=output)
        console.print(f"[green]Graph saved to:[/green] {output}")
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(code=1) from e


def main():
    app()


if __name__ == "__main__":
    main()
