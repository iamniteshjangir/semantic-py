"""Utilities for discovering semantic objects inside a Python source tree."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

from pysemantic.exceptions import RegistryError, format_error
from pysemantic.modeling import Dimension, Entity, Measure, Model


class ModuleLoaderError(RegistryError):
    """Custom exception for module loader errors."""

    DOMAIN = "registry.loader"

    def __init__(self, summary: str, **context: Any):
        super().__init__(format_error(self.DOMAIN, summary, **context))


class ModuleLoader:
    """Discover and import semantic objects from a Python directory."""

    def __init__(self, source_path: str | Path):
        self.source_path = Path(source_path).resolve()
        self._reset_results()

    def load_objects(self) -> None:
        """Load all semantic objects from the configured source path."""
        self._reset_results()
        self._validate_source_path()

        for file_path in self._discover_python_files():
            module = self._import_module(file_path)
            self._collect_models(module)

    def _reset_results(self) -> None:
        self.models: dict[str, Model] = {}
        self.entities: dict[str, Entity] = {}
        self.dimensions: dict[str, Dimension] = {}
        self.measures: dict[str, Measure] = {}

    def _validate_source_path(self) -> None:
        if not self.source_path.exists():
            raise ModuleLoaderError(
                "Source path does not exist",
                source_path=str(self.source_path),
            )

        if not self.source_path.is_dir():
            raise ModuleLoaderError(
                "Source path must be a directory",
                source_path=str(self.source_path),
            )

    def _discover_python_files(self) -> list[Path]:
        """Return all Python files under the source path, excluding __init__.py."""
        python_files = [
            file_path
            for file_path in self.source_path.rglob("*.py")
            if file_path.name != "__init__.py"
        ]
        return sorted(python_files)

    def _import_module(self, file_path: Path) -> ModuleType:
        """Import a module from a file path."""
        relative_path = file_path.relative_to(self.source_path)
        module_name = ".".join(relative_path.with_suffix("").parts)

        spec = importlib.util.spec_from_file_location(
            module_name,
            file_path,
            submodule_search_locations=None,
        )

        if spec is None or spec.loader is None:
            raise ModuleLoaderError(
                "Unable to create import spec for module",
                file_path=str(file_path),
                module=module_name,
            )

        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        try:
            spec.loader.exec_module(module)
        except Exception as exc:  # pragma: no cover - surfaced to user as registry error
            sys.modules.pop(module_name, None)
            raise ModuleLoaderError(
                "Failed to import module",
                file_path=str(file_path),
                module=module_name,
            ) from exc

        return module

    def _collect_models(self, module: ModuleType) -> None:
        """Collect all models from the module."""
        for attr_name in dir(module):
            if attr_name.startswith("_"):
                continue

            attr = getattr(module, attr_name)
            if isinstance(attr, Model):
                if attr.name in self.models:
                    raise ModuleLoaderError(
                        "Duplicate model detected",
                        model=attr.name,
                    )
                self.models[attr.name] = attr
                for entity in attr.entities or []:
                    self.entities[f"{attr.name}.{entity.name}"] = entity
                for dimension in attr.dimensions or []:
                    self.dimensions[f"{attr.name}.{dimension.name}"] = dimension
                for measure in attr.measures or []:
                    self.measures[f"{attr.name}.{measure.name}"] = measure

