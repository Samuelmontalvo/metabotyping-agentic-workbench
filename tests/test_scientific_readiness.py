import io
import unittest

from scripts.evaluate_scientific_readiness import (
    CONFIGURED_MODULES,
    Gate,
    RecordingResult,
    _discover_test_modules,
    _gate_configuration_issues,
    _gate_row,
    _logical_test_module,
    _markdown,
    _unmapped_modules,
    _unmapped_nonpassing_tests,
)


class _FakeTest:
    __module__ = "unittest.loader"

    def __init__(self, test_id: str) -> None:
        self._test_id = test_id

    def id(self) -> str:
        return self._test_id


class ScientificReadinessIntegrityTests(unittest.TestCase):
    def test_every_discovered_module_has_exactly_one_gate_owner(self):
        discovered_modules = _discover_test_modules()

        self.assertEqual(_unmapped_modules(discovered_modules), [])
        self.assertEqual(set(CONFIGURED_MODULES), set(discovered_modules))
        self.assertEqual(len(CONFIGURED_MODULES), len(set(CONFIGURED_MODULES)))

    def test_collection_error_is_attributed_to_configured_module(self):
        test = _FakeTest("unittest.loader._FailedTest.test_metabolite_effect_search")

        self.assertEqual(_logical_test_module(test), "test_metabolite_effect_search")

    def test_normal_test_module_is_not_inferred_from_class_name_segment(self):
        MisleadingTest = type(
            "test_benchmark",
            (),
            {
                "__module__": "tests.test_unmapped_module",
                "id": lambda self: (
                    "tests.test_unmapped_module.test_benchmark.test_failure"
                ),
            },
        )

        self.assertEqual(
            _logical_test_module(MisleadingTest()),
            "test_unmapped_module",
        )

    def test_gate_fails_when_a_configured_module_does_not_collect(self):
        gate = Gate("example", "purpose", ("test_one", "test_two"))
        records = [
            {
                "id": "test_one.Example.test_passes",
                "module": "test_one",
                "status": "passed",
                "detail": "",
            }
        ]

        row = _gate_row(gate, records)

        self.assertEqual(row["status"], "fail")
        self.assertEqual(row["observed_modules"], ["test_one"])
        self.assertEqual(row["missing_modules"], ["test_two"])

    def test_gate_fails_when_collection_error_is_recorded(self):
        gate = Gate("example", "purpose", ("test_one",))
        records = [
            {
                "id": "unittest.loader._FailedTest.test_one",
                "module": "test_one",
                "status": "error",
                "detail": "ImportError",
            }
        ]

        row = _gate_row(gate, records)

        self.assertEqual(row["status"], "fail")
        self.assertEqual(row["counts"]["error"], 1)
        self.assertEqual(row["missing_modules"], [])

    def test_duplicate_gate_module_assignment_is_rejected(self):
        gates = (
            Gate("one", "purpose", ("test_shared",)),
            Gate("two", "purpose", ("test_shared",)),
        )

        issues = _gate_configuration_issues(gates)

        self.assertEqual(
            issues,
            ["test module test_shared is assigned to multiple gates: one, two"],
        )

    def test_empty_gate_configuration_is_rejected_and_fails(self):
        gate = Gate("empty", "purpose", ())

        self.assertEqual(
            _gate_configuration_issues((gate,)),
            ["gate empty has no configured test modules"],
        )
        self.assertEqual(_gate_row(gate, [])["status"], "fail")

    def test_recording_result_captures_failed_subtest_once(self):
        class FailingSubtest(unittest.TestCase):
            def runTest(self):
                with self.subTest(case="synthetic"):
                    self.fail("synthetic subtest failure")

        runner = unittest.TextTestRunner(
            stream=io.StringIO(),
            verbosity=0,
            resultclass=RecordingResult,
        )
        result = runner.run(unittest.TestSuite([FailingSubtest()]))

        self.assertIsInstance(result, RecordingResult)
        self.assertEqual(result.testsRun, 1)
        self.assertEqual(len(result.records), 1)
        self.assertEqual(result.records[0]["status"], "failed")
        self.assertIn("synthetic subtest failure", result.records[0]["detail"])

    def test_real_failed_test_is_attributed_and_fails_its_gate(self):
        failed_test = unittest.loader._FailedTest(  # type: ignore[attr-defined]
            "test_benchmark",
            ImportError("synthetic import failure"),
        )
        runner = unittest.TextTestRunner(
            stream=io.StringIO(),
            verbosity=0,
            resultclass=RecordingResult,
        )
        result = runner.run(unittest.TestSuite([failed_test]))

        self.assertIsInstance(result, RecordingResult)
        self.assertEqual(result.records[0]["module"], "test_benchmark")
        gate = Gate("benchmark", "purpose", ("test_benchmark",))
        self.assertEqual(_gate_row(gate, result.records)["status"], "fail")

    def test_unmapped_failure_is_preserved_in_payload_and_markdown(self):
        record = {
            "id": "test_unmapped.Example.test_failure",
            "module": "test_unmapped",
            "status": "failed",
            "detail": "synthetic failure",
        }
        unmapped = _unmapped_nonpassing_tests([record])
        payload = {
            "strict_release_gate_status": "fail",
            "tests_run": 1,
            "counts": {
                "passed": 0,
                "failed": 1,
                "error": 0,
                "skipped": 0,
                "expected_failure": 0,
                "unexpected_success": 0,
            },
            "gates": [],
            "nonpassing_tests": [record],
            "gate_configuration_issues": [],
            "unmapped_nonpassing_tests": unmapped,
            "limitations": [],
        }

        self.assertEqual(unmapped, [record])
        self.assertIn(
            "Unmapped nonpassing test: `test_unmapped.Example.test_failure`",
            _markdown(payload),
        )

    def test_passing_unmapped_module_is_reported_in_gate_integrity(self):
        unmapped_modules = _unmapped_modules(
            ["test_configured", "test_new_passing"],
            ["test_configured"],
        )
        payload = {
            "strict_release_gate_status": "fail",
            "tests_run": 2,
            "counts": {
                "passed": 2,
                "failed": 0,
                "error": 0,
                "skipped": 0,
                "expected_failure": 0,
                "unexpected_success": 0,
            },
            "gates": [],
            "nonpassing_tests": [],
            "gate_configuration_issues": [],
            "unmapped_modules": unmapped_modules,
            "unmapped_nonpassing_tests": [],
            "limitations": [],
        }

        self.assertEqual(unmapped_modules, ["test_new_passing"])
        self.assertIn(
            "Discovered test module `test_new_passing` has no configured gate owner.",
            _markdown(payload),
        )


if __name__ == "__main__":
    unittest.main()
