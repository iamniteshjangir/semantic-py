from __future__ import annotations

from pathlib import Path

from pysemantic.core.ast import QueryAST
from pysemantic.core.generator import SQLGenerator
from pysemantic.core.planner import QueryPlanner
from pysemantic.modeling import Model
from pysemantic.registry import Registry


class SemanticLayer:
    """
    The main entry point for the PySemantic library.

    Supports two initialization styles:

        # 1. Directory of model files
        sl = SemanticLayer(model_path="./models")

        # 2. Explicit list of Model objects
        sl = SemanticLayer(models=[orders, customers])
    """

    def __init__(
        self,
        model_path: str | None = None,
        models: list[Model] | None = None,
    ):
        if model_path and models:
            raise ValueError("Provide either 'model_path' or 'models', not both.")
        if not model_path and not models:
            raise ValueError("You must provide either 'model_path' (directory) or 'models' (list of Model objects).")

        self.model_path = model_path
        self._models_list = models

        self.registry = Registry()
        self._init_registry()

        self.planner = QueryPlanner(self.registry)
        self.generator = SQLGenerator(self.registry)

    def _init_registry(self) -> None:
        if self._models_list is not None:
            self.registry.initialize_from_models(self._models_list)
        else:
            self.registry.initialize(Path(self.model_path))

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
            measures: List of measures to aggregate.
            dimensions: List of dimensions to group by.
            filters: List of filters. Dicts safer: {'field': '..', 'op': '..', 'value': ..}
            order_by: List of columns to order by.
            limit: Maximum number of rows to return.

        Returns:
            Generated SQL query string.
        """
        ast = QueryAST.from_request(
            measures=measures,
            dimensions=dimensions,
            filters=filters,
            order_by=order_by,
            limit=limit,
        )

        plan = self.planner.plan(ast)
        sql = self.generator.generate(plan)

        return sql

    def reload(self, model_path: str | None = None, models: list[Model] | None = None) -> None:
        """
        Reloads the registry.
        Useful for development loops (e.g. in Jupyter) without restarting the kernel.
        """
        if model_path:
            self.model_path = model_path
            self._models_list = None
        if models:
            self._models_list = models
            self.model_path = None

        self.registry = Registry()
        self._init_registry()

        self.planner = QueryPlanner(self.registry)
        self.generator = SQLGenerator(self.registry)

    def generate_graph(self, output_file: str = "entity_graph.html") -> None:
        """
        Generates a visualization of the entity graph.

        Args:
            output_file: The path to save the generated graph HTML.
        """
        self.registry.generate_graph(output_file=output_file)
