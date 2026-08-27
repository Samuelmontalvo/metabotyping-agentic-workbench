"""Enforce the declared network-boundary allowlist by AST scan.

Live ingestion is a supported, opt-in mode, but it must stay confined to a small
reviewed set of modules. This test makes that boundary machine-checked instead of
documented-only: any module outside the allowlist that imports a network client is
a failure, and any allowlist entry that no longer exists or no longer needs network
access is also a failure so the allowlist cannot rot.
"""

from __future__ import annotations

import ast
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

SCANNED_DIRECTORIES = ("src", "scripts", "tests")

# Modules permitted to reach the network. Adding an entry is a reviewed change to
# CLAUDE.md and AGENTS.md, not a test-only edit.
NETWORK_BOUNDARY_ALLOWLIST = frozenset(
    {
        "scripts/fetch_live_records.py",
        "scripts/volcano_compare.py",
        "src/metabotyping_agentic/live_sources/literature_search.py",
        "src/metabotyping_agentic/live_sources/metabolomics_workbench.py",
        "src/metabotyping_agentic/live_sources/metgene.py",
        "src/metabotyping_agentic/live_sources/motrpac_volcano_compare.py",
    }
)

# Import roots that can open a socket. Matched on the dotted prefix, so
# ``urllib.request`` matches ``from urllib.request import urlopen`` and
# ``import urllib.request`` alike.
NETWORK_CLIENT_MODULES = frozenset(
    {
        "aiohttp",
        "boto3",
        "ftplib",
        "http.client",
        "httpx",
        "paramiko",
        "requests",
        "smtplib",
        "socket",
        "socketserver",
        "urllib.request",
        "urllib3",
        "websockets",
        "xmlrpc.client",
    }
)


def _is_network_module(dotted_name: str) -> bool:
    return any(
        dotted_name == candidate or dotted_name.startswith(f"{candidate}.")
        for candidate in NETWORK_CLIENT_MODULES
    )


def _python_files() -> list[Path]:
    paths: list[Path] = []
    for directory in SCANNED_DIRECTORIES:
        paths.extend((ROOT / directory).rglob("*.py"))
    return sorted(path for path in paths if "__pycache__" not in path.parts)


def _network_imports(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.extend(alias.name for alias in node.names if _is_network_module(alias.name))
        elif isinstance(node, ast.ImportFrom):
            # ``from . import x`` has no module; relative imports cannot be a network client.
            if node.level or not node.module:
                continue
            if _is_network_module(node.module):
                found.append(node.module)
            else:
                found.extend(
                    f"{node.module}.{alias.name}"
                    for alias in node.names
                    if _is_network_module(f"{node.module}.{alias.name}")
                )
    return sorted(set(found))


class NetworkBoundaryTests(unittest.TestCase):
    def test_only_allowlisted_modules_import_network_clients(self):
        violations: dict[str, list[str]] = {}
        for path in _python_files():
            relative = path.relative_to(ROOT).as_posix()
            if relative in NETWORK_BOUNDARY_ALLOWLIST:
                continue
            imports = _network_imports(path)
            if imports:
                violations[relative] = imports

        self.assertEqual(
            violations,
            {},
            "network imports outside the declared allowlist; add the module to "
            "NETWORK_BOUNDARY_ALLOWLIST only as a reviewed change to CLAUDE.md",
        )

    def test_every_allowlisted_module_exists_and_still_needs_network_access(self):
        missing = sorted(
            relative
            for relative in NETWORK_BOUNDARY_ALLOWLIST
            if not (ROOT / relative).is_file()
        )
        self.assertEqual(missing, [], "allowlisted module no longer exists")

        unused = sorted(
            relative
            for relative in NETWORK_BOUNDARY_ALLOWLIST
            if not _network_imports(ROOT / relative)
        )
        self.assertEqual(
            unused,
            [],
            "allowlisted module no longer imports a network client; remove it from the allowlist",
        )

    def test_offline_pilot_modules_are_outside_the_allowlist(self):
        # The offline pilot must stay offline: none of the modules it imports may be
        # allowlisted, so a live adapter can never be pulled into a reproducible run.
        offline_entry_points = (
            "src/metabotyping_agentic/cli.py",
            "scripts/run_pilot.py",
            "src/metabotyping_agentic/reports/render.py",
            "src/metabotyping_agentic/evaluation/benchmark.py",
        )
        for relative in offline_entry_points:
            with self.subTest(module=relative):
                self.assertTrue((ROOT / relative).is_file())
                self.assertNotIn(relative, NETWORK_BOUNDARY_ALLOWLIST)
                self.assertEqual(_network_imports(ROOT / relative), [])

    def test_documented_allowlist_matches_the_enforced_allowlist(self):
        claude_md = (ROOT / "CLAUDE.md").read_text(encoding="utf-8")
        for relative in sorted(NETWORK_BOUNDARY_ALLOWLIST):
            with self.subTest(module=relative):
                self.assertIn(relative, claude_md)


if __name__ == "__main__":
    unittest.main()
