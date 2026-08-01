from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from laicode.algorithm_benchmark import (
    AlgorithmExperimentError,
    registered_algorithm_tasks,
    replay_algorithm_experiment,
    smoke_algorithm_language,
)
from laicode.algorithm_language import (
    I64,
    AlgorithmLanguageError,
    AlgorithmProgram,
    AlgorithmVocabulary,
    Assign,
    Expression,
    If,
    Let,
    Return,
    EMPTY_ALGORITHM_VOCABULARY,
    encode_program,
    execute_program,
    extend_vocabulary,
    intrinsic_uses,
    learn_expression_intrinsic,
    validate_program,
)
from laicode.canonical import load_json_strict


class AlgorithmLanguageKernelTests(unittest.TestCase):
    def test_registered_programs_match_all_independent_oracles(self) -> None:
        for task in registered_algorithm_tasks().values():
            with self.subTest(task=task.task_id):
                validate_program(task.program)
                for case in task.cases:
                    result = execute_program(task.program, case.nums, case.target)
                    self.assertEqual(result.value, case.expected)

    def test_array_bounds_are_checked(self) -> None:
        program = AlgorithmProgram(
            "bounds_probe",
            I64,
            (Return(Expression("get", (Expression("var", name="nums"), Expression("const", value=1)))),),
        )
        with self.assertRaisesRegex(AlgorithmLanguageError, "outside the input"):
            execute_program(program, (7,), 0)

    def test_nested_declarations_are_rejected(self) -> None:
        program = AlgorithmProgram(
            "nested_declaration",
            I64,
            (
                Let("value", Expression("const", value=0)),
                If(
                    Expression(
                        "eq",
                        (
                            Expression("var", name="value"),
                            Expression("const", value=0),
                        ),
                    ),
                    (Let("hidden", Expression("const", value=1)),),
                    (),
                ),
                Return(Expression("var", name="value")),
            ),
        )
        with self.assertRaisesRegex(AlgorithmLanguageError, "top-level only"):
            validate_program(program)

    def test_cross_task_learning_is_transparent_and_transfers(self) -> None:
        tasks = registered_algorithm_tasks()
        first_training = [tasks["count_target"], tasks["linear_search_first"]]
        first = learn_expression_intrinsic(
            [task.program for task in first_training],
            EMPTY_ALGORITHM_VOCABULARY,
            evidence_catalog_id="sha256:" + "1" * 64,
            cycle=1,
        )
        self.assertEqual(first.lowering.op, "eq")
        self.assertEqual(first.training_task_ids, ("count_target", "linear_search_first"))
        vocabulary = extend_vocabulary(EMPTY_ALGORITHM_VOCABULARY, first)
        encoded = encode_program(tasks["binary_search"].program, vocabulary)
        self.assertIn(first.entry_id, intrinsic_uses(encoded))

        case = tasks["binary_search"].cases[0]
        core = execute_program(tasks["binary_search"].program, case.nums, case.target)
        learned = execute_program(encoded, case.nums, case.target, vocabulary)
        self.assertEqual(core.value, learned.value)
        self.assertLess(learned.dispatches, core.dispatches)

    def test_assignment_cannot_change_a_local_type(self) -> None:
        program = AlgorithmProgram(
            "type_probe",
            I64,
            (
                Let("value", Expression("const", value=0)),
                Assign(
                    "value",
                    Expression("eq", (Expression("const", value=0), Expression("const", value=0))),
                ),
                Return(Expression("var", name="value")),
            ),
        )
        with self.assertRaisesRegex(AlgorithmLanguageError, "type differs"):
            validate_program(program)


@unittest.skipUnless(shutil.which("cc"), "a C compiler is required")
class AlgorithmLanguageExperimentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temporary = tempfile.TemporaryDirectory()
        cls.root = Path(cls.temporary.name)
        cls.report, cls.replay, cls.native = smoke_algorithm_language(cls.root / "result")
        cls.bundle = cls.root / "result" / "bundle"

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temporary.cleanup()

    def _document(self, relative: str):
        return load_json_strict((self.bundle / relative).read_bytes())

    def test_complete_study_grows_and_validates_the_language(self) -> None:
        self.assertTrue(self.report.all_valid)
        self.assertEqual(self.report.task_count, 7)
        self.assertEqual(self.report.case_count, 224)
        self.assertEqual(self.report.cycle_count, 3)
        run_record = self._document("run-report.json")
        assert isinstance(run_record, dict)
        report = run_record["report"]
        self.assertEqual(
            [row["entry_count"] for row in report["cycle_results"]],
            [0, 1, 2],
        )
        self.assertEqual(
            [row["cases_passed"] for row in report["cycle_results"]],
            [224, 224, 224],
        )

    def test_platform_style_tasks_gain_dispatch_without_semantic_change(self) -> None:
        run_record = self._document("run-report.json")
        assert isinstance(run_record, dict)
        transfer = run_record["report"]["platform_style_transfer"]
        self.assertEqual(
            set(transfer),
            {"binary_search", "maximum_subarray", "two_sum_indices"},
        )
        for task_id, evidence in transfer.items():
            with self.subTest(task=task_id):
                self.assertTrue(evidence["all_cycles_valid"])
                self.assertGreater(evidence["dispatch_reduction"], 0)

    def test_generated_language_source_c_and_trace_are_inspectable(self) -> None:
        learned_source = (
            self.bundle / "cycles" / "cycle-2" / "maximum_subarray" / "program.lai"
        ).read_text(encoding="utf-8")
        generated_c = (
            self.bundle / "cycles" / "cycle-2" / "maximum_subarray" / "program.c"
        ).read_text(encoding="utf-8")
        trace = self._document("cycles/cycle-2/maximum_subarray/trace.json")
        self.assertIn("op_", learned_source)
        self.assertIn("learned op_", generated_c)
        self.assertIn("lai_run", generated_c)
        self.assertGreaterEqual(len(trace["events"]), 3)
        self.assertEqual(trace["events"][-1]["event"], "return")

    def test_saved_language_artifacts_load_and_execute_independently(self) -> None:
        vocabulary_document = self._document("vocabularies/cycle-2.json")
        program_document = self._document(
            "cycles/cycle-2/binary_search/encoded-program.json"
        )
        assert isinstance(vocabulary_document, dict)
        assert isinstance(program_document, dict)
        vocabulary = AlgorithmVocabulary.from_document(vocabulary_document)
        program = AlgorithmProgram.from_document(program_document)
        task = registered_algorithm_tasks()["binary_search"]
        case = task.cases[5]

        result = execute_program(program, case.nums, case.target, vocabulary)

        self.assertEqual(result.value, case.expected)
        self.assertEqual(vocabulary.vocabulary_id, self.report.final_vocabulary_id)

    def test_native_c_validates_every_final_task_and_platform_cycle(self) -> None:
        self.assertTrue(self.native.all_valid)
        self.assertEqual(self.native.translations_passed, 13)
        self.assertEqual(self.native.cases_passed, 416)

    def test_bundle_replays_byte_for_byte(self) -> None:
        self.assertEqual(self.replay.source_report_id, self.report.report_id)
        self.assertEqual(self.replay.replay_report_id, self.report.report_id)
        self.assertEqual(self.replay.files_verified, 138)

    def test_tampering_breaks_replay(self) -> None:
        tampered = self.root / "tampered"
        shutil.copytree(self.bundle, tampered)
        path = tampered / "cycles" / "cycle-2" / "binary_search" / "program.lai"
        path.write_text(path.read_text(encoding="utf-8") + "\n", encoding="utf-8")
        with self.assertRaisesRegex(AlgorithmExperimentError, "replay mismatch"):
            replay_algorithm_experiment(tampered)


if __name__ == "__main__":
    unittest.main()
