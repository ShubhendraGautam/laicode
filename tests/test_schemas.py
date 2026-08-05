from __future__ import annotations

import unittest
from pathlib import Path

from laicode.canonical import load_json_strict
from laicode.function_benchmark import (
    CASE_SET_SCHEMA_VERSION as FUNCTION_CASE_SET_SCHEMA_VERSION,
    EXPERIMENT_SCHEMA_VERSION as FUNCTION_EXPERIMENT_SCHEMA_VERSION,
    NATIVE_RECORD_SCHEMA_VERSION as FUNCTION_NATIVE_RECORD_SCHEMA_VERSION,
    RUN_RECORD_SCHEMA_VERSION as FUNCTION_RUN_RECORD_SCHEMA_VERSION,
    TASK_SCHEMA_VERSION as FUNCTION_TASK_SCHEMA_VERSION,
    TRACE_SCHEMA_VERSION as FUNCTION_TRACE_SCHEMA_VERSION,
    VALIDITY_SCHEMA_VERSION as FUNCTION_VALIDITY_SCHEMA_VERSION,
)
from laicode.function_language import (
    ENCODED_PROGRAM_SCHEMA_VERSION as ENCODED_FUNCTION_PROGRAM_SCHEMA_VERSION,
    PROGRAM_SCHEMA_VERSION as FUNCTION_PROGRAM_SCHEMA_VERSION,
    VOCABULARY_SCHEMA_VERSION as FUNCTION_VOCABULARY_SCHEMA_VERSION,
)
from laicode.function_synthesis import (
    EXPERIMENT_SCHEMA_VERSION as SYNTHESIS_EXPERIMENT_SCHEMA_VERSION,
    RUN_RECORD_SCHEMA_VERSION as SYNTHESIS_RUN_RECORD_SCHEMA_VERSION,
    registered_synthesis_tasks,
)


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_DIR = ROOT / "schemas"

# `function-language-defs` is a shared `$defs` bundle referenced by the others,
# so it carries no `schema_version` of its own.
SHARED_DEFS = "function-language-defs.v2.schema.json"


class SchemaArtifactTests(unittest.TestCase):
    def test_every_schema_is_strict_profile_json(self) -> None:
        paths = sorted(SCHEMA_DIR.glob("*.schema.json"))
        self.assertGreaterEqual(len(paths), 14)
        for path in paths:
            with self.subTest(path=path.name):
                document = load_json_strict(path.read_bytes())
                self.assertIsInstance(document, dict)

    def test_runtime_versions_match_machine_schema_constants(self) -> None:
        synthesis_task_version = registered_synthesis_tasks()[0].contract_document[
            "schema_version"
        ]
        expectations = {
            "function-program.v2.schema.json": FUNCTION_PROGRAM_SCHEMA_VERSION,
            "encoded-function-program.v2.schema.json": (
                ENCODED_FUNCTION_PROGRAM_SCHEMA_VERSION
            ),
            "function-vocabulary.v2.schema.json": FUNCTION_VOCABULARY_SCHEMA_VERSION,
            "function-task-contract.v2.schema.json": FUNCTION_TASK_SCHEMA_VERSION,
            "function-case-set.v2.schema.json": FUNCTION_CASE_SET_SCHEMA_VERSION,
            "function-language-experiment.v2.schema.json": (
                FUNCTION_EXPERIMENT_SCHEMA_VERSION
            ),
            "function-validity-report.v2.schema.json": FUNCTION_VALIDITY_SCHEMA_VERSION,
            "function-execution-trace.v2.schema.json": FUNCTION_TRACE_SCHEMA_VERSION,
            "function-language-run-report-record.v2.schema.json": (
                FUNCTION_RUN_RECORD_SCHEMA_VERSION
            ),
            "function-native-validity-report-record.v2.schema.json": (
                FUNCTION_NATIVE_RECORD_SCHEMA_VERSION
            ),
            "synthesis-experiment.v2.schema.json": SYNTHESIS_EXPERIMENT_SCHEMA_VERSION,
            "synthesis-run-report-record.v2.schema.json": (
                SYNTHESIS_RUN_RECORD_SCHEMA_VERSION
            ),
            "synthesis-task-contract.v2.schema.json": synthesis_task_version,
        }
        for name, expected in expectations.items():
            with self.subTest(schema=name):
                document = load_json_strict((SCHEMA_DIR / name).read_bytes())
                assert isinstance(document, dict)
                properties = document["properties"]
                assert isinstance(properties, dict)
                schema_version = properties["schema_version"]
                assert isinstance(schema_version, dict)
                self.assertEqual(schema_version["const"], expected)

    def test_every_versioned_schema_is_covered_by_a_runtime_constant(self) -> None:
        """A schema with no runtime constant behind it is an orphan artifact."""

        present = {
            path.name
            for path in SCHEMA_DIR.glob("*.schema.json")
            if path.name != SHARED_DEFS
        }
        covered = {
            "function-program.v2.schema.json",
            "encoded-function-program.v2.schema.json",
            "function-vocabulary.v2.schema.json",
            "function-task-contract.v2.schema.json",
            "function-case-set.v2.schema.json",
            "function-language-experiment.v2.schema.json",
            "function-validity-report.v2.schema.json",
            "function-execution-trace.v2.schema.json",
            "function-language-run-report-record.v2.schema.json",
            "function-native-validity-report-record.v2.schema.json",
            "synthesis-experiment.v2.schema.json",
            "synthesis-run-report-record.v2.schema.json",
            "synthesis-task-contract.v2.schema.json",
        }
        self.assertEqual(present, covered)

    def test_every_relative_schema_reference_resolves(self) -> None:
        def visit(value: object, *, owner: Path) -> None:
            if isinstance(value, dict):
                reference = value.get("$ref")
                if isinstance(reference, str) and not (
                    reference.startswith("#") or "://" in reference
                ):
                    target = reference.split("#", 1)[0]
                    self.assertTrue(
                        (owner.parent / target).is_file(),
                        f"{owner.name} has missing reference {reference}",
                    )
                for nested in value.values():
                    visit(nested, owner=owner)
            elif isinstance(value, list):
                for nested in value:
                    visit(nested, owner=owner)

        for path in sorted(SCHEMA_DIR.glob("*.schema.json")):
            document = load_json_strict(path.read_bytes())
            visit(document, owner=path)


if __name__ == "__main__":
    unittest.main()
