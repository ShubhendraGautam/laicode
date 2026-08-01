from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from laicode.canonical import load_json_strict
from laicode.language_benchmark import (
    prepare_comparator_package,
    replay_comparator_package,
    run_comparator_benchmark,
)
from laicode.machine_experiment import MachineExperimentError, run_machine_experiment


class LanguageComparatorPackageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temporary = tempfile.TemporaryDirectory()
        cls.root = Path(cls.temporary.name)
        cls.machine = cls.root / "machine"
        cls.package = cls.root / "package"
        run_machine_experiment(cls.machine)
        cls.package_report = prepare_comparator_package(
            cls.machine,
            cls.package,
            scale=1,
            trials=3,
            warmups=1,
            startup_trials=3,
        )

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temporary.cleanup()

    def _document(self, relative: str):
        return load_json_strict((self.package / relative).read_bytes())

    def test_manifest_separates_learning_curve_from_ecosystem_ranking(self) -> None:
        manifest = self._document("benchmark-manifest.json")
        assert isinstance(manifest, dict)

        self.assertEqual(len(manifest["pits"]), 3)
        self.assertEqual(len(manifest["adapters"]), 7)
        self.assertEqual(
            manifest["claim_separation"]["learning_curve"],
            "compare_laicode_cycles_only",
        )
        evolution = manifest["language_evolution"]
        self.assertEqual([item["entry_count"] for item in evolution], [0, 1, 2])
        reuse_tokens = [
            item["weighted_dispatch_tokens_by_pit"]["reuse_holdout"]
            for item in evolution
        ]
        shift_tokens = [
            item["weighted_dispatch_tokens_by_pit"]["shift_no_reuse"]
            for item in evolution
        ]
        self.assertGreater(reuse_tokens[0], reuse_tokens[1])
        self.assertGreater(reuse_tokens[1], reuse_tokens[2])
        self.assertEqual(shift_tokens, [shift_tokens[0]] * 3)

    def test_package_has_cross_language_sources_and_reference_checksums(self) -> None:
        expected = {
            "c-direct.c",
            "javascript-direct.js",
            "laicode-cycle-0.c",
            "laicode-cycle-1.c",
            "laicode-cycle-2.c",
            "python-direct.py",
        }
        self.assertEqual(
            {path.name for path in (self.package / "sources").iterdir()},
            expected,
        )
        references = self._document("reference-results.json")
        assert isinstance(references, dict)
        results = references["results_by_pit"]
        assert isinstance(results, dict)
        self.assertEqual(set(results), {"reuse_holdout", "audit_transfer", "shift_no_reuse"})
        for result in results.values():
            self.assertRegex(result["checksum"], r"^[0-9a-f]{16}$")
            self.assertGreater(result["pipeline_invocations"], 0)

    def test_package_replays_byte_for_byte(self) -> None:
        replay = replay_comparator_package(self.machine, self.package)

        self.assertEqual(replay.package_id, self.package_report.package_id)
        self.assertEqual(replay.files_verified, 9)

    def test_source_tampering_breaks_replay(self) -> None:
        tampered = self.root / "tampered"
        shutil.copytree(self.package, tampered)
        source = tampered / "sources" / "c-direct.c"
        source.write_text(source.read_text(encoding="utf-8") + "\n", encoding="utf-8")

        with self.assertRaisesRegex(MachineExperimentError, "replay mismatch"):
            replay_comparator_package(self.machine, tampered)

    def test_invalid_trial_protocol_is_refused(self) -> None:
        with self.assertRaisesRegex(MachineExperimentError, "odd integer"):
            prepare_comparator_package(
                self.machine,
                self.root / "invalid",
                trials=2,
            )


@unittest.skipUnless(
    shutil.which("cc") and shutil.which("python3"),
    "required comparator toolchains are unavailable",
)
class LanguageComparatorHostTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temporary = tempfile.TemporaryDirectory()
        cls.root = Path(cls.temporary.name)
        cls.machine = cls.root / "machine"
        cls.package = cls.root / "package"
        cls.output = cls.root / "host"
        run_machine_experiment(cls.machine)
        prepare_comparator_package(
            cls.machine,
            cls.package,
            scale=1,
            trials=3,
            warmups=1,
            startup_trials=3,
        )
        cls.host_report = run_comparator_benchmark(
            cls.machine,
            cls.package,
            cls.output,
        )
        cls.record = load_json_strict(
            (cls.output / "benchmark-report.json").read_bytes()
        )

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temporary.cleanup()

    def test_every_completed_adapter_matches_all_reference_checksums(self) -> None:
        self.assertTrue(self.host_report.correctness_passed)
        self.assertTrue(
            {"laicode_cycle_0", "laicode_cycle_1", "laicode_cycle_2", "python_3_direct"}
            .issubset(self.host_report.completed_adapters)
        )
        assert isinstance(self.record, dict)
        report = self.record["report"]
        assert isinstance(report, dict)
        for adapter in report["adapter_results"]:
            if adapter["status"] != "complete":
                continue
            for pit in adapter["pits"].values():
                self.assertTrue(pit["checksum_matches_reference"])
                self.assertEqual(len(pit["steady_state"]["raw_ns"]), 3)
                self.assertGreater(pit["maximum_resident_kibibytes"], 0)

    def test_report_retains_learning_curve_and_descriptive_ranking(self) -> None:
        assert isinstance(self.record, dict)
        report = self.record["report"]
        assert isinstance(report, dict)

        self.assertEqual(set(report["learning_curve_by_pit"]), {
            "reuse_holdout", "audit_transfer", "shift_no_reuse"
        })
        for curve in report["learning_curve_by_pit"].values():
            self.assertEqual([item["cycle"] for item in curve], [0, 1, 2])
        interpretation = report["interpretation"]
        self.assertTrue(interpretation["ecosystem_ranking_is_descriptive_only"])
        self.assertTrue(interpretation["early_losses_and_non_monotonic_results_retained"])

    def test_build_startup_size_and_variability_are_reported_separately(self) -> None:
        assert isinstance(self.record, dict)
        report = self.record["report"]
        assert isinstance(report, dict)
        complete = [
            item for item in report["adapter_results"] if item["status"] == "complete"
        ]
        for adapter in complete:
            self.assertGreater(adapter["source_bytes"], 0)
            self.assertGreater(adapter["runnable_artifact_bytes"], 0)
            self.assertEqual(len(adapter["cold_start"]["raw_ns"]), 3)
            self.assertIn(adapter["build_kind"], {
                "ahead_of_time_c11", "interpreted_no_ahead_of_time_build"
            })
            if adapter["build_kind"] == "ahead_of_time_c11":
                self.assertEqual(len(adapter["build_measurement"]["raw_ns"]), 3)
                self.assertEqual(adapter["build_ns"], adapter["build_measurement"]["median_ns"])
            else:
                self.assertIsNone(adapter["build_measurement"])
            for pit in adapter["pits"].values():
                summary = pit["steady_state"]
                self.assertGreaterEqual(summary["mad_parts_per_million"], 0)
                self.assertGreaterEqual(summary["spread_parts_per_million"], 0)


if __name__ == "__main__":
    unittest.main()
