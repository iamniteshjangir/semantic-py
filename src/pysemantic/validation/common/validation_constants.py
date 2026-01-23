import keyword
import re

# Python reserved words
RESERVED_WORDS = set(keyword.kwlist)

# SQL keywords that cannot be used as identifiers
SQL_KEYWORDS = {
    "select",
    "from",
    "where",
    "join",
    "inner",
    "left",
    "right",
    "outer",
    "full",
    "on",
    "group",
    "by",
    "order",
    "having",
    "as",
    "and",
    "or",
    "not",
    "in",
    "like",
    "between",
    "is",
    "null",
    "distinct",
    "union",
    "all",
    "intersect",
    "except",
    "insert",
    "into",
    "values",
    "update",
    "set",
    "delete",
    "create",
    "table",
    "alter",
    "drop",
    "index",
    "view",
    "database",
    "schema",
    "constraint",
    "primary",
    "key",
    "foreign",
    "references",
    "unique",
    "check",
    "default",
    "auto_increment",
    "limit",
    "offset",
    "case",
    "when",
    "then",
    "else",
    "end",
    "cast",
    "convert",
    "count",
    "sum",
    "avg",
    "min",
    "max",
    "exists",
    "any",
    "some",
}

# Combined reserved words (Python + SQL)
ALL_RESERVED_WORDS = RESERVED_WORDS | SQL_KEYWORDS

# Regex pattern for valid Python identifiers
VALID_IDENTIFIER_PATTERN = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")

# Valid aggregation functions for measures
VALID_MEASURE_AGGS = ["sum", "avg", "mean", "count", "count_distinct", "min", "max"]

# Valid data types for dimensions
VALID_DIMENSION_DTYPES = ["string", "int", "float", "boolean", "date", "datetime"]

GRAIN_KEYWORDS = ["hourly", "daily", "monthly", "yearly"]
