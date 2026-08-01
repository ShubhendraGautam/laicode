"""Replayable algorithm-language growth and platform-style validity study."""

from __future__ import annotations

import hashlib
import platform
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Mapping, Sequence

from .algorithm_language import (
    ARRAY_I64,
    BOOL,
    I64,
    PAIR_I64,
    AlgorithmLanguageError,
    AlgorithmProgram,
    AlgorithmVocabulary,
    Assign,
    EMPTY_ALGORITHM_VOCABULARY,
    Expression,
    ForRange,
    If,
    Let,
    Return,
    While,
    encode_program,
    execute_program,
    extend_vocabulary,
    generate_c_source,
    intrinsic_uses,
    learn_expression_intrinsic,
    render_program,
    validate_program,
)
from .canonical import (
    CanonicalizationError,
    JsonValue,
    canonical_json_bytes,
    content_id,
    load_json_strict,
)


TASK_SCHEMA_VERSION = "AlgorithmTaskContractV0"
CASE_SET_SCHEMA_VERSION = "AlgorithmCaseSetV0"
EXPERIMENT_SCHEMA_VERSION = "AlgorithmLanguageExperimentV0"
VALIDITY_SCHEMA_VERSION = "AlgorithmValidityReportV0"
TRACE_SCHEMA_VERSION = "AlgorithmExecutionTraceV0"
RUN_REPORT_SCHEMA_VERSION = "AlgorithmLanguageRunReportV0"
RUN_RECORD_SCHEMA_VERSION = "AlgorithmLanguageRunReportRecordV0"
NATIVE_REPORT_SCHEMA_VERSION = "AlgorithmNativeValidityReportV0"
NATIVE_RECORD_SCHEMA_VERSION = "AlgorithmNativeValidityReportRecordV0"
REPLAY_SCHEMA_VERSION = "AlgorithmLanguageReplayV0"

REGISTERED_AT = "2026-08-01T00:00:00Z"
DEFAULT_CASES_PER_TASK = 32
COMPILER_FLAGS = ("-O2", "-std=c11", "-Wall", "-Wextra", "-Werror")


class AlgorithmExperimentError(ValueError):
    """Raised when the algorithm-language study cannot be reproduced."""


AlgorithmOutput = int | tuple[int, int]
Oracle = Callable[[tuple[int, ...], int], AlgorithmOutput]


def _e(op: str, *arguments: Expression) -> Expression:
    return Expression(op, tuple(arguments))


def _var(name: str) -> Expression:
    return Expression("var", name=name)


def _const(value: int) -> Expression:
    return Expression("const", value=value)


def _len() -> Expression:
    return _e("len", _var("nums"))


def _get(index: str | Expression) -> Expression:
    value = _var(index) if isinstance(index, str) else index
    return _e("get", _var("nums"), value)


def _program_count_target() -> AlgorithmProgram:
    return AlgorithmProgram(
        "count_target",
        I64,
        (
            Let("acc", _const(0)),
            ForRange(
                "i",
                _const(0),
                _len(),
                (
                    If(
                        _e("eq", _get("i"), _var("target")),
                        (Assign("acc", _e("add", _var("acc"), _const(1))),),
                        (),
                    ),
                ),
            ),
            Return(_var("acc")),
        ),
    )


def _program_linear_search() -> AlgorithmProgram:
    return AlgorithmProgram(
        "linear_search_first",
        I64,
        (
            Let("result", _const(-1)),
            ForRange(
                "i",
                _const(0),
                _len(),
                (
                    If(
                        _e(
                            "and",
                            _e("eq", _var("result"), _const(-1)),
                            _e("eq", _get("i"), _var("target")),
                        ),
                        (Assign("result", _var("i")),),
                        (),
                    ),
                ),
            ),
            Return(_var("result")),
        ),
    )


def _program_sum_array() -> AlgorithmProgram:
    return AlgorithmProgram(
        "sum_array",
        I64,
        (
            Let("acc", _const(0)),
            ForRange(
                "i",
                _const(0),
                _len(),
                (Assign("acc", _e("add", _var("acc"), _get("i"))),),
            ),
            Return(_var("acc")),
        ),
    )


def _program_sum_positive() -> AlgorithmProgram:
    return AlgorithmProgram(
        "sum_positive_values",
        I64,
        (
            Let("acc", _const(0)),
            ForRange(
                "i",
                _const(0),
                _len(),
                (
                    If(
                        _e("gt", _get("i"), _const(0)),
                        (Assign("acc", _e("add", _var("acc"), _get("i"))),),
                        (),
                    ),
                ),
            ),
            Return(_var("acc")),
        ),
    )


def _program_binary_search() -> AlgorithmProgram:
    return AlgorithmProgram(
        "binary_search",
        I64,
        (
            Let("low", _const(0)),
            Let("high", _e("sub", _len(), _const(1))),
            Let("mid", _const(0)),
            Let("result", _const(-1)),
            While(
                _e(
                    "and",
                    _e("le", _var("low"), _var("high")),
                    _e("eq", _var("result"), _const(-1)),
                ),
                (
                    Assign(
                        "mid",
                        _e(
                            "add",
                            _var("low"),
                            _e(
                                "div_trunc",
                                _e("sub", _var("high"), _var("low")),
                                _const(2),
                            ),
                        ),
                    ),
                    If(
                        _e("eq", _get("mid"), _var("target")),
                        (Assign("result", _var("mid")),),
                        (
                            If(
                                _e("lt", _get("mid"), _var("target")),
                                (
                                    Assign(
                                        "low", _e("add", _var("mid"), _const(1))
                                    ),
                                ),
                                (
                                    Assign(
                                        "high", _e("sub", _var("mid"), _const(1))
                                    ),
                                ),
                            ),
                        ),
                    ),
                ),
            ),
            Return(_var("result")),
        ),
    )


def _program_maximum_subarray() -> AlgorithmProgram:
    return AlgorithmProgram(
        "maximum_subarray",
        I64,
        (
            Let("current", _get(_const(0))),
            Let("best", _get(_const(0))),
            ForRange(
                "i",
                _const(1),
                _len(),
                (
                    Assign(
                        "current",
                        _e(
                            "max",
                            _get("i"),
                            _e("add", _var("current"), _get("i")),
                        ),
                    ),
                    Assign("best", _e("max", _var("best"), _var("current"))),
                ),
            ),
            Return(_var("best")),
        ),
    )


def _program_two_sum() -> AlgorithmProgram:
    return AlgorithmProgram(
        "two_sum_indices",
        PAIR_I64,
        (
            Let("found_i", _const(-1)),
            Let("found_j", _const(-1)),
            Let("needed", _const(0)),
            ForRange(
                "i",
                _const(0),
                _len(),
                (
                    Assign("needed", _e("sub", _var("target"), _get("i"))),
                    ForRange(
                        "j",
                        _e("add", _var("i"), _const(1)),
                        _len(),
                        (
                            If(
                                _e(
                                    "and",
                                    _e("eq", _var("found_i"), _const(-1)),
                                    _e("eq", _get("j"), _var("needed")),
                                ),
                                (
                                    Assign("found_i", _var("i")),
                                    Assign("found_j", _var("j")),
                                ),
                                (),
                            ),
                        ),
                    ),
                ),
            ),
            Return(_e("pair", _var("found_i"), _var("found_j"))),
        ),
    )


def _oracle_count(nums: tuple[int, ...], target: int) -> int:
    return sum(value == target for value in nums)


def _oracle_linear(nums: tuple[int, ...], target: int) -> int:
    return nums.index(target) if target in nums else -1


def _oracle_sum(nums: tuple[int, ...], target: int) -> int:
    del target
    return sum(nums)


def _oracle_sum_positive(nums: tuple[int, ...], target: int) -> int:
    del target
    return sum(value for value in nums if value > 0)


def _oracle_binary(nums: tuple[int, ...], target: int) -> int:
    low = 0
    high = len(nums) - 1
    while low <= high:
        middle = low + (high - low) // 2
        if nums[middle] == target:
            return middle
        if nums[middle] < target:
            low = middle + 1
        else:
            high = middle - 1
    return -1


def _oracle_maximum_subarray(nums: tuple[int, ...], target: int) -> int:
    del target
    if not nums:
        raise AlgorithmExperimentError("maximum-subarray oracle requires nonempty input")
    current = nums[0]
    best = nums[0]
    for value in nums[1:]:
        current = max(value, current + value)
        best = max(best, current)
    return best


def _two_sum_solutions(nums: tuple[int, ...], target: int) -> list[tuple[int, int]]:
    return [
        (left, right)
        for left in range(len(nums))
        for right in range(left + 1, len(nums))
        if nums[left] + nums[right] == target
    ]


def _oracle_two_sum(nums: tuple[int, ...], target: int) -> tuple[int, int]:
    solutions = _two_sum_solutions(nums, target)
    return solutions[0] if solutions else (-1, -1)


class _SplitMix64:
    def __init__(self, seed: int) -> None:
        self.state = seed & ((1 << 64) - 1)

    def next(self) -> int:
        self.state = (self.state + 0x9E3779B97F4A7C15) & ((1 << 64) - 1)
        value = self.state
        value = ((value ^ (value >> 30)) * 0xBF58476D1CE4E5B9) & ((1 << 64) - 1)
        value = ((value ^ (value >> 27)) * 0x94D049BB133111EB) & ((1 << 64) - 1)
        return value ^ (value >> 31)

    def integer(self, minimum: int, maximum: int) -> int:
        return minimum + self.next() % (maximum - minimum + 1)


@dataclass(frozen=True)
class AlgorithmCase:
    nums: tuple[int, ...]
    target: int
    expected: AlgorithmOutput

    def to_document(self) -> dict[str, JsonValue]:
        expected: JsonValue = list(self.expected) if isinstance(self.expected, tuple) else self.expected
        value: dict[str, JsonValue] = {
            "nums": list(self.nums),
            "target": self.target,
            "expected": expected,
        }
        return {"case_id": content_id(value), **value}


@dataclass(frozen=True)
class AlgorithmTask:
    task_id: str
    title: str
    partition: str
    analogue: str
    compatibility: str
    preconditions: tuple[str, ...]
    program: AlgorithmProgram
    cases: tuple[AlgorithmCase, ...]
    oracle: Oracle

    def contract_document(self) -> dict[str, JsonValue]:
        return {
            "schema_version": TASK_SCHEMA_VERSION,
            "task_id": self.task_id,
            "title": self.title,
            "partition": self.partition,
            "platform_analogue": self.analogue,
            "compatibility_claim": self.compatibility,
            "input": {
                "nums": ARRAY_I64,
                "target": I64,
            },
            "output": self.program.return_type,
            "preconditions": list(self.preconditions),
            "oracle": "independent_trusted_python_reference_v0",
            "program_id": self.program.program_id,
            "case_count": len(self.cases),
            "case_set_id": self.case_set_id,
        }

    @property
    def case_set_document(self) -> dict[str, JsonValue]:
        return {
            "schema_version": CASE_SET_SCHEMA_VERSION,
            "task_id": self.task_id,
            "cases": [item.to_document() for item in self.cases],
        }

    @property
    def case_set_id(self) -> str:
        return content_id(self.case_set_document)

    @property
    def contract_id(self) -> str:
        return content_id(self.contract_document())


def _general_cases(seed: int, oracle: Oracle, *, nonempty: bool = False) -> tuple[AlgorithmCase, ...]:
    generator = _SplitMix64(seed)
    cases: list[AlgorithmCase] = []
    for index in range(DEFAULT_CASES_PER_TASK):
        minimum = 1 if nonempty else 0
        length = generator.integer(minimum, 14)
        nums = tuple(generator.integer(-30, 30) for _ in range(length))
        if index % 3 == 0 and nums:
            target = nums[generator.integer(0, len(nums) - 1)]
        else:
            target = generator.integer(-35, 35)
        cases.append(AlgorithmCase(nums, target, oracle(nums, target)))
    return tuple(cases)


def _binary_cases() -> tuple[AlgorithmCase, ...]:
    generator = _SplitMix64(704)
    cases: list[AlgorithmCase] = []
    for index in range(DEFAULT_CASES_PER_TASK):
        length = generator.integer(0, 18)
        values: set[int] = set()
        while len(values) < length:
            values.add(generator.integer(-80, 80))
        nums = tuple(sorted(values))
        if index % 2 == 0 and nums:
            target = nums[generator.integer(0, len(nums) - 1)]
        else:
            target = generator.integer(-90, 90)
        cases.append(AlgorithmCase(nums, target, _oracle_binary(nums, target)))
    return tuple(cases)


def _two_sum_cases() -> tuple[AlgorithmCase, ...]:
    generator = _SplitMix64(1)
    cases: list[AlgorithmCase] = []
    attempts = 0
    while len(cases) < DEFAULT_CASES_PER_TASK:
        attempts += 1
        if attempts > 10_000:
            raise AlgorithmExperimentError("cannot generate unique two-sum cases")
        length = generator.integer(2, 10)
        values: set[int] = set()
        while len(values) < length:
            values.add(generator.integer(-50, 50))
        nums = tuple(sorted(values))
        left = generator.integer(0, length - 2)
        right = generator.integer(left + 1, length - 1)
        target = nums[left] + nums[right]
        solutions = _two_sum_solutions(nums, target)
        if len(solutions) == 1:
            cases.append(AlgorithmCase(nums, target, solutions[0]))
    return tuple(cases)


def registered_algorithm_tasks() -> dict[str, AlgorithmTask]:
    definitions = (
        AlgorithmTask(
            "count_target",
            "Count target occurrences",
            "learning_cycle_1",
            "competitive_programming_array_count",
            "training_task_not_platform_acceptance_claim",
            ("array length is at most 14",),
            _program_count_target(),
            _general_cases(101, _oracle_count),
            _oracle_count,
        ),
        AlgorithmTask(
            "linear_search_first",
            "First linear-search index",
            "learning_cycle_1",
            "competitive_programming_linear_search",
            "training_task_not_platform_acceptance_claim",
            ("returns the first index or -1",),
            _program_linear_search(),
            _general_cases(102, _oracle_linear),
            _oracle_linear,
        ),
        AlgorithmTask(
            "sum_array",
            "Sum an integer array",
            "learning_cycle_2",
            "competitive_programming_array_sum",
            "training_task_not_platform_acceptance_claim",
            ("all registered sums fit signed i64",),
            _program_sum_array(),
            _general_cases(201, _oracle_sum),
            _oracle_sum,
        ),
        AlgorithmTask(
            "sum_positive_values",
            "Sum positive values",
            "learning_cycle_2",
            "competitive_programming_filtered_sum",
            "training_task_not_platform_acceptance_claim",
            ("all registered sums fit signed i64",),
            _program_sum_positive(),
            _general_cases(202, _oracle_sum_positive),
            _oracle_sum_positive,
        ),
        AlgorithmTask(
            "binary_search",
            "Binary search",
            "protected_holdout",
            "leetcode_704_style",
            "contract_equivalent_locally_not_official_submission",
            ("nums is strictly increasing", "returns matching index or -1"),
            _program_binary_search(),
            _binary_cases(),
            _oracle_binary,
        ),
        AlgorithmTask(
            "maximum_subarray",
            "Maximum subarray",
            "protected_holdout",
            "leetcode_53_style",
            "contract_equivalent_locally_not_official_submission",
            ("nums is nonempty", "all intermediate sums fit signed i64"),
            _program_maximum_subarray(),
            _general_cases(53, _oracle_maximum_subarray, nonempty=True),
            _oracle_maximum_subarray,
        ),
        AlgorithmTask(
            "two_sum_indices",
            "Two sum indices",
            "postfreeze_audit",
            "leetcode_1_style",
            "contract_equivalent_locally_not_official_submission",
            ("exactly one index pair sums to target", "indices are distinct"),
            _program_two_sum(),
            _two_sum_cases(),
            _oracle_two_sum,
        ),
    )
    for task in definitions:
        validate_program(task.program)
        for case in task.cases:
            if task.oracle(case.nums, case.target) != case.expected:
                raise AssertionError("registered algorithm oracle evidence differs")
    return {task.task_id: task for task in definitions}


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
        raise AlgorithmExperimentError(f"cannot read {path}: {error}") from error
    if not isinstance(value, dict):
        raise AlgorithmExperimentError(f"expected an object in {path}")
    return value


def _evidence_catalog_id(tasks: Sequence[AlgorithmTask], cycle: int) -> str:
    return content_id(
        {
            "schema_version": "AlgorithmLearningEvidenceCatalogV0",
            "cycle": cycle,
            "disclosure": "prefreeze_training_only",
            "tasks": [
                {
                    "task_id": task.task_id,
                    "contract_id": task.contract_id,
                    "program_id": task.program.program_id,
                    "case_set_id": task.case_set_id,
                }
                for task in sorted(tasks, key=lambda item: item.task_id)
            ],
        }
    )


def _build_vocabularies(tasks: Mapping[str, AlgorithmTask]) -> tuple[AlgorithmVocabulary, ...]:
    primitive = EMPTY_ALGORITHM_VOCABULARY
    cycle_1_tasks = [tasks["count_target"], tasks["linear_search_first"]]
    first = learn_expression_intrinsic(
        [task.program for task in cycle_1_tasks],
        primitive,
        evidence_catalog_id=_evidence_catalog_id(cycle_1_tasks, 1),
        cycle=1,
    )
    cycle_1 = extend_vocabulary(primitive, first)
    cycle_2_tasks = cycle_1_tasks + [tasks["sum_array"], tasks["sum_positive_values"]]
    second = learn_expression_intrinsic(
        [task.program for task in cycle_2_tasks],
        cycle_1,
        evidence_catalog_id=_evidence_catalog_id(cycle_2_tasks, 2),
        cycle=2,
    )
    cycle_2 = extend_vocabulary(cycle_1, second)
    if first.lowering.op != "eq" or second.lowering.op != "add":
        raise AlgorithmExperimentError("registered growth motifs changed unexpectedly")
    return primitive, cycle_1, cycle_2


@dataclass(frozen=True)
class AlgorithmExperimentReport:
    report_id: str
    task_count: int
    case_count: int
    cycle_count: int
    final_vocabulary_id: str
    all_valid: bool


@dataclass(frozen=True)
class AlgorithmReplayReport:
    source_report_id: str
    replay_report_id: str
    files_verified: int

    def to_document(self) -> dict[str, JsonValue]:
        return {
            "schema_version": REPLAY_SCHEMA_VERSION,
            "source_report_id": self.source_report_id,
            "replay_report_id": self.replay_report_id,
            "files_verified": self.files_verified,
            "exact_match": True,
        }


@dataclass(frozen=True)
class AlgorithmNativeReport:
    report_id: str
    compiler: str
    translations_passed: int
    cases_passed: int
    all_valid: bool


def _report_from_record(record: Mapping[str, JsonValue]) -> AlgorithmExperimentReport:
    if set(record) != {"schema_version", "report_id", "report"} or record.get(
        "schema_version"
    ) != RUN_RECORD_SCHEMA_VERSION:
        raise AlgorithmExperimentError("algorithm run record is invalid")
    report_id = record["report_id"]
    report = record["report"]
    if not isinstance(report_id, str) or not isinstance(report, dict):
        raise AlgorithmExperimentError("algorithm run record payload is invalid")
    if content_id(report) != report_id or report.get("schema_version") != RUN_REPORT_SCHEMA_VERSION:
        raise AlgorithmExperimentError("algorithm run report identity differs")
    return AlgorithmExperimentReport(
        report_id,
        int(report["task_count"]),
        int(report["case_count"]),
        int(report["cycle_count"]),
        str(report["final_vocabulary_id"]),
        bool(report["all_valid"]),
    )


def run_algorithm_experiment(output_directory: str | Path) -> AlgorithmExperimentReport:
    output = Path(output_directory)
    if output.exists():
        raise AlgorithmExperimentError(f"algorithm output already exists: {output}")
    tasks = registered_algorithm_tasks()
    vocabularies = _build_vocabularies(tasks)
    manifest: dict[str, JsonValue] = {
        "schema_version": EXPERIMENT_SCHEMA_VERSION,
        "experiment_name": "typed-algorithm-language-growth-a0-v0",
        "question": "does transparent cross-task vocabulary growth preserve algorithm validity and transfer",
        "kernel": "StructuredI64ArrayKernelV0",
        "cycles": [0, 1, 2],
        "learning_partitions": {
            "cycle_1": ["count_target", "linear_search_first"],
            "cycle_2": ["sum_array", "sum_positive_values"],
        },
        "protected_holdout": ["binary_search", "maximum_subarray"],
        "postfreeze_audit": ["two_sum_indices"],
        "validity_rule": "all_cycle_interpreter_cases_match_independent_oracle",
        "native_rule": "supplemental_compilation_must_match_the_same_archived_cases",
        "authority": "D0_offline_no_platform_submission_or_deployment",
        "registered_at": REGISTERED_AT,
    }
    output.mkdir(parents=True, exist_ok=False)
    _write_document(output / "experiment-manifest.json", manifest)
    for task in tasks.values():
        root = output / "tasks" / task.task_id
        _write_document(root / "contract.json", task.contract_document())
        _write_document(root / "cases.json", task.case_set_document)
        _write_document(root / "program.json", task.program.to_document())
        _write_text(root / "program.lai", render_program(task.program))
    for cycle, vocabulary in enumerate(vocabularies):
        _write_document(
            output / "vocabularies" / f"cycle-{cycle}.json",
            vocabulary.to_document(),
        )

    cycle_rows: list[JsonValue] = []
    result_by_task: dict[str, dict[int, Mapping[str, JsonValue]]] = {
        task_id: {} for task_id in tasks
    }
    for cycle, vocabulary in enumerate(vocabularies):
        passed_in_cycle = 0
        dispatch_in_cycle = 0
        for task in tasks.values():
            encoded = encode_program(task.program, vocabulary)
            cases = [item.to_document() for item in task.cases]
            case_results: list[JsonValue] = []
            total_dispatches = 0
            total_steps = 0
            trace_case_index = max(
                range(len(task.cases)),
                key=lambda index: (len(task.cases[index].nums), -index),
            )
            for case_index, case in enumerate(task.cases):
                core_result = execute_program(
                    task.program,
                    case.nums,
                    case.target,
                )
                result = execute_program(
                    encoded,
                    case.nums,
                    case.target,
                    vocabulary,
                    trace=case_index == trace_case_index,
                )
                if core_result.value != case.expected or result.value != core_result.value:
                    raise AlgorithmExperimentError(
                        f"algorithm validity failed for {task.task_id} cycle {cycle}"
                    )
                passed_in_cycle += 1
                total_dispatches += result.dispatches
                total_steps += result.steps
                case_results.append(
                    {
                        "case_id": case.to_document()["case_id"],
                        "actual": list(result.value) if isinstance(result.value, tuple) else result.value,
                        "matches_oracle": True,
                        "matches_core_lowering": True,
                        "dispatches": result.dispatches,
                        "steps": result.steps,
                    }
                )
                if case_index == trace_case_index:
                    _write_document(
                        output
                        / "cycles"
                        / f"cycle-{cycle}"
                        / task.task_id
                        / "trace.json",
                        {
                            "schema_version": TRACE_SCHEMA_VERSION,
                            "task_id": task.task_id,
                            "cycle": cycle,
                            "case_id": case.to_document()["case_id"],
                            "events": [dict(event) for event in result.trace],
                            "truncated": result.trace_truncated,
                        },
                    )
            encoded_id = content_id(encoded.to_document(encoded=True))
            validity: dict[str, JsonValue] = {
                "schema_version": VALIDITY_SCHEMA_VERSION,
                "task_id": task.task_id,
                "partition": task.partition,
                "cycle": cycle,
                "core_program_id": task.program.program_id,
                "encoded_program_id": encoded_id,
                "vocabulary_id": vocabulary.vocabulary_id,
                "intrinsic_entry_ids": sorted(set(intrinsic_uses(encoded))),
                "intrinsic_static_uses": len(intrinsic_uses(encoded)),
                "cases_passed": len(task.cases),
                "cases_total": len(task.cases),
                "all_outputs_match_oracle": True,
                "total_dispatches": total_dispatches,
                "total_steps": total_steps,
                "case_results": case_results,
            }
            task_root = output / "cycles" / f"cycle-{cycle}" / task.task_id
            _write_document(task_root / "encoded-program.json", encoded.to_document(encoded=True))
            _write_text(task_root / "program.lai", render_program(encoded))
            _write_text(task_root / "program.c", generate_c_source(encoded, vocabulary, cases))
            _write_document(task_root / "validity.json", validity)
            result_by_task[task.task_id][cycle] = validity
            dispatch_in_cycle += total_dispatches
        new_entry_id: JsonValue = None
        if cycle > 0:
            previous_ids = set(vocabularies[cycle - 1].by_id())
            new_entry_id = next(iter(set(vocabulary.by_id()) - previous_ids))
        cycle_rows.append(
            {
                "cycle": cycle,
                "vocabulary_id": vocabulary.vocabulary_id,
                "entry_count": len(vocabulary.entries),
                "new_entry_id": new_entry_id,
                "cases_passed": passed_in_cycle,
                "total_dispatches": dispatch_in_cycle,
            }
        )
    transfer: dict[str, JsonValue] = {}
    for task_id in ("binary_search", "maximum_subarray", "two_sum_indices"):
        baseline = int(result_by_task[task_id][0]["total_dispatches"])
        final = int(result_by_task[task_id][2]["total_dispatches"])
        transfer[task_id] = {
            "partition": tasks[task_id].partition,
            "cycle_0_dispatches": baseline,
            "cycle_2_dispatches": final,
            "dispatch_reduction": baseline - final,
            "all_cycles_valid": True,
        }
    report: dict[str, JsonValue] = {
        "schema_version": RUN_REPORT_SCHEMA_VERSION,
        "status": "complete",
        "experiment_manifest_id": content_id(manifest),
        "task_count": len(tasks),
        "case_count": sum(len(task.cases) for task in tasks.values()),
        "cycle_count": len(vocabularies),
        "final_vocabulary_id": vocabularies[-1].vocabulary_id,
        "cycle_results": cycle_rows,
        "platform_style_transfer": transfer,
        "all_valid": True,
        "validity_scope": "trusted_interpreter_all_cycles",
        "generated_c_sources": len(tasks) * len(vocabularies),
        "native_validation_required_for_compiled_claim": True,
        "official_platform_submission_performed": False,
        "limitations": [
            "local_contract_equivalence_not_official_leetcode_acceptance",
            "fixed_i64_array_and_scalar_abi",
            "bounded_structured_control_flow_only",
            "synthetic_deterministic_cases_not_hidden_platform_tests",
            "learned_intrinsics_preserve_fixed_transparent_lowering",
            "no_memory_allocation_strings_graphs_or_recursion",
        ],
    }
    report_id = content_id(report)
    _write_document(
        output / "run-report.json",
        {
            "schema_version": RUN_RECORD_SCHEMA_VERSION,
            "report_id": report_id,
            "report": report,
        },
    )
    return _report_from_record(_read_object(output / "run-report.json"))


def replay_algorithm_experiment(bundle_directory: str | Path) -> AlgorithmReplayReport:
    source = Path(bundle_directory)
    if not source.is_dir():
        raise AlgorithmExperimentError(f"algorithm bundle does not exist: {source}")
    source_report = _report_from_record(_read_object(source / "run-report.json"))
    with tempfile.TemporaryDirectory(prefix="laicode-algorithm-replay-") as directory:
        replay = Path(directory) / "bundle"
        replay_report = run_algorithm_experiment(replay)
        source_files = sorted(path.relative_to(source) for path in source.rglob("*") if path.is_file())
        replay_files = sorted(path.relative_to(replay) for path in replay.rglob("*") if path.is_file())
        if source_files != replay_files:
            raise AlgorithmExperimentError("algorithm replay inventory differs")
        for relative in source_files:
            if (source / relative).read_bytes() != (replay / relative).read_bytes():
                raise AlgorithmExperimentError(
                    f"algorithm replay mismatch in {relative.as_posix()}"
                )
        if source_report.report_id != replay_report.report_id:
            raise AlgorithmExperimentError("algorithm replay report identity differs")
    return AlgorithmReplayReport(
        source_report.report_id,
        replay_report.report_id,
        len(source_files),
    )


def _sha256_bytes(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _parse_native_output(value: str) -> tuple[int, str]:
    fields: dict[str, str] = {}
    for line in value.splitlines():
        if "=" not in line:
            raise AlgorithmExperimentError("native algorithm output is invalid")
        key, item = line.split("=", 1)
        if key in fields:
            raise AlgorithmExperimentError("native algorithm output has duplicate fields")
        fields[key] = item
    if set(fields) != {"cases", "checksum"}:
        raise AlgorithmExperimentError("native algorithm output fields are invalid")
    try:
        cases = int(fields["cases"])
    except ValueError as error:
        raise AlgorithmExperimentError("native algorithm case count is invalid") from error
    checksum = fields["checksum"]
    if cases < 1 or len(checksum) != 16 or any(item not in "0123456789abcdef" for item in checksum):
        raise AlgorithmExperimentError("native algorithm result is invalid")
    return cases, checksum


def validate_algorithm_native(
    bundle_directory: str | Path,
    output_directory: str | Path,
    *,
    compiler: str = "cc",
) -> AlgorithmNativeReport:
    bundle = Path(bundle_directory)
    output = Path(output_directory)
    if output.exists():
        raise AlgorithmExperimentError(f"native algorithm output exists: {output}")
    replay = replay_algorithm_experiment(bundle)
    compiler_path = shutil.which(compiler)
    if compiler_path is None:
        raise AlgorithmExperimentError(f"C compiler {compiler!r} is not installed")
    compiler_version = subprocess.run(
        (compiler_path, "--version"),
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    ).stdout.strip()
    tasks = registered_algorithm_tasks()
    selections = [
        (cycle, task_id)
        for cycle in range(3)
        for task_id in ("binary_search", "maximum_subarray", "two_sum_indices")
    ] + [
        (2, task_id)
        for task_id in (
            "count_target",
            "linear_search_first",
            "sum_array",
            "sum_positive_values",
        )
    ]
    output.mkdir(parents=True, exist_ok=False)
    results: list[JsonValue] = []
    cases_passed = 0
    for cycle, task_id in selections:
        source_path = bundle / "cycles" / f"cycle-{cycle}" / task_id / "program.c"
        artifact = output / "artifacts" / f"cycle-{cycle}--{task_id}"
        artifact.parent.mkdir(parents=True, exist_ok=True)
        compilation = subprocess.run(
            (compiler_path, *COMPILER_FLAGS, str(source_path), "-o", str(artifact)),
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        if compilation.returncode != 0:
            raise AlgorithmExperimentError(
                f"generated C failed for {task_id} cycle {cycle}: {compilation.stderr.strip()}"
            )
        execution = subprocess.run(
            (str(artifact),),
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        if execution.returncode != 0:
            raise AlgorithmExperimentError(
                f"generated C validity failed for {task_id} cycle {cycle}"
            )
        case_count, checksum = _parse_native_output(execution.stdout)
        if case_count != len(tasks[task_id].cases):
            raise AlgorithmExperimentError("generated C case count differs")
        artifact_bytes = artifact.read_bytes()
        cases_passed += case_count
        results.append(
            {
                "cycle": cycle,
                "task_id": task_id,
                "source_sha256": _sha256_bytes(source_path.read_bytes()),
                "artifact_sha256": _sha256_bytes(artifact_bytes),
                "artifact_bytes": len(artifact_bytes),
                "cases_passed": case_count,
                "checksum": checksum,
                "valid": True,
            }
        )
    host_report: dict[str, JsonValue] = {
        "schema_version": NATIVE_REPORT_SCHEMA_VERSION,
        "source_algorithm_report_id": replay.source_report_id,
        "host": {
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
        },
        "compiler": {
            "requested": compiler,
            "resolved_path": compiler_path,
            "version": compiler_version,
            "flags": list(COMPILER_FLAGS),
        },
        "translations": results,
        "translations_passed": len(results),
        "cases_passed": cases_passed,
        "all_valid": True,
        "performance_claim": False,
    }
    report_id = content_id(host_report)
    _write_document(
        output / "native-report.json",
        {
            "schema_version": NATIVE_RECORD_SCHEMA_VERSION,
            "report_id": report_id,
            "report": host_report,
        },
    )
    return AlgorithmNativeReport(
        report_id,
        compiler_path,
        len(results),
        cases_passed,
        True,
    )


def smoke_algorithm_language(
    output_directory: str | Path,
    *,
    compiler: str = "cc",
) -> tuple[AlgorithmExperimentReport, AlgorithmReplayReport, AlgorithmNativeReport]:
    output = Path(output_directory)
    if output.exists():
        raise AlgorithmExperimentError(f"algorithm smoke output exists: {output}")
    bundle = output / "bundle"
    native = output / "native"
    report = run_algorithm_experiment(bundle)
    replay = replay_algorithm_experiment(bundle)
    host = validate_algorithm_native(bundle, native, compiler=compiler)
    return report, replay, host
