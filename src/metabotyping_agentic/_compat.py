"""Small compatibility layer for offline smoke runs before dependencies are installed."""

from __future__ import annotations

import json
from enum import Enum
from typing import Any, get_args, get_origin

try:  # pragma: no cover - exercised when optional dependency is installed
    from pydantic import BaseModel, ConfigDict, Field

    PYDANTIC_AVAILABLE = True
except ModuleNotFoundError:  # pragma: no cover - fallback is covered in this environment
    PYDANTIC_AVAILABLE = False

    class _FieldSpec:
        def __init__(self, default: Any = None, default_factory: Any = None) -> None:
            self.default = default
            self.default_factory = default_factory

        def value(self) -> Any:
            if self.default_factory is not None:
                return self.default_factory()
            return self.default

    def Field(default: Any = None, default_factory: Any = None, **_: Any) -> Any:
        return _FieldSpec(default=default, default_factory=default_factory)

    def ConfigDict(**kwargs: Any) -> dict[str, Any]:
        return kwargs

    class BaseModel:
        """Minimal subset of Pydantic's API used by the offline MVP."""

        model_config: dict[str, Any] = {}

        def __init__(self, **data: Any) -> None:
            annotations: dict[str, Any] = {}
            for cls in reversed(self.__class__.mro()):
                annotations.update(getattr(cls, "__annotations__", {}))
            for name, annotation in annotations.items():
                if name == "model_config":
                    continue
                if name in data:
                    value = data.pop(name)
                else:
                    value = getattr(self.__class__, name, None)
                    if isinstance(value, _FieldSpec):
                        value = value.value()
                setattr(self, name, self._coerce(annotation, value))
            for name, value in data.items():
                setattr(self, name, value)

        @classmethod
        def model_validate(cls, value: Any) -> BaseModel:
            if isinstance(value, cls):
                return value
            return cls(**value)

        @classmethod
        def model_json_schema(cls) -> dict[str, Any]:
            annotations = getattr(cls, "__annotations__", {})
            return {
                "$schema": "https://json-schema.org/draft/2020-12/schema",
                "title": cls.__name__,
                "type": "object",
                "properties": {name: {"type": "string"} for name in annotations if name != "model_config"},
            }

        def model_dump(self, **_: Any) -> dict[str, Any]:
            annotations = getattr(self.__class__, "__annotations__", {})
            return {
                name: self._dump_value(getattr(self, name))
                for name in annotations
                if name != "model_config"
            }

        def model_dump_json(self, **kwargs: Any) -> str:
            return json.dumps(self.model_dump(), **kwargs)

        def _coerce(self, annotation: Any, value: Any) -> Any:
            origin = get_origin(annotation)
            args = get_args(annotation)
            if value is None:
                return value
            if origin is list and args:
                return [self._coerce(args[0], item) for item in value]
            if isinstance(annotation, type) and issubclass(annotation, Enum):
                if isinstance(value, annotation):
                    return value
                try:
                    return annotation(value)
                except ValueError:
                    return value
            return value

        def _dump_value(self, value: Any) -> Any:
            if isinstance(value, Enum):
                return value.value
            if isinstance(value, BaseModel):
                return value.model_dump()
            if isinstance(value, list):
                return [self._dump_value(item) for item in value]
            if isinstance(value, dict):
                return {key: self._dump_value(item) for key, item in value.items()}
            return value

