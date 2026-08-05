from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"
FULL_SHA_ACTION = re.compile(
    r"^\s*uses:\s+[^@\s]+@([0-9a-f]{40})(?:\s+#.*)?$",
    re.MULTILINE,
)
ANY_ACTION = re.compile(r"^\s*uses:\s+", re.MULTILINE)


class ContinuousIntegrationConfigurationTests(unittest.TestCase):
    def _workflow(self, name: str) -> str:
        return (WORKFLOWS / name).read_text(encoding="utf-8")

    def test_actions_are_immutable_and_workflows_are_read_only(self) -> None:
        for name in ("ci.yml", "nightly.yml"):
            with self.subTest(workflow=name):
                workflow = self._workflow(name)
                action_count = len(ANY_ACTION.findall(workflow))
                pinned_count = len(FULL_SHA_ACTION.findall(workflow))
                self.assertGreater(action_count, 0)
                self.assertEqual(pinned_count, action_count)
                self.assertIn("permissions:\n  contents: read", workflow)
                self.assertIn("persist-credentials: false", workflow)
                self.assertNotIn("pull_request_target", workflow)

    def test_ci_covers_supported_python_versions_and_full_suite(self) -> None:
        workflow = self._workflow("ci.yml")
        self.assertIn('          - "3.10"', workflow)
        self.assertIn('          - "3.14"', workflow)
        self.assertIn("python -m unittest discover -v", workflow)
        self.assertIn("timeout-minutes: 20", workflow)

    def test_nightly_is_scheduled_replayable_and_retained(self) -> None:
        workflow = self._workflow("nightly.yml")
        self.assertIn('cron: "17 2 * * *"', workflow)
        self.assertIn("workflow_dispatch:", workflow)
        self.assertIn("smoke-function-language", workflow)
        self.assertIn("smoke-function-synthesis", workflow)
        self.assertIn("if: always()", workflow)
        self.assertIn("retention-days: 30", workflow)
        self.assertIn("timeout-minutes: 45", workflow)


if __name__ == "__main__":
    unittest.main()
