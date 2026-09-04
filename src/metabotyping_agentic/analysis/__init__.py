"""Deterministic, offline statistical analysis for metabolomics matrices.

This package computes ordination, supervised discrimination, per-feature
screening, biomarker performance, set enrichment, and effect-size synthesis.

The package REFUSES to: open a network connection (every input is a reviewed
local file); import numpy, scipy, scikit-learn, pandas, or matplotlib outside
``ml_extras`` (the byte-reproducible offline pilot consumes this package, and
LAPACK results are not byte-stable across BLAS builds); infer a declaration the
caller did not make; impute a missing value; or convert an unsupported claim
into a supported one by relabelling it.
"""

from __future__ import annotations


class AnalysisValidationError(ValueError):
    """Raised when an analysis input or request is scientifically unsafe.

    Every raise carries the remediation the caller must apply, so a refusal is
    actionable rather than merely a rejection.
    """


__all__ = ["AnalysisValidationError"]
