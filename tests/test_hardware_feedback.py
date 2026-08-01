from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from laicode.canonical import canonical_json_bytes, content_id, load_json_strict
from laicode.hardware_feedback import (
    _aggregate_documents,
    replay_hardware_feedback_study,
    resolve_target_vocabulary,
    run_hardware_feedback_study,
)
from laicode.language_benchmark import _load_machine_state, prepare_comparator_package
from laicode.machine_experiment import MachineExperimentError, run_machine_experiment


@unittest.skipUnless(
    shutil.which("cc") and shutil.which("python3"),
    "required feedback toolchains are unavailable",
)
class HardwareFeedbackStudyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temporary = tempfile.TemporaryDirectory()
        cls.root = Path(cls.temporary.name)
        cls.machine = cls.root / "machine"
        cls.package = cls.root / "package"
        cls.study = cls.root / "study"
        run_machine_experiment(cls.machine)
        prepare_comparator_package(
            cls.machine,
            cls.package,
            scale=1,
            trials=3,
            warmups=1,
            startup_trials=3,
        )
        cls.report = run_hardware_feedback_study(
            cls.machine,
            cls.package,
            cls.study,
            sessions=3,
            minimum_improvement_ppm=0,
            required_win_rate_ppm=500_000,
        )

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temporary.cleanup()

    def _study_document(self, relative: str):
        return load_json_strict((self.study / relative).read_bytes())

    def test_study_freezes_offline_target_profile_without_deployment(self) -> None:
        self.assertEqual(self.report.session_count, 3)
        self.assertFalse(self.report.deployment_performed)
        self.assertEqual(self.report.selected_cycles_by_pit["shift_no_reuse"], 0)
        profile = self._study_document("target-profile.json")
        decision = self._study_document("lifecycle-decision.json")
        assert isinstance(profile, dict) and isinstance(decision, dict)

        shift = profile["profiles_by_pit"]["shift_no_reuse"]
        self.assertEqual(shift["active_entry_ids"], [])
        self.assertEqual(len(shift["retired_entry_ids"]), 2)
        self.assertTrue(shift["fallback_to_primitives"])
        self.assertTrue(shift["retirement_is_profile_exclusion_not_deletion"])
        self.assertFalse(decision["primitive_semantics_changed"])
        self.assertFalse(decision["vocabulary_entries_deleted"])
        self.assertFalse(decision["new_entries_generated_from_host_timing"])
        self.assertFalse(decision["deployment_performed"])

        _, _, _, vocabularies = _load_machine_state(self.machine)
        for pit_id, selected_cycle in self.report.selected_cycles_by_pit.items():
            resolved = resolve_target_vocabulary(profile, pit_id, vocabularies)
            self.assertEqual(resolved, vocabularies[selected_cycle])

    def test_profile_resolver_rejects_unknown_pit(self) -> None:
        profile = self._study_document("target-profile.json")
        assert isinstance(profile, dict)
        _, _, _, vocabularies = _load_machine_state(self.machine)

        with self.assertRaisesRegex(MachineExperimentError, "has no pit"):
            resolve_target_vocabulary(profile, "unclassified", vocabularies)

    def test_decision_replays_exactly_without_rerunning_timings(self) -> None:
        replay = replay_hardware_feedback_study(
            self.machine,
            self.package,
            self.study,
        )

        self.assertEqual(replay.source_report_id, self.report.report_id)
        self.assertEqual(replay.replay_report_id, self.report.report_id)
        self.assertEqual(replay.session_reports_verified, 3)
        archived_session_files = sum(
            1
            + len(list((session / "raw").glob("*.txt")))
            + len(list((session / "artifacts").iterdir()))
            for session in (self.study / "sessions").iterdir()
        )
        self.assertEqual(replay.files_verified, 5 + archived_session_files)
        self.assertFalse(replay.to_document()["host_timings_rerun"])

    def test_raw_session_tampering_breaks_decision_replay(self) -> None:
        tampered = self.root / "tampered-raw"
        shutil.copytree(self.study, tampered)
        raw = next((tampered / "sessions" / "session-001" / "raw").glob("*.txt"))
        value = raw.read_text(encoding="utf-8")
        raw.write_text(value.replace("ns=", "ns=1,"), encoding="utf-8")

        with self.assertRaisesRegex(MachineExperimentError, "raw evidence"):
            replay_hardware_feedback_study(self.machine, self.package, tampered)

    def test_session_schema_substitution_breaks_decision_replay(self) -> None:
        tampered = self.root / "tampered-session-schema"
        shutil.copytree(self.study, tampered)
        path = tampered / "sessions" / "session-001" / "benchmark-report.json"
        record = load_json_strict(path.read_bytes())
        assert isinstance(record, dict)
        record["schema_version"] = "DifferentHostReportRecordV0"
        path.write_bytes(canonical_json_bytes(record) + b"\n")

        with self.assertRaisesRegex(MachineExperimentError, "unknown schema"):
            replay_hardware_feedback_study(self.machine, self.package, tampered)

    def test_target_mismatch_is_rejected_before_decision_replay(self) -> None:
        mismatched = self.root / "mismatched-target"
        shutil.copytree(self.study, mismatched)
        path = mismatched / "study-manifest.json"
        manifest = load_json_strict(path.read_bytes())
        assert isinstance(manifest, dict)
        target = manifest["target"]
        assert isinstance(target, dict)
        target["cpu_model"] = "different-target"
        manifest["target_id"] = content_id(target)
        path.write_bytes(canonical_json_bytes(manifest) + b"\n")

        with self.assertRaisesRegex(MachineExperimentError, "target differs"):
            replay_hardware_feedback_study(self.machine, self.package, mismatched)

    def test_even_session_count_is_refused_before_output_creation(self) -> None:
        output = self.root / "even-sessions"
        with self.assertRaisesRegex(MachineExperimentError, "odd integer"):
            run_hardware_feedback_study(
                self.machine,
                self.package,
                output,
                sessions=2,
            )
        self.assertFalse(output.exists())

    def test_registered_gates_choose_gain_and_reject_no_reuse_synthetically(self) -> None:
        manifest = self._study_document("study-manifest.json")
        comparator = load_json_strict(
            (self.package / "benchmark-manifest.json").read_bytes()
        )
        assert isinstance(manifest, dict) and isinstance(comparator, dict)
        _, _, _, vocabularies = _load_machine_state(self.machine)

        def session() -> dict:
            adapters = []
            for cycle, median in ((0, 1_000), (1, 700), (2, 500)):
                adapters.append(
                    {
                        "status": "complete",
                        "adapter_id": f"laicode_cycle_{cycle}",
                        "pits": {
                            pit: {"steady_state": {"median_ns": median}}
                            for pit in (
                                "reuse_holdout",
                                "audit_transfer",
                                "shift_no_reuse",
                            )
                        },
                    }
                )
            return {"adapter_results": adapters}

        aggregate, profile, _, _ = _aggregate_documents(
            manifest,
            comparator,
            (session(), session(), session()),
            vocabularies,
        )

        self.assertEqual(profile["profiles_by_pit"]["reuse_holdout"]["selected_cycle"], 2)
        self.assertEqual(profile["profiles_by_pit"]["audit_transfer"]["selected_cycle"], 2)
        self.assertEqual(profile["profiles_by_pit"]["shift_no_reuse"]["selected_cycle"], 0)
        shift_rows = aggregate["pit_aggregates"]["shift_no_reuse"]["cycle_evidence"]
        self.assertIn(
            "no_deterministic_token_reduction",
            shift_rows[2]["eligibility_reasons"],
        )


if __name__ == "__main__":
    unittest.main()
