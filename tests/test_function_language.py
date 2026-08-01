from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from laicode.canonical import load_json_strict
from laicode.function_benchmark import (
    FunctionExperimentError,
    registered_function_tasks,
    replay_function_experiment,
    smoke_function_language,
)
from laicode.function_language import (
    EMPTY_FUNCTION_VOCABULARY,
    ENTRY_PARAMETERS,
    I64,
    Assign,
    Expression,
    ForRange,
    FunctionDef,
    FunctionLanguageError,
    FunctionProgram,
    FunctionVocabulary,
    If,
    Parameter,
    Return,
    call_depth,
    encode_program,
    execute_program,
    extend_vocabulary,
    learn_function_abstraction,
    learned_definition,
    learned_uses,
    validate_program,
)


def _var(name: str) -> Expression:
    return Expression("var", name=name)


def _const(value: int) -> Expression:
    return Expression("const", value=value)


def _call(name: str, *arguments: Expression) -> Expression:
    return Expression("call", tuple(arguments), name=name)


def _identity(name: str) -> FunctionDef:
    return FunctionDef(name, (Parameter("x", I64),), I64, (Return(_var("x")),))


def _entry(task_id: str, *body: object) -> FunctionDef:
    return FunctionDef(task_id, ENTRY_PARAMETERS, I64, tuple(body))  # type: ignore[arg-type]


class FunctionLanguageKernelTests(unittest.TestCase):
    def test_registered_programs_match_independent_oracles(self) -> None:
        for task in registered_function_tasks().values():
            with self.subTest(task=task.task_id):
                validate_program(task.program)
                for case in task.cases:
                    actual = execute_program(task.program, case.nums, case.target).value
                    self.assertEqual(actual, case.expected)

    def test_recursion_is_rejected_by_forward_only_resolution(self) -> None:
        recursive = FunctionDef(
            "countdown",
            (Parameter("x", I64),),
            I64,
            (
                If(
                    Expression("gt", (_var("x"), _const(0))),
                    (Return(_call("countdown", Expression("sub", (_var("x"), _const(1))))),),
                    (),
                ),
                Return(_var("x")),
            ),
        )
        program = FunctionProgram("recursion_probe", (recursive, _entry("recursion_probe", Return(_call("countdown", _var("target"))))))
        with self.assertRaisesRegex(FunctionLanguageError, "not callable here"):
            validate_program(program)

    def test_mutual_recursion_is_rejected(self) -> None:
        first = FunctionDef("ping", (Parameter("x", I64),), I64, (Return(_call("pong", _var("x"))),))
        second = FunctionDef("pong", (Parameter("x", I64),), I64, (Return(_call("ping", _var("x"))),))
        program = FunctionProgram("mutual_probe", (first, second, _entry("mutual_probe", Return(_call("ping", _var("target"))))))
        with self.assertRaisesRegex(FunctionLanguageError, "not callable here"):
            validate_program(program)

    def test_call_depth_beyond_the_kernel_limit_is_rejected(self) -> None:
        functions = [_identity("level_0")]
        for level in range(1, 5):
            functions.append(
                FunctionDef(f"level_{level}", (Parameter("x", I64),), I64, (Return(_call(f"level_{level - 1}", _var("x"))),))
            )
        program = FunctionProgram("depth_probe", (*functions, _entry("depth_probe", Return(_call("level_4", _var("target"))))))
        with self.assertRaisesRegex(FunctionLanguageError, "call depth exceeds"):
            validate_program(program)

    def test_bounded_call_depth_is_accepted_and_reported(self) -> None:
        functions = [_identity("level_0")]
        for level in range(1, 3):
            functions.append(
                FunctionDef(f"level_{level}", (Parameter("x", I64),), I64, (Return(_call(f"level_{level - 1}", _var("x"))),))
            )
        program = FunctionProgram("depth_ok_probe", (*functions, _entry("depth_ok_probe", Return(_call("level_2", _var("target"))))))
        validate_program(program)
        self.assertEqual(call_depth(program), 4)
        self.assertEqual(execute_program(program, (), 11).value, 11)

    def test_unreachable_functions_are_rejected(self) -> None:
        program = FunctionProgram(
            "dead_probe",
            (_identity("unused"), _entry("dead_probe", Return(_var("target")))),
        )
        with self.assertRaisesRegex(FunctionLanguageError, "never called from the entry point"):
            validate_program(program)

    def test_call_arguments_are_statically_typed(self) -> None:
        program = FunctionProgram(
            "mistyped_probe",
            (_identity("double"), _entry("mistyped_probe", Return(_call("double", _var("nums"))))),
        )
        with self.assertRaisesRegex(FunctionLanguageError, "is mistyped"):
            validate_program(program)

    def test_every_function_must_end_with_its_only_top_level_return(self) -> None:
        program = FunctionProgram(
            "fallthrough_probe",
            (_entry("fallthrough_probe", If(Expression("gt", (_var("target"), _const(0))), (Return(_const(1)),), ())),),
        )
        with self.assertRaisesRegex(FunctionLanguageError, "must end with a return"):
            validate_program(program)

    def test_growth_requires_cross_task_evidence_and_transfers(self) -> None:
        tasks = registered_function_tasks()
        first_tasks = [tasks["sum_absolute"], tasks["count_large_absolute"]]
        first = learn_function_abstraction(
            [task.program for task in first_tasks],
            EMPTY_FUNCTION_VOCABULARY,
            evidence_catalog_id="sha256:" + "1" * 64,
            cycle=1,
        )
        self.assertEqual(first.kind, "abs_value")
        self.assertEqual(first.training_task_ids, ("count_large_absolute", "sum_absolute"))
        vocabulary = extend_vocabulary(EMPTY_FUNCTION_VOCABULARY, first)
        encoded = encode_program(tasks["sum_absolute_deviation"].program, vocabulary)
        self.assertTrue(learned_uses(encoded))
        self.assertLess(encoded.definition_statements, tasks["sum_absolute_deviation"].program.definition_statements)
        case = tasks["sum_absolute_deviation"].cases[5]
        core = execute_program(tasks["sum_absolute_deviation"].program, case.nums, case.target)
        learned = execute_program(encoded, case.nums, case.target, vocabulary)
        self.assertEqual(core.value, learned.value)
        self.assertEqual(core.dispatches, learned.dispatches)

    def test_a_single_task_abstraction_is_not_learned(self) -> None:
        tasks = registered_function_tasks()
        with self.assertRaisesRegex(FunctionLanguageError, "requires at least two tasks"):
            learn_function_abstraction(
                [tasks["sum_absolute"].program],
                EMPTY_FUNCTION_VOCABULARY,
                evidence_catalog_id="sha256:" + "2" * 64,
                cycle=1,
            )

    def test_conflicting_definitions_under_one_name_are_not_learned(self) -> None:
        genuine = learned_definition("abs_value")
        impostor = FunctionDef("abs_value", (Parameter("x", I64),), I64, (Return(_var("x")),))
        first = FunctionProgram("first_task", (genuine, _entry("first_task", Return(_call("abs_value", _var("target"))))))
        second = FunctionProgram("second_task", (impostor, _entry("second_task", Return(_call("abs_value", _var("target"))))))
        with self.assertRaisesRegex(FunctionLanguageError, "no cross-task abstraction"):
            learn_function_abstraction(
                [first, second],
                EMPTY_FUNCTION_VOCABULARY,
                evidence_catalog_id="sha256:" + "3" * 64,
                cycle=1,
            )

    def test_the_input_array_cannot_be_assigned(self) -> None:
        program = FunctionProgram(
            "input_mutation_probe",
            (_entry("input_mutation_probe", Assign("nums", _const(1)), Return(_var("target"))),),
        )
        with self.assertRaisesRegex(FunctionLanguageError, "assignment type differs"):
            validate_program(program)

    def test_returning_from_a_loop_is_rejected(self) -> None:
        program = FunctionProgram(
            "loop_return_probe",
            (
                _entry(
                    "loop_return_probe",
                    ForRange("i", _const(0), Expression("len", (_var("nums"),)), (Return(_var("i")),)),
                    Return(_const(0)),
                ),
            ),
        )
        with self.assertRaisesRegex(FunctionLanguageError, "must not return from a loop"):
            validate_program(program)

    def test_learned_entries_keep_a_transparent_definition(self) -> None:
        tasks = registered_function_tasks()
        entry = learn_function_abstraction(
            [tasks["sum_absolute"].program, tasks["count_large_absolute"].program],
            EMPTY_FUNCTION_VOCABULARY,
            evidence_catalog_id="sha256:" + "4" * 64,
            cycle=1,
        )
        document = entry.to_document()
        self.assertEqual(document["definition"], learned_definition("abs_value").to_document())
        self.assertEqual(entry.definition.statement_count, 3)
        restored = type(entry).from_document(document)
        self.assertEqual(restored.entry_id, entry.entry_id)


@unittest.skipUnless(shutil.which("cc"), "a C compiler is required")
class FunctionLanguageExperimentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temporary = tempfile.TemporaryDirectory()
        cls.root = Path(cls.temporary.name)
        cls.report, cls.replay, cls.native = smoke_function_language(cls.root / "result")
        cls.bundle = cls.root / "result" / "bundle"

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temporary.cleanup()

    def _document(self, relative: str):
        return load_json_strict((self.bundle / relative).read_bytes())

    def test_complete_study_grows_and_validates_every_task(self) -> None:
        self.assertTrue(self.report.all_valid)
        self.assertEqual((self.report.task_count, self.report.case_count, self.report.cycle_count), (7, 224, 3))
        report = self._document("run-report.json")["report"]
        self.assertEqual([row["entry_count"] for row in report["cycle_results"]], [0, 1, 2])
        self.assertEqual([row["cases_passed"] for row in report["cycle_results"]], [224, 224, 224])
        definitions = [row["total_definition_statements"] for row in report["cycle_results"]]
        self.assertGreater(definitions[0], definitions[1])
        self.assertGreater(definitions[1], definitions[2])

    def test_learned_abstraction_preserves_exact_dispatch(self) -> None:
        report = self._document("run-report.json")["report"]
        dispatches = {row["total_dispatches"] for row in report["cycle_results"]}
        self.assertEqual(len(dispatches), 1)
        for task_id, evidence in report["platform_style_transfer"].items():
            with self.subTest(task=task_id):
                self.assertEqual(evidence["dispatch_change"], 0)
                self.assertGreater(evidence["definition_statement_reduction"], 0)
                self.assertTrue(evidence["all_cycles_valid"])

    def test_learned_functions_transfer_to_protected_and_audit_tasks(self) -> None:
        report = self._document("run-report.json")["report"]
        self.assertEqual(
            set(report["platform_style_transfer"]),
            {"highest_altitude", "sum_absolute_deviation", "max_increasing_difference"},
        )
        audit = self._document("cycles/cycle-2/max_increasing_difference/validity.json")
        self.assertEqual(audit["partition"], "postfreeze_audit")
        self.assertEqual(len(audit["learned_entry_ids"]), 1)
        self.assertEqual(audit["definition_statements"], 3)

    def test_call_graph_source_trace_and_generated_c_are_inspectable(self) -> None:
        source = (self.bundle / "cycles/cycle-2/max_absolute/program.lai").read_text(encoding="utf-8")
        generated = (self.bundle / "cycles/cycle-2/max_absolute/program.c").read_text(encoding="utf-8")
        trace = self._document("cycles/cycle-2/max_absolute/trace.json")
        validity = self._document("cycles/cycle-2/max_absolute/validity.json")
        self.assertIn("use fn op_", source)
        self.assertIn("fn max_absolute_pair", source)
        self.assertIn("algorithm max_absolute(nums: array<i64>, target: i64) -> i64", source)
        self.assertIn("/* learned max_of entry_id=sha256:", generated)
        self.assertIn("/* call_graph max_absolute -> max_absolute_pair */", generated)
        self.assertEqual(validity["static_call_depth"], 3)
        self.assertEqual(validity["call_graph"]["max_absolute"], ["max_absolute_pair"])
        self.assertTrue(any(event.get("learned") for event in trace["events"]))
        depths = [event["depth"] for event in trace["events"] if "depth" in event]
        self.assertEqual(max(depths), 3)

    def test_unlearned_local_functions_are_reported(self) -> None:
        report = self._document("run-report.json")["report"]
        self.assertEqual(report["unlearned_local_functions"], ["max_absolute_pair", "min_of"])
        source = (self.bundle / "cycles/cycle-2/max_increasing_difference/program.lai").read_text(encoding="utf-8")
        self.assertIn("fn min_of", source)

    def test_saved_artifacts_load_and_execute_independently(self) -> None:
        vocabulary = FunctionVocabulary.from_document(self._document("vocabularies/cycle-2.json"))
        program = FunctionProgram.from_document(self._document("cycles/cycle-2/highest_altitude/encoded-program.json"))
        case = registered_function_tasks()["highest_altitude"].cases[4]
        actual = execute_program(program, case.nums, case.target, vocabulary)
        self.assertEqual(actual.value, case.expected)
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
        path = tampered / "cycles/cycle-2/highest_altitude/program.lai"
        path.write_text(path.read_text(encoding="utf-8") + "\n", encoding="utf-8")
        with self.assertRaisesRegex(FunctionExperimentError, "replay mismatch"):
            replay_function_experiment(tampered)


if __name__ == "__main__":
    unittest.main()
