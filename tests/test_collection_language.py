from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from laicode.canonical import load_json_strict
from laicode.collection_benchmark import (
    CollectionExperimentError,
    registered_collection_tasks,
    replay_collection_experiment,
    smoke_collection_language,
)
from laicode.collection_language import (
    I64,
    VECTOR_I64,
    EMPTY_COLLECTION_VOCABULARY,
    CollectionLanguageError,
    CollectionProgram,
    CollectionVocabulary,
    Expression,
    OwnVector,
    Push,
    RecordField,
    Return,
    ReturnType,
    VECTOR_RETURN,
    encode_program,
    execute_program,
    extend_vocabulary,
    intrinsic_uses,
    learn_collection_intrinsic,
    validate_program,
)


def _var(name: str) -> Expression:
    return Expression("var", name=name)


def _const(value: int) -> Expression:
    return Expression("const", value=value)


class CollectionLanguageKernelTests(unittest.TestCase):
    def test_registered_programs_match_independent_oracles(self) -> None:
        for task in registered_collection_tasks().values():
            with self.subTest(task=task.task_id):
                validate_program(task.program)
                for case in task.cases:
                    actual = execute_program(task.program, case.nums, case.target).value
                    if isinstance(actual, tuple):
                        actual = list(actual)
                    elif isinstance(actual, dict):
                        actual = {
                            key: list(value) if isinstance(value, tuple) else value
                            for key, value in actual.items()
                        }
                    self.assertEqual(actual, case.expected)

    def test_owned_vector_capacity_is_enforced(self) -> None:
        program = CollectionProgram(
            "capacity_probe",
            VECTOR_RETURN,
            (
                OwnVector("values", _const(1)),
                Push("values", _const(1)),
                Push("values", _const(2)),
                Return((("value", _var("values")),)),
            ),
        )
        with self.assertRaisesRegex(CollectionLanguageError, "capacity was exceeded"):
            execute_program(program, (), 0)

    def test_record_fields_are_statically_checked(self) -> None:
        result_type = ReturnType(
            "record",
            "collection_result",
            (RecordField("values", VECTOR_I64), RecordField("length", I64)),
        )
        program = CollectionProgram(
            "record_probe",
            result_type,
            (
                OwnVector("values", _const(0)),
                Return((("length", _const(0)), ("values", _var("values")))),
            ),
        )
        with self.assertRaisesRegex(CollectionLanguageError, "return fields are mistyped"):
            validate_program(program)

    def test_growth_requires_cross_task_evidence_and_transfers(self) -> None:
        tasks = registered_collection_tasks()
        first_tasks = [tasks["copy_array"], tasks["reverse_array"]]
        first = learn_collection_intrinsic(
            [task.program for task in first_tasks],
            EMPTY_COLLECTION_VOCABULARY,
            evidence_catalog_id="sha256:" + "1" * 64,
            cycle=1,
        )
        self.assertEqual(first.kind, "push_indexed")
        vocabulary = extend_vocabulary(EMPTY_COLLECTION_VOCABULARY, first)
        encoded = encode_program(tasks["remove_element"].program, vocabulary)
        self.assertTrue(intrinsic_uses(encoded))
        case = tasks["remove_element"].cases[5]
        core = execute_program(tasks["remove_element"].program, case.nums, case.target)
        learned = execute_program(encoded, case.nums, case.target, vocabulary)
        self.assertEqual(core.value, learned.value)
        self.assertLess(learned.dispatches, core.dispatches)

    def test_input_is_not_an_assignment_or_push_target(self) -> None:
        program = CollectionProgram(
            "input_mutation_probe",
            VECTOR_RETURN,
            (
                OwnVector("values", _const(0)),
                Push("nums", _const(1)),
                Return((("value", _var("values")),)),
            ),
        )
        with self.assertRaisesRegex(CollectionLanguageError, "push is mistyped"):
            validate_program(program)


@unittest.skipUnless(shutil.which("cc"), "a C compiler is required")
class CollectionLanguageExperimentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temporary = tempfile.TemporaryDirectory()
        cls.root = Path(cls.temporary.name)
        cls.report, cls.replay, cls.native = smoke_collection_language(cls.root / "result")
        cls.bundle = cls.root / "result" / "bundle"

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temporary.cleanup()

    def _document(self, relative: str):
        return load_json_strict((self.bundle / relative).read_bytes())

    def test_complete_study_grows_and_validates_owned_outputs(self) -> None:
        self.assertTrue(self.report.all_valid)
        self.assertEqual((self.report.task_count, self.report.case_count, self.report.cycle_count), (7, 224, 3))
        record = self._document("run-report.json")
        report = record["report"]
        self.assertEqual([row["entry_count"] for row in report["cycle_results"]], [0, 1, 2])
        self.assertEqual([row["cases_passed"] for row in report["cycle_results"]], [224, 224, 224])
        dispatches = [row["total_dispatches"] for row in report["cycle_results"]]
        self.assertGreater(dispatches[0], dispatches[1])
        self.assertGreater(dispatches[1], dispatches[2])
        self.assertEqual(report["record_tasks"], ["remove_element"])

    def test_learned_statement_forms_transfer_to_protected_and_audit_tasks(self) -> None:
        report = self._document("run-report.json")["report"]
        self.assertEqual(set(report["platform_style_transfer"]), {"remove_element", "move_zeroes"})
        for task_id, evidence in report["platform_style_transfer"].items():
            with self.subTest(task=task_id):
                self.assertTrue(evidence["all_cycles_valid"])
                self.assertGreater(evidence["dispatch_reduction"], 0)

    def test_record_source_trace_and_generated_c_are_inspectable(self) -> None:
        source = (self.bundle / "cycles/cycle-2/remove_element/program.lai").read_text(encoding="utf-8")
        generated = (self.bundle / "cycles/cycle-2/remove_element/program.c").read_text(encoding="utf-8")
        trace = self._document("cycles/cycle-2/remove_element/trace.json")
        self.assertIn("record collection_result", source)
        self.assertIn("own out: vector<i64>", source)
        self.assertIn("append_indexed_if", source)
        self.assertIn("learned op_", generated)
        self.assertEqual(trace["events"][-1]["event"], "return")

    def test_saved_artifacts_load_and_execute_independently(self) -> None:
        vocabulary = CollectionVocabulary.from_document(self._document("vocabularies/cycle-2.json"))
        program = CollectionProgram.from_document(self._document("cycles/cycle-2/move_zeroes/encoded-program.json"))
        case = registered_collection_tasks()["move_zeroes"].cases[4]
        actual = execute_program(program, case.nums, case.target, vocabulary)
        self.assertEqual(list(actual.value), case.expected)
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
        path = tampered / "cycles/cycle-2/remove_element/program.lai"
        path.write_text(path.read_text(encoding="utf-8") + "\n", encoding="utf-8")
        with self.assertRaisesRegex(CollectionExperimentError, "replay mismatch"):
            replay_collection_experiment(tampered)


if __name__ == "__main__":
    unittest.main()
