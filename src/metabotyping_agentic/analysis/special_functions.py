"""Stdlib-only special functions for the offline analysis package.

This module is the canonical home for the continued-fraction incomplete beta
that backs every t and F tail in the repository. ``live_sources`` re-exports
from here rather than the reverse, so an offline analysis never has to import a
module that opens a socket.

Determinism is structural, not incidental. Every root-find runs a *fixed*
number of bisection steps rather than exiting on a tolerance, so the iteration
count is a versioned constant and the result cannot vary with the input's
distance from the bracket. Sums that reach a published artifact use
``math.fsum``; the builtin ``sum`` is never used on floats because its float
fast path gained Neumaier compensation in CPython 3.12.

The module REFUSES to: exit a root-find early on a data-dependent tolerance;
use ``math.hypot`` or ``math.atan2`` (neither is required to be correctly
rounded, and CPython's ``hypot`` accuracy has changed across releases); or
return a probability outside ``[MIN_PROBABILITY, 1.0]``.
"""

from __future__ import annotations

import math

from . import AnalysisValidationError

# Matches plotting.metabolomics.MIN_PROBABILITY and
# live_sources.motrpac_volcano_compare.MIN_P_VALUE so a p-value floor is one
# number across the repository.
MIN_PROBABILITY = 1e-300

# Continued-fraction controls, carried over verbatim from the implementation
# this module replaced so the extracted arithmetic is byte-identical.
_BETA_MAX_ITERATIONS = 200
_BETA_EPSILON = 3e-14
_BETA_FLOOR = 1e-300

# Lower/upper incomplete gamma controls, in the same style as the beta block.
_GAMMA_MAX_ITERATIONS = 300
_GAMMA_EPSILON = 3e-14
_GAMMA_FLOOR = 1e-300

# A fixed step count, not a tolerance. Bisection halves the bracket each step,
# so 200 steps drives a bracket of width w to w * 2**-200 -- far below double
# precision for every bracket this module constructs. Because the count is
# fixed, the number of transcendental evaluations does not depend on the input,
# and the result is reproducible across interpreters and architectures.
BISECTION_ITERATIONS = 200

# Quantile brackets are grown by doubling from this width, with a hard ceiling
# so a malformed request raises instead of looping.
_QUANTILE_INITIAL_BOUND = 1.0
# Generous, because bisection runs a fixed 200 steps regardless of bracket
# width, so a wide bracket costs nothing. It has to be generous: a t with one
# degree of freedom is Cauchy, whose two-sided tail is about 2/(pi*t), so a
# p-value of 1e-6 already puts the critical value near 6.4e5 and the doubling
# sequence overshoots a 1e6 ceiling before testing it. No finite ceiling covers
# every (p, df) pair down to MIN_PROBABILITY, so this is a practical guard that
# refuses rather than looping.
_QUANTILE_MAX_BOUND = 1e12


def _betacf(a: float, b: float, x: float) -> float:
    max_iter = _BETA_MAX_ITERATIONS
    eps = _BETA_EPSILON
    fpmin = _BETA_FLOOR
    qab = a + b
    qap = a + 1.0
    qam = a - 1.0
    c = 1.0
    d = 1.0 - qab * x / qap
    if abs(d) < fpmin:
        d = fpmin
    d = 1.0 / d
    h = d
    for m in range(1, max_iter + 1):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        if abs(d) < fpmin:
            d = fpmin
        c = 1.0 + aa / c
        if abs(c) < fpmin:
            c = fpmin
        d = 1.0 / d
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        if abs(d) < fpmin:
            d = fpmin
        c = 1.0 + aa / c
        if abs(c) < fpmin:
            c = fpmin
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < eps:
            break
    return h


def regularized_beta(x: float, a: float, b: float) -> float:
    """Return the regularized incomplete beta function I_x(a, b)."""
    if x <= 0:
        return 0.0
    if x >= 1:
        return 1.0
    bt = math.exp(
        math.lgamma(a + b)
        - math.lgamma(a)
        - math.lgamma(b)
        + a * math.log(x)
        + b * math.log1p(-x)
    )
    if x < (a + 1.0) / (a + b + 2.0):
        return bt * _betacf(a, b, x) / a
    return 1.0 - bt * _betacf(b, a, 1.0 - x) / b


def _lower_gamma_series(a: float, x: float) -> float:
    """Return P(a, x) by its ascending series, valid for x < a + 1."""
    ap = a
    total = 1.0 / a
    term = total
    for _ in range(1, _GAMMA_MAX_ITERATIONS + 1):
        ap += 1.0
        term *= x / ap
        total += term
        if abs(term) < abs(total) * _GAMMA_EPSILON:
            break
    return total * math.exp(-x + a * math.log(x) - math.lgamma(a))


def _upper_gamma_continued_fraction(a: float, x: float) -> float:
    """Return Q(a, x) by a modified Lentz continued fraction, valid for x >= a + 1."""
    b = x + 1.0 - a
    c = 1.0 / _GAMMA_FLOOR
    d = 1.0 / b
    h = d
    for i in range(1, _GAMMA_MAX_ITERATIONS + 1):
        an = -i * (i - a)
        b += 2.0
        d = an * d + b
        if abs(d) < _GAMMA_FLOOR:
            d = _GAMMA_FLOOR
        c = b + an / c
        if abs(c) < _GAMMA_FLOOR:
            c = _GAMMA_FLOOR
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < _GAMMA_EPSILON:
            break
    return math.exp(-x + a * math.log(x) - math.lgamma(a)) * h


def regularized_gamma_p(a: float, x: float) -> float:
    """Return the regularized lower incomplete gamma function P(a, x)."""
    if a <= 0.0:
        raise AnalysisValidationError(
            f"regularized_gamma_p needs a positive shape, got a={a!r}. "
            "Remediation: pass degrees of freedom divided by two, which is positive "
            "for every distribution this module supports."
        )
    if x < 0.0:
        raise AnalysisValidationError(
            f"regularized_gamma_p needs a non-negative argument, got x={x!r}. "
            "Remediation: a chi-square statistic cannot be negative; check the caller."
        )
    if x == 0.0:
        return 0.0
    if x < a + 1.0:
        return _lower_gamma_series(a, x)
    return 1.0 - _upper_gamma_continued_fraction(a, x)


def regularized_gamma_q(a: float, x: float) -> float:
    """Return the regularized upper incomplete gamma function Q(a, x) = 1 - P(a, x)."""
    if a <= 0.0:
        raise AnalysisValidationError(
            f"regularized_gamma_q needs a positive shape, got a={a!r}. "
            "Remediation: pass degrees of freedom divided by two."
        )
    if x < 0.0:
        raise AnalysisValidationError(
            f"regularized_gamma_q needs a non-negative argument, got x={x!r}. "
            "Remediation: a chi-square statistic cannot be negative; check the caller."
        )
    if x == 0.0:
        return 1.0
    if x < a + 1.0:
        return 1.0 - _lower_gamma_series(a, x)
    return _upper_gamma_continued_fraction(a, x)


def clamp_probability(value: float) -> float:
    """Clamp a computed tail into [MIN_PROBABILITY, 1.0]."""
    if not math.isfinite(value):
        raise AnalysisValidationError(
            f"a non-finite probability ({value!r}) cannot be published. "
            "Remediation: report the originating statistic as not testable rather "
            "than emitting a placeholder p-value."
        )
    return max(min(value, 1.0), MIN_PROBABILITY)


def student_t_sf(t_statistic: float, degrees_of_freedom: float) -> float:
    """Return the two-sided Student t tail probability."""
    if degrees_of_freedom <= 0.0:
        raise AnalysisValidationError(
            f"student_t_sf needs positive degrees of freedom, got {degrees_of_freedom!r}. "
            "Remediation: a contrast with no residual degrees of freedom is not testable; "
            "emit analysis_status='not_tested_insufficient_n' instead."
        )
    absolute = abs(t_statistic)
    if not math.isfinite(absolute):
        raise AnalysisValidationError(
            f"student_t_sf needs a finite statistic, got {t_statistic!r}. "
            "Remediation: a zero-variance contrast is not testable; refuse it upstream."
        )
    x = degrees_of_freedom / (degrees_of_freedom + absolute * absolute)
    return clamp_probability(regularized_beta(x, degrees_of_freedom / 2.0, 0.5))


def chi_square_sf(statistic: float, degrees_of_freedom: float) -> float:
    """Return the chi-square upper tail probability."""
    if degrees_of_freedom <= 0.0:
        raise AnalysisValidationError(
            f"chi_square_sf needs positive degrees of freedom, got {degrees_of_freedom!r}. "
            "Remediation: Cochran Q with k = 1 has no degrees of freedom; report "
            "heterogeneity as not estimable."
        )
    if statistic <= 0.0:
        return 1.0
    return clamp_probability(regularized_gamma_q(degrees_of_freedom / 2.0, statistic / 2.0))


def f_distribution_sf(
    statistic: float, numerator_df: float, denominator_df: float
) -> float:
    """Return the F upper tail probability.

    Expressed through ``regularized_beta`` rather than a separate F routine, so
    the ANOVA tail and the t tail share one continued fraction and one set of
    determinism guarantees.
    """
    if numerator_df <= 0.0 or denominator_df <= 0.0:
        raise AnalysisValidationError(
            "f_distribution_sf needs positive degrees of freedom, got "
            f"numerator_df={numerator_df!r}, denominator_df={denominator_df!r}. "
            "Remediation: a design with one group or no residual degrees of freedom "
            "is not testable."
        )
    if statistic <= 0.0:
        return 1.0
    x = denominator_df / (denominator_df + numerator_df * statistic)
    return clamp_probability(
        regularized_beta(x, denominator_df / 2.0, numerator_df / 2.0)
    )


def normal_cdf(z_score: float) -> float:
    """Return the standard normal cumulative distribution function."""
    return 0.5 * math.erfc(-z_score / math.sqrt(2.0))


def normal_sf_two_sided(z_score: float) -> float:
    """Return the two-sided standard normal tail probability."""
    return clamp_probability(math.erfc(abs(z_score) / math.sqrt(2.0)))


def _bisect_monotone_decreasing(
    function, target: float, low: float, high: float
) -> float:
    """Bisect a monotone-decreasing function for a fixed number of steps.

    The step count is fixed rather than tolerance-driven so the number of
    transcendental evaluations, and therefore the result, does not depend on the
    input's position within the bracket.
    """
    for _ in range(BISECTION_ITERATIONS):
        middle = 0.5 * (low + high)
        if function(middle) > target:
            low = middle
        else:
            high = middle
    return 0.5 * (low + high)


def student_t_quantile(two_sided_probability: float, degrees_of_freedom: float) -> float:
    """Return the positive t value whose two-sided tail equals the given probability."""
    if not 0.0 < two_sided_probability <= 1.0:
        raise AnalysisValidationError(
            "student_t_quantile needs a two-sided probability in (0, 1], got "
            f"{two_sided_probability!r}. Remediation: clamp the p-value to "
            "MIN_PROBABILITY before inverting it, and record p_value_floor."
        )
    if degrees_of_freedom <= 0.0:
        raise AnalysisValidationError(
            "student_t_quantile needs positive degrees of freedom, got "
            f"{degrees_of_freedom!r}. Remediation: a contrast with no residual "
            "degrees of freedom has no critical value."
        )
    if two_sided_probability == 1.0:
        return 0.0
    high = _QUANTILE_INITIAL_BOUND
    while student_t_sf(high, degrees_of_freedom) > two_sided_probability:
        high *= 2.0
        if high > _QUANTILE_MAX_BOUND:
            raise AnalysisValidationError(
                "student_t_quantile could not bracket a critical value below "
                f"{_QUANTILE_MAX_BOUND:g} for probability {two_sided_probability!r} "
                f"and {degrees_of_freedom!r} degrees of freedom. Remediation: the "
                "p-value is at or below the MIN_PROBABILITY floor, so its interval "
                "is not recoverable; report the standard error as absent rather than "
                "reconstructing one."
            )
    return _bisect_monotone_decreasing(
        lambda value: student_t_sf(value, degrees_of_freedom),
        two_sided_probability,
        0.0,
        high,
    )


def normal_quantile_two_sided(two_sided_probability: float) -> float:
    """Return the positive z value whose two-sided normal tail equals the probability.

    Bisected on ``normal_sf_two_sided`` rather than taken from a rational
    approximation, so this module carries one determinism story and no
    unauditable magic-constant table.
    """
    if not 0.0 < two_sided_probability <= 1.0:
        raise AnalysisValidationError(
            "normal_quantile_two_sided needs a probability in (0, 1], got "
            f"{two_sided_probability!r}. Remediation: clamp to MIN_PROBABILITY first."
        )
    if two_sided_probability == 1.0:
        return 0.0
    high = _QUANTILE_INITIAL_BOUND
    while normal_sf_two_sided(high) > two_sided_probability:
        high *= 2.0
        if high > _QUANTILE_MAX_BOUND:
            raise AnalysisValidationError(
                "normal_quantile_two_sided could not bracket a critical value below "
                f"{_QUANTILE_MAX_BOUND:g}. Remediation: the probability is at the "
                "MIN_PROBABILITY floor; report the interval as not recoverable."
            )
    return _bisect_monotone_decreasing(
        normal_sf_two_sided, two_sided_probability, 0.0, high
    )


def regularized_beta_inverse(probability: float, a: float, b: float) -> float:
    """Return x such that I_x(a, b) equals the given probability.

    Used for the F quantile behind the Hotelling T-squared limit. Bisected on a
    monotone-increasing function, so the bracket is [0, 1] and needs no growth.
    """
    if not 0.0 <= probability <= 1.0:
        raise AnalysisValidationError(
            f"regularized_beta_inverse needs a probability in [0, 1], got {probability!r}."
        )
    if a <= 0.0 or b <= 0.0:
        raise AnalysisValidationError(
            f"regularized_beta_inverse needs positive shapes, got a={a!r}, b={b!r}."
        )
    if probability == 0.0:
        return 0.0
    if probability == 1.0:
        return 1.0
    low = 0.0
    high = 1.0
    for _ in range(BISECTION_ITERATIONS):
        middle = 0.5 * (low + high)
        if regularized_beta(middle, a, b) < probability:
            low = middle
        else:
            high = middle
    return 0.5 * (low + high)


def f_distribution_quantile(
    upper_tail_probability: float, numerator_df: float, denominator_df: float
) -> float:
    """Return the F value whose upper tail equals the given probability."""
    if not 0.0 < upper_tail_probability < 1.0:
        raise AnalysisValidationError(
            "f_distribution_quantile needs a probability in (0, 1), got "
            f"{upper_tail_probability!r}."
        )
    if numerator_df <= 0.0 or denominator_df <= 0.0:
        raise AnalysisValidationError(
            "f_distribution_quantile needs positive degrees of freedom, got "
            f"numerator_df={numerator_df!r}, denominator_df={denominator_df!r}."
        )
    # I_x(d2/2, d1/2) = upper tail, with x = d2 / (d2 + d1 * F).
    x = regularized_beta_inverse(
        upper_tail_probability, denominator_df / 2.0, numerator_df / 2.0
    )
    if x <= 0.0:
        raise AnalysisValidationError(
            "f_distribution_quantile inverted to a degenerate bound for "
            f"probability {upper_tail_probability!r}. Remediation: widen alpha or "
            "report the limit as not estimable."
        )
    return denominator_df * (1.0 - x) / (numerator_df * x)


def mann_whitney_exact_counts(group_a_size: int, group_b_size: int) -> list[int]:
    """Return exact null counts for the Mann-Whitney U statistic.

    ``result[u]`` is the number of the ``comb(n1 + n2, n1)`` equally likely
    orderings whose U statistic equals ``u``. Integer arithmetic throughout, so
    the null distribution is exact and identical on every platform -- the same
    reasoning that made ``fisher_right_tail_p_value`` an integer routine.

    Uses f(m, n, u) = f(m - 1, n, u - n) + f(m, n - 1, u), tabulated
    iteratively rather than recursively so the call depth cannot overflow.
    """
    if group_a_size < 0 or group_b_size < 0:
        raise AnalysisValidationError(
            "mann_whitney_exact_counts needs non-negative group sizes, got "
            f"{group_a_size!r} and {group_b_size!r}."
        )
    table: dict[tuple[int, int], list[int]] = {}
    for m in range(group_a_size + 1):
        for n in range(group_b_size + 1):
            size = m * n
            counts = [0] * (size + 1)
            if m == 0 or n == 0:
                counts[0] = 1
            else:
                left = table[(m - 1, n)]
                below = table[(m, n - 1)]
                for u in range(size + 1):
                    total = 0
                    shifted = u - n
                    if 0 <= shifted < len(left):
                        total += left[shifted]
                    if u < len(below):
                        total += below[u]
                    counts[u] = total
            table[(m, n)] = counts
    return table[(group_a_size, group_b_size)]


__all__ = [
    "BISECTION_ITERATIONS",
    "MIN_PROBABILITY",
    "chi_square_sf",
    "clamp_probability",
    "f_distribution_quantile",
    "f_distribution_sf",
    "mann_whitney_exact_counts",
    "normal_cdf",
    "normal_quantile_two_sided",
    "normal_sf_two_sided",
    "regularized_beta",
    "regularized_beta_inverse",
    "regularized_gamma_p",
    "regularized_gamma_q",
    "student_t_quantile",
    "student_t_sf",
]
