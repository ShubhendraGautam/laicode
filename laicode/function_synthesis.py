"""A2-S matched-budget program synthesis over the bounded-function kernel.

The A0, A1, and A2 studies all learn vocabulary from programs a human wrote,
then check that an encoder can substitute it back. None of them tests the
question the project actually asks: does learned vocabulary help a machine
*construct* a program it has never seen?

This module answers that with an enumerative synthesizer. It searches for the
loop body of a fixed accumulator skeleton, under two arms that differ only in
the vocabulary available:

    primitive : add, sub, and comparisons over acc, nums[i], target, constants
    learned   : the same, plus the A2 vocabulary entries as callable operators

Both arms get an identical candidate budget. The headline metric is candidates
evaluated, which is deterministic and machine independent, in keeping with the
repository rule that wall-clock timing never enters a selection identity.

Search runs over compiled closures for speed. Every solution is then
materialized as a real `FunctionProgram`, validated by the trusted kernel, and
executed by the trusted interpreter against independent oracles. Nothing is
reported as solved on the strength of the fast path alone.
"""

from __future__ import annotations

import itertools
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, Iterator, Mapping, Sequence

from .canonical import (
    CanonicalizationError,
    JsonValue,
    canonical_json_bytes,
    content_id,
    load_json_strict,
)
from .function_language import (
    ENTRY_PARAMETERS,
    EMPTY_FUNCTION_VOCABULARY,
    I64,
    Assign,
    Expression,
    ForRange,
    FunctionDef,
    FunctionProgram,
    FunctionVocabulary,
    FunctionVocabularyEntry,
    If,
    Let,
    Return,
    Statement,
    execute_program,
    render_program,
    validate_program,
)


SKELETON_VERSION = "AccumulatorFoldSkeletonV2"
SEARCH_VERSION = "SizeOrderedObservationalSearchV2"
ACCUMULATOR = "acc"
INDEX = "i"

MAX_EXPRESSION_SIZE = 6
MAX_CONDITION_OPERAND_SIZE = 3
MAX_BODY_SIZE = 14
MAX_BODY_STATEMENTS = 2

# Observational-equivalence probes. Two expressions that agree on every probe
# are interchangeable, so only the first is enumerated.
PROBES: tuple[tuple[int, int, int], ...] = tuple(
    (accumulator, element, target)
    for accumulator in (0, 3, -2, 7, -9)
    for element in (-5, 0, 4, -1, 9, 12)
    for target in (0, 2, -3, 6)
)

Evaluator = Callable[[int, int, int], int]
Predicate = Callable[[int, int, int], bool]


class SynthesisError(RuntimeError):
    """Raised when a synthesis run violates its own methodology guards."""


@dataclass(frozen=True)
class SearchNode:
    """One enumerated candidate carrying both a fast closure and real A2 syntax."""

    expression: Expression
    size: int
    evaluate: Evaluator


@dataclass(frozen=True)
class ConditionNode:
    expression: Expression
    size: int
    evaluate: Predicate


def _var(name: str) -> Expression:
    return Expression("var", name=name)


def _const(value: int) -> Expression:
    return Expression("const", value=value)


def _op(operator: str, *arguments: Expression) -> Expression:
    return Expression(operator, tuple(arguments))


ELEMENT = _op("get", _var("nums"), _var(INDEX))


def _leaves() -> Iterable[SearchNode]:
    yield SearchNode(_var(ACCUMULATOR), 1, lambda a, x, t: a)
    yield SearchNode(ELEMENT, 1, lambda a, x, t: x)
    yield SearchNode(_var("target"), 1, lambda a, x, t: t)
    for value in (0, 1, -1):
        yield SearchNode(_const(value), 1, lambda a, x, t, v=value: v)


def _behaviour(evaluate: Callable[[int, int, int], object]) -> tuple:
    return tuple(evaluate(a, x, t) for a, x, t in PROBES)


def expression_nodes(vocabulary: FunctionVocabulary, max_size: int = MAX_EXPRESSION_SIZE) -> tuple[SearchNode, ...]:
    """Enumerate expressions bottom-up, deduped by behaviour on the probes."""

    by_size: dict[int, list[SearchNode]] = {}
    seen: set[tuple] = set()
    pool: list[SearchNode] = []

    def add(node: SearchNode) -> None:
        key = _behaviour(node.evaluate)
        if key in seen:
            return
        seen.add(key)
        by_size.setdefault(node.size, []).append(node)
        pool.append(node)

    for node in _leaves():
        add(node)

    entries = sorted(vocabulary.entries, key=lambda item: item.entry_id)
    unary = [item for item in entries if len(item.parameter_types) == 1]
    binary = [item for item in entries if len(item.parameter_types) == 2]

    for size in range(2, max_size + 1):
        for left_size in range(1, size):
            right_size = size - left_size - 1
            if right_size >= 1:
                for left in by_size.get(left_size, ()):
                    for right in by_size.get(right_size, ()):
                        add(SearchNode(
                            _op("add", left.expression, right.expression), size,
                            lambda a, x, t, f=left.evaluate, g=right.evaluate: f(a, x, t) + g(a, x, t),
                        ))
                        add(SearchNode(
                            _op("sub", left.expression, right.expression), size,
                            lambda a, x, t, f=left.evaluate, g=right.evaluate: f(a, x, t) - g(a, x, t),
                        ))
                        for entry in binary:
                            if entry.return_type != I64 or entry.parameter_types != (I64, I64):
                                continue
                            add(SearchNode(
                                Expression("learned_call", (left.expression, right.expression), entry_id=entry.entry_id),
                                size,
                                _binary_learned(entry, left.evaluate, right.evaluate),
                            ))
            if left_size == size - 1:
                for operand in by_size.get(left_size, ()):
                    for entry in unary:
                        if entry.return_type != I64 or entry.parameter_types != (I64,):
                            continue
                        add(SearchNode(
                            Expression("learned_call", (operand.expression,), entry_id=entry.entry_id),
                            size,
                            _unary_learned(entry, operand.evaluate),
                        ))
    return tuple(pool)


def _entry_call(entry: "FunctionVocabularyEntry") -> Callable[..., int]:
    """Fast evaluator for a vocabulary entry, tabled or discovered."""

    from .function_discovery import compile_definition

    if entry.discovered_definition is None:
        if entry.kind == "abs_value":
            return lambda value: abs(value)
        if entry.kind == "max_of":
            return lambda left, right: max(left, right)
        raise SynthesisError(f"no fast evaluator for learned entry {entry.kind!r}")
    return compile_definition(entry.definition)


def _unary_learned(entry: "FunctionVocabularyEntry", operand: Evaluator) -> Evaluator:
    call = _entry_call(entry)
    return lambda a, x, t: call(operand(a, x, t))


def _binary_learned(entry: "FunctionVocabularyEntry", left: Evaluator, right: Evaluator) -> Evaluator:
    call = _entry_call(entry)
    return lambda a, x, t: call(left(a, x, t), right(a, x, t))


_COMPARISONS: tuple[tuple[str, Callable[[int, int], bool]], ...] = (
    ("lt", lambda p, q: p < q),
    ("le", lambda p, q: p <= q),
    ("eq", lambda p, q: p == q),
    ("ne", lambda p, q: p != q),
)


def condition_nodes(
    expressions: Sequence[SearchNode],
    max_operand_size: int = MAX_CONDITION_OPERAND_SIZE,
) -> tuple[ConditionNode, ...]:
    """Enumerate comparisons, deduped by behaviour, dropping constant predicates.

    The operand cap is applied identically in both arms. An earlier revision
    capped it at a size where only bare leaves qualified, which silently gave
    the learned arm richer conditions than the primitive arm.
    """

    operands = [node for node in expressions if node.size <= max_operand_size]
    seen: set[tuple] = set()
    pool: list[ConditionNode] = []
    for left, right in itertools.product(operands, operands):
        for operator, apply in _COMPARISONS:
            evaluate = (
                lambda a, x, t, f=left.evaluate, g=right.evaluate, o=apply: o(f(a, x, t), g(a, x, t))
            )
            key = _behaviour(evaluate)
            if key in seen or all(key) or not any(key):
                continue
            seen.add(key)
            pool.append(ConditionNode(
                _op(operator, left.expression, right.expression),
                left.size + right.size,
                evaluate,
            ))
    return tuple(pool)


@dataclass(frozen=True)
class StatementNode:
    """A candidate statement.

    Real A2 syntax is built only by `statements()`, on the winner. Materializing
    a syntax tree per pool entry exhausts memory: the learned arm's pool holds
    millions of statements, and only one of them is ever needed as syntax.
    """

    parts: tuple[tuple[ConditionNode | None, SearchNode], ...]
    size: int
    evaluate: Evaluator

    def statements(self) -> tuple[Statement, ...]:
        built: list[Statement] = []
        for condition, assignment in self.parts:
            assign = Assign(ACCUMULATOR, assignment.expression)
            built.append(assign if condition is None else If(condition.expression, (assign,), ()))
        return tuple(built)


def statement_nodes(
    expressions: Sequence[SearchNode],
    conditions: Sequence[ConditionNode],
) -> tuple[StatementNode, ...]:
    pool: list[StatementNode] = [
        StatementNode(((None, node),), node.size, node.evaluate) for node in expressions
    ]
    for condition in conditions:
        for node in expressions:
            pool.append(StatementNode(
                ((condition, node),),
                condition.size + node.size,
                lambda a, x, t, c=condition.evaluate, f=node.evaluate: f(a, x, t) if c(a, x, t) else a,
            ))
    return tuple(sorted(pool, key=lambda item: item.size))


def body_candidates(
    statements: Sequence[StatementNode],
    max_size: int = MAX_BODY_SIZE,
    max_statements: int = MAX_BODY_STATEMENTS,
) -> Iterator[StatementNode]:
    """Yield candidate loop bodies in nondecreasing total size."""

    for size in range(1, max_size + 1):
        for node in statements:
            if node.size == size:
                yield node
        if max_statements < 2:
            continue
        for first in statements:
            if first.size >= size:
                break
            for second in statements:
                total = first.size + second.size
                if total > size:
                    break
                if total == size:
                    yield StatementNode(
                        first.parts + second.parts,
                        total,
                        lambda a, x, t, f=first.evaluate, g=second.evaluate: g(f(a, x, t), x, t),
                    )


def build_program(task_id: str, body: Sequence[Statement]) -> FunctionProgram:
    """Materialize a searched body as a real, kernel-validated A2 program."""

    entry = FunctionDef(
        task_id,
        ENTRY_PARAMETERS,
        I64,
        (
            Let(ACCUMULATOR, _const(0)),
            ForRange(INDEX, _const(0), _op("len", _var("nums")), tuple(body)),
            Return(_var(ACCUMULATOR)),
        ),
    )
    return FunctionProgram(task_id, (entry,))


def fold(evaluate: Evaluator, nums: Sequence[int], target: int) -> int:
    accumulator = 0
    for value in nums:
        accumulator = evaluate(accumulator, value, target)
    return accumulator


Oracle = Callable[[Sequence[int], int], int]


def _sum_absolute_deviation(nums: Sequence[int], target: int) -> int:
    return sum(abs(value - target) for value in nums)


def _max_absolute_deviation(nums: Sequence[int], target: int) -> int:
    return max([abs(value - target) for value in nums] + [0])


def _sum_positive_part(nums: Sequence[int], target: int) -> int:
    del target
    return sum(max(0, value) for value in nums)


def _max_shifted_value(nums: Sequence[int], target: int) -> int:
    return max([value + target for value in nums] + [0])


def _sum_all(nums: Sequence[int], target: int) -> int:
    del target
    return sum(nums)


def _count_all(nums: Sequence[int], target: int) -> int:
    del target
    return len(nums)


def _sum_shifted(nums: Sequence[int], target: int) -> int:
    return sum(value + target for value in nums)


TRAINING_CASES: tuple[tuple[tuple[int, ...], int], ...] = (
    ((), 0), ((3,), 1), ((-4, 2), 0), ((5, -5, 0), 2), ((1, 2, 3), -1),
    ((-7, -2), 3), ((0, 0), 0), ((9, -3, 6, -8), 2), ((-11, 4), -6),
    ((8, 8, -8), 5), ((2, -1, 7, -12, 3), -4), ((6,), 6),
)
HELDOUT_CASES: tuple[tuple[tuple[int, ...], int], ...] = (
    ((4, -6, 11, -2, 0), 3), ((-1, -1, -1), -2), ((12,), -12), ((), 5),
    ((2, 7, -9, 4), 0), ((-5, 5), 1), ((10, -10, 3, 3), -7), ((0, 6, -6), 4),
    ((-3, 9, 1), 2), ((7, -4), -1),
)


@dataclass(frozen=True)
class SynthesisTask:
    task_id: str
    family: str
    description: str
    oracle: Oracle
    requires_learned_vocabulary: bool

    @property
    def contract_document(self) -> dict[str, JsonValue]:
        return {
            "schema_version": "SynthesisTaskContractV2",
            "task_id": self.task_id,
            "family": self.family,
            "description": self.description,
            "requires_learned_vocabulary": self.requires_learned_vocabulary,
            "skeleton": SKELETON_VERSION,
            "training_cases": len(TRAINING_CASES),
            "heldout_cases": len(HELDOUT_CASES),
            "oracle": "independent_python_reference_v2",
        }


def registered_synthesis_tasks() -> tuple[SynthesisTask, ...]:
    """Treatment tasks need abs or max; control tasks are add/sub only.

    The control family exists so the study can detect the cost of carrying a
    larger vocabulary. Without it a clean sweep would be unfalsifiable.
    """

    return (
        SynthesisTask("sum_absolute_deviation", "treatment",
                      "total distance from every value to the target", _sum_absolute_deviation, True),
        SynthesisTask("max_absolute_deviation", "treatment",
                      "largest distance from any value to the target", _max_absolute_deviation, True),
        SynthesisTask("sum_positive_part", "treatment",
                      "sum of the positive parts of the input", _sum_positive_part, True),
        SynthesisTask("max_shifted_value", "treatment",
                      "largest shifted value, floored at zero", _max_shifted_value, True),
        SynthesisTask("sum_all", "control", "total of the input", _sum_all, False),
        SynthesisTask("count_all", "control", "number of input elements", _count_all, False),
        SynthesisTask("sum_shifted", "control",
                      "total of the input with the target added per element", _sum_shifted, False),
    )


_POOL_CACHE: dict[str, tuple[tuple[SearchNode, ...], tuple[ConditionNode, ...], tuple[StatementNode, ...]]] = {}


def search_pools(
    vocabulary: FunctionVocabulary,
) -> tuple[tuple[SearchNode, ...], tuple[ConditionNode, ...], tuple[StatementNode, ...]]:
    """Return the enumerated pools for a vocabulary, memoized by its identity.

    The pools depend only on the vocabulary, so rebuilding them per task would
    dominate the run: the learned arm's statement pool holds millions of entries.
    """

    key = vocabulary.vocabulary_id
    cached = _POOL_CACHE.get(key)
    if cached is None:
        expressions = expression_nodes(vocabulary)
        conditions = condition_nodes(expressions)
        cached = (expressions, conditions, statement_nodes(expressions, conditions))
        _POOL_CACHE[key] = cached
    return cached


@dataclass(frozen=True)
class SynthesisResult:
    task_id: str
    arm: str
    outcome: str
    candidates_evaluated: int
    program: FunctionProgram | None
    rendered: str | None
    generalizes: bool | None
    kernel_verified: bool
    pool_expressions: int
    pool_conditions: int
    pool_statements: int

    def to_document(self) -> dict[str, JsonValue]:
        payload: dict[str, JsonValue] = {
            "task_id": self.task_id,
            "arm": self.arm,
            "outcome": self.outcome,
            "candidates_evaluated": self.candidates_evaluated,
            "generalizes": self.generalizes,
            "kernel_verified": self.kernel_verified,
            "pool_expressions": self.pool_expressions,
            "pool_conditions": self.pool_conditions,
            "pool_statements": self.pool_statements,
        }
        if self.program is not None:
            payload["program_id"] = self.program.program_id
            payload["program"] = self.rendered
        return payload


def synthesize(
    task: SynthesisTask,
    vocabulary: FunctionVocabulary,
    *,
    budget: int,
    arm: str,
) -> SynthesisResult:
    """Search for a loop body, then verify any hit with the trusted kernel.

    `outcome` is one of `solved`, `budget`, or `exhausted`. A `solved` result
    whose `generalizes` is false is a decoy that fitted the training cases only;
    the true search cost for that task is strictly greater than the number
    reported here.
    """

    expressions, conditions, statements = search_pools(vocabulary)
    training = tuple((nums, target, task.oracle(nums, target)) for nums, target in TRAINING_CASES)
    evaluated = 0

    def result(outcome: str, node: StatementNode | None) -> SynthesisResult:
        program = rendered = None
        generalizes = None
        verified = False
        if node is not None:
            program = build_program(task.task_id, node.statements())
            validate_program(program, vocabulary)
            # Trusted-path verification: the fast closure found it, but only the
            # real interpreter is allowed to certify it.
            generalizes = all(
                execute_program(program, nums, target, vocabulary).value == task.oracle(nums, target)
                for nums, target in TRAINING_CASES + HELDOUT_CASES
            )
            verified = all(
                execute_program(program, nums, target, vocabulary).value == expected
                for nums, target, expected in training
            )
            if not verified:
                raise SynthesisError(
                    f"fast search and trusted interpreter disagree for {task.task_id} ({arm})"
                )
            rendered = render_program(program, vocabulary)
        return SynthesisResult(
            task.task_id, arm, outcome, evaluated, program, rendered, generalizes, verified,
            len(expressions), len(conditions), len(statements),
        )

    for node in body_candidates(statements):
        evaluated += 1
        if evaluated > budget:
            evaluated -= 1
            return result("budget", None)
        if all(fold(node.evaluate, nums, target) == expected for nums, target, expected in training):
            return result("solved", node)
    return result("exhausted", None)


EXPERIMENT_SCHEMA_VERSION = "SynthesisExperimentV2"
RUN_REPORT_SCHEMA_VERSION = "SynthesisRunReportV2"
RUN_RECORD_SCHEMA_VERSION = "SynthesisRunReportRecordV2"
REPLAY_SCHEMA_VERSION = "SynthesisReplayV2"
REGISTERED_AT = "2026-08-02T00:00:00Z"
REGISTERED_BUDGET = 100_000_000


@dataclass(frozen=True)
class SynthesisExperimentReport:
    report_id: str
    task_count: int
    budget: int
    treatment_median_ratio_ppm: int | None
    control_median_ratio_ppm: int | None


def _ratio_ppm(primitive: SynthesisResult, learned: SynthesisResult) -> int | None:
    """Ratio in parts per million.

    The canonical JSON profile admits only signed 64-bit integers, so ratios
    are carried as integer ppm rather than floats. 1_000_000 ppm is parity;
    7_495_000_000 ppm is a 7,495x reduction.
    """

    if not learned.candidates_evaluated:
        return None
    return (primitive.candidates_evaluated * 1_000_000) // learned.candidates_evaluated


def _median_ppm(values: Sequence[int]) -> int | None:
    if not values:
        return None
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) // 2


def experiment_manifest(budget: int) -> dict[str, JsonValue]:
    return {
        "schema_version": EXPERIMENT_SCHEMA_VERSION,
        "experiment_name": "learned-vocabulary-synthesis-transfer-a2s-v1",
        "question": "does learned vocabulary reduce the search cost of constructing unseen programs",
        "kernel": "CallGraphFunctionKernelV2",
        "skeleton": SKELETON_VERSION,
        "search": SEARCH_VERSION,
        "arms": ["primitive", "learned"],
        "matched_budget_candidates": budget,
        "metric": "candidates_evaluated_deterministic_machine_independent",
        "treatment_tasks": [item.task_id for item in registered_synthesis_tasks() if item.family == "treatment"],
        "control_tasks": [item.task_id for item in registered_synthesis_tasks() if item.family == "control"],
        "control_rule": "control_tasks_are_solvable_with_add_sub_only_so_vocabulary_can_only_cost",
        "verification_rule": "every_reported_solution_is_revalidated_by_the_trusted_kernel_and_interpreter",
        "generalization_rule": "a_solution_that_fails_heldout_cases_makes_its_candidate_count_a_lower_bound",
        "vocabulary_provenance": "a2_cycle_2_entries_learned_from_hand_written_training_programs",
        "authority": "D0_offline_no_deployment",
        "registered_at": REGISTERED_AT,
    }


def run_synthesis(budget: int = REGISTERED_BUDGET) -> tuple[dict[str, JsonValue], tuple[SynthesisResult, ...]]:
    """Run both arms over every registered task and return the manifest plus results."""

    from .function_benchmark import registered_function_tasks, build_function_vocabularies

    vocabularies = build_function_vocabularies(registered_function_tasks())
    arms = (("primitive", EMPTY_FUNCTION_VOCABULARY), ("learned", vocabularies[-1]))
    results: list[SynthesisResult] = []
    for task in registered_synthesis_tasks():
        for arm, vocabulary in arms:
            results.append(synthesize(task, vocabulary, budget=budget, arm=arm))
    return experiment_manifest(budget), tuple(results)


def synthesis_report(manifest: Mapping[str, JsonValue], results: Sequence[SynthesisResult]) -> dict[str, JsonValue]:
    tasks = {item.task_id: item for item in registered_synthesis_tasks()}
    by_task: dict[str, dict[str, SynthesisResult]] = {}
    for item in results:
        by_task.setdefault(item.task_id, {})[item.arm] = item

    rows: list[JsonValue] = []
    treatment: list[int] = []
    control: list[int] = []
    for task_id, task in tasks.items():
        primitive, learned = by_task[task_id]["primitive"], by_task[task_id]["learned"]
        ratio = _ratio_ppm(primitive, learned)
        # The ratio understates whenever the primitive arm did not actually
        # solve the task: a hit that fails held-out cases is a decoy, and a run
        # stopped at the budget never reached its solution. Both make the
        # reported count a floor on the arm's true cost.
        lower_bound = (
            primitive.outcome != "solved"
            or primitive.generalizes is False
        )
        if ratio is not None:
            (treatment if task.family == "treatment" else control).append(ratio)
        rows.append({
            "task_id": task_id,
            "family": task.family,
            "requires_learned_vocabulary": task.requires_learned_vocabulary,
            "primitive": primitive.to_document(),
            "learned": learned.to_document(),
            "candidate_ratio_ppm_primitive_over_learned": ratio,
            "ratio_is_lower_bound": lower_bound,
        })

    return {
        "schema_version": RUN_REPORT_SCHEMA_VERSION,
        "status": "complete",
        "experiment_manifest_id": content_id(dict(manifest)),
        "matched_budget_candidates": manifest["matched_budget_candidates"],
        "task_count": len(tasks),
        "results": rows,
        "treatment_median_ratio_ppm": _median_ppm(treatment),
        "control_median_ratio_ppm": _median_ppm(control),
        "all_reported_solutions_kernel_verified": all(
            item.kernel_verified for item in results if item.outcome == "solved"
        ),
        "limitations": [
            "vocabulary_was_learned_from_hand_written_programs_not_synthesized_ones",
            "one_fixed_accumulator_skeleton_rather_than_open_ended_program_search",
            "enumerative_search_is_not_a_model_driven_proposer",
            "a_non_generalizing_hit_makes_its_arm_cost_a_lower_bound_only",
            "synthetic_deterministic_cases_not_hidden_platform_tests",
        ],
    }


def _write_document(path: Path, value: JsonValue) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as handle:
        handle.write(canonical_json_bytes(value) + b"\n")


def _write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(value)


def _read_object(path: Path) -> Mapping[str, JsonValue]:
    try:
        value = load_json_strict(path.read_bytes())
    except (OSError, CanonicalizationError) as error:
        raise SynthesisError(f"cannot read {path}: {error}") from error
    if not isinstance(value, dict):
        raise SynthesisError(f"expected an object in {path}")
    return value


def _report_from_record(record: Mapping[str, JsonValue]) -> SynthesisExperimentReport:
    if set(record) != {"schema_version", "report_id", "report"} or record.get("schema_version") != RUN_RECORD_SCHEMA_VERSION:
        raise SynthesisError("synthesis run record is invalid")
    report_id, report = record["report_id"], record["report"]
    if not isinstance(report_id, str) or not isinstance(report, dict) or content_id(report) != report_id:
        raise SynthesisError("synthesis run report identity differs")
    return SynthesisExperimentReport(
        report_id,
        int(report["task_count"]),
        int(report["matched_budget_candidates"]),
        report["treatment_median_ratio_ppm"],
        report["control_median_ratio_ppm"],
    )


def run_synthesis_experiment(
    output_directory: str | Path,
    *,
    budget: int = REGISTERED_BUDGET,
) -> SynthesisExperimentReport:
    output = Path(output_directory)
    if output.exists():
        raise SynthesisError(f"synthesis output already exists: {output}")
    manifest, results = run_synthesis(budget)
    output.mkdir(parents=True, exist_ok=False)
    _write_document(output / "experiment-manifest.json", manifest)
    for task in registered_synthesis_tasks():
        _write_document(output / "tasks" / task.task_id / "contract.json", task.contract_document)
    for item in results:
        root = output / "results" / item.task_id
        _write_document(root / f"{item.arm}.json", item.to_document())
        if item.rendered is not None:
            _write_text(root / f"{item.arm}.lai", item.rendered)
    report = synthesis_report(manifest, results)
    report_id = content_id(report)
    _write_document(
        output / "run-report.json",
        {"schema_version": RUN_RECORD_SCHEMA_VERSION, "report_id": report_id, "report": report},
    )
    return _report_from_record(_read_object(output / "run-report.json"))


@dataclass(frozen=True)
class SynthesisReplayReport:
    source_report_id: str
    replay_report_id: str
    files_verified: int


def replay_synthesis_experiment(
    bundle_directory: str | Path,
    *,
    budget: int = REGISTERED_BUDGET,
) -> SynthesisReplayReport:
    source = Path(bundle_directory)
    if not source.is_dir():
        raise SynthesisError(f"synthesis bundle does not exist: {source}")
    source_report = _report_from_record(_read_object(source / "run-report.json"))
    with tempfile.TemporaryDirectory(prefix="laicode-synthesis-replay-") as directory:
        replay = Path(directory) / "bundle"
        replay_report = run_synthesis_experiment(replay, budget=budget)
        source_files = sorted(path.relative_to(source) for path in source.rglob("*") if path.is_file())
        replay_files = sorted(path.relative_to(replay) for path in replay.rglob("*") if path.is_file())
        if source_files != replay_files:
            raise SynthesisError("synthesis replay inventory differs")
        for relative in source_files:
            if (source / relative).read_bytes() != (replay / relative).read_bytes():
                raise SynthesisError(f"synthesis replay mismatch in {relative.as_posix()}")
        if source_report.report_id != replay_report.report_id:
            raise SynthesisError("synthesis replay report identity differs")
    return SynthesisReplayReport(source_report.report_id, replay_report.report_id, len(source_files))


def smoke_function_synthesis(
    output_directory: str | Path,
    *,
    budget: int = REGISTERED_BUDGET,
) -> tuple[SynthesisExperimentReport, SynthesisReplayReport]:
    output = Path(output_directory)
    if output.exists():
        raise SynthesisError(f"synthesis smoke output exists: {output}")
    bundle = output / "bundle"
    report = run_synthesis_experiment(bundle, budget=budget)
    replay = replay_synthesis_experiment(bundle, budget=budget)
    return report, replay
