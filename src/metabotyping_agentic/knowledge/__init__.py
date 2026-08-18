"""Deterministic source routing for multi-database metabolomics research."""

from .source_registry import (
    SOURCE_REGISTRY,
    build_retrieval_plan,
    infer_identifier_namespace,
    validate_registry,
)

__all__ = [
    "SOURCE_REGISTRY",
    "build_retrieval_plan",
    "infer_identifier_namespace",
    "validate_registry",
]
