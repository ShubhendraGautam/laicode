from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from laicode.canonical import canonical_json_bytes, load_json_strict
from laicode.machine_experiment import (
    MachineExperimentError,
    replay_machine_experiment,
    run_machine_experiment,
)
from laicode.machine_hardware import measure_machine_hardware


class MachineExperimentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temporary = tempfile.TemporaryDirectory()
        cls.bundle = Path(cls.temporary.name) / "run"
        cls.report = run_machine_experiment(cls.bundle)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temporary.cleanup()

    def _document(self, relative: str):
        return load_json_strict((self.bundle / relative).read_bytes())

    def test_learned_vocabulary_wins_matched_protected_comparison(self) -> None:
        costs = self.report.operational_total_units

        self.assertEqual(self.report.selected_variant, "learned")
        self.assertTrue(self.report.central_hypothesis_passed)
        self.assertLess(costs["learned"], costs["fixed_human"])
        self.assertLess(costs["learned"], costs["primitive"])
        self.assertLess(costs["learned"], costs["seeded_random"])

        vocabularies = {
            name: self._document(f"vocabularies/{name}.json")
            for name in ("learned", "fixed_human", "seeded_random")
        }
        lengths = []
        for vocabulary in vocabularies.values():
            assert isinstance(vocabulary, dict)
            entries = vocabulary["entries"]
            assert isinstance(entries, list)
            lengths.append(sorted(len(entry["lowering"]) for entry in entries))
        self.assertEqual(lengths, [[3, 6], [3, 6], [3, 6]])

    def test_persisted_vocabulary_causally_changes_cycle_two_proposal(self) -> None:
        cycle = self._document("cycles/cycle-2.json")
        assert isinstance(cycle, dict)

        self.assertTrue(cycle["persistent_vocabulary_changed_proposal"])
        self.assertNotEqual(
            cycle["selected_lowering"],
            cycle["counterfactual_empty_vocabulary_lowering"],
        )
        self.assertLess(cycle["output_encoded_tokens"], cycle["input_encoded_tokens"])

    def test_decision_is_frozen_without_audit_payload(self) -> None:
        decision = self._document("offline-decision.json")
        audit = self._document("audit-report.json")
        assert isinstance(decision, dict) and isinstance(audit, dict)

        self.assertEqual(decision["research_audit_evaluation_ids"], [])
        self.assertFalse(decision["research_audit_payload_used"])
        self.assertFalse(audit["audit_used_for_selection"])
        self.assertEqual(audit["audit_winner"], "learned")

    def test_negative_transfer_is_retained(self) -> None:
        self.assertGreater(
            self.report.future_total_units["learned"],
            self.report.future_total_units["primitive"],
        )
        record = self._document("run-report.json")
        assert isinstance(record, dict)
        report = record["report"]
        assert isinstance(report, dict)
        self.assertTrue(report["future_negative_transfer_retained"])
        self.assertFalse(report["deployment_performed"])

    def test_bundle_replays_byte_for_byte(self) -> None:
        replay = replay_machine_experiment(self.bundle)

        self.assertEqual(replay.source_report_id, self.report.report_id)
        self.assertEqual(replay.replay_report_id, self.report.report_id)
        self.assertEqual(replay.files_verified, 38)

    def test_tampering_breaks_replay(self) -> None:
        tampered = Path(self.temporary.name) / "tampered"
        shutil.copytree(self.bundle, tampered)
        path = tampered / "cycles" / "cycle-2.json"
        value = load_json_strict(path.read_bytes())
        assert isinstance(value, dict)
        value["output_encoded_tokens"] = int(value["output_encoded_tokens"]) + 1
        path.write_bytes(canonical_json_bytes(value) + b"\n")

        with self.assertRaisesRegex(MachineExperimentError, "replay mismatch"):
            replay_machine_experiment(tampered)

    def test_existing_output_is_refused(self) -> None:
        with self.assertRaisesRegex(MachineExperimentError, "already exists"):
            run_machine_experiment(self.bundle)


@unittest.skipUnless(shutil.which("cc"), "a C compiler is required")
class MachineHardwareAdapterTests(unittest.TestCase):
    def test_generated_native_runner_preserves_semantics_and_measures(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bundle = root / "run"
            output = root / "hardware"
            run_machine_experiment(bundle)
            report = measure_machine_hardware(
                bundle,
                output,
                trials=3,
                scale=20,
            )

            self.assertTrue(report.checksums_match)
            self.assertGreater(report.primitive_median_ns, 0)
            self.assertGreater(report.learned_median_ns, 0)
            measurement = load_json_strict((output / "measurement.json").read_bytes())
            assert isinstance(measurement, dict)
            payload = measurement["report"]
            assert isinstance(payload, dict)
            result = payload["result"]
            assert isinstance(result, dict)
            self.assertFalse(result["used_for_deterministic_identity_or_selection"])
            self.assertTrue((output / "measurement.c").is_file())
            self.assertTrue((output / "measurement-runner").is_file())


if __name__ == "__main__":
    unittest.main()
