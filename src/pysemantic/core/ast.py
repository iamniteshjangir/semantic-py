import re
from dataclasses import dataclass, field
from typing import ClassVar

from pysemantic.exceptions import ASTError, format_error


class ASTValidationError(ASTError):
    """Custom exception for AST validation errors."""

    DOMAIN = "validation.ast"

    def __init__(self, summary: str, **context):
        super().__init__(format_error(self.DOMAIN, summary, **context))


@dataclass
class Filter:
    """
    Represents a structured filter condition.
    Prevents SQL injection by separating field, operator, and value.
    """

    field: str
    operator: str
    value: str | int | float | bool

    VALID_OPERATORS: ClassVar[set[str]] = {
        "=",
        "!=",
        ">",
        "<",
        ">=",
        "<=",
        "in",
        "not in",
        "like",
        "ilike",
        "is",
        "is not",
    }

    def __post_init__(self):
        # normalize operator
        self.operator = self.operator.lower().strip()
        if self.operator not in self.VALID_OPERATORS:
            raise ASTValidationError(summary=f"Invalid filter operator: {self.operator}")


@dataclass
class QueryAST:
    """
    The Abstract Syntax Tree (AST) representing the User's Request.
    This is the 'Input' to the Planner.
    """

    measures: list[str]
    dimensions: list[str] = field(default_factory=list)
    filters: list[Filter] = field(default_factory=list)
    order_by: list[str] = field(default_factory=list)
    limit: int | None = None

    @classmethod
    def from_request(
        cls,
        measures: list[str],
        dimensions: list[str] | None = None,
        filters: list[dict | str] | None = None,
        order_by: list[str] | None = None,
        limit: int | None = None,
    ) -> "QueryAST":
        """
        Factory method to parse raw arguments into an AST.
        """
        parsed_filters = []
        if filters:
            for f in filters:
                if isinstance(f, dict):
                    # Expecting {'field': 'x', 'operator': '=', 'value': 10}
                    # Map 'op' to 'operator' for convenience if strict dict required
                    field_name = f.get("field")
                    operator = f.get("operator") or f.get("op")
                    _sentinel = object()
                    value = f.get("value", _sentinel)

                    if not field_name or not operator or value is _sentinel:
                        raise ASTValidationError(
                            summary=f"Invalid filter dictionary: {f}. Must contain 'field', 'operator', and 'value'."
                        )

                    parsed_filters.append(Filter(field_name, operator, value))

                elif isinstance(f, str):
                    # Strict parsing of string: "field op value"
                    # This is a basic parser; for complex cases, users should use dicts

                    # Regex handles: field operator value
                    # Value can be quoted string 'val' or number 123
                    match = re.match(
                        r"^([\w\.]+)\s+([!=<>]+|in|not\s+in|like|ilike|is|is\s+not)\s+(.+)$", f.strip(), re.IGNORECASE
                    )
                    if not match:
                        raise ASTValidationError(
                            summary=f"Invalid filter string format: '{f}'. Use structured dict for complex filters."
                        )

                    field_name, op, val_str = match.groups()

                    # Basic value inference
                    val_str = val_str.strip()
                    if (val_str.startswith("'") and val_str.endswith("'")) or (
                        val_str.startswith('"') and val_str.endswith('"')
                    ):
                        value = val_str[1:-1]
                    # Security Check for unquoted strings:
                    elif " " in val_str:
                        raise ASTValidationError(
                            f"Invalid filter value: '{val_str}'. Values with spaces must be quoted."
                        )
                    # End Security Check
                    elif val_str.lower() == "true":
                        value = True
                    elif val_str.lower() == "false":
                        value = False
                    elif val_str.lower() == "null":
                        value = "NULL"  # Special handling for NULL
                    else:
                        try:
                            if "." in val_str:
                                value = float(val_str)
                            else:
                                value = int(val_str)
                        except ValueError as e:
                            # Fallback to string if strictly alphanumeric, else error to prevent injection
                            if val_str.isalnum() or val_str.replace("_", "").isalnum():
                                value = val_str
                            else:
                                # If it contains special chars and wasn't quoted, it might be dangerous
                                raise ASTValidationError(
                                    summary=f"Invalid filter value: '{val_str}'. Complex string values must be quoted."
                                ) from e

                    parsed_filters.append(Filter(field_name, op, value))
                else:
                    raise ASTValidationError(f"Invalid filter format: {f}")

        return cls(
            measures=measures,
            dimensions=dimensions or [],
            filters=parsed_filters,
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
