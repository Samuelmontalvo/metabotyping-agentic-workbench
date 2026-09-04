"""Determinism and accuracy gates for the stdlib analysis numerics.

These tests exist to prevent five specific defects, three of which were real
and were caught during implementation:

1. A convergence test that compared the off-diagonal *sum of squares* against a
   bound scaled by the Frobenius *norm*. The units disagree, so the sweep
   stopped while the largest off-diagonal was still near ``sqrt(eps)`` --
   published eigenvalues carried a relative error near 1e-10 instead of 1e-16.
2. A Rutishauser threshold derived from a norm rather than from the sum of
   absolute off-diagonals. The threshold came out so large that every rotation
   was skipped, and on a matrix with decades-apart column scales the solver
   returned the input diagonal after zero rotations.
3. The "no progress this sweep means converged" rule firing *during* the
   threshold phase, which skips rotations by design. Combined with (2) this made
   a completely undecomposed matrix report success.
4. Eigenvector signs that depend on input row or column order, which would make
   a committed loadings CSV change under a harmless re-export of the same cohort.
5. A publication float that keeps ``-0.0``, whose ``repr`` differs from ``0.0``
   and would change committed bytes for a value of zero.
"""

from __future__ import annotations

import math
import random
import unittest

from metabotyping_agentic.analysis import AnalysisValidationError
from metabotyping_agentic.analysis import linalg as la
from metabotyping_agentic.analysis import special_functions as sf
from metabotyping_agentic.analysis.determinism import (
    LCG_OUTPUT_BOUND,
    MAX_PERMUTATION_WORK_UNITS,
    DeterminismError,
    LinearCongruentialGenerator,
    estimate_cost,
    published,
    published_row,
)


def _reconstruction_error(matrix, decomposition):
    size = len(matrix)
    rebuilt = [
        [
            math.fsum(
                decomposition.eigenvalues[j]
                * decomposition.eigenvectors[j][row]
                * decomposition.eigenvectors[j][column]
                for j in range(size)
            )
            for column in range(size)
        ]
        for row in range(size)
    ]
    return max(
        abs(rebuilt[row][column] - matrix[row][column])
        for row in range(size)
        for column in range(size)
    )


def _orthonormality_error(decomposition):
    size = len(decomposition.eigenvectors)
    return max(
        abs(
            math.fsum(
                a * b
                for a, b in zip(
                    decomposition.eigenvectors[i], decomposition.eigenvectors[j]
                )
            )
            - (1.0 if i == j else 0.0)
        )
        for i in range(size)
        for j in range(size)
    )


def _pca_via_gram(matrix, feature_ids, components, *, ddof=1):
    """Gram-route PCA with loading recovery and the canonical sign rule."""
    height = len(matrix)
    width = len(matrix[0])
    centered = la.center(matrix)
    decomposition = la.symmetric_eigen(la.gram_matrix(centered, ddof=ddof))
    columns = la.transpose(centered)
    result = []
    for index in range(components):
        eigenvalue = decomposition.eigenvalues[index]
        vector = decomposition.eigenvectors[index]
        norm = math.sqrt((height - ddof) * eigenvalue)
        raw = [
            math.fsum(a * b for a, b in zip(columns[feature], vector)) / norm
            for feature in range(width)
        ]
        loading, pivot, _ = la.canonicalize_sign(raw, labels=feature_ids)
        flip = -1.0 if raw[pivot] < 0.0 else 1.0
        score = [flip * norm * component for component in vector]
        result.append((eigenvalue, loading, score))
    return result


class SpecialFunctionTests(unittest.TestCase):
    def test_student_t_quantile_matches_published_critical_values(self):
        expected = {
            1: 12.7062047361747,
            2: 4.30265272974946,
            5: 2.57058183563631,
            10: 2.22813885198627,
            30: 2.04227245630124,
        }
        for degrees, critical in expected.items():
            with self.subTest(degrees_of_freedom=degrees):
                self.assertAlmostEqual(
                    sf.student_t_quantile(0.05, degrees), critical, places=10
                )

    def test_student_t_quantile_round_trips_through_its_own_tail(self):
        # Guards against a bracket that grows past the true root, which a table
        # of critical values alone would not reveal at unusual probabilities.
        for degrees in (1, 3, 12, 57, 300, 10_000):
            for probability in (0.5, 0.1, 0.05, 0.01, 1e-6):
                with self.subTest(degrees_of_freedom=degrees, probability=probability):
                    quantile = sf.student_t_quantile(probability, degrees)
                    self.assertAlmostEqual(
                        sf.student_t_sf(quantile, degrees), probability, places=9
                    )

    def test_student_t_quantile_exceeds_the_normal_quantile_at_finite_degrees(self):
        # The t distribution is heavier tailed than the normal, so its critical
        # value must be strictly larger and must approach the normal from above.
        normal = sf.normal_quantile_two_sided(0.05)
        previous = None
        for degrees in (10, 100, 1_000, 100_000, 1_000_000):
            quantile = sf.student_t_quantile(0.05, degrees)
            self.assertGreater(quantile, normal)
            if previous is not None:
                self.assertLess(quantile, previous)
            previous = quantile
        self.assertAlmostEqual(previous, normal, places=5)

    def test_normal_quantile_matches_the_published_two_sided_critical_value(self):
        self.assertAlmostEqual(
            sf.normal_quantile_two_sided(0.05), 1.959963984540054, places=12
        )

    def test_chi_square_tail_matches_published_critical_values(self):
        for statistic, degrees in (
            (3.841458820694124, 1),
            (5.991464547107979, 2),
            (18.307038053275146, 10),
        ):
            with self.subTest(degrees_of_freedom=degrees):
                self.assertAlmostEqual(sf.chi_square_sf(statistic, degrees), 0.05, places=12)

    def test_f_tail_equals_the_squared_t_tail_at_one_numerator_degree(self):
        # F(1, d) is exactly t(d) squared. Two independent expressions of the
        # same continued fraction must agree, which cross-checks both callers.
        for degrees in (2, 5, 12, 40, 120):
            for statistic in (0.4, 1.0, 2.137, 5.5):
                with self.subTest(degrees_of_freedom=degrees, statistic=statistic):
                    self.assertEqual(
                        sf.student_t_sf(statistic, degrees),
                        sf.f_distribution_sf(statistic * statistic, 1, degrees),
                    )

    def test_regularized_gamma_halves_sum_to_one(self):
        for shape in (0.5, 1.0, 2.5, 7.0, 50.0):
            for argument in (0.25, 1.0, 3.0, 9.0, 60.0):
                with self.subTest(shape=shape, argument=argument):
                    self.assertAlmostEqual(
                        sf.regularized_gamma_p(shape, argument)
                        + sf.regularized_gamma_q(shape, argument),
                        1.0,
                        places=13,
                    )

    def test_f_quantile_inverts_the_f_tail(self):
        for probability in (0.1, 0.05, 0.01):
            for numerator, denominator in ((2, 10), (3, 20), (5, 5), (1, 7)):
                with self.subTest(
                    probability=probability, degrees=(numerator, denominator)
                ):
                    quantile = sf.f_distribution_quantile(
                        probability, numerator, denominator
                    )
                    self.assertAlmostEqual(
                        sf.f_distribution_sf(quantile, numerator, denominator),
                        probability,
                        places=9,
                    )

    def test_mann_whitney_exact_counts_enumerate_every_ordering(self):
        for size_a in range(0, 7):
            for size_b in range(0, 7):
                with self.subTest(size_a=size_a, size_b=size_b):
                    counts = sf.mann_whitney_exact_counts(size_a, size_b)
                    self.assertEqual(len(counts), size_a * size_b + 1)
                    self.assertEqual(sum(counts), math.comb(size_a + size_b, size_a))
                    # The null distribution of U is symmetric about n1*n2/2.
                    self.assertEqual(counts, counts[::-1])

    def test_mann_whitney_exact_counts_match_brute_force_enumeration(self):
        import itertools

        for size_a, size_b in ((3, 4), (4, 4), (2, 5)):
            with self.subTest(size_a=size_a, size_b=size_b):
                total = size_a + size_b
                brute = [0] * (size_a * size_b + 1)
                for positions in itertools.combinations(range(total), size_a):
                    chosen = set(positions)
                    statistic = sum(
                        1
                        for a in positions
                        for b in range(total)
                        if b not in chosen and a > b
                    )
                    brute[statistic] += 1
                self.assertEqual(sf.mann_whitney_exact_counts(size_a, size_b), brute)

    def test_probability_refusals_name_a_remediation(self):
        for call in (
            lambda: sf.student_t_sf(1.0, 0.0),
            lambda: sf.chi_square_sf(1.0, 0.0),
            lambda: sf.student_t_quantile(0.0, 10),
            lambda: sf.student_t_quantile(1.5, 10),
            lambda: sf.regularized_gamma_p(0.0, 1.0),
            lambda: sf.regularized_gamma_q(1.0, -1.0),
            lambda: sf.f_distribution_sf(1.0, 0.0, 5.0),
        ):
            with self.subTest(call=call):
                with self.assertRaises(AnalysisValidationError) as caught:
                    call()
                self.assertIn("Remediation", str(caught.exception))

    def test_a_p_value_at_the_floor_refuses_rather_than_inventing_an_interval(self):
        # A clamped p-value carries no recoverable interval. Reconstructing a
        # standard error from it would manufacture a precision the source never
        # reported, so the only correct answer is a refusal.
        with self.assertRaises(AnalysisValidationError) as caught:
            sf.student_t_quantile(sf.MIN_PROBABILITY, 5)
        self.assertIn("not recoverable", str(caught.exception))
        self.assertIn("Remediation", str(caught.exception))

    def test_a_heavy_tailed_low_degree_critical_value_is_still_reachable(self):
        # t with one degree of freedom is Cauchy, so its two-sided tail is about
        # 2/(pi*t) and a p-value of 1e-6 puts the critical value near 6.4e5.
        # An over-tight bracket ceiling would refuse a value that exists.
        quantile = sf.student_t_quantile(1e-6, 1)
        self.assertAlmostEqual(quantile, 2.0 / (math.pi * 1e-6), delta=1.0)


class DeterminismTests(unittest.TestCase):
    def test_published_normalizes_negative_zero(self):
        # repr(-0.0) != repr(0.0), so an unnormalized negative zero would change
        # committed CSV bytes for a value that is zero.
        self.assertEqual(repr(published(-0.0)), repr(0.0))
        self.assertEqual(repr(published(-1e-15)), repr(0.0))

    def test_published_rounds_to_the_declared_precision(self):
        self.assertEqual(published(1.0 / 3.0), 0.3333333333)
        self.assertEqual(published(2.0), 2.0)
        self.assertIsNone(published(None))

    def test_published_refuses_a_non_finite_value(self):
        for value in (float("nan"), float("inf"), float("-inf")):
            with self.subTest(value=value):
                with self.assertRaises(DeterminismError) as caught:
                    published(value)
                self.assertIn("Remediation", str(caught.exception))

    def test_published_row_leaves_non_floats_alone(self):
        row = published_row(
            {"name": "citrate", "count": 3, "flag": True, "effect": 1.0 / 7.0}
        )
        self.assertEqual(row["name"], "citrate")
        self.assertEqual(row["count"], 3)
        self.assertIs(row["flag"], True)
        self.assertEqual(row["effect"], 0.1428571429)

    def test_generator_stream_is_locked_to_literal_values(self):
        # Locks the permutation stream. random.Random is deliberately not used
        # because the Mersenne Twister stream is a CPython implementation
        # detail, so a p-value could change with the interpreter unnoticed.
        generator = LinearCongruentialGenerator(20240101)
        self.assertEqual(
            [generator.next_raw() for _ in range(10)],
            [
                1437807710,
                802395843,
                1244882781,
                1676148508,
                1682695312,
                1389844537,
                798923085,
                1633923863,
                1422082514,
                209042513,
            ],
        )
        self.assertEqual(
            LinearCongruentialGenerator(20240101).permutation(10),
            [3, 9, 7, 1, 2, 4, 8, 5, 6, 0],
        )

    def test_generator_is_reproducible_and_seed_sensitive(self):
        self.assertEqual(
            LinearCongruentialGenerator(7).permutation(25),
            LinearCongruentialGenerator(7).permutation(25),
        )
        self.assertNotEqual(
            LinearCongruentialGenerator(7).permutation(25),
            LinearCongruentialGenerator(8).permutation(25),
        )

    def test_permutation_is_a_permutation(self):
        for count in (0, 1, 2, 13, 64):
            with self.subTest(count=count):
                order = LinearCongruentialGenerator(3).permutation(count)
                self.assertEqual(sorted(order), list(range(count)))

    def test_below_is_unbiased_across_a_long_run(self):
        generator = LinearCongruentialGenerator(11)
        counts = [0] * 6
        draws = 60_000
        for _ in range(draws):
            counts[generator.below(6)] += 1
        expected = draws / 6
        for face, count in enumerate(counts):
            with self.subTest(face=face):
                self.assertLess(abs(count - expected) / expected, 0.05)

    def test_generator_refuses_an_impossible_bound(self):
        generator = LinearCongruentialGenerator(1)
        for bound in (0, -3, LCG_OUTPUT_BOUND + 1):
            with self.subTest(bound=bound):
                with self.assertRaises(DeterminismError):
                    generator.below(bound)

    def test_cost_estimate_flags_a_request_above_its_cap(self):
        estimate = estimate_cost(
            operation_estimate=13_000_000_000,
            cap_name="MAX_PERMUTATION_WORK_UNITS",
            cap_value=MAX_PERMUTATION_WORK_UNITS,
        )
        self.assertFalse(estimate.within_cap)
        self.assertGreater(estimate.estimated_seconds, 0.0)
        self.assertEqual(estimate.as_row()["cap_name"], "MAX_PERMUTATION_WORK_UNITS")
        self.assertTrue(
            estimate_cost(
                operation_estimate=1_000,
                cap_name="MAX_PERMUTATION_WORK_UNITS",
                cap_value=MAX_PERMUTATION_WORK_UNITS,
            ).within_cap
        )


class JacobiAccuracyTests(unittest.TestCase):
    def test_closed_form_two_by_two(self):
        decomposition = la.symmetric_eigen([[2.0, 1.0], [1.0, 2.0]])
        self.assertEqual(decomposition.eigenvalues, (3.0, 1.0))

    def test_a_diagonal_matrix_needs_no_rotation(self):
        decomposition = la.symmetric_eigen(
            [[5.0, 0.0, 0.0], [0.0, 3.0, 0.0], [0.0, 0.0, 1.0]]
        )
        self.assertEqual(decomposition.eigenvalues, (5.0, 3.0, 1.0))
        self.assertEqual(decomposition.rotations_applied, 0)

    def test_reconstruction_and_orthonormality_hold_at_machine_precision(self):
        # Regression for the units bug: a tolerance built from a norm compared
        # against a sum of squares stopped the sweep at roughly sqrt(eps),
        # giving a relative reconstruction error near 1e-10.
        generator = random.Random(3)
        for size in (5, 12, 25, 40):
            with self.subTest(size=size):
                matrix = [
                    [generator.gauss(0.0, 1.0) for _ in range(size + 3)]
                    for _ in range(size)
                ]
                gram = la.gram_matrix(la.center(matrix))
                decomposition = la.symmetric_eigen(gram)
                relative = _reconstruction_error(gram, decomposition) / la.frobenius_norm(gram)
                self.assertLess(relative, 1e-14)
                self.assertLess(_orthonormality_error(decomposition), 1e-13)

    def test_columns_spanning_many_decades_are_still_decomposed(self):
        # Regression for the threshold bug: a threshold derived from a norm was
        # so large that every rotation was skipped, and the "no progress"
        # convergence rule then reported success on an undecomposed matrix.
        generator = random.Random(5)
        matrix = [
            [generator.gauss(0.0, 1.0) * (10.0 ** (index % 7)) for index in range(20)]
            for _ in range(15)
        ]
        gram = la.gram_matrix(la.center(matrix))
        decomposition = la.symmetric_eigen(gram)
        self.assertGreater(decomposition.rotations_applied, 0)
        relative = _reconstruction_error(gram, decomposition) / la.frobenius_norm(gram)
        self.assertLess(relative, 1e-14)

    def test_eigenvalue_trace_matches_total_variance(self):
        generator = random.Random(17)
        matrix = [[generator.gauss(0.0, 1.0) for _ in range(9)] for _ in range(20)]
        centered = la.center(matrix)
        decomposition = la.symmetric_eigen(la.covariance_matrix(centered))
        variance = la.total_variance(centered)
        self.assertLess(
            abs(math.fsum(decomposition.eigenvalues) - variance) / variance, 1e-12
        )

    def test_gram_and_covariance_routes_agree_when_both_are_feasible(self):
        generator = random.Random(23)
        matrix = [[generator.gauss(0.0, 1.0) for _ in range(12)] for _ in range(25)]
        centered = la.center(matrix)
        gram = la.symmetric_eigen(la.gram_matrix(centered))
        covariance = la.symmetric_eigen(la.covariance_matrix(centered))
        self.assertEqual(
            [published(value) for value in gram.eigenvalues[:12]],
            [published(value) for value in covariance.eigenvalues[:12]],
        )

    def test_a_rank_deficient_gram_yields_no_negative_and_only_negligible_dust(self):
        # Centering costs one degree of freedom, so the centered matrix has rank
        # min(n - 1, p) = 6 and the remaining eigenvalues are round-off dust.
        # symmetric_eigen is a general symmetric solver and deliberately does
        # NOT truncate: enforcing max_identifiable_components is ordination's
        # job, so what is guaranteed here is that no eigenvalue is negative and
        # every one beyond the true rank is negligible against the largest.
        generator = random.Random(29)
        matrix = [[generator.gauss(0.0, 1.0) for _ in range(6)] for _ in range(14)]
        decomposition = la.symmetric_eigen(la.gram_matrix(la.center(matrix)))
        self.assertTrue(all(value >= 0.0 for value in decomposition.eigenvalues))
        largest = decomposition.eigenvalues[0]
        self.assertGreater(largest, 0.0)
        for index, value in enumerate(decomposition.eigenvalues[6:], start=6):
            with self.subTest(component=index + 1):
                self.assertLess(value / largest, 1e-14)

    def test_degenerate_eigenvalues_are_reported_not_given_a_convention(self):
        decomposition = la.symmetric_eigen(
            [[2.0, 0.0, 0.0], [0.0, 2.0, 0.0], [0.0, 0.0, 1.0]]
        )
        self.assertEqual(
            decomposition.identifiability,
            (
                la.IDENTIFIABILITY_DEGENERATE,
                la.IDENTIFIABILITY_DEGENERATE,
                la.IDENTIFIABILITY_UNIQUE,
            ),
        )

    def test_an_asymmetric_matrix_is_refused_exactly_not_within_a_tolerance(self):
        with self.assertRaises(la.LinearAlgebraError) as caught:
            la.symmetric_eigen([[1.0, 2.0], [2.0000000001, 1.0]])
        self.assertIn("not exactly symmetric", str(caught.exception))
        self.assertIn("gram_matrix", str(caught.exception))

    def test_non_convergence_raises_instead_of_returning_a_partial_result(self):
        generator = random.Random(31)
        matrix = [[generator.gauss(0.0, 1.0) for _ in range(15)] for _ in range(12)]
        gram = la.gram_matrix(la.center(matrix))
        with self.assertRaises(la.LinearAlgebraError) as caught:
            la.symmetric_eigen(gram, max_sweeps=1)
        self.assertIn("did not converge", str(caught.exception))
        self.assertIn("Remediation", str(caught.exception))

    def test_a_non_square_matrix_is_refused(self):
        with self.assertRaises(la.LinearAlgebraError):
            la.symmetric_eigen([[1.0, 2.0, 3.0], [2.0, 1.0, 0.0]])


class SignConventionTests(unittest.TestCase):
    def test_the_pivot_is_the_largest_magnitude_with_a_label_tie_break(self):
        vector, pivot, rule = la.canonicalize_sign(
            [-0.5, 0.5, 0.2], labels=["beta", "alpha", "gamma"]
        )
        # Both leading components have magnitude 0.5, so the label decides.
        self.assertEqual(pivot, 1)
        self.assertEqual(vector, [-0.5, 0.5, 0.2])
        self.assertIn("casefolded", rule)

    def test_the_vector_is_negated_when_the_pivot_is_negative(self):
        vector, pivot, _ = la.canonicalize_sign(
            [-0.9, 0.1], labels=["alpha", "beta"]
        )
        self.assertEqual(pivot, 0)
        self.assertEqual(vector, [0.9, -0.1])

    def test_an_all_zero_vector_is_refused(self):
        with self.assertRaises(la.LinearAlgebraError) as caught:
            la.canonicalize_sign([0.0, 0.0], labels=["a", "b"])
        self.assertIn("max_identifiable_components", str(caught.exception))

    def test_a_label_count_mismatch_is_refused(self):
        with self.assertRaises(la.LinearAlgebraError):
            la.canonicalize_sign([1.0, 2.0], labels=["only_one"])


class OrdinationInvarianceTests(unittest.TestCase):
    """The properties the whole sign design exists to guarantee."""

    @classmethod
    def setUpClass(cls):
        generator = random.Random(101)
        cls.samples = 18
        cls.features = 40
        cls.components = 4
        cls.feature_ids = [f"feat_{index:03d}" for index in range(cls.features)]
        cls.sample_ids = [f"s{index:02d}" for index in range(cls.samples)]
        cls.matrix = [
            [
                generator.gauss(0.0, 1.0) + (2.5 if (row < 9 and column < 6) else 0.0)
                for column in range(cls.features)
            ]
            for row in range(cls.samples)
        ]
        cls.baseline = _pca_via_gram(cls.matrix, cls.feature_ids, cls.components)

    def test_eigenvalues_and_loadings_are_invariant_to_sample_row_order(self):
        order = LinearCongruentialGenerator(41).permutation(self.samples)
        permuted = _pca_via_gram(
            [self.matrix[index] for index in order], self.feature_ids, self.components
        )
        for index, (base, other) in enumerate(zip(self.baseline, permuted)):
            with self.subTest(component=index + 1):
                self.assertEqual(published(base[0]), published(other[0]))
                self.assertEqual(
                    [published(value) for value in base[1]],
                    [published(value) for value in other[1]],
                )

    def test_scores_are_invariant_to_row_order_after_rematching_on_sample_id(self):
        order = LinearCongruentialGenerator(43).permutation(self.samples)
        permuted = _pca_via_gram(
            [self.matrix[index] for index in order], self.feature_ids, self.components
        )
        for index, (base, other) in enumerate(zip(self.baseline, permuted)):
            with self.subTest(component=index + 1):
                remapped = {
                    self.sample_ids[order[position]]: other[2][position]
                    for position in range(self.samples)
                }
                for position, sample_id in enumerate(self.sample_ids):
                    self.assertEqual(
                        published(base[2][position]), published(remapped[sample_id])
                    )

    def test_loadings_are_invariant_to_feature_column_order(self):
        order = LinearCongruentialGenerator(47).permutation(self.features)
        permuted = _pca_via_gram(
            [[row[index] for index in order] for row in self.matrix],
            [self.feature_ids[index] for index in order],
            self.components,
        )
        relabelled = [self.feature_ids[index] for index in order]
        for index, (base, other) in enumerate(zip(self.baseline, permuted)):
            with self.subTest(component=index + 1):
                self.assertEqual(published(base[0]), published(other[0]))
                remapped = dict(zip(relabelled, other[1]))
                for position, feature_id in enumerate(self.feature_ids):
                    self.assertEqual(
                        published(base[1][position]), published(remapped[feature_id])
                    )

    def test_loadings_are_unit_norm(self):
        for index, (_, loading, _) in enumerate(self.baseline):
            with self.subTest(component=index + 1):
                self.assertAlmostEqual(
                    math.sqrt(math.fsum(value * value for value in loading)),
                    1.0,
                    places=12,
                )


if __name__ == "__main__":
    unittest.main()
