"""Reproducibility primitives shared by every analysis module.

Three concerns live here because each of them, left to a caller's discretion,
silently breaks byte reproducibility:

* **Publication rounding.** Linear algebra built from ``+ - * /`` and
  ``math.sqrt`` is already bit-identical across platforms, but p-values route
  through ``math.exp``, ``math.log``, and ``math.lgamma``, and libm disagrees
  across architectures. ``scripts/run_metabolite_effect_search.py`` records
  x86_64 and arm64 differing at the 13th significant digit. Rounding every
  published float to ten decimal digits leaves three digits of margin, so that
  class of drift cannot reach a committed artifact.
* **Pseudorandomness.** Permutation tests need a shuffled label vector.
  ``random.Random`` is not usable: the Mersenne Twister stream and
  ``random.shuffle``'s internals are CPython implementation details, not a
  stability contract. The generator here is fully specified integer arithmetic.
* **Cost ceilings.** This package is byte-reproducible pure Python, not a
  compute engine. Every expensive entry point estimates its work first and
  refuses with an ordered remediation, so a request that would take an hour
  fails in milliseconds instead of hanging a pilot run or a CI job.

The module REFUSES to: publish a non-finite float; emit ``-0.0`` (which
``repr``s differently from ``0.0`` and would change a committed CSV); draw from
a generator it does not fully specify; or let a caller past a cost cap.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from . import AnalysisValidationError


class DeterminismError(AnalysisValidationError):
    """Raised when a value or a request would break byte reproducibility."""


# --------------------------------------------------------------------------
# Publication rounding
# --------------------------------------------------------------------------

PUBLISHED_DECIMAL_DIGITS = 10
ROUNDING_RULE = "round_half_even_to_10_decimal_digits_then_normalize_negative_zero"
PRECISION_POLICY = "rounded_10_decimal_digits"
EXACT_PRECISION_POLICY = "exact_integer_hypergeometric_unrounded"


def published(value: float | None) -> float | None:
    """Round a float destined for a committed artifact.

    Mirrors ``evaluation.medication_classifier._rounded`` in intent: one
    chokepoint, so no caller can emit an unrounded float by forgetting to.
    """
    if value is None:
        return None
    numeric = float(value)
    if not math.isfinite(numeric):
        raise DeterminismError(
            f"a non-finite value ({numeric!r}) cannot be published. Remediation: "
            "emit None together with a labelled reason field (for example "
            "auc_se_undefined_reason) rather than a placeholder number."
        )
    rounded = round(numeric, PUBLISHED_DECIMAL_DIGITS)
    # round() preserves the sign of zero, and repr(-0.0) != repr(0.0), so an
    # unnormalized negative zero would change bytes for a value of zero.
    return 0.0 if rounded == 0 else rounded


def published_row(row: dict[str, object]) -> dict[str, object]:
    """Return ``row`` with every float value passed through :func:`published`."""
    result: dict[str, object] = {}
    for key, value in row.items():
        if isinstance(value, bool) or not isinstance(value, float):
            result[key] = value
        else:
            result[key] = published(value)
    return result


# --------------------------------------------------------------------------
# Fully specified pseudorandom generator
# --------------------------------------------------------------------------

# Knuth's MMIX constants for a 64-bit linear congruential generator.
LCG_MULTIPLIER = 6364136223846793005
LCG_INCREMENT = 1442695040888963407
LCG_MODULUS = 1 << 64
# The low bits of an LCG have short periods, so only the high bits are used.
LCG_OUTPUT_SHIFT = 33
LCG_OUTPUT_BITS = 64 - LCG_OUTPUT_SHIFT
LCG_OUTPUT_BOUND = 1 << LCG_OUTPUT_BITS
# An odd golden-ratio constant, so nearby seeds do not produce nearby states.
LCG_SEED_MIX = 0x9E3779B97F4A7C15
LCG_WARMUP_DRAWS = 4
LCG_ALGORITHM = "knuth_mmix_64_bit_lcg_high_31_bits_rejection_sampled"


@dataclass
class LinearCongruentialGenerator:
    """A fully specified 64-bit LCG.

    Pure integer arithmetic, so the stream is identical on every interpreter
    and architecture. ``random.Random`` is deliberately not used: its stream is
    an implementation detail, and a permutation p-value that silently changed
    with the interpreter would be undetectable in review.
    """

    seed: int

    def __post_init__(self) -> None:
        if not isinstance(self.seed, int) or isinstance(self.seed, bool):
            raise DeterminismError(
                f"the generator seed must be an int, got {self.seed!r}. Remediation: "
                "declare an integer seed in the analysis specification so it is "
                "recorded in provenance."
            )
        self._state = (self.seed ^ LCG_SEED_MIX) % LCG_MODULUS
        self._draws = 0
        for _ in range(LCG_WARMUP_DRAWS):
            self.next_raw()

    def next_raw(self) -> int:
        """Return the next raw draw in ``[0, 2**31)``."""
        self._state = (LCG_MULTIPLIER * self._state + LCG_INCREMENT) % LCG_MODULUS
        self._draws += 1
        return self._state >> LCG_OUTPUT_SHIFT

    @property
    def draws_consumed(self) -> int:
        """Return how many raw draws have been taken, warm-up included."""
        return self._draws

    def below(self, bound: int) -> int:
        """Return a draw in ``[0, bound)`` without modulo bias.

        Rejection sampling, so the number of raw draws consumed depends on the
        stream rather than being constant -- which is still fully reproducible,
        because the stream is.
        """
        if bound <= 0:
            raise DeterminismError(
                f"below() needs a positive bound, got {bound!r}."
            )
        if bound > LCG_OUTPUT_BOUND:
            raise DeterminismError(
                f"below() cannot draw from a bound above {LCG_OUTPUT_BOUND} "
                f"(got {bound!r}) without widening the generator output."
            )
        limit = (LCG_OUTPUT_BOUND // bound) * bound
        while True:
            raw = self.next_raw()
            if raw < limit:
                return raw % bound

    def permutation(self, count: int) -> list[int]:
        """Return a permutation of ``range(count)`` by downward Fisher-Yates."""
        if count < 0:
            raise DeterminismError(
                f"permutation() needs a non-negative count, got {count!r}."
            )
        order = list(range(count))
        for index in range(count - 1, 0, -1):
            swap = self.below(index + 1)
            order[index], order[swap] = order[swap], order[index]
        return order


# --------------------------------------------------------------------------
# Cost ceilings
# --------------------------------------------------------------------------

# Jacobi on the n x n Gram matrix dominates ordination and scales as n cubed.
MAX_SAMPLES_EIGEN = 300
MAX_FEATURES_TIER_A = 20_000
# A p x p covariance eigendecomposition is only viable when p is small; at
# p = 5000 the matrix alone is roughly 1.6 GB of Python floats.
MAX_FEATURES_COVARIANCE_ROUTE = 400
# Naive Lance-Williams linkage is O(n cubed) tuple comparisons.
MAX_SAMPLES_CLUSTERING = 250
MAX_PLS_COMPONENTS = 10
MAX_PERMUTATIONS = 999
MAX_PERMUTATION_WORK_UNITS = 3_000_000_000

# Measured on this repository's development machine at roughly 33 million
# math.fsum multiply-accumulates per second, then held deliberately
# conservative so an estimate errs toward refusing rather than toward hanging.
ESTIMATED_MACS_PER_SECOND = 5_000_000

# The pure-Python envelope within which permutation-validated discriminant
# analysis completes in seconds rather than tens of minutes. Stated here so a
# caller reads it from a constant instead of discovering it by waiting.
TIER_A_DISCRIMINANT_ENVELOPE = {
    "max_samples": 60,
    "max_features": 500,
    "max_permutations": 199,
}


@dataclass(frozen=True)
class CostEstimate:
    """The projected cost of a request, and whether it is permitted."""

    operation_estimate: int
    estimated_seconds: float
    cap_name: str
    cap_value: int
    within_cap: bool

    def as_row(self) -> dict[str, object]:
        return {
            "operation_estimate": self.operation_estimate,
            "estimated_seconds": published(self.estimated_seconds),
            "cap_name": self.cap_name,
            "cap_value": self.cap_value,
            "within_cap": self.within_cap,
        }


def estimate_cost(
    *, operation_estimate: int, cap_name: str, cap_value: int
) -> CostEstimate:
    """Project the cost of a request against a named cap."""
    if operation_estimate < 0:
        raise DeterminismError(
            f"operation_estimate cannot be negative, got {operation_estimate!r}."
        )
    return CostEstimate(
        operation_estimate=operation_estimate,
        estimated_seconds=operation_estimate / ESTIMATED_MACS_PER_SECOND,
        cap_name=cap_name,
        cap_value=cap_value,
        within_cap=operation_estimate <= cap_value,
    )


def format_cost_refusal(estimate: CostEstimate, *, remediation: str) -> str:
    """Render the standard cost refusal message.

    Every cost refusal reads the same way and always ends in an ordered
    remediation, so a caller who hits one knows what to change.
    """
    minutes = estimate.estimated_seconds / 60.0
    return (
        f"this request needs an estimated {estimate.operation_estimate:.3g} "
        f"multiply-accumulate operations (about {minutes:.1f} minutes of pure-Python "
        f"arithmetic), which exceeds {estimate.cap_name} = "
        f"{estimate.cap_value:.3g}. This module is byte-reproducible pure Python, "
        f"not a compute engine. Remediation, in order of preference: {remediation}"
    )


__all__ = [
    "EXACT_PRECISION_POLICY",
    "ESTIMATED_MACS_PER_SECOND",
    "LCG_ALGORITHM",
    "MAX_FEATURES_COVARIANCE_ROUTE",
    "MAX_FEATURES_TIER_A",
    "MAX_PERMUTATIONS",
    "MAX_PERMUTATION_WORK_UNITS",
    "MAX_PLS_COMPONENTS",
    "MAX_SAMPLES_CLUSTERING",
    "MAX_SAMPLES_EIGEN",
    "PRECISION_POLICY",
    "PUBLISHED_DECIMAL_DIGITS",
    "ROUNDING_RULE",
    "TIER_A_DISCRIMINANT_ENVELOPE",
    "CostEstimate",
    "DeterminismError",
    "LinearCongruentialGenerator",
    "estimate_cost",
    "format_cost_refusal",
    "published",
    "published_row",
]
