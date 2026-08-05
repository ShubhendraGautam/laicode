"""Tests for anti-unification abstraction discovery.

These exist to answer one question about the module: can it produce an
abstraction that nobody wrote down first, and is that abstraction sound? The
whitelist test and the interpreter-agreement test are the two that carry the
research claim; the rest guard the machinery underneath them.
"""

from __future__ import annotations

import unittest

from laicode.function_discovery import (
    ACCUMULATOR,
    DiscoveredAbstraction,
    DiscoveryError,
    Template,
    anti_unify,
    body_template,
    compile_definition,
    covers,
    definition_from_template,
    discover_abstractions,
    discovered_entry,
    discovery_evidence_id,
    generalizations,
)
from laicode.function_language import (
    DISCOVERY_LEARNER_VERSION,
    EMPTY_FUNCTION_VOCABULARY,
    Assign,
    Expression,
    ForRange,
    FunctionLanguageError,
    If,
    Let,
    Return,
    execute_program,
    extend_vocabulary,
    validate_program,
)
from laicode.function_synthesis import INDEX, build_program


def var(name: str) -> Expression:
    return Expression("var", name=name)


def const(value: int) -> Expression:
    return Expression("const", value=value)


def op(operator: str, *arguments: Expression) -> Expression:
    return Expression(operator, tuple(arguments))


ACC = var(ACCUMULATOR)
TARGET = var("target")
ELEMENT = op("get", var("nums"), var(INDEX))

# Two loop bodies of the shape the synthesizer actually emits. They differ only
# in what is being compared, which is what makes `max` fall out of them.
MAX_ELEMENT = Template(op("lt", ACC, ELEMENT), ELEMENT)
MAX_SHIFTED = Template(
    op("lt", ACC, op("add", ELEMENT, TARGET)),
    op("add", ELEMENT, TARGET),
)


class BodyTemplateTests(unittest.TestCase):
    def test_plain_accumulator_assignment_becomes_an_unconditional_template(self) -> None:
        template = body_template((Assign(ACCUMULATOR, op("add", ACC, ELEMENT)),))
        self.assertIsNotNone(template)
        assert template is not None
        self.assertIsNone(template.condition)
        self.assertEqual(template.value, op("add", ACC, ELEMENT))

    def test_guarded_accumulator_assignment_keeps_its_condition(self) -> None:
        statements = (If(op("lt", ACC, ELEMENT), (Assign(ACCUMULATOR, ELEMENT),), ()),)
        template = body_template(statements)
        self.assertIsNotNone(template)
        assert template is not None
        self.assertEqual(template.condition, op("lt", ACC, ELEMENT))
        self.assertEqual(template.value, ELEMENT)

    def test_unsupported_bodies_are_rejected(self) -> None:
        cases = {
            "multiple statements": (
                Assign(ACCUMULATOR, ELEMENT),
                Assign(ACCUMULATOR, ACC),
            ),
            "assigns something other than the accumulator": (
                Assign("other", ELEMENT),
            ),
            "has an else branch": (
                If(op("lt", ACC, ELEMENT), (Assign(ACCUMULATOR, ELEMENT),),
                   (Assign(ACCUMULATOR, ACC),)),
            ),
            "guards a non-accumulator assignment": (
                If(op("lt", ACC, ELEMENT), (Assign("other", ELEMENT),), ()),
            ),
            "is not an assignment at all": (Return(ACC),),
        }
        for label, statements in cases.items():
            with self.subTest(body=label):
                self.assertIsNone(body_template(statements))


class AntiUnificationTests(unittest.TestCase):
    def test_agreeing_positions_are_preserved(self) -> None:
        result = anti_unify(
            Template(None, op("add", ACC, const(1))),
            Template(None, op("add", ACC, const(2))),
        )
        assert result is not None
        self.assertEqual(result.value.op, "add")
        self.assertEqual(result.value.arguments[0], ACC)

    def test_disagreeing_positions_become_placeholders(self) -> None:
        result = anti_unify(
            Template(None, op("add", ACC, const(1))),
            Template(None, op("add", ACC, const(2))),
        )
        assert result is not None
        hole = result.value.arguments[1]
        self.assertEqual(hole.op, "var")
        assert hole.name is not None
        self.assertTrue(hole.name.startswith("hole_"))

    def test_identical_disagreements_share_one_placeholder(self) -> None:
        """`acc < X { acc = X }` must reuse one hole, or `max` cannot appear."""

        result = anti_unify(MAX_ELEMENT, MAX_SHIFTED)
        assert result is not None
        assert result.condition is not None
        self.assertEqual(result.condition.arguments[1], result.value)

    def test_a_generalization_always_covers_both_of_its_inputs(self) -> None:
        """The defining property of anti-unification.

        Regression: differing constants used to take the structural branch and
        be rebuilt as the left constant, producing a template that covered its
        left input and not its right. That silently dropped candidates rather
        than admitting wrong ones, because `covers` is recomputed per task.
        """

        pairs = (
            (Template(None, op("add", ACC, const(1))),
             Template(None, op("add", ACC, const(2)))),
            (Template(None, op("add", const(1), const(2))),
             Template(None, op("add", const(3), const(4)))),
            (MAX_ELEMENT, MAX_SHIFTED),
            (Template(op("lt", ACC, const(0)), ELEMENT),
             Template(op("lt", ACC, const(5)), TARGET)),
        )
        for left, right in pairs:
            with self.subTest(left=left.value.to_document()):
                result = anti_unify(left, right)
                assert result is not None
                self.assertTrue(covers(result, left))
                self.assertTrue(covers(result, right))

    def test_differing_condition_shape_does_not_unify(self) -> None:
        self.assertIsNone(anti_unify(MAX_ELEMENT, Template(None, ELEMENT)))
        self.assertIsNone(anti_unify(Template(None, ELEMENT), MAX_ELEMENT))

    def test_placeholders_are_numbered_left_to_right(self) -> None:
        result = anti_unify(
            Template(None, op("add", const(1), const(2))),
            Template(None, op("add", const(3), const(4))),
        )
        assert result is not None
        variants = generalizations(result)
        names = [item.name for item in variants[0].value.arguments]
        self.assertEqual(names, ["hole_0", "hole_1"])

    def test_generalizations_include_the_template_itself_and_are_deduplicated(self) -> None:
        result = anti_unify(MAX_ELEMENT, MAX_SHIFTED)
        assert result is not None
        variants = generalizations(result)
        self.assertEqual(variants[0], result)
        documents = [
            (None if item.condition is None else item.condition.to_document(),
             item.value.to_document())
            for item in variants
        ]
        self.assertEqual(len(documents), len(set(map(str, documents))))


class CoverageTests(unittest.TestCase):
    def test_a_generalization_covers_the_programs_it_came_from(self) -> None:
        pattern = anti_unify(MAX_ELEMENT, MAX_SHIFTED)
        assert pattern is not None
        self.assertTrue(covers(pattern, MAX_ELEMENT))
        self.assertTrue(covers(pattern, MAX_SHIFTED))

    def test_a_placeholder_must_bind_consistently(self) -> None:
        pattern = anti_unify(MAX_ELEMENT, MAX_SHIFTED)
        assert pattern is not None
        # `acc < element { acc = target }` uses two different values where the
        # pattern demands one, so it must not be counted as covered.
        mismatched = Template(op("lt", ACC, ELEMENT), TARGET)
        self.assertFalse(covers(pattern, mismatched))

    def test_shape_mismatch_is_not_covered(self) -> None:
        pattern = anti_unify(MAX_ELEMENT, MAX_SHIFTED)
        assert pattern is not None
        self.assertFalse(covers(pattern, Template(None, ELEMENT)))


class DefinitionTests(unittest.TestCase):
    def test_a_guarded_template_becomes_a_valid_self_contained_function(self) -> None:
        pattern = anti_unify(MAX_ELEMENT, MAX_SHIFTED)
        assert pattern is not None
        definition = definition_from_template(pattern)
        self.assertIsNotNone(definition)
        assert definition is not None
        self.assertEqual(definition.return_type, "i64")
        self.assertEqual(len(definition.parameters), 2)
        self.assertEqual(definition.statement_count, 3)
        self.assertIsInstance(definition.body[0], If)
        self.assertIsInstance(definition.body[1], Return)

    def test_an_unconditional_template_cannot_become_a_definition(self) -> None:
        """A recorded narrowing, not an accident.

        `check_discovered_definition` requires at least two statements, and an
        unconditional template lowers to a single `return`. Discovery can
        therefore only ever propose guarded abstractions today.
        """

        pattern = anti_unify(
            Template(None, op("add", ACC, const(1))),
            Template(None, op("add", ACC, const(2))),
        )
        assert pattern is not None
        self.assertIsNone(definition_from_template(pattern))

    def test_templates_holding_the_input_array_are_rejected(self) -> None:
        """`nums` is an array; it cannot become a scalar parameter."""

        pattern = anti_unify(
            Template(op("lt", ACC, ELEMENT), op("add", ELEMENT, const(1))),
            Template(op("lt", ACC, ELEMENT), op("add", ELEMENT, const(2))),
        )
        assert pattern is not None
        self.assertIsNone(definition_from_template(pattern))

    def test_a_definition_never_takes_more_than_the_kernel_allows(self) -> None:
        pattern = anti_unify(
            Template(op("lt", var("a"), var("b")), op("add", var("c"), var("d"))),
            Template(op("lt", var("e"), var("f")), op("add", var("g"), var("h"))),
        )
        assert pattern is not None
        definition = definition_from_template(pattern)
        if definition is not None:
            self.assertLessEqual(len(definition.parameters), 4)


class DiscoveryTests(unittest.TestCase):
    def templates(self) -> dict[str, Template]:
        return {
            "max_element": MAX_ELEMENT,
            "max_shifted": MAX_SHIFTED,
        }

    def test_discovery_requires_at_least_two_tasks(self) -> None:
        with self.assertRaises(DiscoveryError):
            discover_abstractions({"only": MAX_ELEMENT})

    def test_discovery_raises_when_no_cross_task_structure_exists(self) -> None:
        with self.assertRaises(DiscoveryError):
            discover_abstractions({
                "unconditional": Template(None, op("add", ACC, const(1))),
                "guarded": MAX_ELEMENT,
            })

    def test_discovery_recovers_maximum_tracking_from_two_programs(self) -> None:
        best = discover_abstractions(self.templates())[0]
        self.assertGreaterEqual(len(best.covered_task_ids), 2)
        call = compile_definition(best.definition)
        # Whatever it named the function, it must behave as `max`.
        for left in (-9, -1, 0, 1, 7):
            for right in (-9, -1, 0, 1, 7):
                self.assertEqual(call(left, right), max(left, right))

    def test_discovered_names_never_collide_with_the_hand_written_table(self) -> None:
        """R1: discovery must not be a lookup with extra steps."""

        from laicode.function_language import _DEFINITIONS

        for abstraction in discover_abstractions(self.templates()):
            self.assertNotIn(abstraction.definition.name, _DEFINITIONS)
            self.assertTrue(abstraction.definition.name.startswith("fn_"))

    def test_discovery_consults_no_table_of_known_abstractions(self) -> None:
        """R1, structurally: emptying the table changes nothing about discovery."""

        import laicode.function_language as language

        original = dict(language._DEFINITIONS)
        before = [item.definition.name for item in discover_abstractions(self.templates())]
        language._DEFINITIONS.clear()
        try:
            after = [item.definition.name for item in discover_abstractions(self.templates())]
        finally:
            language._DEFINITIONS.update(original)
        self.assertEqual(before, after)

    def test_every_proposal_covers_at_least_two_tasks(self) -> None:
        for abstraction in discover_abstractions(self.templates()):
            self.assertGreaterEqual(len(abstraction.covered_task_ids), 2)

    def test_proposals_are_ranked_by_coverage_then_simplicity(self) -> None:
        proposals = discover_abstractions(self.templates())
        keys = [
            (-len(item.covered_task_ids), item.parameter_count,
             item.definition.statement_count, item.definition.name)
            for item in proposals
        ]
        self.assertEqual(keys, sorted(keys))

    def test_discovery_is_deterministic(self) -> None:
        first = discover_abstractions(self.templates())
        second = discover_abstractions(self.templates())
        self.assertEqual(
            [item.definition.name for item in first],
            [item.definition.name for item in second],
        )

    def test_task_order_does_not_change_the_result(self) -> None:
        forward = discover_abstractions({
            "max_element": MAX_ELEMENT, "max_shifted": MAX_SHIFTED,
        })
        reversed_order = discover_abstractions({
            "max_shifted": MAX_SHIFTED, "max_element": MAX_ELEMENT,
        })
        self.assertEqual(
            [item.definition.name for item in forward],
            [item.definition.name for item in reversed_order],
        )

    def test_evidence_identity_covers_the_corpus_and_cycle(self) -> None:
        templates = self.templates()
        self.assertEqual(
            discovery_evidence_id(templates, 1),
            discovery_evidence_id(dict(reversed(list(templates.items()))), 1),
        )
        self.assertNotEqual(
            discovery_evidence_id(templates, 1),
            discovery_evidence_id(templates, 2),
        )


class VocabularyEntryTests(unittest.TestCase):
    def entry(self):
        templates = {"max_element": MAX_ELEMENT, "max_shifted": MAX_SHIFTED}
        best = discover_abstractions(templates)[0]
        return best, discovered_entry(
            best,
            EMPTY_FUNCTION_VOCABULARY,
            evidence_catalog_id=discovery_evidence_id(templates, 1),
            cycle=1,
        )

    def test_a_discovered_entry_carries_its_own_definition(self) -> None:
        best, entry = self.entry()
        self.assertEqual(entry.discovered_definition, best.definition)
        self.assertEqual(entry.learner_id, DISCOVERY_LEARNER_VERSION)

    def test_the_kernel_accepts_a_program_built_on_a_discovered_entry(self) -> None:
        _, entry = self.entry()
        vocabulary = extend_vocabulary(EMPTY_FUNCTION_VOCABULARY, entry)
        program = build_program("discovered_max", (
            Assign(ACCUMULATOR, Expression(
                "learned_call", (ACC, ELEMENT), entry_id=entry.entry_id,
            )),
        ))
        validate_program(program, vocabulary)

    def test_the_fast_closure_agrees_with_the_trusted_interpreter(self) -> None:
        """The find-versus-certify split is only sound if the two agree."""

        best, entry = self.entry()
        vocabulary = extend_vocabulary(EMPTY_FUNCTION_VOCABULARY, entry)
        program = build_program("discovered_max", (
            Assign(ACCUMULATOR, Expression(
                "learned_call", (ACC, ELEMENT), entry_id=entry.entry_id,
            )),
        ))
        validate_program(program, vocabulary)
        call = compile_definition(best.definition)
        cases = ((), (3,), (-4, 2), (5, -5, 0), (1, 2, 3), (-7, -2), (9, -3, 6, -8))
        for nums in cases:
            with self.subTest(nums=nums):
                accumulator = 0
                for value in nums:
                    accumulator = call(accumulator, value)
                interpreted = execute_program(program, nums, 0, vocabulary).value
                self.assertEqual(interpreted, accumulator)


class CompilationTests(unittest.TestCase):
    def test_unsupported_statements_are_refused(self) -> None:
        best = discover_abstractions({
            "max_element": MAX_ELEMENT, "max_shifted": MAX_SHIFTED,
        })[0]
        broken = type(best.definition)(
            best.definition.name,
            best.definition.parameters,
            best.definition.return_type,
            (Let("x", const(1)), Return(const(0))),
        )
        with self.assertRaises(DiscoveryError):
            compile_definition(broken)

    def test_a_definition_that_cannot_return_is_an_error(self) -> None:
        best = discover_abstractions({
            "max_element": MAX_ELEMENT, "max_shifted": MAX_SHIFTED,
        })[0]
        parameters = best.definition.parameters
        headless = type(best.definition)(
            best.definition.name,
            parameters,
            best.definition.return_type,
            (If(op("lt", var(parameters[0].name), var(parameters[0].name)),
                (Return(const(1)),), ()),),
        )
        call = compile_definition(headless)
        with self.assertRaises(DiscoveryError):
            call(*[0] * len(parameters))


if __name__ == "__main__":
    unittest.main()
