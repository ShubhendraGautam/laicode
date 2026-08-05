from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from laicode.canonical import load_json_strict
from laicode.function_benchmark import (
    build_function_vocabularies,
    registered_function_tasks,
)
from laicode.function_language import (
    EMPTY_FUNCTION_VOCABULARY,
    FunctionProgram,
    execute_program,
    validate_program,
)
from laicode.function_synthesis import (
    HELDOUT_CASES,
    TRAINING_CASES,
    SynthesisError,
    build_program,
    registered_synthesis_tasks,
    replay_synthesis_experiment,
    run_synthesis_experiment,
    search_pools,
    synthesize,
)


# Small enough for a unit suite: the controls and the two cheap treatment tasks
# resolve, while the expensive treatment tasks stop at the budget.
TEST_BUDGET = 200_000


def _vocabularies():
    return build_function_vocabularies(registered_function_tasks())


class SynthesisSearchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.learned = _vocabularies()[-1]
        cls.tasks = {item.task_id: item for item in registered_synthesis_tasks()}
        # Warm the memoized pools once; rebuilding them per test dominates runtime.
        search_pools(EMPTY_FUNCTION_VOCABULARY)
        search_pools(cls.learned)

    def _run(self, task_id: str, arm: str):
        vocabulary = self.learned if arm == "learned" else EMPTY_FUNCTION_VOCABULARY
        return synthesize(self.tasks[task_id], vocabulary, budget=TEST_BUDGET, arm=arm)

    def test_every_registered_task_has_an_independent_oracle(self) -> None:
        for task in registered_synthesis_tasks():
            with self.subTest(task=task.task_id):
                for nums, target in TRAINING_CASES + HELDOUT_CASES:
                    self.assertIsInstance(task.oracle(nums, target), int)

    def test_control_tasks_are_solved_identically_by_both_arms(self) -> None:
        for task_id in ("sum_all", "count_all", "sum_shifted"):
            with self.subTest(task=task_id):
                primitive = self._run(task_id, "primitive")
                learned = self._run(task_id, "learned")
                self.assertEqual(primitive.outcome, "solved")
                self.assertEqual(learned.outcome, "solved")
                self.assertTrue(primitive.generalizes)
                self.assertTrue(learned.generalizes)
                # Same program: a control cannot benefit from the vocabulary.
                self.assertEqual(primitive.program, learned.program)

    def test_a_larger_vocabulary_costs_search_on_control_tasks(self) -> None:
        """The vocabulary tax. Without it, a favourable result is unfalsifiable."""
        for task_id in ("sum_all", "count_all", "sum_shifted"):
            with self.subTest(task=task_id):
                primitive = self._run(task_id, "primitive")
                learned = self._run(task_id, "learned")
                self.assertGreater(learned.candidates_evaluated, primitive.candidates_evaluated)

    def test_learned_vocabulary_cuts_search_on_treatment_tasks(self) -> None:
        for task_id in ("sum_positive_part", "max_shifted_value"):
            with self.subTest(task=task_id):
                primitive = self._run(task_id, "primitive")
                learned = self._run(task_id, "learned")
                self.assertEqual(primitive.outcome, "solved")
                self.assertEqual(learned.outcome, "solved")
                self.assertTrue(learned.generalizes)
                self.assertLess(learned.candidates_evaluated, primitive.candidates_evaluated // 10)

    def test_synthesized_programs_are_valid_kernel_programs(self) -> None:
        result = self._run("sum_positive_part", "learned")
        assert result.program is not None
        validate_program(result.program, self.learned)
        self.assertTrue(result.kernel_verified)
        for nums, target in TRAINING_CASES + HELDOUT_CASES:
            actual = execute_program(result.program, nums, target, self.learned).value
            self.assertEqual(actual, self.tasks["sum_positive_part"].oracle(nums, target))

    def test_learned_solutions_carry_real_vocabulary_entry_identities(self) -> None:
        result = self._run("max_shifted_value", "learned")
        assert result.program is not None
        document = result.program.to_document()
        entry_ids = {item.entry_id for item in self.learned.entries}
        found = set()

        def walk(value: object) -> None:
            if isinstance(value, dict):
                if value.get("op") == "learned_call":
                    found.add(value["entry_id"])
                for nested in value.values():
                    walk(nested)
            elif isinstance(value, list):
                for nested in value:
                    walk(nested)

        walk(document)
        self.assertTrue(found)
        self.assertTrue(found <= entry_ids)

    def test_reported_program_round_trips_through_the_transport(self) -> None:
        result = self._run("sum_shifted", "primitive")
        assert result.program is not None
        restored = FunctionProgram.from_document(result.program.to_document())
        self.assertEqual(restored.program_id, result.program.program_id)

    def test_budget_is_reported_rather_than_silently_exceeded(self) -> None:
        result = synthesize(
            self.tasks["sum_absolute_deviation"], EMPTY_FUNCTION_VOCABULARY, budget=5_000, arm="primitive"
        )
        self.assertEqual(result.outcome, "budget")
        self.assertEqual(result.candidates_evaluated, 5_000)
        self.assertIsNone(result.program)

    def test_skeleton_builds_a_valid_program(self) -> None:
        pools = search_pools(EMPTY_FUNCTION_VOCABULARY)
        node = pools[2][0]
        program = build_program("skeleton_probe", node.statements())
        validate_program(program)
        self.assertEqual(program.entry.name, "skeleton_probe")


class SynthesisBundleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temporary = tempfile.TemporaryDirectory()
        cls.root = Path(cls.temporary.name)
        cls.bundle = cls.root / "bundle"
        cls.report = run_synthesis_experiment(cls.bundle, budget=TEST_BUDGET)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temporary.cleanup()

    def _document(self, relative: str):
        return load_json_strict((self.bundle / relative).read_bytes())

    def test_truncated_or_decoy_ratios_are_marked_as_lower_bounds(self) -> None:
        report = self._document("run-report.json")["report"]
        for row in report["results"]:
            with self.subTest(task=row["task_id"]):
                truthful = (
                    row["primitive"]["outcome"] == "solved"
                    and row["primitive"]["generalizes"] is True
                )
                self.assertEqual(row["ratio_is_lower_bound"], not truthful)

    def test_report_separates_treatment_from_control(self) -> None:
        report = self._document("run-report.json")["report"]
        families = {row["task_id"]: row["family"] for row in report["results"]}
        self.assertEqual(families["sum_absolute_deviation"], "treatment")
        self.assertEqual(families["sum_all"], "control")
        # 1_000_000 ppm is parity: treatment must beat it, control must not.
        self.assertGreater(report["treatment_median_ratio_ppm"], 1_000_000)
        self.assertLess(report["control_median_ratio_ppm"], 1_000_000)

    def test_every_reported_solution_is_kernel_verified(self) -> None:
        report = self._document("run-report.json")["report"]
        self.assertTrue(report["all_reported_solutions_kernel_verified"])
        for row in report["results"]:
            for arm in ("primitive", "learned"):
                if row[arm]["outcome"] == "solved":
                    self.assertTrue(row[arm]["kernel_verified"])

    def test_limitations_name_the_hand_written_vocabulary(self) -> None:
        report = self._document("run-report.json")["report"]
        self.assertIn(
            "vocabulary_was_learned_from_hand_written_programs_not_synthesized_ones",
            report["limitations"],
        )

    def test_bundle_replays_byte_for_byte(self) -> None:
        replay = replay_synthesis_experiment(self.bundle, budget=TEST_BUDGET)
        self.assertEqual(replay.source_report_id, self.report.report_id)
        self.assertEqual(replay.replay_report_id, self.report.report_id)
        self.assertGreater(replay.files_verified, 0)

    def test_tampering_breaks_replay(self) -> None:
        tampered = self.root / "tampered"
        shutil.copytree(self.bundle, tampered)
        path = tampered / "results" / "sum_all" / "primitive.lai"
        path.write_text(path.read_text(encoding="utf-8") + "\n", encoding="utf-8")
        with self.assertRaisesRegex(SynthesisError, "replay mismatch"):
            replay_synthesis_experiment(tampered, budget=TEST_BUDGET)


if __name__ == "__main__":
    unittest.main()
