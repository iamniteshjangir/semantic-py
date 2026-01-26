"""Centralized exception hierarchy for the pysemantic project.

This module defines a consistent exception structure that all packages
within pysemantic (modeling, validation, parsing, logical planning, etc.)
should use. Having a shared hierarchy makes it easier for downstream
consumers to handle errors at the right granularity (e.g., catch all
validation errors vs. a specific entity validation failure) while keeping
error messages uniform across the codebase.
"""

from __future__ import annotations

from typing import Any

__all__ = [
    "ConfigurationError",
    "LogicalPlanError",
    "ModelingError",
    "NamingCollisionError",
    "ParsingError",
    "PySemanticError",
    "ValidationError",
    "format_error",
]


class PySemanticError(Exception):
    """Base exception for all pysemantic errors."""


class ModelingError(PySemanticError):
    """Raised for issues originating from the modeling package."""


class RegistryError(PySemanticError):
    """Raised for issues originating from the registry package."""


class ValidationError(PySemanticError):
    """Raised for input/model validation related issues."""


class ParsingError(PySemanticError):
    """Raised while parsing semantic definitions or configuration files."""


class LogicalPlanError(PySemanticError):
    """Raised for logical planning problems (query planning, optimization, etc.)."""


class ConfigurationError(PySemanticError):
    """Raised for configuration or environment related issues."""


class NamingCollisionError(ValidationError):
    """Raised when two semantic objects share the same identifier."""

    DOMAIN = "validation.naming"

    def __init__(self, summary: str, **context: Any):
        super().__init__(format_error(self.DOMAIN, summary, **context))


def format_error(domain: str, summary: str, **details: Any) -> str:
    """Create a consistently formatted error message.

    Args:
        domain: Logical area where the error originated, e.g.
        ``"validation.entities"`` or ``"registry.loader"``.
        summary: Short, user-friendly description of the failure.
        **details: Optional keyword arguments that add structured context.

    Returns:
        A formatted string following the pattern:
        ``"{domain}: {summary} (key1='value1', key2='value2')"``.
        Details are omitted when no extra context is provided.
    """
    context_parts = [f"{key}={value!r}" for key, value in details.items() if value is not None]
    context = f" ({', '.join(context_parts)})" if context_parts else ""
    return f"{domain}: {summary}{context}"
