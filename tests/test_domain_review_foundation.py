from __future__ import annotations

import json
import tomllib
import unittest
from copy import deepcopy
from pathlib import Path

from metabotyping_agentic.io import read_json, to_plain
from metabotyping_agentic.review import (
    ROLE_REVIEW_DIMENSIONS,
    DomainReviewPacket,
    DomainReviewRole,
    EvidenceState,
    build_packet_digest,
    domain_review_schema_path,
    validate_domain_review_packet,
    validate_domain_review_packet_or_raise,
)
from metabotyping_agentic.schemas import project_schema_path, validate_against_schema


ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = ROOT / "tests" / "fixtures" / "domain_review"
REPOSITORY_SCHEMA_PATH = project_schema_path("domain_review_packet.schema.json")
SCHEMA_PATH = domain_review_schema_path()
FIXTURE_PATHS = sorted(FIXTURE_DIR.glob("*.json"))
MISSING_STATES = {
    EvidenceState.NOT_REPORTED.value,
    EvidenceState.NOT_AVAILABLE.value,
    EvidenceState.UNRESOLVED.value,
}


def _load_packets() -> list[dict[str, object]]:
    return [read_json(path) for path in FIXTURE_PATHS]


def _with_current_digest(packet: dict[str, object]) -> dict[str, object]:
    packet["packet_digest"] = build_packet_digest(packet)
    return packet


class DomainReviewFoundationTests(unittest.TestCase):
    def test_all_role_fixtures_validate_as_models_schema_and_semantics(self):
        self.assertTrue(SCHEMA_PATH.is_file())
        self.assertEqual(
            SCHEMA_PATH.read_bytes(),
            REPOSITORY_SCHEMA_PATH.read_bytes(),
        )
        packets = _load_packets()
        self.assertEqual(len(packets), 4)
        self.assertEqual(
            {packet["role"] for packet in packets},
            {role.value for role in DomainReviewRole},
        )

        for raw in packets:
            with self.subTest(role=raw["role"]):
                packet = DomainReviewPacket.model_validate(raw)
                self.assertEqual(to_plain(packet), raw)
                self.assertEqual(validate_against_schema(raw, SCHEMA_PATH), [])
                self.assertEqual(validate_domain_review_packet(raw), [])
                validate_domain_review_packet_or_raise(packet)

    def test_every_required_dimension_has_explicit_coverage_and_missing_states(self):
        for packet in _load_packets():
            with self.subTest(role=packet["role"]):
                required = set(ROLE_REVIEW_DIMENSIONS[str(packet["role"])])
                evidence = packet["evidence"]
                covered = {item["dimension"] for item in evidence}
                self.assertEqual(covered, required)
                self.assertTrue(
                    any(item["state"] in MISSING_STATES for item in evidence),
                    "Fixture must demonstrate explicit missing or unresolved evidence.",
                )
                self.assertTrue(all(item["detail"].strip() for item in evidence))

    def test_omitted_required_dimension_fails_closed_even_with_valid_digest(self):
        packet = deepcopy(_load_packets()[0])
        removed = packet["evidence"].pop()
        _with_current_digest(packet)

        errors = validate_domain_review_packet(packet)
        self.assertTrue(
            any(
                "missing required role dimensions" in error
                and removed["dimension"] in error
                for error in errors
            )
        )

    def test_duplicate_and_dangling_ids_fail_closed(self):
        duplicate = deepcopy(_load_packets()[0])
        duplicate["evidence"].append(deepcopy(duplicate["evidence"][0]))
        _with_current_digest(duplicate)
        duplicate_errors = validate_domain_review_packet(duplicate)
        self.assertTrue(any("duplicate evidence_id" in error for error in duplicate_errors))

        dangling = deepcopy(_load_packets()[0])
        dangling["human_review_questions"][0]["evidence_ids"] = ["missing-evidence"]
        _with_current_digest(dangling)
        dangling_errors = validate_domain_review_packet(dangling)
        self.assertTrue(any("unresolved references" in error for error in dangling_errors))

        provenance_dangling = deepcopy(_load_packets()[0])
        provenance_dangling["evidence"][0]["provenance_ids"] = ["missing-provenance"]
        _with_current_digest(provenance_dangling)
        provenance_errors = validate_domain_review_packet(provenance_dangling)
        self.assertTrue(any("unresolved references" in error for error in provenance_errors))

    def test_bad_digest_and_unsupported_role_fail_closed(self):
        packet = deepcopy(_load_packets()[0])
        packet["packet_digest"] = "f" * 64
        self.assertTrue(
            any(
                "packet_digest does not match" in error
                for error in validate_domain_review_packet(packet)
            )
        )

        unsupported = deepcopy(packet)
        unsupported["role"] = "unbounded-domain-decider"
        _with_current_digest(unsupported)
        self.assertTrue(
            any(
                "unsupported domain review role" in error
                for error in validate_domain_review_packet(unsupported)
            )
        )

    def test_human_authority_and_empty_execution_are_invariants(self):
        packet = deepcopy(_load_packets()[0])
        packet["decision_authority"] = "automatic"
        packet["human_adjudication_status"] = "not_required"
        packet["executable_actions"] = ["merge variables"]
        _with_current_digest(packet)

        errors = validate_domain_review_packet(packet)
        self.assertTrue(any("advisory_only" in error for error in errors))
        self.assertTrue(any("human_adjudication_status" in error for error in errors))
        self.assertTrue(any("executable_actions must be empty" in error for error in errors))
        with self.assertRaisesRegex(ValueError, "domain review packet failed validation"):
            validate_domain_review_packet_or_raise(packet)

    def test_scope_version_is_required_and_nonempty(self):
        missing = deepcopy(_load_packets()[0])
        del missing["scope_version"]
        _with_current_digest(missing)
        self.assertTrue(
            any("scope_version" in error for error in validate_domain_review_packet(missing))
        )

        blank = deepcopy(_load_packets()[0])
        blank["scope_version"] = ""
        _with_current_digest(blank)
        self.assertTrue(
            any("scope_version" in error for error in validate_domain_review_packet(blank))
        )

    def test_forbidden_decision_outputs_fail_without_jsonschema(self):
        prohibited_fields = (
            "acceptance",
            "confidence_score",
            "transforms",
            "pooling_authorization",
            "risk_of_bias_score",
            "meta_analytic_results",
        )
        for field in prohibited_fields:
            with self.subTest(field=field):
                packet = deepcopy(_load_packets()[0])
                packet[field] = [] if field.endswith("s") else "prohibited"
                _with_current_digest(packet)
                errors = validate_domain_review_packet(packet)
                self.assertTrue(
                    any(
                        field in error and "advisory-only" in error
                        for error in errors
                    )
                )
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        self.assertFalse(schema["additionalProperties"])

    def test_model_instances_cannot_drop_or_hide_undeclared_authority_fields(self):
        raw = deepcopy(_load_packets()[0])
        raw["acceptance"] = "accepted"
        _with_current_digest(raw)
        with self.assertRaises(ValueError):
            DomainReviewPacket.model_validate(raw)

        packet = DomainReviewPacket.model_validate(_load_packets()[0])
        object.__setattr__(packet, "acceptance", "accepted")
        errors = validate_domain_review_packet(packet)
        self.assertTrue(
            any(
                "packet.acceptance" in error and "advisory-only" in error
                for error in errors
            )
        )

    def test_prohibited_authority_statements_cannot_hide_in_evidence_prose(self):
        packet = deepcopy(_load_packets()[0])
        packet["evidence"][0]["detail"] = (
            "Pooling authorized; confidence score 0.99; mapping accepted."
        )
        _with_current_digest(packet)

        errors = validate_domain_review_packet(packet)

        self.assertTrue(any("pooling permission" in error for error in errors))
        self.assertTrue(any("confidence score" in error for error in errors))
        self.assertTrue(
            any("acceptance or rejection decision" in error for error in errors)
        )

    def test_imperative_acceptance_and_rejection_decisions_are_prohibited(self):
        statements = (
            "Accept this mapping.",
            "Reject this dataset.",
            "The study should be accepted.",
            "Acceptance is recommended.",
        )
        for statement in statements:
            with self.subTest(statement=statement):
                packet = deepcopy(_load_packets()[0])
                packet["evidence"][0]["detail"] = statement
                _with_current_digest(packet)

                self.assertTrue(
                    any(
                        "acceptance or rejection decision" in error
                        for error in validate_domain_review_packet(packet)
                    )
                )

    def test_documented_absent_requires_linked_provenance(self):
        packets = _load_packets()
        evidence_items = [
            item
            for packet in packets
            for item in packet["evidence"]
            if item["state"] == EvidenceState.DOCUMENTED_ABSENT.value
        ]
        self.assertTrue(evidence_items)
        self.assertTrue(all(item["provenance_ids"] for item in evidence_items))

        packet = deepcopy(
            next(
                item
                for item in packets
                if any(
                    evidence["state"] == EvidenceState.DOCUMENTED_ABSENT.value
                    for evidence in item["evidence"]
                )
            )
        )
        documented_absent = next(
            item
            for item in packet["evidence"]
            if item["state"] == EvidenceState.DOCUMENTED_ABSENT.value
        )
        documented_absent["provenance_ids"] = []
        _with_current_digest(packet)

        self.assertTrue(
            any(
                "documented_absent" in error and "requires provenance" in error
                for error in validate_domain_review_packet(packet)
            )
        )

    def test_digest_is_independent_of_id_keyed_collection_order(self):
        packet = deepcopy(_load_packets()[0])
        expected = build_packet_digest(packet)
        packet["provenance"].reverse()
        packet["evidence"].reverse()
        packet["limitations"].reverse()
        packet["blockers"].reverse()
        packet["human_review_questions"].reverse()
        for ids in packet["referenced_entities"].values():
            ids.reverse()
        for item in packet["evidence"]:
            item["provenance_ids"].reverse()
        for collection in ("limitations", "blockers", "human_review_questions"):
            for item in packet[collection]:
                item["evidence_ids"].reverse()

        self.assertEqual(build_packet_digest(packet), expected)

    def test_model_schema_and_paired_manifest_role_names_are_synchronized(self):
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        schema_roles = set(schema["properties"]["role"]["enum"])
        schema_states = set(
            schema["$defs"]["evidenceItem"]["properties"]["state"]["enum"]
        )
        model_roles = {role.value for role in DomainReviewRole}
        self.assertEqual(schema_roles, model_roles)
        self.assertEqual(schema_states, {state.value for state in EvidenceState})
        self.assertEqual(set(ROLE_REVIEW_DIMENSIONS), model_roles)

        codex_paths = {
            path.stem: path
            for path in (ROOT / ".codex" / "agents").glob("*.toml")
            if path.stem in model_roles
        }
        claude_paths = {
            path.stem: path
            for path in (ROOT / ".claude" / "agents").glob("*.md")
            if path.stem in model_roles
        }
        self.assertEqual(set(codex_paths), model_roles)
        self.assertEqual(set(claude_paths), model_roles)

        for role in sorted(model_roles):
            with self.subTest(role=role):
                codex = tomllib.loads(codex_paths[role].read_text(encoding="utf-8"))
                claude_text = claude_paths[role].read_text(encoding="utf-8")
                self.assertEqual(codex["name"], role)
                self.assertIn(f"name: {role}", claude_text)
                for text in (
                    codex["developer_instructions"],
                    claude_text,
                ):
                    lowered = text.lower()
                    self.assertIn("validate_domain_review_packet()", text)
                    self.assertIn("advisory-only", lowered)
                    self.assertIn("human adjudication", lowered)
                    self.assertIn("no executable actions", lowered)
                    self.assertIn("confidence", lowered)
                    self.assertIn("pooling", lowered)
                    self.assertIn("meta-analytic", lowered)
                    for state in sorted(state.value for state in EvidenceState):
                        self.assertIn(f"`{state}`", text)
                    for dimension in ROLE_REVIEW_DIMENSIONS[role]:
                        self.assertIn(f"`{dimension}`", text)


if __name__ == "__main__":
    unittest.main()
