"""Run behavioral scientific-safety gates and write auditable local reports.

This complements ``evaluate_skills.py``.  The skill audit checks contracts and
implementation links; this script executes the offline synthetic regression
suite and groups results by scientific risk domain.  Passing these gates is not
independent validation on external cohorts or analytical platforms.
"""

from __future__ import annotations

import argparse
import io
import json
import sys
import unittest
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


@dataclass(frozen=True)
class Gate:
    name: str
    purpose: str
    modules: tuple[str, ...]


GATES = (
    Gate(
        "identity_and_assay_harmonization",
        "Blocks name-only identity, unresolved isomers, unsafe pooling, cross-study batch correction, and irreversible imputation.",
        ("test_assay_harmonization",),
    ),
    Gate(
        "provenance_and_multi_repository_safety",
        "Retains one-to-many repository records and prevents duplicate normalized keys from silently overwriting evidence.",
        ("test_metadata_extraction", "test_motrpac_volcano_compare", "test_source_registry"),
    ),
    Gate(
        "statistical_and_review_safety",
        "Keeps uncertain mappings or annotations review-gated and validates effect-search multiplicity semantics.",
        ("test_variable_crosswalk", "test_metabolite_effect_search"),
    ),
    Gate(
        "motrpac_style_plotting",
        "Validates contrast/FDR semantics, mapping and coverage gates, hierarchy views, deterministic exports, and optional renderers.",
        ("test_metabolomics_plotting",),
    ),
    Gate(
        "skill_and_agent_contracts",
        "Checks paired Codex/Claude skill contracts, implementation links, and agent review boundaries.",
        ("test_skill_agent_evaluation",),
    ),
    Gate(
        "benchmark_integrity_and_reproducibility",
        "Validates explicit benchmark denominators, disagreement accounting, provenance, and byte-reproducible pilot outputs.",
        ("test_benchmark", "test_pilot_reproducibility"),
    ),
    Gate(
        "domain_review_contract_safety",
        "Validates advisory-only domain review packets, complete evidence-state coverage, and non-executable review boundaries.",
        ("test_domain_review_foundation",),
    ),
    Gate(
        "scientific_readiness_gate_integrity",
        "Validates required-module collection, import-error attribution, and unique gate ownership.",
        ("test_scientific_readiness",),
    ),
)

CONFIGURED_MODULES = tuple(module for gate in GATES for module in gate.modules)


class RecordingResult(unittest.TextTestResult):
    """Record every test status in a stable machine-readable form."""

    def __init__(self, stream: Any, descriptions: bool, verbosity: int) -> None:
        super().__init__(stream, descriptions, verbosity)
        self.records: list[dict[str, str]] = []
        self._subtest_nonpassing: dict[str, dict[str, Any]] = {}

    @staticmethod
    def _row(test: unittest.case.TestCase, status: str, detail: str = "") -> dict[str, str]:
        return {
            "id": test.id(),
            "module": _logical_test_module(test),
            "status": status,
            "detail": detail,
        }

    def addSuccess(self, test: unittest.case.TestCase) -> None:  # noqa: N802
        super().addSuccess(test)
        self.records.append(self._row(test, "passed"))

    def addSkip(self, test: unittest.case.TestCase, reason: str) -> None:  # noqa: N802
        super().addSkip(test, reason)
        self.records.append(self._row(test, "skipped", reason))

    def addFailure(self, test: unittest.case.TestCase, err: Any) -> None:  # noqa: N802
        super().addFailure(test, err)
        self.records.append(self._row(test, "failed", self._exc_info_to_string(err, test)))

    def addError(self, test: unittest.case.TestCase, err: Any) -> None:  # noqa: N802
        super().addError(test, err)
        self.records.append(self._row(test, "error", self._exc_info_to_string(err, test)))

    def addExpectedFailure(self, test: unittest.case.TestCase, err: Any) -> None:  # noqa: N802
        super().addExpectedFailure(test, err)
        self.records.append(
            self._row(test, "expected_failure", self._exc_info_to_string(err, test))
        )

    def addUnexpectedSuccess(self, test: unittest.case.TestCase) -> None:  # noqa: N802
        super().addUnexpectedSuccess(test)
        self.records.append(self._row(test, "unexpected_success"))

    def addSubTest(  # noqa: N802
        self,
        test: unittest.case.TestCase,
        subtest: unittest.case.TestCase,
        err: tuple[type[BaseException], BaseException, Any] | None,
    ) -> None:
        super().addSubTest(test, subtest, err)
        if err is None:
            return
        status = (
            "failed"
            if issubclass(err[0], test.failureException)
            else "error"
        )
        test_id = test.id()
        pending = self._subtest_nonpassing.setdefault(
            test_id,
            {"status": status, "details": []},
        )
        if status == "error":
            pending["status"] = "error"
        pending["details"].append(self._exc_info_to_string(err, subtest))

    def stopTest(self, test: unittest.case.TestCase) -> None:  # noqa: N802
        pending = self._subtest_nonpassing.pop(test.id(), None)
        already_recorded = any(row["id"] == test.id() for row in self.records)
        if pending is not None and not already_recorded:
            self.records.append(
                self._row(
                    test,
                    str(pending["status"]),
                    "\n\n".join(str(item) for item in pending["details"]),
                )
            )
        super().stopTest(test)


def _counts(records: list[dict[str, str]]) -> dict[str, int]:
    statuses = ("passed", "failed", "error", "skipped", "expected_failure", "unexpected_success")
    return {status: sum(row["status"] == status for row in records) for status in statuses}


def _logical_test_module(test: unittest.case.TestCase) -> str:
    """Resolve normal tests and unittest collection failures to the configured module."""
    class_module = test.__class__.__module__
    if class_module != "unittest.loader":
        return class_module.split(".")[-1]
    test_id = test.id()
    failed_module = test_id.rsplit(".", 1)[-1]
    return failed_module


def _gate_configuration_issues(gates: tuple[Gate, ...] = GATES) -> list[str]:
    owners: dict[str, list[str]] = {}
    issues = [
        f"gate {gate.name} has no configured test modules"
        for gate in gates
        if not gate.modules
    ]
    for gate in gates:
        for module in gate.modules:
            owners.setdefault(module, []).append(gate.name)
    issues.extend(
        f"test module {module} is assigned to multiple gates: {', '.join(names)}"
        for module, names in sorted(owners.items())
        if len(names) > 1
    )
    return issues


def _gate_row(gate: Gate, records: list[dict[str, str]]) -> dict[str, Any]:
    selected = [row for row in records if row["module"] in gate.modules]
    observed_modules = sorted({row["module"] for row in selected})
    missing_modules = sorted(set(gate.modules) - set(observed_modules))
    counts = _counts(selected)
    strict_pass = bool(gate.modules) and not missing_modules and counts == {
        "passed": len(selected),
        "failed": 0,
        "error": 0,
        "skipped": 0,
        "expected_failure": 0,
        "unexpected_success": 0,
    }
    return {
        "name": gate.name,
        "purpose": gate.purpose,
        "modules": list(gate.modules),
        "observed_modules": observed_modules,
        "missing_modules": missing_modules,
        "tests": len(selected),
        "counts": counts,
        "status": "pass" if strict_pass else "fail",
    }


def _unmapped_nonpassing_tests(
    records: list[dict[str, str]],
) -> list[dict[str, str]]:
    configured_modules = set(CONFIGURED_MODULES)
    return [
        row
        for row in records
        if row["status"] != "passed" and row["module"] not in configured_modules
    ]


def evaluate() -> dict[str, Any]:
    suite = unittest.defaultTestLoader.discover(str(ROOT / "tests"), pattern="test*.py")
    stream = io.StringIO()
    runner = unittest.TextTestRunner(
        stream=stream,
        verbosity=2,
        resultclass=RecordingResult,
    )
    result = runner.run(suite)
    assert isinstance(result, RecordingResult)
    records = sorted(result.records, key=lambda row: row["id"])
    counts = _counts(records)
    gate_rows = [_gate_row(gate, records) for gate in GATES]
    configuration_issues = _gate_configuration_issues()
    unmapped_nonpassing = _unmapped_nonpassing_tests(records)
    strict_full_pass = (
        result.testsRun == len(records)
        and counts["passed"] == len(records)
        and all(value == 0 for key, value in counts.items() if key != "passed")
        and all(row["status"] == "pass" for row in gate_rows)
        and not configuration_issues
        and not unmapped_nonpassing
    )
    failures = [row for row in records if row["status"] != "passed"]
    return {
        "schema_version": "1.0",
        "validation_scope": "offline synthetic and deterministic repository regression tests",
        "independent_external_validation": False,
        "strict_release_gate_status": "pass" if strict_full_pass else "fail",
        "tests_run": result.testsRun,
        "counts": counts,
        "gates": gate_rows,
        "gate_configuration_issues": configuration_issues,
        "unmapped_nonpassing_tests": unmapped_nonpassing,
        "nonpassing_tests": failures,
        "limitations": [
            "Passing does not validate performance on independent real studies, assay platforms, species, or cohorts.",
            "Database routing tests do not execute optional or planned external connectors.",
            "Hierarchy plots are descriptive; dedicated pathway enrichment and cross-platform meta-analysis models remain separate work.",
            "Skill contract scores measure structure and linkage, not empirical scientific validity.",
        ],
    }


def _markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Scientific Readiness Report",
        "",
        "This report executes the repository's offline synthetic behavioral gates. It complements the structural skill/agent audit and is not independent validation on external cohorts or analytical platforms.",
        "",
        "## Result",
        "",
        f"- Strict synthetic release gate: **{str(payload['strict_release_gate_status']).upper()}**.",
        f"- Tests run: {payload['tests_run']}.",
        "- Counts: " + ", ".join(f"{key}={value}" for key, value in payload["counts"].items()) + ".",
        "",
        "## Behavioral gates",
        "",
        "| Gate | Status | Tests | Passed | Failed | Errors | Skipped | Purpose |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for row in payload["gates"]:
        counts = row["counts"]
        lines.append(
            f"| `{row['name']}` | {str(row['status']).upper()} | {row['tests']} | "
            f"{counts['passed']} | {counts['failed']} | {counts['error']} | "
            f"{counts['skipped']} | {row['purpose']} |"
        )
    lines.extend(["", "## Nonpassing tests", ""])
    if payload["nonpassing_tests"]:
        for row in payload["nonpassing_tests"]:
            detail = str(row["detail"]).strip().splitlines()[-1] if row["detail"] else ""
            lines.append(f"- `{row['id']}`: {row['status']} — {detail}")
    else:
        lines.append("- None.")
    lines.extend(["", "## Gate integrity", ""])
    if payload["gate_configuration_issues"]:
        lines.extend(f"- Configuration error: {item}" for item in payload["gate_configuration_issues"])
    missing_modules = [
        (row["name"], module)
        for row in payload["gates"]
        for module in row["missing_modules"]
    ]
    if missing_modules:
        lines.extend(
            f"- `{gate}` did not collect required module `{module}`."
            for gate, module in missing_modules
        )
    if payload["unmapped_nonpassing_tests"]:
        lines.extend(
            f"- Unmapped nonpassing test: `{row['id']}` ({row['status']})."
            for row in payload["unmapped_nonpassing_tests"]
        )
    if not payload["gate_configuration_issues"] and not missing_modules and not payload["unmapped_nonpassing_tests"]:
        lines.append("- Every configured module collected tests exactly once; no nonpassing test was unmapped.")
    lines.extend(["", "## Interpretation limits", ""])
    lines.extend(f"- {item}" for item in payload["limitations"])
    lines.extend(
        [
            "",
            "The release gate should be rerun after scientific code, schemas, fixtures, skills, agents, or validation rules change.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--json-out",
        type=Path,
        default=ROOT / "docs/scientific_readiness_results.json",
    )
    parser.add_argument(
        "--report-out",
        type=Path,
        default=ROOT / "docs/scientific_readiness_report.md",
    )
    args = parser.parse_args()
    payload = evaluate()
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.report_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    args.report_out.write_text(_markdown(payload), encoding="utf-8")
    print(json.dumps({
        "status": payload["strict_release_gate_status"],
        "tests_run": payload["tests_run"],
        "json": str(args.json_out),
        "report": str(args.report_out),
    }, sort_keys=True))
    return 0 if payload["strict_release_gate_status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
