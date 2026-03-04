from pathlib import Path

from pysemantic.core.ast import QueryAST
from pysemantic.core.generator import SQLGenerator
from pysemantic.core.planner import QueryPlanner
from pysemantic.registry import Registry


class SemanticLayer:
    """
    The main entry point for the PySemantic library.
    Integrates the Registry, Planner, and Generator to execute queries.
    """

    def __init__(self, model_path: str):
        """
        Initialize the Semantic Layer.

        Args:
            model_path (str): Path to the directory constaining model definations.
        """
        # Initalize and Load Registry
        # This scans the folder, validates models, and builds the Entity Graph.
        self.registry = Registry()
        self.model_path = model_path
        self.registry.initialize(Path(model_path))

        # Initalize core Components
        # The Planner needs the Registry to find objects and calculate paths.
        self.planner = QueryPlanner(self.registry)

        # The Generator needs the Registry to look up Entity definitions for JOIN ON clauses.
        self.generator = SQLGenerator(self.registry)

    def query(
        self,
        measures: list[str],
        dimensions: list[str] | None = None,
        filters: list[str] | None = None,
        order_by: list[str] | None = None,
        limit: int | None = None,
    ) -> str:
        """
        Generates a SQL query based on the user's request.

        Args:
            measures (list[str]): List of measures to aggregate.
            dimensions (list[str]): List of dimensions to group by.
            filters (list[dict | str]): List of filters. Strings parsed loosely.
                Dicts safer: {'field': '..', 'op': '..', 'value': ..}
            order_by (list[str]): List of columns to order by.
            limit (int): Maximum number of rows to return.

        Returns:
            str: Generated SQL query.
        """
        # Parse Request into AST (Abstract Syntax Tree)
        # Captures "What the user wants" (Symbols)
        ast = QueryAST.from_request(
            measures=measures,
            dimensions=dimensions,
            filters=filters,
            order_by=order_by,
            limit=limit,
        )

        # Plan the Query (Logical Plan / DST)
        # Converts symobols to objects, identifies the Root Table, and calculates Join Paths.
        plan = self.planner.plan(ast)

        # Generate the SQL Query (Physical Plan)
        # Translates the logical Plan into valid SQL string.
        sql = self.generator.generate(plan)

        return sql

    def reload(self, model_path: str | None = None) -> None:
        """
        Reloads the registry from the file system.
        Useful for development loops (e.g. in Jupyter) without restarting the kernel.
        """
        path = model_path or self.model_path
        if model_path:
            self.model_path = model_path

        # Re-run the initialization flow
        self.registry = Registry()
        self.registry.initialize(Path(path))

        # Re-wire the dependencies
        self.planner = QueryPlanner(self.registry)
        self.generator = SQLGenerator(self.registry)

    def generate_graph(self, output_file: str = "entity_graph.html") -> None:
        """
        Generates a visualization of the entity graph.

        Args:
            output_file (str): The path to save the generated graph image.
        """
        self.registry.generate_graph(output_file=output_file)
