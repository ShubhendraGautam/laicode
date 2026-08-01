from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from laicode.canonical import canonical_json_bytes, load_json_strict
from laicode.prototype import PrototypeError, replay_prototype, run_prototype
from laicode.provenance import AppendOnlyLedger

from .test_kernel import CONTRACT_PATH


class EndToEndPrototypeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temporary = tempfile.TemporaryDirectory()
        cls.bundle = Path(cls.temporary.name) / "run"
        cls.report = run_prototype(CONTRACT_PATH, cls.bundle)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temporary.cleanup()

    def test_complete_run_selects_lfu_without_deployment(self) -> None:
        self.assertEqual(self.report.selected_strategy_id, "lfu")
        self.assertEqual(self.report.audit_primary_improvement_ppm, 31_250)
        self.assertEqual(self.report.prospective_primary_improvement_ppm, -187_500)
        self.assertEqual(len(self.report.all_candidate_ids), 3)
        self.assertEqual(len(self.report.all_artifact_ids), 3)
        self.assertEqual(len(self.report.comparison_decision_ids), 2)
        self.assertEqual(len(self.report.all_trace_ids), 10)
        self.assertEqual(len(self.report.all_evaluation_ids), 13)
        self.assertEqual(self.report.budget["evaluator_queries_total"], 34)
        self.assertEqual(self.report.budget["meta_evaluator_queries"], 8)

        record = load_json_strict((self.bundle / "run-report.json").read_bytes())
        assert isinstance(record, dict)
        report = record["report"]
        assert isinstance(report, dict)
        self.assertFalse(report["deployment_performed"])
        self.assertFalse(report["research_audit_used_for_selection"])
        self.assertEqual(record["report_id"], self.report.report_id)

    def test_evaluator_gate_precedes_candidate_search_in_ledger(self) -> None:
        events = AppendOnlyLedger(self.bundle / "ledger.jsonl").read_all()
        event_types = [event.event_type for event in events]

        self.assertLess(
            event_types.index("manifest_frozen"),
            event_types.index("evaluator_validated"),
        )
        self.assertLess(
            event_types.index("evaluator_validated"),
            event_types.index("candidate_proposed"),
        )
        self.assertLess(
            event_types.index("decision_frozen"),
            event_types.index("research_audit_consumed"),
        )
        self.assertEqual(event_types[-1], "run_completed")
        self.assertEqual(events[-1].event_id, self.report.final_event_id)

    def test_offline_decision_contains_no_audit_evidence(self) -> None:
        decision = load_json_strict(
            (self.bundle / "offline-decision.json").read_bytes()
        )
        assert isinstance(decision, dict)

        self.assertEqual(decision["research_audit_evaluation_ids"], [])
        self.assertEqual(decision["deployment_authority"], "D0_offline_only")
        self.assertEqual(decision["selected_strategy_id"], "lfu")

    def test_bundle_replays_byte_for_byte(self) -> None:
        replay = replay_prototype(self.bundle)

        self.assertTrue(replay.to_document()["exact_match"])
        self.assertEqual(replay.source_report_id, self.report.report_id)
        self.assertEqual(replay.replay_report_id, self.report.report_id)
        self.assertGreaterEqual(replay.files_verified, 40)

    def test_evaluation_payload_tampering_breaks_replay(self) -> None:
        tampered = Path(self.temporary.name) / "tampered"
        shutil.copytree(self.bundle, tampered)
        evaluation_path = sorted((tampered / "evaluations").glob("*.json"))[0]
        document = load_json_strict(evaluation_path.read_bytes())
        assert isinstance(document, dict)
        metrics = document["metrics"]
        assert isinstance(metrics, dict)
        metrics["misses"] = int(metrics["misses"]) + 1
        evaluation_path.write_bytes(canonical_json_bytes(document) + b"\n")

        with self.assertRaisesRegex(PrototypeError, "replay mismatch"):
            replay_prototype(tampered)

    def test_existing_output_directory_is_refused(self) -> None:
        existing = Path(self.temporary.name) / "existing"
        existing.mkdir()

        with self.assertRaisesRegex(PrototypeError, "already exists"):
            run_prototype(CONTRACT_PATH, existing)

    def test_expired_contract_is_refused_before_output_creation(self) -> None:
        document = load_json_strict(CONTRACT_PATH.read_bytes())
        assert isinstance(document, dict)
        document["expires_at"] = "2000-01-01T00:00:00Z"
        contract_path = Path(self.temporary.name) / "expired-contract.json"
        contract_path.write_bytes(canonical_json_bytes(document) + b"\n")
        output = Path(self.temporary.name) / "expired-run"

        with self.assertRaisesRegex(PrototypeError, "contract expired"):
            run_prototype(contract_path, output)

        self.assertFalse(output.exists())

    def test_candidate_churn_limit_is_enforced(self) -> None:
        document = load_json_strict(CONTRACT_PATH.read_bytes())
        assert isinstance(document, dict)
        comparison = document["comparison"]
        assert isinstance(comparison, dict)
        comparison["candidate_churn_limit"] = 2
        contract_path = Path(self.temporary.name) / "low-churn-contract.json"
        contract_path.write_bytes(canonical_json_bytes(document) + b"\n")
        output = Path(self.temporary.name) / "low-churn-run"

        with self.assertRaisesRegex(PrototypeError, "candidate budget exhausted"):
            run_prototype(contract_path, output)


if __name__ == "__main__":
    unittest.main()
