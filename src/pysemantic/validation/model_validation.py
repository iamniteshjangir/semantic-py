from typing import TYPE_CHECKING

from pysemantic import ValidationError
from pysemantic.exceptions import format_error
from pysemantic.validation.common.validation_constants import (
    ALL_RESERVED_WORDS,
    VALID_IDENTIFIER_PATTERN,
)

if TYPE_CHECKING:
    from pysemantic.modeling.model import Model


class ModelValidationError(ValidationError):
    """Custom exception for model validation errors."""

    DOMAIN = "validation.model"

    def __init__(self, summary: str, **context):
        super().__init__(format_error(self.DOMAIN, summary, **context))


class ModelValidation:
    """Validates a model according to business rules.
    Validation Rules:
        1. Model name must be a valid identifier.
        2. Table name must be a valid identifier.
        3. Primary key must be a valid identifier.
    """

    def __init__(self, model: "Model"):
        self.model = model

    def _is_valid_identifier(self, name: str) -> bool:
        """Check if a name is a valid Python identifier and not a reserved word.

        Args:
            name: The name to validate

        Returns:
            True if the name is a valid identifier, False otherwise
        """
        if not name:
            return False
        if name in ALL_RESERVED_WORDS:
            return False
        return bool(VALID_IDENTIFIER_PATTERN.match(name))

    def _validate_model_name_is_valid_identifier(self) -> None:
        """Rule 1: Model names must be valid identifiers."""
        if not self._is_valid_identifier(self.model.name):
            if self.model.name in ALL_RESERVED_WORDS:
                message = f"Model name cannot be a reserved word or SQL keyword. Invalid name: '{self.model.name}'"
                raise ModelValidationError(
                    message,
                    model=self.model.name,
                    model_name=self.model.name,
                )
            message = (
                "Model name must be a valid identifier (no spaces, no symbols, "
                "no reserved words, no SQL keywords). "
                f"Invalid name: '{self.model.name}'"
            )
            raise ModelValidationError(
                message,
                model=self.model.name,
                model_name=self.model.name,
            )

    def _validate_table_name_is_valid_identifier(self) -> None:
        """Rule 2: Table names must be valid identifiers."""
        if not self._is_valid_identifier(self.model.table):
            if self.model.table in ALL_RESERVED_WORDS:
                message = f"Table name cannot be a reserved word or SQL keyword. Invalid name: '{self.model.table}'"
                raise ModelValidationError(
                    message,
                    model=self.model.name,
                    table_name=self.model.table,
                )
            message = (
                "Table name must be a valid identifier (no spaces, no symbols, "
                "no reserved words, no SQL keywords). "
                f"Invalid name: '{self.model.table}'"
            )
            raise ModelValidationError(
                message,
                model=self.model.name,
                table_name=self.model.table,
            )

    def _validate_primary_key_is_valid_identifier(self) -> None:
        """Rule 3: Primary key must be a valid identifier."""
        if not self._is_valid_identifier(self.model.primary_key):
            if self.model.primary_key in ALL_RESERVED_WORDS:
                message = (
                    f"Primary key cannot be a reserved word or SQL keyword. Invalid name: '{self.model.primary_key}'"
                )
                raise ModelValidationError(
                    message,
                    model=self.model.name,
                    primary_key=self.model.primary_key,
                )
            message = (
                "Primary key must be a valid identifier (no spaces, no symbols, "
                "no reserved words, no SQL keywords). "
                f"Invalid name: '{self.model.primary_key}'"
            )
            raise ModelValidationError(
                message,
                model=self.model.name,
                primary_key=self.model.primary_key,
            )

    def validate(self) -> None:
        """Validate the model according to business rules.
        Validation Rules:
            1. Model name must be a valid identifier.
            2. Table name must be a valid identifier.
            3. Primary key must be a valid identifier.
        """
        self._validate_model_name_is_valid_identifier()
        self._validate_table_name_is_valid_identifier()
        self._validate_primary_key_is_valid_identifier()
