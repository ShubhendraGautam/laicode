from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from laicode.cache import generate_trace
from laicode.canonical import canonical_json_bytes, load_json_strict
from laicode.isolation import IsolationError
from laicode.prototype import run_prototype
from laicode.provenance import AppendOnlyLedger
from laicode.shadow import ShadowError, replay_shadow, run_shadow

from .test_kernel import CONTRACT_PATH


class D1ShadowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temporary = tempfile.TemporaryDirectory()
        cls.root = Path(cls.temporary.name)
        cls.source = cls.root / "source"
        run_prototype(CONTRACT_PATH, cls.source)
        cls.trace = generate_trace(
            "recency_shift",
            401,
            event_count=256,
            name="d1-regression-trace",
        )
        cls.bundle = cls.root / "shadow"
        cls.report = run_shadow(cls.source, cls.trace, cls.bundle)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temporary.cleanup()

    def test_regressing_challenger_is_revoked_without_served_effects(self) -> None:
        self.assertEqual(self.report.disposition, "revoked_regression")
        self.assertEqual(self.report.revoked_at_event_count, 192)
        self.assertTrue(self.report.checkpoint_ids)

        record = load_json_strict((self.bundle / "shadow-report.json").read_bytes())
        assert isinstance(record, dict)
        report = record["report"]
        assert isinstance(report, dict)
        self.assertEqual(
            report["served_artifact_id"],
            report["champion_artifact_id"],
        )
        self.assertFalse(report["challenger_served_effects"])
        self.assertFalse(report["deployment_performed"])
        self.assertFalse(report["promotion_performed"])
        self.assertTrue(report["last_known_good_preserved"])

    def test_lease_is_external_bounded_and_nonextendable(self) -> None:
        lease = load_json_strict((self.bundle / "lease.json").read_bytes())
        assert isinstance(lease, dict)

        self.assertEqual(lease["mode"], "D1_counterfactual_stateful_shadow")
        self.assertFalse(lease["candidate_may_extend_lease"])
        self.assertFalse(lease["served_effects_authorized"])
        self.assertEqual(lease["maximum_events"], 256)
        limits = lease["worker_limits"]
        assert isinstance(limits, dict)
        self.assertEqual(limits["processes"], 1)
        self.assertGreater(limits["memory_bytes"], 0)

    def test_ledger_records_revocation_before_recovery(self) -> None:
        events = AppendOnlyLedger(self.bundle / "ledger.jsonl").read_all()
        event_types = [event.event_type for event in events]

        self.assertLess(
            event_types.index("shadow_lease_issued"),
            event_types.index("shadow_lease_revoked"),
        )
        self.assertLess(
            event_types.index("shadow_lease_revoked"),
            event_types.index("shadow_recovery_verified"),
        )
        self.assertEqual(event_types[-1], "shadow_run_completed")
        self.assertEqual(events[-1].event_id, self.report.final_event_id)

    def test_shadow_bundle_replays_byte_for_byte(self) -> None:
        replay = replay_shadow(self.bundle)

        self.assertEqual(replay.source_report_id, self.report.report_id)
        self.assertEqual(replay.replay_report_id, self.report.report_id)
        self.assertGreaterEqual(replay.files_verified, 60)

    def test_lease_tampering_is_detected_before_replay(self) -> None:
        tampered = self.root / "tampered-shadow"
        shutil.copytree(self.bundle, tampered)
        lease_path = tampered / "lease.json"
        lease = load_json_strict(lease_path.read_bytes())
        assert isinstance(lease, dict)
        triggers = lease["rollback_triggers"]
        assert isinstance(triggers, dict)
        triggers["miss_ratio_regression_ppm"] = 999_999
        lease_path.write_bytes(canonical_json_bytes(lease) + b"\n")

        with self.assertRaisesRegex(ShadowError, "lease identity mismatch"):
            replay_shadow(tampered)

    def test_nonregressing_shadow_expires_without_promotion(self) -> None:
        trace = generate_trace(
            "scan_resistance",
            409,
            event_count=128,
            name="d1-nonregression-trace",
        )
        output = self.root / "nonregressing-shadow"
        report = run_shadow(self.source, trace, output)

        self.assertEqual(report.disposition, "lease_expired_no_promotion")
        self.assertIsNone(report.revoked_at_event_count)
        record = load_json_strict((output / "shadow-report.json").read_bytes())
        assert isinstance(record, dict)
        payload = record["report"]
        assert isinstance(payload, dict)
        self.assertFalse(payload["promotion_performed"])

    def test_short_trace_is_refused_without_creating_output(self) -> None:
        trace = generate_trace("mixed_bursts", 419, event_count=32)
        output = self.root / "short-shadow"

        with self.assertRaisesRegex(ShadowError, "shorter than"):
            run_shadow(self.source, trace, output)

        self.assertFalse(output.exists())

    def test_worker_failure_revokes_lease_and_leaves_no_complete_report(self) -> None:
        trace = generate_trace("mixed_bursts", 421, event_count=64)
        output = self.root / "failed-worker-shadow"

        with patch(
            "laicode.shadow.evaluate_artifact_isolated",
            side_effect=IsolationError("injected worker failure"),
        ):
            with self.assertRaisesRegex(ShadowError, "champion remained unchanged"):
                run_shadow(self.source, trace, output)

        self.assertFalse((output / "shadow-report.json").exists())
        event_types = [
            event.event_type
            for event in AppendOnlyLedger(output / "ledger.jsonl").read_all()
        ]
        self.assertIn("incident", event_types)
        self.assertEqual(event_types[-1], "shadow_lease_revoked")


if __name__ == "__main__":
    unittest.main()
