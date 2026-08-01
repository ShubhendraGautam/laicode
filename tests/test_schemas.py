from __future__ import annotations

import unittest
from pathlib import Path

from laicode.algorithm_benchmark import (
    CASE_SET_SCHEMA_VERSION as ALGORITHM_CASE_SET_SCHEMA_VERSION,
    EXPERIMENT_SCHEMA_VERSION as ALGORITHM_EXPERIMENT_SCHEMA_VERSION,
    NATIVE_RECORD_SCHEMA_VERSION as ALGORITHM_NATIVE_RECORD_SCHEMA_VERSION,
    RUN_RECORD_SCHEMA_VERSION as ALGORITHM_RUN_RECORD_SCHEMA_VERSION,
    TASK_SCHEMA_VERSION as ALGORITHM_TASK_SCHEMA_VERSION,
    TRACE_SCHEMA_VERSION as ALGORITHM_TRACE_SCHEMA_VERSION,
    VALIDITY_SCHEMA_VERSION as ALGORITHM_VALIDITY_SCHEMA_VERSION,
)
from laicode.algorithm_language import (
    ENCODED_PROGRAM_SCHEMA_VERSION as ENCODED_ALGORITHM_PROGRAM_SCHEMA_VERSION,
    PROGRAM_SCHEMA_VERSION as ALGORITHM_PROGRAM_SCHEMA_VERSION,
    VOCABULARY_SCHEMA_VERSION as ALGORITHM_VOCABULARY_SCHEMA_VERSION,
)
from laicode.collection_benchmark import (
    CASE_SET_SCHEMA_VERSION as COLLECTION_CASE_SET_SCHEMA_VERSION,
    EXPERIMENT_SCHEMA_VERSION as COLLECTION_EXPERIMENT_SCHEMA_VERSION,
    NATIVE_RECORD_SCHEMA_VERSION as COLLECTION_NATIVE_RECORD_SCHEMA_VERSION,
    RUN_RECORD_SCHEMA_VERSION as COLLECTION_RUN_RECORD_SCHEMA_VERSION,
    TASK_SCHEMA_VERSION as COLLECTION_TASK_SCHEMA_VERSION,
    TRACE_SCHEMA_VERSION as COLLECTION_TRACE_SCHEMA_VERSION,
    VALIDITY_SCHEMA_VERSION as COLLECTION_VALIDITY_SCHEMA_VERSION,
)
from laicode.collection_language import (
    ENCODED_PROGRAM_SCHEMA_VERSION as ENCODED_COLLECTION_PROGRAM_SCHEMA_VERSION,
    PROGRAM_SCHEMA_VERSION as COLLECTION_PROGRAM_SCHEMA_VERSION,
    VOCABULARY_SCHEMA_VERSION as COLLECTION_VOCABULARY_SCHEMA_VERSION,
)
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
from laicode.canonical import load_json_strict
from laicode.cache import (
    SIMULATION_SCHEMA_VERSION,
    SNAPSHOT_SCHEMA_VERSION,
    TRACE_SCHEMA_VERSION,
)
from laicode.contracts import SCHEMA_VERSION as CONTRACT_SCHEMA_VERSION
from laicode.evaluation import (
    AUDIT_REPORT_SCHEMA_VERSION,
    EVALUATOR_META_REPORT_SCHEMA_VERSION,
    EVIDENCE_CATALOG_SCHEMA_VERSION,
    PARTITION_EVALUATION_SCHEMA_VERSION,
    PROMOTION_DECISION_SCHEMA_VERSION,
)
from laicode.kernel import (
    ACTION_RESULT_SCHEMA_VERSION,
    ACTION_SCHEMA_VERSION,
    ARTIFACT_SCHEMA_VERSION,
    PROGRAM_SCHEMA_VERSION,
    PROGRAM_STATE_SCHEMA_VERSION,
)
from laicode.hardware_feedback import (
    AGGREGATE_SCHEMA_VERSION as HARDWARE_FEEDBACK_AGGREGATE_SCHEMA_VERSION,
    DECISION_SCHEMA_VERSION as HARDWARE_LIFECYCLE_DECISION_SCHEMA_VERSION,
    RUN_RECORD_SCHEMA_VERSION as HARDWARE_FEEDBACK_RUN_RECORD_SCHEMA_VERSION,
    STUDY_MANIFEST_SCHEMA_VERSION as HARDWARE_FEEDBACK_STUDY_SCHEMA_VERSION,
    TARGET_PROFILE_SCHEMA_VERSION as HARDWARE_TARGET_PROFILE_SCHEMA_VERSION,
    TARGET_SCHEMA_VERSION as MACHINE_HARDWARE_TARGET_SCHEMA_VERSION,
)
from laicode.language_benchmark import (
    BENCHMARK_MANIFEST_SCHEMA_VERSION,
    HOST_RECORD_SCHEMA_VERSION as COMPARATOR_HOST_RECORD_SCHEMA_VERSION,
    PACKAGE_RECORD_SCHEMA_VERSION as COMPARATOR_PACKAGE_RECORD_SCHEMA_VERSION,
    REFERENCE_RESULTS_SCHEMA_VERSION,
)
from laicode.machine_language import PIPELINE_SCHEMA_VERSION, VOCABULARY_SCHEMA_VERSION
from laicode.machine_experiment import (
    CORPUS_SCHEMA_VERSION,
    CYCLE_SCHEMA_VERSION,
    EVALUATION_SCHEMA_VERSION as MACHINE_EVALUATION_SCHEMA_VERSION,
    RUN_REPORT_RECORD_SCHEMA_VERSION as MACHINE_RUN_REPORT_RECORD_SCHEMA_VERSION,
)
from laicode.machine_hardware import HARDWARE_RECORD_SCHEMA_VERSION
from laicode.prototype import (
    EXPERIMENT_MANIFEST_SCHEMA_VERSION,
    IMPLEMENTATION_MANIFEST_SCHEMA_VERSION,
    OFFLINE_DECISION_SCHEMA_VERSION,
    RUN_REPORT_RECORD_SCHEMA_VERSION,
)
from laicode.shadow import (
    SHADOW_CHECKPOINT_SCHEMA_VERSION,
    SHADOW_LEASE_SCHEMA_VERSION,
    SHADOW_REPORT_RECORD_SCHEMA_VERSION,
)
from laicode.worker import (
    WORKER_REQUEST_SCHEMA_VERSION,
    WORKER_RESPONSE_SCHEMA_VERSION,
)
from laicode.provenance import (
    CANDIDATE_RECORD_SCHEMA_VERSION,
    LEDGER_RECORD_SCHEMA_VERSION,
)


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_DIR = ROOT / "schemas"


class SchemaArtifactTests(unittest.TestCase):
    def test_every_schema_is_strict_profile_json(self) -> None:
        paths = sorted(SCHEMA_DIR.glob("*.schema.json"))
        self.assertGreaterEqual(len(paths), 27)
        for path in paths:
            with self.subTest(path=path.name):
                document = load_json_strict(path.read_bytes())
                self.assertIsInstance(document, dict)

    def test_runtime_versions_match_machine_schema_constants(self) -> None:
        expectations = {
            "cache-policy-ir.v0.schema.json": PROGRAM_SCHEMA_VERSION,
            "cache-policy-program-state.v0.schema.json": PROGRAM_STATE_SCHEMA_VERSION,
            "cache-policy-action-result.v0.schema.json": ACTION_RESULT_SCHEMA_VERSION,
            "cache-policy-artifact.v0.schema.json": ARTIFACT_SCHEMA_VERSION,
            "cache-trace.v0.schema.json": TRACE_SCHEMA_VERSION,
            "cache-snapshot.v0.schema.json": SNAPSHOT_SCHEMA_VERSION,
            "cache-simulation-result.v0.schema.json": SIMULATION_SCHEMA_VERSION,
            "cache-partition-evaluation.v0.schema.json": (
                PARTITION_EVALUATION_SCHEMA_VERSION
            ),
            "cache-evidence-catalog.v0.schema.json": EVIDENCE_CATALOG_SCHEMA_VERSION,
            "cache-promotion-decision.v0.schema.json": PROMOTION_DECISION_SCHEMA_VERSION,
            "cache-audit-report.v0.schema.json": AUDIT_REPORT_SCHEMA_VERSION,
            "evaluator-meta-test-report.v0.schema.json": (
                EVALUATOR_META_REPORT_SCHEMA_VERSION
            ),
            "candidate-record.v0.schema.json": CANDIDATE_RECORD_SCHEMA_VERSION,
            "ledger-record.v0.schema.json": LEDGER_RECORD_SCHEMA_VERSION,
            "cache-experiment-manifest.v0.schema.json": (
                EXPERIMENT_MANIFEST_SCHEMA_VERSION
            ),
            "implementation-manifest.v0.schema.json": (
                IMPLEMENTATION_MANIFEST_SCHEMA_VERSION
            ),
            "offline-selection-decision.v0.schema.json": (
                OFFLINE_DECISION_SCHEMA_VERSION
            ),
            "prototype-run-report-record.v0.schema.json": (
                RUN_REPORT_RECORD_SCHEMA_VERSION
            ),
            "cache-worker-request.v0.schema.json": WORKER_REQUEST_SCHEMA_VERSION,
            "cache-worker-response.v0.schema.json": WORKER_RESPONSE_SCHEMA_VERSION,
            "cache-shadow-lease.v0.schema.json": SHADOW_LEASE_SCHEMA_VERSION,
            "cache-shadow-checkpoint.v0.schema.json": (
                SHADOW_CHECKPOINT_SCHEMA_VERSION
            ),
            "cache-shadow-run-report-record.v0.schema.json": (
                SHADOW_REPORT_RECORD_SCHEMA_VERSION
            ),
            "evolution-contract.v0.schema.json": CONTRACT_SCHEMA_VERSION,
            "word-pipeline.v0.schema.json": PIPELINE_SCHEMA_VERSION,
            "machine-vocabulary.v0.schema.json": VOCABULARY_SCHEMA_VERSION,
            "machine-program-corpus.v0.schema.json": CORPUS_SCHEMA_VERSION,
            "machine-learning-cycle.v0.schema.json": CYCLE_SCHEMA_VERSION,
            "machine-partition-evaluation.v0.schema.json": (
                MACHINE_EVALUATION_SCHEMA_VERSION
            ),
            "machine-experiment-run-report-record.v0.schema.json": (
                MACHINE_RUN_REPORT_RECORD_SCHEMA_VERSION
            ),
            "machine-host-measurement-record.v0.schema.json": (
                HARDWARE_RECORD_SCHEMA_VERSION
            ),
            "language-comparator-manifest.v0.schema.json": (
                BENCHMARK_MANIFEST_SCHEMA_VERSION
            ),
            "language-comparator-reference-results.v0.schema.json": (
                REFERENCE_RESULTS_SCHEMA_VERSION
            ),
            "language-comparator-package-record.v0.schema.json": (
                COMPARATOR_PACKAGE_RECORD_SCHEMA_VERSION
            ),
            "language-comparator-host-report-record.v0.schema.json": (
                COMPARATOR_HOST_RECORD_SCHEMA_VERSION
            ),
            "machine-hardware-target.v0.schema.json": (
                MACHINE_HARDWARE_TARGET_SCHEMA_VERSION
            ),
            "hardware-feedback-study-manifest.v0.schema.json": (
                HARDWARE_FEEDBACK_STUDY_SCHEMA_VERSION
            ),
            "hardware-feedback-aggregate.v0.schema.json": (
                HARDWARE_FEEDBACK_AGGREGATE_SCHEMA_VERSION
            ),
            "hardware-vocabulary-target-profile.v0.schema.json": (
                HARDWARE_TARGET_PROFILE_SCHEMA_VERSION
            ),
            "hardware-vocabulary-lifecycle-decision.v0.schema.json": (
                HARDWARE_LIFECYCLE_DECISION_SCHEMA_VERSION
            ),
            "hardware-feedback-run-report-record.v0.schema.json": (
                HARDWARE_FEEDBACK_RUN_RECORD_SCHEMA_VERSION
            ),
            "algorithm-program.v0.schema.json": ALGORITHM_PROGRAM_SCHEMA_VERSION,
            "encoded-algorithm-program.v0.schema.json": (
                ENCODED_ALGORITHM_PROGRAM_SCHEMA_VERSION
            ),
            "algorithm-vocabulary.v0.schema.json": (
                ALGORITHM_VOCABULARY_SCHEMA_VERSION
            ),
            "algorithm-task-contract.v0.schema.json": (
                ALGORITHM_TASK_SCHEMA_VERSION
            ),
            "algorithm-case-set.v0.schema.json": (
                ALGORITHM_CASE_SET_SCHEMA_VERSION
            ),
            "algorithm-language-experiment.v0.schema.json": (
                ALGORITHM_EXPERIMENT_SCHEMA_VERSION
            ),
            "algorithm-validity-report.v0.schema.json": (
                ALGORITHM_VALIDITY_SCHEMA_VERSION
            ),
            "algorithm-execution-trace.v0.schema.json": (
                ALGORITHM_TRACE_SCHEMA_VERSION
            ),
            "algorithm-language-run-report-record.v0.schema.json": (
                ALGORITHM_RUN_RECORD_SCHEMA_VERSION
            ),
            "algorithm-native-validity-report-record.v0.schema.json": (
                ALGORITHM_NATIVE_RECORD_SCHEMA_VERSION
            ),
            "collection-program.v1.schema.json": COLLECTION_PROGRAM_SCHEMA_VERSION,
            "encoded-collection-program.v1.schema.json": (
                ENCODED_COLLECTION_PROGRAM_SCHEMA_VERSION
            ),
            "collection-vocabulary.v1.schema.json": (
                COLLECTION_VOCABULARY_SCHEMA_VERSION
            ),
            "collection-task-contract.v1.schema.json": (
                COLLECTION_TASK_SCHEMA_VERSION
            ),
            "collection-case-set.v1.schema.json": (
                COLLECTION_CASE_SET_SCHEMA_VERSION
            ),
            "collection-language-experiment.v1.schema.json": (
                COLLECTION_EXPERIMENT_SCHEMA_VERSION
            ),
            "collection-validity-report.v1.schema.json": (
                COLLECTION_VALIDITY_SCHEMA_VERSION
            ),
            "collection-execution-trace.v1.schema.json": (
                COLLECTION_TRACE_SCHEMA_VERSION
            ),
            "collection-language-run-report-record.v1.schema.json": (
                COLLECTION_RUN_RECORD_SCHEMA_VERSION
            ),
            "collection-native-validity-report-record.v1.schema.json": (
                COLLECTION_NATIVE_RECORD_SCHEMA_VERSION
            ),
            "function-program.v2.schema.json": FUNCTION_PROGRAM_SCHEMA_VERSION,
            "encoded-function-program.v2.schema.json": (
                ENCODED_FUNCTION_PROGRAM_SCHEMA_VERSION
            ),
            "function-vocabulary.v2.schema.json": (
                FUNCTION_VOCABULARY_SCHEMA_VERSION
            ),
            "function-task-contract.v2.schema.json": (
                FUNCTION_TASK_SCHEMA_VERSION
            ),
            "function-case-set.v2.schema.json": (
                FUNCTION_CASE_SET_SCHEMA_VERSION
            ),
            "function-language-experiment.v2.schema.json": (
                FUNCTION_EXPERIMENT_SCHEMA_VERSION
            ),
            "function-validity-report.v2.schema.json": (
                FUNCTION_VALIDITY_SCHEMA_VERSION
            ),
            "function-execution-trace.v2.schema.json": (
                FUNCTION_TRACE_SCHEMA_VERSION
            ),
            "function-language-run-report-record.v2.schema.json": (
                FUNCTION_RUN_RECORD_SCHEMA_VERSION
            ),
            "function-native-validity-report-record.v2.schema.json": (
                FUNCTION_NATIVE_RECORD_SCHEMA_VERSION
            ),
        }
        for filename, expected in expectations.items():
            with self.subTest(filename=filename):
                document = load_json_strict((SCHEMA_DIR / filename).read_bytes())
                assert isinstance(document, dict)
                properties = document["properties"]
                assert isinstance(properties, dict)
                schema_version = properties["schema_version"]
                assert isinstance(schema_version, dict)
                self.assertEqual(schema_version["const"], expected)

        action = load_json_strict(
            (SCHEMA_DIR / "cache-policy-action.v0.schema.json").read_bytes()
        )
        assert isinstance(action, dict)
        variants = action["oneOf"]
        assert isinstance(variants, list)
        for variant in variants:
            assert isinstance(variant, dict)
            properties = variant["properties"]
            assert isinstance(properties, dict)
            schema_version = properties["schema_version"]
            assert isinstance(schema_version, dict)
            self.assertEqual(schema_version["const"], ACTION_SCHEMA_VERSION)

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
