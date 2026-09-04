"""Bit-reproducible dense linear algebra for metabolomics-shaped matrices.

Every routine here uses only ``+ - * /`` and ``math.sqrt``. IEEE-754 requires
all five to be correctly rounded, so a fixed operation order gives a
bit-identical result on every interpreter and architecture. That is why the
eigensolver is cyclic Jacobi rather than the cheaper Householder
tridiagonalization with implicit-shift QL:

* Jacobi needs no ``hypot`` (not required to be correctly rounded, and
  CPython's accuracy has changed across releases) and no branch on the sign of
  two nearly equal quantities, so inputs differing in the last bit cannot take
  different code paths.
* ``off(A)`` decreases monotonically under every rotation, so "no progress this
  sweep" is a sound epsilon-free stopping rule and the solver can publish a
  convergence artifact rather than a tuning constant.
* Jacobi computes the *small* eigenvalues of a positive semi-definite matrix to
  high relative accuracy (Demmel and Veselic, 1992). QL does not. Scree tails
  and cross-validated variance fractions read exactly those small eigenvalues.

The cost premium over QL is affordable only because the p >> n case is routed
through the n x n Gram matrix. See :func:`gram_matrix`.

The module REFUSES to: treat an asymmetric matrix as symmetric (the check is an
exact ``!=``, not a tolerance, because :func:`gram_matrix` and
:func:`covariance_matrix` mirror their upper triangle by assignment); use
``builtin sum`` on floats; return eigenvectors whose signs depend on input row
or column order; report a component drawn from a degenerate eigenvalue subspace
as interpretable; or compute a variance as ``E[x^2] - E[x]^2``.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

from . import AnalysisValidationError


class LinearAlgebraError(AnalysisValidationError):
    """Raised when a matrix or a decomposition request is unusable."""


JACOBI_MAX_SWEEPS = 60
# Rutishauser's threshold phase: during early sweeps, skip rotations that are
# small relative to the remaining off-diagonal mass.
JACOBI_THRESHOLD_SWEEPS = 3
JACOBI_THRESHOLD_FACTOR = 0.2
JACOBI_OFF_TOLERANCE_SCALE = 2.0**-52
# Two eigenvalues closer than this share a subspace whose rotation is
# arbitrary; any convention invented for them would be fiction.
DEGENERACY_TOLERANCE_SCALE = 2.0**-26
# A positive semi-definite matrix can yield a slightly negative eigenvalue from
# round-off. Clamp within this band, raise beyond it.
NEGATIVE_EIGENVALUE_CLAMP_SCALE = 2.0**-40

JACOBI_ALGORITHM = "cyclic_jacobi_two_sided_rotation"
SIGN_CONVENTION = (
    "the loading with the largest absolute value is positive; magnitude ties are "
    "broken by the lexicographically smallest casefolded feature identifier"
)
IDENTIFIABILITY_UNIQUE = "unique"
IDENTIFIABILITY_DEGENERATE = "degenerate_subspace_rotation_arbitrary"

ROUTE_GRAM = "gram_n_by_n"
ROUTE_COVARIANCE = "covariance_p_by_p"


# --------------------------------------------------------------------------
# Primitives
# --------------------------------------------------------------------------


def _require_rectangular(matrix: Sequence[Sequence[float]], *, name: str) -> tuple[int, int]:
    if not matrix:
        raise LinearAlgebraError(
            f"{name} is empty. Remediation: intake must refuse an empty matrix before "
            "any analysis is requested."
        )
    width = len(matrix[0])
    if width == 0:
        raise LinearAlgebraError(f"{name} has zero columns.")
    for index, row in enumerate(matrix):
        if len(row) != width:
            raise LinearAlgebraError(
                f"{name} is ragged: row {index} has {len(row)} cells but row 0 has "
                f"{width}. Remediation: matrix_intake rejects ragged input; this "
                "matrix did not come through it."
            )
    return len(matrix), width


def transpose(matrix: Sequence[Sequence[float]]) -> list[list[float]]:
    """Return the transpose of ``matrix``."""
    _require_rectangular(matrix, name="matrix")
    return [list(column) for column in zip(*matrix)]


def dot(left: Sequence[float], right: Sequence[float]) -> float:
    """Return the inner product of two vectors."""
    if len(left) != len(right):
        raise LinearAlgebraError(
            f"dot() needs equal lengths, got {len(left)} and {len(right)}."
        )
    return math.fsum(a * b for a, b in zip(left, right))


def matvec(matrix: Sequence[Sequence[float]], vector: Sequence[float]) -> list[float]:
    """Return ``matrix @ vector``."""
    _, width = _require_rectangular(matrix, name="matrix")
    if width != len(vector):
        raise LinearAlgebraError(
            f"matvec() shape mismatch: matrix has {width} columns, vector has "
            f"{len(vector)} entries."
        )
    return [math.fsum(a * b for a, b in zip(row, vector)) for row in matrix]


def matmul(
    left: Sequence[Sequence[float]], right: Sequence[Sequence[float]]
) -> list[list[float]]:
    """Return ``left @ right``."""
    _, left_width = _require_rectangular(left, name="left")
    right_height, _ = _require_rectangular(right, name="right")
    if left_width != right_height:
        raise LinearAlgebraError(
            f"matmul() shape mismatch: left has {left_width} columns, right has "
            f"{right_height} rows."
        )
    right_columns = transpose(right)
    return [
        [math.fsum(a * b for a, b in zip(row, column)) for column in right_columns]
        for row in left
    ]


def column_means(matrix: Sequence[Sequence[float]]) -> list[float]:
    """Return the mean of each column."""
    height, width = _require_rectangular(matrix, name="matrix")
    return [
        math.fsum(matrix[row][column] for row in range(height)) / height
        for column in range(width)
    ]


def column_sds(
    matrix: Sequence[Sequence[float]], *, ddof: int = 1
) -> list[float]:
    """Return the standard deviation of each column, computed in two passes.

    Strictly two-pass. ``E[x^2] - E[x]^2`` suffers catastrophic cancellation on
    LC-MS intensities, where the mean dwarfs the spread.
    """
    height, width = _require_rectangular(matrix, name="matrix")
    if height - ddof <= 0:
        raise LinearAlgebraError(
            f"column_sds() needs more than {ddof} rows to use ddof={ddof}, got "
            f"{height}. Remediation: a standard deviation is not defined here; "
            "report the feature as not testable."
        )
    means = column_means(matrix)
    result: list[float] = []
    for column in range(width):
        mean = means[column]
        variance = math.fsum(
            (matrix[row][column] - mean) ** 2 for row in range(height)
        ) / (height - ddof)
        result.append(math.sqrt(variance) if variance > 0.0 else 0.0)
    return result


def center(
    matrix: Sequence[Sequence[float]], *, means: Sequence[float] | None = None
) -> list[list[float]]:
    """Return ``matrix`` with each column's mean subtracted."""
    _, width = _require_rectangular(matrix, name="matrix")
    offsets = list(means) if means is not None else column_means(matrix)
    if len(offsets) != width:
        raise LinearAlgebraError(
            f"center() needs one mean per column, got {len(offsets)} for {width} columns."
        )
    return [[value - offsets[index] for index, value in enumerate(row)] for row in matrix]


def scale(
    matrix: Sequence[Sequence[float]], *, divisors: Sequence[float]
) -> list[list[float]]:
    """Return ``matrix`` with each column divided by its divisor."""
    _, width = _require_rectangular(matrix, name="matrix")
    if len(divisors) != width:
        raise LinearAlgebraError(
            f"scale() needs one divisor per column, got {len(divisors)} for {width} columns."
        )
    for index, divisor in enumerate(divisors):
        if divisor == 0.0:
            raise LinearAlgebraError(
                f"column {index} has a zero divisor. Remediation: run "
                "preprocessing.drop_zero_variance_features first; a constant feature "
                "cannot be scaled and must be dropped with a recorded reason."
            )
    return [
        [value / divisors[index] for index, value in enumerate(row)] for row in matrix
    ]


def frobenius_norm(matrix: Sequence[Sequence[float]]) -> float:
    """Return the Frobenius norm of ``matrix``."""
    _require_rectangular(matrix, name="matrix")
    return math.sqrt(math.fsum(value * value for row in matrix for value in row))


def total_variance(centered: Sequence[Sequence[float]], *, ddof: int = 1) -> float:
    """Return the total variance of a centered matrix.

    Computed independently of any decomposition, so it can cross-check the
    eigenvalue trace.
    """
    height, _ = _require_rectangular(centered, name="centered")
    if height - ddof <= 0:
        raise LinearAlgebraError(
            f"total_variance() needs more than {ddof} rows, got {height}."
        )
    return math.fsum(value * value for row in centered for value in row) / (height - ddof)


def _symmetric_from_upper(size: int, upper: dict[tuple[int, int], float]) -> list[list[float]]:
    """Build a matrix from its upper triangle, mirroring by assignment.

    Mirroring rather than recomputing is what makes the result symmetric
    *bitwise*, which in turn lets :func:`symmetric_eigen` check symmetry with an
    exact comparison instead of an epsilon.
    """
    result = [[0.0] * size for _ in range(size)]
    for (row, column), value in upper.items():
        result[row][column] = value
        result[column][row] = value
    return result


def gram_matrix(
    centered: Sequence[Sequence[float]], *, ddof: int = 1
) -> list[list[float]]:
    """Return the n x n Gram matrix ``Xc @ Xc.T / (n - ddof)``.

    This is the route that makes PCA possible at metabolomics feature counts.
    A p x p covariance matrix at p = 5000 is roughly 25 million Python floats
    (about 1.6 GB) and its Jacobi decomposition takes on the order of a day.
    The nonzero spectra of ``Xc.T @ Xc`` and ``Xc @ Xc.T`` are identical, so the
    n x n form yields the same eigenvalues and the loadings are recovered as
    ``Xc.T @ u / sqrt((n - ddof) * theta)``.
    """
    height, _ = _require_rectangular(centered, name="centered")
    if height - ddof <= 0:
        raise LinearAlgebraError(
            f"gram_matrix() needs more than {ddof} rows, got {height}."
        )
    denominator = height - ddof
    upper: dict[tuple[int, int], float] = {}
    for row in range(height):
        left = centered[row]
        for column in range(row, height):
            upper[(row, column)] = (
                math.fsum(a * b for a, b in zip(left, centered[column])) / denominator
            )
    return _symmetric_from_upper(height, upper)


def covariance_matrix(
    centered: Sequence[Sequence[float]], *, ddof: int = 1
) -> list[list[float]]:
    """Return the p x p covariance matrix ``Xc.T @ Xc / (n - ddof)``."""
    height, width = _require_rectangular(centered, name="centered")
    if height - ddof <= 0:
        raise LinearAlgebraError(
            f"covariance_matrix() needs more than {ddof} rows, got {height}."
        )
    denominator = height - ddof
    columns = transpose(centered)
    upper: dict[tuple[int, int], float] = {}
    for row in range(width):
        left = columns[row]
        for column in range(row, width):
            upper[(row, column)] = (
                math.fsum(a * b for a, b in zip(left, columns[column])) / denominator
            )
    return _symmetric_from_upper(width, upper)


# --------------------------------------------------------------------------
# Symmetric eigendecomposition
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class EigenDecomposition:
    """The result of a cyclic Jacobi decomposition, with its own audit trail."""

    eigenvalues: tuple[float, ...]
    eigenvectors: tuple[tuple[float, ...], ...]
    sweeps_used: int
    rotations_applied: int
    off_diagonal_norm: float
    input_frobenius_norm: float
    converged: bool
    clamped_negative_eigenvalue_count: int
    identifiability: tuple[str, ...]
    algorithm: str = JACOBI_ALGORITHM

    def __post_init__(self) -> None:
        if len(self.eigenvalues) != len(self.eigenvectors):
            raise LinearAlgebraError(
                "EigenDecomposition needs one eigenvector per eigenvalue, got "
                f"{len(self.eigenvalues)} values and {len(self.eigenvectors)} vectors."
            )
        if len(self.identifiability) != len(self.eigenvalues):
            raise LinearAlgebraError(
                "EigenDecomposition needs one identifiability status per eigenvalue."
            )

    @property
    def rank_positive(self) -> int:
        """Return how many eigenvalues are strictly positive."""
        return sum(1 for value in self.eigenvalues if value > 0.0)


def _off_diagonal_absolute_sum(matrix: list[list[float]], size: int) -> float:
    """Return the sum of absolute values of the strict upper off-diagonal part.

    The threshold phase compares this against an individual ``|a_pq|``, so it
    must be a magnitude. Deriving the threshold from a norm (or worse, a norm
    squared) makes it so large that every rotation is skipped, and the sweep
    then reports convergence having done nothing.
    """
    return math.fsum(
        abs(matrix[row][column])
        for row in range(size - 1)
        for column in range(row + 1, size)
    )


def _off_diagonal_norm(matrix: list[list[float]], size: int) -> float:
    """Return the Frobenius norm of the strict upper off-diagonal part.

    A norm, not a sum of squares: the convergence test compares it against
    ``eps * ||A||_F``, and mixing the two units would stop the sweep while the
    largest off-diagonal was still around ``sqrt(eps)`` -- visible as a
    reconstruction error near 1e-10 rather than 1e-15.
    """
    return math.sqrt(
        math.fsum(
            matrix[row][column] * matrix[row][column]
            for row in range(size - 1)
            for column in range(row + 1, size)
        )
    )


def symmetric_eigen(
    matrix: Sequence[Sequence[float]], *, max_sweeps: int = JACOBI_MAX_SWEEPS
) -> EigenDecomposition:
    """Return the eigendecomposition of a symmetric matrix by cyclic Jacobi.

    Eigenvalues descend. Eigenvector signs are *not* canonicalized here: the
    sign rule has to be applied in feature space by the caller, because
    permuting sample rows permutes the components of a score eigenvector while
    leaving a loading vector's indices untouched. See :func:`canonicalize_sign`.
    """
    size, width = _require_rectangular(matrix, name="matrix")
    if size != width:
        raise LinearAlgebraError(
            f"symmetric_eigen() needs a square matrix, got {size} by {width}."
        )
    for row in range(size):
        for column in range(row + 1, size):
            if matrix[row][column] != matrix[column][row]:
                raise LinearAlgebraError(
                    f"the matrix is not exactly symmetric at ({row}, {column}): "
                    f"{matrix[row][column]!r} against {matrix[column][row]!r}. "
                    "Remediation: build it with gram_matrix() or covariance_matrix(), "
                    "which mirror the upper triangle by assignment so symmetry is "
                    "bitwise rather than approximate."
                )

    working = [list(row) for row in matrix]
    vectors = [[1.0 if row == column else 0.0 for column in range(size)] for row in range(size)]
    input_norm = frobenius_norm(matrix)

    rotations = 0
    sweeps = 0
    converged = False
    off = _off_diagonal_norm(working, size)
    tolerance = JACOBI_OFF_TOLERANCE_SCALE * input_norm

    if size == 1 or off == 0.0:
        converged = True

    while not converged and sweeps < max_sweeps:
        sweep_start_off = off
        in_threshold_phase = sweeps < JACOBI_THRESHOLD_SWEEPS
        threshold = (
            JACOBI_THRESHOLD_FACTOR
            * _off_diagonal_absolute_sum(working, size)
            / (size * size)
            if in_threshold_phase
            else 0.0
        )
        # Strictly increasing row-major traversal of the upper triangle. No
        # magnitude pivoting: an argmax over off-diagonals would have to resolve
        # equal magnitudes by scan order, which is a tie whose resolution
        # depends on storage layout. Cyclic order has no tie to break.
        for p in range(size - 1):
            for q in range(p + 1, size):
                apq = working[p][q]
                if apq == 0.0:
                    continue
                magnitude = abs(apq)
                if in_threshold_phase and magnitude < threshold:
                    continue
                if not in_threshold_phase and magnitude <= JACOBI_OFF_TOLERANCE_SCALE * (
                    abs(working[p][p]) + abs(working[q][q])
                ):
                    working[p][q] = 0.0
                    working[q][p] = 0.0
                    continue

                theta = (working[q][q] - working[p][p]) / (2.0 * apq)
                sign = 1.0 if theta >= 0.0 else -1.0
                t = sign / (abs(theta) + math.sqrt(theta * theta + 1.0))
                c = 1.0 / math.sqrt(t * t + 1.0)
                s = t * c
                tau = s / (1.0 + c)

                working[p][p] -= t * apq
                working[q][q] += t * apq
                # Set exactly zero rather than computing a near-zero value.
                working[p][q] = 0.0
                working[q][p] = 0.0

                for k in range(size):
                    if k == p or k == q:
                        continue
                    akp = working[k][p]
                    akq = working[k][q]
                    new_kp = akp - s * (akq + tau * akp)
                    new_kq = akq + s * (akp - tau * akq)
                    working[k][p] = new_kp
                    working[p][k] = new_kp
                    working[k][q] = new_kq
                    working[q][k] = new_kq

                for k in range(size):
                    vkp = vectors[k][p]
                    vkq = vectors[k][q]
                    vectors[k][p] = vkp - s * (vkq + tau * vkp)
                    vectors[k][q] = vkq + s * (vkp - tau * vkq)

                rotations += 1

        sweeps += 1
        off = _off_diagonal_norm(working, size)
        if off == 0.0:
            converged = True
        elif in_threshold_phase:
            # The threshold phase skips small rotations deliberately, so "no
            # progress" carries no information yet; keep sweeping.
            converged = False
        elif off >= sweep_start_off:
            # Jacobi is monotone: every rotation strictly reduces off(A). No
            # progress therefore means the floating-point floor, which is a
            # sound stopping rule that needs no epsilon.
            converged = True
        elif off <= tolerance:
            converged = True

    if not converged:
        raise LinearAlgebraError(
            f"cyclic Jacobi did not converge in {max_sweeps} sweeps (off-diagonal "
            f"norm {off:.3e} against Frobenius norm {input_norm:.3e}). "
            "Remediation: this normally means the matrix was not built by "
            "gram_matrix()/covariance_matrix() and is not exactly symmetric, or the "
            "columns span many orders of magnitude; declare an autoscale or "
            "pareto_scale step in the preprocessing ledger and re-run."
        )

    raw = [(working[index][index], [vectors[row][index] for row in range(size)])
           for index in range(size)]
    # Stable descending sort. Exact ties keep Jacobi's emission order, but ties
    # are reported as degenerate below rather than relied upon.
    raw.sort(key=lambda item: -item[0])

    largest = raw[0][0] if raw else 0.0
    clamp_floor = -NEGATIVE_EIGENVALUE_CLAMP_SCALE * abs(largest)
    clamped = 0
    eigenvalues: list[float] = []
    for value, _ in raw:
        if value < 0.0:
            if value >= clamp_floor:
                eigenvalues.append(0.0)
                clamped += 1
                continue
            raise LinearAlgebraError(
                f"eigenvalue {value!r} is negative beyond round-off (clamp floor "
                f"{clamp_floor!r}), so the input is not positive semi-definite. "
                "Remediation: a covariance or Gram matrix cannot have a materially "
                "negative eigenvalue; this matrix was not produced by "
                "gram_matrix() or covariance_matrix()."
            )
        eigenvalues.append(value)

    degeneracy_tolerance = DEGENERACY_TOLERANCE_SCALE * abs(largest)
    identifiability = [IDENTIFIABILITY_UNIQUE] * size
    for index in range(size - 1):
        if abs(eigenvalues[index] - eigenvalues[index + 1]) <= degeneracy_tolerance:
            identifiability[index] = IDENTIFIABILITY_DEGENERATE
            identifiability[index + 1] = IDENTIFIABILITY_DEGENERATE

    return EigenDecomposition(
        eigenvalues=tuple(eigenvalues),
        eigenvectors=tuple(tuple(vector) for _, vector in raw),
        sweeps_used=sweeps,
        rotations_applied=rotations,
        off_diagonal_norm=off,
        input_frobenius_norm=input_norm,
        converged=converged,
        clamped_negative_eigenvalue_count=clamped,
        identifiability=tuple(identifiability),
    )


def canonicalize_sign(
    vector: Sequence[float], *, labels: Sequence[str]
) -> tuple[list[float], int, str]:
    """Return ``vector`` with a reproducible sign, plus the pivot and the rule.

    The pivot is the largest-magnitude component, with magnitude ties broken by
    the lexicographically smallest casefolded label. Keying the tie-break on a
    *label* rather than an index is what makes the choice invariant to column
    order, and applying the rule to a loading vector rather than a score vector
    is what makes it invariant to row order.
    """
    if len(vector) != len(labels):
        raise LinearAlgebraError(
            f"canonicalize_sign() needs one label per component, got {len(labels)} "
            f"labels for {len(vector)} components."
        )
    if not vector:
        raise LinearAlgebraError("canonicalize_sign() needs a non-empty vector.")

    pivot = min(
        range(len(vector)),
        key=lambda index: (-abs(vector[index]), labels[index].casefold(), index),
    )
    if abs(vector[pivot]) == 0.0:
        raise LinearAlgebraError(
            "every component of this vector is zero, so it is not a unit eigenvector. "
            "Remediation: the requested component lies outside the identifiable rank; "
            "reduce the component count to the reported max_identifiable_components."
        )
    if vector[pivot] < 0.0:
        return [-value for value in vector], pivot, SIGN_CONVENTION
    return list(vector), pivot, SIGN_CONVENTION


__all__ = [
    "DEGENERACY_TOLERANCE_SCALE",
    "IDENTIFIABILITY_DEGENERATE",
    "IDENTIFIABILITY_UNIQUE",
    "JACOBI_ALGORITHM",
    "JACOBI_MAX_SWEEPS",
    "ROUTE_COVARIANCE",
    "ROUTE_GRAM",
    "SIGN_CONVENTION",
    "EigenDecomposition",
    "LinearAlgebraError",
    "canonicalize_sign",
    "center",
    "column_means",
    "column_sds",
    "covariance_matrix",
    "dot",
    "frobenius_norm",
    "gram_matrix",
    "matmul",
    "matvec",
    "scale",
    "symmetric_eigen",
    "total_variance",
    "transpose",
]
