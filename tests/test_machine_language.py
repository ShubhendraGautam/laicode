from __future__ import annotations

import unittest

from laicode.canonical import content_id
from laicode.machine_language import (
    EMPTY_VOCABULARY,
    MachineLanguageError,
    MachineVocabulary,
    WeightedProgram,
    WordInstruction,
    WordProgram,
    encode_program,
    evaluate_cost,
    execute_encoded,
    execute_program,
    learn_one_superinstruction,
)


MIX = (
    WordInstruction("xor_shift_right", 30),
    WordInstruction("multiply_const", 0xBF58476D1CE4E5B9),
    WordInstruction("xor_shift_right", 27),
)
EVIDENCE_ID = content_id({"corpus": "machine-language-training-v0"})


def program(
    prefix: WordInstruction,
    suffix: WordInstruction,
) -> WordProgram:
    return WordProgram((prefix,) + MIX + (suffix,))


class HardwareShapedLanguageTests(unittest.TestCase):
    def setUp(self) -> None:
        self.training = (
            WeightedProgram(
                program(
                    WordInstruction("add_const", 7),
                    WordInstruction("rotate_left", 13),
                ),
                100,
            ),
            WeightedProgram(
                program(
                    WordInstruction("xor_const", 0x9E3779B97F4A7C15),
                    WordInstruction("and_const", 0x7FFFFFFFFFFFFFFF),
                ),
                120,
            ),
            WeightedProgram(
                program(
                    WordInstruction("or_const", 1),
                    WordInstruction("add_const", 11),
                ),
                80,
            ),
        )
        self.held_out = (
            WeightedProgram(
                program(
                    WordInstruction("rotate_left", 9),
                    WordInstruction("xor_const", 0x94D049BB133111EB),
                ),
                150,
            ),
        )

    def test_unsigned_constants_have_canonical_transport(self) -> None:
        instruction = WordInstruction(
            "multiply_const",
            0xBF58476D1CE4E5B9,
        )

        self.assertEqual(
            instruction.to_document()["operand"],
            "0xbf58476d1ce4e5b9",
        )
        self.assertEqual(
            WordInstruction.from_document(instruction.to_document()),
            instruction,
        )

    def test_primitive_semantics_are_total_modulo_u64(self) -> None:
        pipeline = WordProgram(
            (
                WordInstruction("add_const", 1),
                WordInstruction("multiply_const", 3),
                WordInstruction("rotate_left", 1),
            )
        )

        self.assertEqual(execute_program(pipeline, (1 << 64) - 1), 0)
        with self.assertRaisesRegex(MachineLanguageError, "unsigned"):
            execute_program(pipeline, -1)

    def test_execution_weighted_learning_discovers_shared_machine_phrase(self) -> None:
        vocabulary = learn_one_superinstruction(
            self.training,
            EMPTY_VOCABULARY,
            evidence_catalog_id=EVIDENCE_ID,
            cycle=1,
        )

        self.assertEqual(len(vocabulary.entries), 1)
        self.assertEqual(vocabulary.entries[0].lowering, MIX)
        self.assertEqual(vocabulary.parent_vocabulary_id, EMPTY_VOCABULARY.vocabulary_id)
        self.assertGreater(vocabulary.entries[0].estimated_saving, 0)

    def test_learned_encoding_lowers_exactly_and_preserves_all_outputs(self) -> None:
        vocabulary = learn_one_superinstruction(
            self.training,
            EMPTY_VOCABULARY,
            evidence_catalog_id=EVIDENCE_ID,
            cycle=1,
        )
        candidate = self.held_out[0].program
        encoded = encode_program(candidate, vocabulary)

        self.assertLess(len(encoded.tokens), len(candidate.instructions))
        for value in (0, 1, 2, (1 << 63) - 1, 1 << 63, (1 << 64) - 1):
            self.assertEqual(
                execute_encoded(encoded, vocabulary, value),
                execute_program(candidate, value),
            )

    def test_learned_vocabulary_reduces_held_out_dispatch_cost(self) -> None:
        learned = learn_one_superinstruction(
            self.training,
            EMPTY_VOCABULARY,
            evidence_catalog_id=EVIDENCE_ID,
            cycle=1,
        )
        primitive_cost = evaluate_cost(self.held_out, EMPTY_VOCABULARY)
        learned_cost = evaluate_cost(self.held_out, learned)

        self.assertEqual(learned_cost.alu_units, primitive_cost.alu_units)
        self.assertLess(learned_cost.dispatch_units, primitive_cost.dispatch_units)
        self.assertLess(learned_cost.total_units, primitive_cost.total_units)

    def test_vocabulary_persists_and_changes_next_cycle_action_space(self) -> None:
        first = learn_one_superinstruction(
            self.training,
            EMPTY_VOCABULARY,
            evidence_catalog_id=EVIDENCE_ID,
            cycle=1,
        )
        second_training = (
            WeightedProgram(
                WordProgram(
                    (
                        WordInstruction("add_const", 3),
                        WordInstruction("rotate_left", 17),
                        WordInstruction("xor_const", 5),
                        WordInstruction("add_const", 3),
                        WordInstruction("rotate_left", 17),
                        WordInstruction("xor_const", 5),
                    )
                ),
                200,
            ),
        )
        second = learn_one_superinstruction(
            second_training,
            first,
            evidence_catalog_id=content_id({"corpus": "cycle-2"}),
            cycle=2,
        )

        self.assertEqual(second.parent_vocabulary_id, first.vocabulary_id)
        self.assertEqual(len(second.entries), 2)
        self.assertTrue(
            set(first.by_id()).issubset(second.by_id()),
        )

    def test_vocabulary_rejects_unsorted_or_duplicate_entries(self) -> None:
        learned = learn_one_superinstruction(
            self.training,
            EMPTY_VOCABULARY,
            evidence_catalog_id=EVIDENCE_ID,
            cycle=1,
        )
        entry = learned.entries[0]

        with self.assertRaisesRegex(MachineLanguageError, "unique"):
            MachineVocabulary(
                parent_vocabulary_id=learned.vocabulary_id,
                entries=(entry, entry),
            )


if __name__ == "__main__":
    unittest.main()
