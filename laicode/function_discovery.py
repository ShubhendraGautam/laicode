"""A3-D abstraction discovery by anti-unification over synthesized programs.

Every learned entry in A0, A1, and A2 traces back to a program a human wrote.
The learner's job was recognition: spot a shape that a person had already
written twice. That measures an encoder, not discovery.

This module closes the loop. It takes programs the *synthesizer* produced for
training tasks, finds structure recurring across distinct tasks, and abstracts
that structure into a new function by anti-unification -- generalizing the
positions where the programs disagree into parameters. The result is an ordinary
`FunctionVocabularyEntry` carrying its own archived definition, so it stays as
transparent and as replayable as a hand-written one.

Nothing here consults a table of known abstractions. If the discovered function
happens to coincide with something a human would have written, that is a
finding, not a lookup.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterator, Mapping, Sequence

from .canonical import JsonValue, content_id
from .function_language import (
    DISCOVERY_LEARNER_VERSION,
    I64,
    Assign,
    Expression,
    FunctionDef,
    FunctionLanguageError,
    FunctionVocabulary,
    FunctionVocabularyEntry,
    If,
    MAX_PARAMETERS,
    Parameter,
    Return,
    Statement,
    check_discovered_definition,
)


DISCOVERY_VERSION = "AntiUnificationDiscoveryV3"
ACCUMULATOR = "acc"
MAX_CANDIDATE_PARAMETERS = MAX_PARAMETERS


class DiscoveryError(RuntimeError):
    """Raised when abstraction discovery cannot produce a valid entry."""


@dataclass(frozen=True)
class Template:
    """A loop body reduced to how it transforms the accumulator.

    `condition` is None for an unconditional assignment. A guarded assignment
    keeps its condition, because the guard is usually the interesting part of
    the shape being abstracted.
    """

    condition: Expression | None
    value: Expression

    @property
    def parts(self) -> tuple[Expression, ...]:
        return (self.value,) if self.condition is None else (self.condition, self.value)


def body_template(statements: Sequence[Statement]) -> Template | None:
    """Reduce a synthesized loop body to a template, or None if unsupported."""

    if len(statements) != 1:
        return None
    statement = statements[0]
    if isinstance(statement, Assign) and statement.name == ACCUMULATOR:
        return Template(None, statement.value)
    if (
        isinstance(statement, If)
        and not statement.else_body
        and len(statement.then_body) == 1
        and isinstance(statement.then_body[0], Assign)
        and statement.then_body[0].name == ACCUMULATOR
    ):
        return Template(statement.condition, statement.then_body[0].value)
    return None


def _placeholder(index: int) -> Expression:
    return Expression("var", name=f"hole_{index}")


def _is_placeholder(expression: Expression) -> bool:
    return expression.op == "var" and expression.name is not None and expression.name.startswith("hole_")


def _anti_unify(
    left: Expression,
    right: Expression,
    substitutions: dict[tuple[str, str], Expression],
) -> Expression:
    """Least general generalization of two expressions.

    Positions where the two agree keep their structure; positions where they
    differ become placeholders. Identical disagreements share one placeholder,
    so repeated structure stays linked rather than being abstracted twice.
    """

    if left == right:
        return left
    # `value` has to be compared too. Without it two different constants take
    # the structural branch -- same op, same arity, both names None -- and are
    # rebuilt as the left constant, yielding a "generalization" that does not
    # cover its own right-hand input.
    if (
        left.op == right.op
        and len(left.arguments) == len(right.arguments)
        and left.name == right.name
        and left.value == right.value
        and left.entry_id == right.entry_id
    ):
        return Expression(
            left.op,
            tuple(_anti_unify(a, b, substitutions) for a, b in zip(left.arguments, right.arguments)),
            name=left.name,
            value=left.value,
            entry_id=left.entry_id,
        )
    key = (content_id(left.to_document()), content_id(right.to_document()))
    if key not in substitutions:
        substitutions[key] = _placeholder(len(substitutions))
    return substitutions[key]


def anti_unify(first: Template, second: Template) -> Template | None:
    if (first.condition is None) != (second.condition is None):
        return None
    substitutions: dict[tuple[str, str], Expression] = {}
    condition = None
    if first.condition is not None and second.condition is not None:
        condition = _anti_unify(first.condition, second.condition, substitutions)
    value = _anti_unify(first.value, second.value, substitutions)
    return Template(condition, value)


def _subtrees(expression: Expression) -> Iterator[Expression]:
    yield expression
    for argument in expression.arguments:
        yield from _subtrees(argument)


def _replace(expression: Expression, target: Expression, replacement: Expression) -> Expression:
    if expression == target:
        return replacement
    if not expression.arguments:
        return expression
    return Expression(
        expression.op,
        tuple(_replace(item, target, replacement) for item in expression.arguments),
        name=expression.name,
        value=expression.value,
        entry_id=expression.entry_id,
    )


def _contains_placeholder(expression: Expression) -> bool:
    return any(_is_placeholder(item) for item in _subtrees(expression))


def generalizations(template: Template) -> list[Template]:
    """The anti-unified template plus variants that abstract more aggressively.

    Anti-unification keeps as much shared structure as it can, which is not
    always the useful abstraction: two programs that both compute `acc < (a + b)`
    share the `+`, but the reusable idea is `acc < anything`. Collapsing a shared
    placeholder-bearing subtree into a single parameter recovers that, so both
    readings are offered and ranked on evidence.
    """

    results = [template]
    seen = {content_id(_document(template))}
    candidates: list[Expression] = []
    for part in template.parts:
        for subtree in _subtrees(part):
            if _contains_placeholder(subtree) and not _is_placeholder(subtree) and subtree not in candidates:
                candidates.append(subtree)
    for subtree in sorted(candidates, key=lambda item: -len(tuple(_subtrees(item)))):
        replacement = _placeholder(0)
        condition = None if template.condition is None else _replace(template.condition, subtree, replacement)
        value = _replace(template.value, subtree, replacement)
        variant = _renumber(Template(condition, value))
        key = content_id(_document(variant))
        if key not in seen:
            seen.add(key)
            results.append(variant)
    return results


def _document(template: Template) -> dict[str, JsonValue]:
    return {
        "condition": None if template.condition is None else template.condition.to_document(),
        "value": template.value.to_document(),
    }


def _ordered_placeholders(template: Template) -> list[str]:
    order: list[str] = []
    for part in template.parts:
        for item in _subtrees(part):
            if _is_placeholder(item) and item.name is not None and item.name not in order:
                order.append(item.name)
    return order


def _renumber(template: Template) -> Template:
    """Give placeholders a canonical left-to-right numbering."""

    mapping = {name: _placeholder(index) for index, name in enumerate(_ordered_placeholders(template))}

    def rewrite(expression: Expression) -> Expression:
        if _is_placeholder(expression) and expression.name is not None:
            return mapping[expression.name]
        if not expression.arguments:
            return expression
        return Expression(
            expression.op,
            tuple(rewrite(item) for item in expression.arguments),
            name=expression.name,
            value=expression.value,
            entry_id=expression.entry_id,
        )

    condition = None if template.condition is None else rewrite(template.condition)
    return Template(condition, rewrite(template.value))


def _free_variables(template: Template) -> list[str]:
    order: list[str] = []
    for part in template.parts:
        for item in _subtrees(part):
            if item.op == "var" and item.name is not None and not _is_placeholder(item) and item.name not in order:
                order.append(item.name)
    return order


def definition_from_template(template: Template) -> FunctionDef | None:
    """Turn a template into a pure function of its inputs, or None if invalid.

    A guarded assignment `if C { acc = E }` is exactly the function
    `if C { return E } return acc`, which is why the accumulator has to appear
    as a parameter: the function must be able to return it unchanged.
    """

    template = _renumber(template)
    free = _free_variables(template)
    placeholders = _ordered_placeholders(template)
    if template.condition is not None and ACCUMULATOR not in free:
        free = [ACCUMULATOR, *free]
    names = [*free, *placeholders]
    if not names or len(names) > MAX_CANDIDATE_PARAMETERS:
        return None
    if any(name.startswith("nums") for name in free):
        return None

    rename = {name: f"p{index}" for index, name in enumerate(names)}

    def rewrite(expression: Expression) -> Expression:
        if expression.op == "var" and expression.name is not None:
            return Expression("var", name=rename[expression.name])
        if not expression.arguments:
            return expression
        return Expression(
            expression.op,
            tuple(rewrite(item) for item in expression.arguments),
            name=expression.name,
            value=expression.value,
            entry_id=expression.entry_id,
        )

    parameters = tuple(Parameter(rename[name], I64) for name in names)
    if template.condition is None:
        body: tuple[Statement, ...] = (Return(rewrite(template.value)),)
    else:
        body = (
            If(rewrite(template.condition), (Return(rewrite(template.value)),), ()),
            Return(Expression("var", name=rename[ACCUMULATOR])),
        )
    signature = content_id({
        "schema_version": DISCOVERY_VERSION,
        "parameters": [item.to_document() for item in parameters],
        "return_type": I64,
        "body": [_statement_document(item) for item in body],
    })
    try:
        definition = FunctionDef(f"fn_{signature[7:15]}", parameters, I64, body)
        check_discovered_definition(definition)
    except FunctionLanguageError:
        return None
    return definition


def _statement_document(statement: Statement) -> dict[str, JsonValue]:
    from .function_language import statement_to_document

    return statement_to_document(statement)


def _matches(pattern: Expression, concrete: Expression, bindings: dict[str, Expression]) -> bool:
    """One-way match: can `pattern` be instantiated to `concrete`?"""

    if _is_placeholder(pattern):
        assert pattern.name is not None
        bound = bindings.get(pattern.name)
        if bound is None:
            bindings[pattern.name] = concrete
            return True
        return bound == concrete
    if pattern.op != concrete.op or pattern.name != concrete.name or pattern.value != concrete.value:
        return False
    if len(pattern.arguments) != len(concrete.arguments):
        return False
    return all(_matches(a, b, bindings) for a, b in zip(pattern.arguments, concrete.arguments))


def covers(pattern: Template, concrete: Template) -> bool:
    if (pattern.condition is None) != (concrete.condition is None):
        return False
    bindings: dict[str, Expression] = {}
    if pattern.condition is not None and concrete.condition is not None:
        if not _matches(pattern.condition, concrete.condition, bindings):
            return False
    return _matches(pattern.value, concrete.value, bindings)


@dataclass(frozen=True)
class DiscoveredAbstraction:
    definition: FunctionDef
    template: Template
    covered_task_ids: tuple[str, ...]

    @property
    def parameter_count(self) -> int:
        return len(self.definition.parameters)


def discover_abstractions(templates: Mapping[str, Template]) -> tuple[DiscoveredAbstraction, ...]:
    """Propose abstractions from synthesized programs, best first.

    Candidates come from anti-unifying every pair of task templates. Each is
    scored by how many distinct tasks it covers, then by how few parameters it
    needs, so a generalization that explains more programs with less machinery
    wins. Ties break on content identity, keeping the result deterministic.
    """

    if len(templates) < 2:
        raise DiscoveryError("abstraction discovery requires at least two tasks")
    ordered = sorted(templates)
    proposals: dict[str, DiscoveredAbstraction] = {}
    for first_index, first in enumerate(ordered):
        for second in ordered[first_index + 1:]:
            pair = anti_unify(templates[first], templates[second])
            if pair is None:
                continue
            for candidate in generalizations(pair):
                definition = definition_from_template(candidate)
                if definition is None:
                    continue
                covered = tuple(
                    task for task in ordered if covers(candidate, templates[task])
                )
                if len(covered) < 2:
                    continue
                proposals[definition.name] = DiscoveredAbstraction(definition, candidate, covered)
    if not proposals:
        raise DiscoveryError("abstraction discovery found no cross-task structure")
    return tuple(sorted(
        proposals.values(),
        key=lambda item: (-len(item.covered_task_ids), item.parameter_count,
                          item.definition.statement_count, item.definition.name),
    ))


def discovery_evidence_id(templates: Mapping[str, Template], cycle: int) -> str:
    return content_id({
        "schema_version": "DiscoveryEvidenceCatalogV3",
        "cycle": cycle,
        "disclosure": "synthesized_training_programs_only",
        "tasks": [
            {"task_id": task, "template": _document(templates[task])}
            for task in sorted(templates)
        ],
    })


def discovered_entry(
    abstraction: DiscoveredAbstraction,
    vocabulary: FunctionVocabulary,
    *,
    evidence_catalog_id: str,
    cycle: int,
) -> FunctionVocabularyEntry:
    """Wrap a discovered abstraction as an ordinary transparent vocabulary entry."""

    return FunctionVocabularyEntry(
        abstraction.definition.name,
        evidence_catalog_id,
        vocabulary.vocabulary_id,
        cycle,
        tuple(sorted(abstraction.covered_task_ids)),
        len(abstraction.covered_task_ids),
        abstraction.definition.statement_count * len(abstraction.covered_task_ids),
        DISCOVERY_LEARNER_VERSION,
        abstraction.definition,
    )


_BINARY: dict[str, Callable[[int, int], int]] = {
    "add": lambda p, q: p + q,
    "sub": lambda p, q: p - q,
}
_PREDICATE: dict[str, Callable[[int, int], bool]] = {
    "eq": lambda p, q: p == q,
    "ne": lambda p, q: p != q,
    "lt": lambda p, q: p < q,
    "le": lambda p, q: p <= q,
    "gt": lambda p, q: p > q,
    "ge": lambda p, q: p >= q,
}


def compile_definition(definition: FunctionDef) -> Callable[..., int]:
    """Compile a discovered definition to a closure over its parameters.

    The synthesizer evaluates millions of candidates, which the trusted
    interpreter cannot do at that rate. This is the same find-versus-certify
    split used elsewhere: the closure is only ever used to search, and every
    surviving program is re-executed by the real interpreter.
    """

    index = {item.name: position for position, item in enumerate(definition.parameters)}

    def expression(value: Expression) -> Callable[[Sequence[int]], int]:
        if value.op == "const":
            constant = value.value
            assert constant is not None
            return lambda arguments: constant
        if value.op == "var":
            assert value.name is not None
            position = index[value.name]
            return lambda arguments: arguments[position]
        compiled = [expression(item) for item in value.arguments]
        if value.op in _BINARY:
            left, right = compiled
            apply = _BINARY[value.op]
            return lambda arguments: apply(left(arguments), right(arguments))
        if value.op in _PREDICATE:
            left, right = compiled
            check = _PREDICATE[value.op]
            return lambda arguments: check(left(arguments), right(arguments))
        raise DiscoveryError(f"discovered definition uses unsupported operator {value.op!r}")

    def block(statements: Sequence[Statement]) -> Callable[[Sequence[int]], int | None]:
        compiled: list[tuple] = []
        for statement in statements:
            if isinstance(statement, Return):
                compiled.append(("return", expression(statement.value)))
            elif isinstance(statement, If):
                compiled.append((
                    "if", expression(statement.condition),
                    block(statement.then_body), block(statement.else_body),
                ))
            else:
                raise DiscoveryError("discovered definition contains an unsupported statement")

        def run(arguments: Sequence[int]) -> int | None:
            for item in compiled:
                if item[0] == "return":
                    return item[1](arguments)
                branch = item[2] if item[1](arguments) else item[3]
                result = branch(arguments)
                if result is not None:
                    return result
            return None

        return run

    body = block(definition.body)

    def call(*arguments: int) -> int:
        result = body(arguments)
        if result is None:
            raise DiscoveryError("discovered definition completed without returning")
        return result

    return call
