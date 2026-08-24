import os
import re
import shutil
import tempfile
import unittest
from pathlib import Path

from metabotyping_agentic.cli import run_pilot_command

ROOT = Path(__file__).resolve().parents[1]
COPIED_INPUT_ROOT = Path("data/examples")
ISO_TIMESTAMP = re.compile(rb"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}")


def _run_isolated_pilot(workspace: Path) -> dict[str, bytes]:
    shutil.copytree(ROOT / "data/examples", workspace / "data/examples")
    previous_cwd = Path.cwd()
    try:
        os.chdir(workspace)
        run_pilot_command(out="reports")
    finally:
        os.chdir(previous_cwd)

    artifacts: dict[str, bytes] = {}
    for path in sorted(workspace.rglob("*")):
        relative_path = path.relative_to(workspace)
        if path.is_file() and not relative_path.is_relative_to(COPIED_INPUT_ROOT):
            artifacts[relative_path.as_posix()] = path.read_bytes()
    return artifacts


class PilotReproducibilityTests(unittest.TestCase):
    def test_two_isolated_runs_have_identical_relative_files_and_bytes(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            first_root = temp_root / "first"
            second_root = temp_root / "second"
            first_root.mkdir()
            second_root.mkdir()

            first = _run_isolated_pilot(first_root)
            second = _run_isolated_pilot(second_root)

            self.assertEqual(sorted(first), sorted(second))
            self.assertEqual(first, second)
            self.assertTrue(first)

            forbidden_paths = (
                str(temp_root).encode(),
                str(first_root).encode(),
                str(second_root).encode(),
            )
            for relative_path, payload in first.items():
                with self.subTest(path=relative_path):
                    self.assertFalse(ISO_TIMESTAMP.search(payload))
                    self.assertNotIn(b'"generated_at"', payload)
                    self.assertNotIn(b'"generated_utc"', payload)
                    for forbidden_path in forbidden_paths:
                        self.assertNotIn(forbidden_path, payload)


if __name__ == "__main__":
    unittest.main()
