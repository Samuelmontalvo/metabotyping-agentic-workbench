import tempfile
import unittest
from pathlib import Path

from scripts.evaluate_skills import (
    _contract_fingerprint,
    _is_normalized_agent_slug,
    _load_claude_agent,
    _load_codex_agent,
    evaluate_agents,
    evaluate_repository,
    load_agent_alias_registry,
    normalize_agent_name,
    resolve_agent_name,
)


class SkillAgentEvaluationTests(unittest.TestCase):
    def test_inventory_is_paired_and_has_no_duplicate_agents(self):
        results = evaluate_repository()
        summary = results["summary"]

        self.assertEqual(summary["paired_skill_names"], 25)
        self.assertEqual(summary["skill_files"], 50)
        self.assertEqual(summary["paired_agent_names"], 23)
        self.assertEqual(summary["agent_files"], 46)
        self.assertEqual(summary["agent_files"], len(results["agents"]))
        self.assertEqual(summary["paired_deprecated_agent_alias_names"], 2)
        self.assertEqual(summary["deprecated_agent_alias_files"], 4)
        self.assertEqual(
            summary["deprecated_agent_alias_files"],
            len(results["agent_aliases"]),
        )
        self.assertEqual(summary["addressable_agent_names"], 25)
        self.assertEqual(summary["addressable_agent_files"], 50)
        self.assertEqual(results["inventory_issues"], [])

    def test_every_contract_passes_structural_and_operational_checks(self):
        results = evaluate_repository()

        self.assertTrue(all(row["structural_score"] == 1.0 for row in results["skills"]))
        self.assertTrue(all(row["operational_score"] == 1.0 for row in results["skills"]))
        self.assertTrue(all(row["score"] == 1.0 for row in results["agents"]))
        self.assertTrue(all(row["score"] == 1.0 for row in results["agent_aliases"]))
        self.assertTrue(
            all(row["checks"]["paired_contract_parity"] for row in results["agents"])
        )
        self.assertTrue(
            all(
                row["checks"]["paired_contract_parity"]
                and row["checks"]["behaviorally_equivalent_to_canonical"]
                for row in results["agent_aliases"]
            )
        )

    def test_agent_alias_normalization_detects_logical_duplicates(self):
        self.assertEqual(normalize_agent_name("variable_crosswalk"), "variable-crosswalk")
        self.assertFalse(_is_normalized_agent_slug("variable_crosswalk"))
        self.assertFalse(_is_normalized_agent_slug("Variable-Crosswalk"))
        self.assertTrue(_is_normalized_agent_slug("variable-crosswalk"))

    def test_contract_fingerprint_preserves_semantic_operators(self):
        self.assertNotEqual(
            _contract_fingerprint("remove when version < 0.3.0"),
            _contract_fingerprint("remove when version > 0.3.0"),
        )

    def test_host_manifests_reject_unsupported_alias_keys(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            codex_path = root / "example.toml"
            codex_path.write_text(
                'name = "example"\n'
                'description = "Example."\n'
                'developer_instructions = "Input contract. Output contract. '
                'Review boundary. Do not infer missing evidence."\n'
                'aliases = ["legacy-example"]\n',
                encoding="utf-8",
            )
            claude_path = root / "example.md"
            claude_path.write_text(
                "---\n"
                "name: example\n"
                "description: Example.\n"
                "alias_of: legacy-example\n"
                "---\n\n"
                "Input contract. Output contract. Review boundary. "
                "Do not infer missing evidence.\n",
                encoding="utf-8",
            )

            _, _, codex_errors = _load_codex_agent(codex_path)
            _, _, claude_errors = _load_claude_agent(claude_path)

        self.assertEqual(
            codex_errors,
            ["unsupported Codex agent manifest keys: aliases"],
        )
        self.assertEqual(
            claude_errors,
            ["unsupported Claude agent frontmatter keys: alias_of"],
        )

    def test_registry_resolves_two_deprecated_aliases_one_hop(self):
        registry, issues = load_agent_alias_registry()

        self.assertEqual(issues, [])
        self.assertEqual(
            registry["aliases"],
            [
                {
                    "alias": "data-quality-reviewer",
                    "canonical": "dataset-readiness-reviewer",
                    "status": "deprecated",
                    "deprecated_since": "0.2.0",
                    "remove_in": "0.3.0",
                    "compatibility": "behaviorally_equivalent",
                    "platforms": ["codex", "claude"],
                },
                {
                    "alias": "motrpac-replication-analyst",
                    "canonical": "motrpac-metadata-readiness-analyst",
                    "status": "deprecated",
                    "deprecated_since": "0.2.0",
                    "remove_in": "0.3.0",
                    "compatibility": "behaviorally_equivalent",
                    "platforms": ["codex", "claude"],
                },
            ],
        )
        self.assertEqual(
            resolve_agent_name("data-quality-reviewer", registry),
            "dataset-readiness-reviewer",
        )
        self.assertEqual(
            resolve_agent_name("motrpac-replication-analyst", registry),
            "motrpac-metadata-readiness-analyst",
        )
        self.assertEqual(
            resolve_agent_name("dataset-readiness-reviewer", registry),
            "dataset-readiness-reviewer",
        )

    def test_alias_expiry_is_a_release_inventory_error(self):
        _, before_removal = evaluate_agents(project_version="0.2.999")
        _, at_removal = evaluate_agents(project_version="0.3.0")

        self.assertEqual(
            [issue for issue in before_removal if issue.startswith("expired agent alias")],
            [],
        )
        self.assertEqual(
            [issue for issue in at_removal if issue.startswith("expired agent alias")],
            [
                "expired agent alias data-quality-reviewer: "
                "remove_in 0.3.0 reached by 0.3.0",
                "expired agent alias motrpac-replication-analyst: "
                "remove_in 0.3.0 reached by 0.3.0",
            ],
        )

    def test_alias_chain_is_rejected(self):
        registry_text = """\
schema_version = 1

[[aliases]]
alias = "legacy-one"
canonical = "legacy-two"
status = "deprecated"
deprecated_since = "0.2.0"
remove_in = "0.3.0"
compatibility = "behaviorally_equivalent"
platforms = ["codex", "claude"]

[[aliases]]
alias = "legacy-two"
canonical = "dataset-readiness-reviewer"
status = "deprecated"
deprecated_since = "0.2.0"
remove_in = "0.3.0"
compatibility = "behaviorally_equivalent"
platforms = ["codex", "claude"]
"""
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "aliases.toml"
            path.write_text(registry_text, encoding="utf-8")
            registry, issues = load_agent_alias_registry(path)

        self.assertTrue(any("one hop" in issue for issue in issues))
        with self.assertRaisesRegex(ValueError, "exactly one hop"):
            resolve_agent_name("legacy-one", registry)

    def test_two_node_alias_cycle_is_rejected(self):
        registry_text = """\
schema_version = 1

[[aliases]]
alias = "legacy-one"
canonical = "legacy-two"
status = "deprecated"
deprecated_since = "0.2.0"
remove_in = "0.3.0"
compatibility = "behaviorally_equivalent"
platforms = ["codex", "claude"]

[[aliases]]
alias = "legacy-two"
canonical = "legacy-one"
status = "deprecated"
deprecated_since = "0.2.0"
remove_in = "0.3.0"
compatibility = "behaviorally_equivalent"
platforms = ["codex", "claude"]
"""
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "aliases.toml"
            path.write_text(registry_text, encoding="utf-8")
            registry, issues = load_agent_alias_registry(path)

        self.assertEqual(sum("one hop" in issue for issue in issues), 2)
        with self.assertRaisesRegex(ValueError, "exactly one hop"):
            resolve_agent_name("legacy-one", registry)

    def test_unknown_alias_target_is_an_inventory_error(self):
        registry_text = """\
schema_version = 1

[[aliases]]
alias = "data-quality-reviewer"
canonical = "unknown-target"
status = "deprecated"
deprecated_since = "0.2.0"
remove_in = "0.3.0"
compatibility = "behaviorally_equivalent"
platforms = ["codex", "claude"]
"""
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "aliases.toml"
            path.write_text(registry_text, encoding="utf-8")
            _, issues = evaluate_agents(alias_registry_path=path)

        self.assertTrue(
            any(
                "unknown canonical target unknown-target for agent alias "
                "data-quality-reviewer" in issue
                for issue in issues
            )
        )


if __name__ == "__main__":
    unittest.main()
