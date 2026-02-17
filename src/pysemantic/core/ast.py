from dataclasses import dataclass, field

from pysemantic.exceptions import ASTError, format_error


class ASTValidationError(ASTError):
    """Custom exception for AST validation errors."""

    DOMAIN = "validation.ast"

    def __init__(self, summary: str, **context):
        super().__init__(format_error(self.DOMAIN, summary, **context))


@dataclass
class FilterAST:
    """Represent a raw filter string (e.g., "amount > 100")"""

    expression: str


@dataclass
class QueryAST:
    """
    The Abstract Syntax Tree (AST) representing the User's Request.
    This is the 'Input' to the Planner.
    """

    measures: list[str]
    dimensions: list[str] = field(default_factory=list)
    filters: list[FilterAST] = field(default_factory=list)
    order_by: list[str] = field(default_factory=list)
    limit: int | None = None

    @classmethod
    def from_request(
        cls,
        measures: list[str],
        dimensions: list[str] | None = None,
        filters: list[str] | None = None,
        order_by: list[str] | None = None,
        limit: int | None = None,
    ) -> "QueryAST":
        """
        Factory method to parse raw arguments into an AST.
        """
        return cls(
            measures=measures,
            dimensions=dimensions or [],
            filters=[FilterAST(f) for f in filters or []],
            order_by=order_by or [],
            limit=limit,
        )

    def __post_init__(self):
        """
        Post-initialization hook to validate and normalize the AST.
        """
        if not self.measures and not self.dimensions:
            raise ASTValidationError(
                summary="Query must contain at least one metric or dimension",
                measures=self.measures,
                dimensions=self.dimensions,
            )
