"""Replayable A2 bounded-function and call-graph language study."""

from __future__ import annotations

import hashlib
import platform
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Mapping, Sequence

from .canonical import CanonicalizationError, JsonValue, canonical_json_bytes, content_id, load_json_strict
from .function_language import (
    EMPTY_FUNCTION_VOCABULARY,
    ENTRY_PARAMETERS,
    I64,
    Assign,
    Expression,
    ForRange,
    FunctionDef,
    FunctionProgram,
    FunctionVocabulary,
    If,
    Let,
    Parameter,
    Return,
    call_depth,
    call_graph,
    encode_program,
    execute_program,
    extend_vocabulary,
    generate_c_source,
    learn_function_abstraction,
    learned_definition,
    learned_uses,
    render_program,
    validate_program,
)


TASK_SCHEMA_VERSION = "FunctionTaskContractV2"
CASE_SET_SCHEMA_VERSION = "FunctionCaseSetV2"
EXPERIMENT_SCHEMA_VERSION = "FunctionLanguageExperimentV2"
VALIDITY_SCHEMA_VERSION = "FunctionValidityReportV2"
TRACE_SCHEMA_VERSION = "FunctionExecutionTraceV2"
RUN_REPORT_SCHEMA_VERSION = "FunctionLanguageRunReportV2"
RUN_RECORD_SCHEMA_VERSION = "FunctionLanguageRunReportRecordV2"
NATIVE_REPORT_SCHEMA_VERSION = "FunctionNativeValidityReportV2"
NATIVE_RECORD_SCHEMA_VERSION = "FunctionNativeValidityReportRecordV2"
REPLAY_SCHEMA_VERSION = "FunctionLanguageReplayV2"
REGISTERED_AT = "2026-08-01T00:00:00Z"
COMPILER_FLAGS = (
    "-std=c11",
    "-O2",
    "-Wall",
    "-Wextra",
    "-Werror",
    "-Wconversion",
    "-Wshadow",
    "-pedantic",
)


class FunctionExperimentError(RuntimeError):
    """Raised when the A2 function-language study cannot be reproduced."""


@dataclass(frozen=True)
class FunctionCase:
    nums: tuple[int, ...]
    target: int
    expected: int

    def to_document(self) -> dict[str, JsonValue]:
        payload: dict[str, JsonValue] = {
            "nums": list(self.nums),
            "target": self.target,
            "expected": self.expected,
        }
        return {"case_id": content_id(payload), **payload}


@dataclass(frozen=True)
class FunctionTask:
    task_id: str
    partition: str
    description: str
    platform_contract: str | None
    program: FunctionProgram
    cases: tuple[FunctionCase, ...]

    @property
    def contract_document(self) -> dict[str, JsonValue]:
        return {
            "schema_version": TASK_SCHEMA_VERSION,
            "task_id": self.task_id,
            "partition": self.partition,
            "description": self.description,
            "platform_contract": self.platform_contract,
            "parameters": [item.to_document() for item in ENTRY_PARAMETERS],
            "return_type": I64,
            "declared_functions": len(self.program.functions),
            "static_call_depth": call_depth(self.program),
            "maximum_input_elements": 256,
            "oracle": "independent_python_reference_v2",
            "official_submission": False,
        }

    @property
    def contract_id(self) -> str:
        return content_id(self.contract_document)

    @property
    def case_set_document(self) -> dict[str, JsonValue]:
        return {
            "schema_version": CASE_SET_SCHEMA_VERSION,
            "task_id": self.task_id,
            "generator": "splitmix64_function_cases_v2",
            "case_count": len(self.cases),
            "cases": [item.to_document() for item in self.cases],
        }

    @property
    def case_set_id(self) -> str:
        return content_id(self.case_set_document)


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


Oracle = Callable[[Sequence[int], int], int]


def _sum_absolute_oracle(nums: Sequence[int], target: int) -> int:
    del target
    return sum(abs(item) for item in nums)


def _count_large_absolute_oracle(nums: Sequence[int], target: int) -> int:
    return sum(1 for item in nums if abs(item) > target)


def _max_absolute_oracle(nums: Sequence[int], target: int) -> int:
    del target
    return max((abs(item) for item in nums), default=0)


def _max_prefix_sum_oracle(nums: Sequence[int], target: int) -> int:
    del target
    best = 0
    total = 0
    for item in nums:
        total += item
        best = max(best, total)
    return best


def _highest_altitude_oracle(nums: Sequence[int], target: int) -> int:
    del target
    best = 0
    altitude = 0
    for item in nums:
        altitude += item
        best = max(best, altitude)
    return best


def _sum_absolute_deviation_oracle(nums: Sequence[int], target: int) -> int:
    return sum(abs(item - target) for item in nums)


def _max_increasing_difference_oracle(nums: Sequence[int], target: int) -> int:
    del target
    best = -1
    for index in range(1, len(nums)):
        smallest = min(nums[:index])
        if nums[index] > smallest:
            best = max(best, nums[index] - smallest)
    return best


def _cases(seed: int, oracle: Oracle, *, target_mode: str) -> tuple[FunctionCase, ...]:
    random = _SplitMix64(seed)
    arrays = [
        (),
        (0,),
        (7,),
        (-7,),
        (1, 5, 2, 10, 6),
        (9, 4, 3, 2),
        (-3, -1, 0, 2, 4),
        (5, -2, 7, -4, 0, 6),
    ]
    while len(arrays) < 32:
        length = random.integer(0, 24)
        arrays.append(tuple(random.integer(-12, 12) for _ in range(length)))
    result: list[FunctionCase] = []
    for index, nums in enumerate(arrays):
        if target_mode == "zero":
            target = 0
        elif nums and index % 2 == 0:
            target = nums[random.integer(0, len(nums) - 1)]
        else:
            target = random.integer(-12, 12)
        result.append(FunctionCase(nums, target, oracle(nums, target)))
    return tuple(result)


def _v(name: str) -> Expression:
    return Expression("var", name=name)


def _c(value: int) -> Expression:
    return Expression("const", value=value)


def _e(op: str, *arguments: Expression) -> Expression:
    return Expression(op, tuple(arguments))


def _call(name: str, *arguments: Expression) -> Expression:
    return Expression("call", tuple(arguments), name=name)


def _abs_value() -> FunctionDef:
    return learned_definition("abs_value")


def _max_of() -> FunctionDef:
    return learned_definition("max_of")


def _min_of() -> FunctionDef:
    return FunctionDef(
        "min_of",
        (Parameter("a", I64), Parameter("b", I64)),
        I64,
        (
            If(_e("gt", _v("a"), _v("b")), (Return(_v("b")),), ()),
            Return(_v("a")),
        ),
    )


def _entry(task_id: str, body: tuple[Return | Let | Assign | ForRange | If, ...]) -> FunctionDef:
    return FunctionDef(task_id, ENTRY_PARAMETERS, I64, body)


def _sum_absolute_program() -> FunctionProgram:
    return FunctionProgram(
        "sum_absolute",
        (
            _abs_value(),
            _entry(
                "sum_absolute",
                (
                    Let("total", _c(0)),
                    ForRange(
                        "i",
                        _c(0),
                        _e("len", _v("nums")),
                        (Assign("total", _e("add", _v("total"), _call("abs_value", _e("get", _v("nums"), _v("i"))))),),
                    ),
                    Return(_v("total")),
                ),
            ),
        ),
    )


def _count_large_absolute_program() -> FunctionProgram:
    return FunctionProgram(
        "count_large_absolute",
        (
            _abs_value(),
            _entry(
                "count_large_absolute",
                (
                    Let("total", _c(0)),
                    ForRange(
                        "i",
                        _c(0),
                        _e("len", _v("nums")),
                        (
                            If(
                                _e("gt", _call("abs_value", _e("get", _v("nums"), _v("i"))), _v("target")),
                                (Assign("total", _e("add", _v("total"), _c(1))),),
                                (),
                            ),
                        ),
                    ),
                    Return(_v("total")),
                ),
            ),
        ),
    )


def _max_absolute_program() -> FunctionProgram:
    pair = FunctionDef(
        "max_absolute_pair",
        (Parameter("a", I64), Parameter("b", I64)),
        I64,
        (Return(_call("max_of", _call("abs_value", _v("a")), _call("abs_value", _v("b")))),),
    )
    return FunctionProgram(
        "max_absolute",
        (
            _abs_value(),
            _max_of(),
            pair,
            _entry(
                "max_absolute",
                (
                    Let("best", _c(0)),
                    ForRange(
                        "i",
                        _c(0),
                        _e("len", _v("nums")),
                        (Assign("best", _call("max_absolute_pair", _v("best"), _e("get", _v("nums"), _v("i")))),),
                    ),
                    Return(_v("best")),
                ),
            ),
        ),
    )


def _max_prefix_sum_program() -> FunctionProgram:
    return FunctionProgram(
        "max_prefix_sum",
        (
            _max_of(),
            _entry(
                "max_prefix_sum",
                (
                    Let("best", _c(0)),
                    Let("total", _c(0)),
                    ForRange(
                        "i",
                        _c(0),
                        _e("len", _v("nums")),
                        (
                            Assign("total", _e("add", _v("total"), _e("get", _v("nums"), _v("i")))),
                            Assign("best", _call("max_of", _v("best"), _v("total"))),
                        ),
                    ),
                    Return(_v("best")),
                ),
            ),
        ),
    )


def _highest_altitude_program() -> FunctionProgram:
    return FunctionProgram(
        "highest_altitude",
        (
            _max_of(),
            _entry(
                "highest_altitude",
                (
                    Let("best", _c(0)),
                    Let("altitude", _c(0)),
                    ForRange(
                        "i",
                        _c(0),
                        _e("len", _v("nums")),
                        (
                            Assign("altitude", _e("add", _v("altitude"), _e("get", _v("nums"), _v("i")))),
                            Assign("best", _call("max_of", _v("best"), _v("altitude"))),
                        ),
                    ),
                    Return(_v("best")),
                ),
            ),
        ),
    )


def _sum_absolute_deviation_program() -> FunctionProgram:
    return FunctionProgram(
        "sum_absolute_deviation",
        (
            _abs_value(),
            _entry(
                "sum_absolute_deviation",
                (
                    Let("total", _c(0)),
                    ForRange(
                        "i",
                        _c(0),
                        _e("len", _v("nums")),
                        (
                            Assign(
                                "total",
                                _e("add", _v("total"), _call("abs_value", _e("sub", _e("get", _v("nums"), _v("i")), _v("target")))),
                            ),
                        ),
                    ),
                    Return(_v("total")),
                ),
            ),
        ),
    )


def _max_increasing_difference_program() -> FunctionProgram:
    return FunctionProgram(
        "max_increasing_difference",
        (
            _max_of(),
            _min_of(),
            _entry(
                "max_increasing_difference",
                (
                    Let("best", _c(-1)),
                    Let("smallest", _c(0)),
                    ForRange(
                        "i",
                        _c(0),
                        _e("len", _v("nums")),
                        (
                            If(
                                _e("gt", _v("i"), _c(0)),
                                (
                                    If(
                                        _e("gt", _e("get", _v("nums"), _v("i")), _v("smallest")),
                                        (
                                            Assign(
                                                "best",
                                                _call("max_of", _v("best"), _e("sub", _e("get", _v("nums"), _v("i")), _v("smallest"))),
                                            ),
                                        ),
                                        (),
                                    ),
                                    Assign("smallest", _call("min_of", _v("smallest"), _e("get", _v("nums"), _v("i")))),
                                ),
                                (Assign("smallest", _e("get", _v("nums"), _v("i"))),),
                            ),
                        ),
                    ),
                    Return(_v("best")),
                ),
            ),
        ),
    )


def registered_function_tasks() -> dict[str, FunctionTask]:
    programs = {
        "sum_absolute": _sum_absolute_program(),
        "count_large_absolute": _count_large_absolute_program(),
        "max_absolute": _max_absolute_program(),
        "max_prefix_sum": _max_prefix_sum_program(),
        "highest_altitude": _highest_altitude_program(),
        "sum_absolute_deviation": _sum_absolute_deviation_program(),
        "max_increasing_difference": _max_increasing_difference_program(),
    }
    specifications = (
        ("sum_absolute", "learning_cycle_1", "total absolute magnitude of the input", None, _sum_absolute_oracle, "zero", 0xA201),
        ("count_large_absolute", "learning_cycle_1", "count values whose magnitude exceeds the target", None, _count_large_absolute_oracle, "random", 0xA202),
        ("max_absolute", "learning_cycle_2", "largest absolute value, zero when empty", None, _max_absolute_oracle, "zero", 0xA203),
        ("max_prefix_sum", "learning_cycle_2", "largest inclusive prefix sum, zero when empty", None, _max_prefix_sum_oracle, "zero", 0xA204),
        ("highest_altitude", "protected_holdout", "highest altitude reached from a gain sequence", "LeetCode 1732-style contract", _highest_altitude_oracle, "zero", 0xA205),
        ("sum_absolute_deviation", "protected_holdout", "total distance from every value to the target", "LeetCode 462-style total-distance contract with a supplied target", _sum_absolute_deviation_oracle, "random", 0xA206),
        ("max_increasing_difference", "postfreeze_audit", "largest increasing difference, minus one when absent", "LeetCode 2016-style contract", _max_increasing_difference_oracle, "zero", 0xA207),
    )
    tasks: dict[str, FunctionTask] = {}
    for task_id, partition, description, platform_contract, oracle, target_mode, seed in specifications:
        task = FunctionTask(task_id, partition, description, platform_contract, programs[task_id], _cases(seed, oracle, target_mode=target_mode))
        validate_program(task.program)
        for case in task.cases:
            if execute_program(task.program, case.nums, case.target).value != case.expected:
                raise AssertionError(f"registered function oracle differs for {task_id}")
        tasks[task_id] = task
    return tasks


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
        raise FunctionExperimentError(f"cannot read {path}: {error}") from error
    if not isinstance(value, dict):
        raise FunctionExperimentError(f"expected an object in {path}")
    return value


def _evidence_catalog_id(tasks: Sequence[FunctionTask], cycle: int) -> str:
    return content_id(
        {
            "schema_version": "FunctionLearningEvidenceCatalogV2",
            "cycle": cycle,
            "disclosure": "prefreeze_training_only",
            "tasks": [
                {"task_id": task.task_id, "contract_id": task.contract_id, "program_id": task.program.program_id, "case_set_id": task.case_set_id}
                for task in sorted(tasks, key=lambda item: item.task_id)
            ],
        }
    )


def _build_vocabularies(tasks: Mapping[str, FunctionTask]) -> tuple[FunctionVocabulary, ...]:
    primitive = EMPTY_FUNCTION_VOCABULARY
    first_tasks = [tasks["sum_absolute"], tasks["count_large_absolute"]]
    first = learn_function_abstraction(
        [task.program for task in first_tasks],
        primitive,
        evidence_catalog_id=_evidence_catalog_id(first_tasks, 1),
        cycle=1,
    )
    cycle_1 = extend_vocabulary(primitive, first)
    second_tasks = first_tasks + [tasks["max_absolute"], tasks["max_prefix_sum"]]
    second = learn_function_abstraction(
        [task.program for task in second_tasks],
        cycle_1,
        evidence_catalog_id=_evidence_catalog_id(second_tasks, 2),
        cycle=2,
    )
    cycle_2 = extend_vocabulary(cycle_1, second)
    if first.kind != "abs_value" or second.kind != "max_of":
        raise FunctionExperimentError("registered A2 growth abstractions changed")
    return primitive, cycle_1, cycle_2


@dataclass(frozen=True)
class FunctionExperimentReport:
    report_id: str
    task_count: int
    case_count: int
    cycle_count: int
    final_vocabulary_id: str
    all_valid: bool


@dataclass(frozen=True)
class FunctionReplayReport:
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
class FunctionNativeReport:
    report_id: str
    compiler: str
    translations_passed: int
    cases_passed: int
    all_valid: bool


def _report_from_record(record: Mapping[str, JsonValue]) -> FunctionExperimentReport:
    if set(record) != {"schema_version", "report_id", "report"} or record.get("schema_version") != RUN_RECORD_SCHEMA_VERSION:
        raise FunctionExperimentError("function run record is invalid")
    report_id, report = record["report_id"], record["report"]
    if not isinstance(report_id, str) or not isinstance(report, dict) or content_id(report) != report_id or report.get("schema_version") != RUN_REPORT_SCHEMA_VERSION:
        raise FunctionExperimentError("function run report identity differs")
    return FunctionExperimentReport(
        report_id,
        int(report["task_count"]),
        int(report["case_count"]),
        int(report["cycle_count"]),
        str(report["final_vocabulary_id"]),
        bool(report["all_valid"]),
    )


def run_function_experiment(output_directory: str | Path) -> FunctionExperimentReport:
    output = Path(output_directory)
    if output.exists():
        raise FunctionExperimentError(f"function output already exists: {output}")
    tasks = registered_function_tasks()
    vocabularies = _build_vocabularies(tasks)
    manifest: dict[str, JsonValue] = {
        "schema_version": EXPERIMENT_SCHEMA_VERSION,
        "experiment_name": "bounded-function-call-graph-language-growth-a2-v1",
        "question": "can learned function abstractions remove duplicated definitions while preserving exact execution cost",
        "kernel": "CallGraphFunctionKernelV2",
        "cycles": [0, 1, 2],
        "learning_partitions": {
            "cycle_1": ["sum_absolute", "count_large_absolute"],
            "cycle_2": ["max_absolute", "max_prefix_sum"],
        },
        "protected_holdout": ["highest_altitude", "sum_absolute_deviation"],
        "postfreeze_audit": ["max_increasing_difference"],
        "validity_rule": "all_cycle_interpreter_cases_match_independent_oracle",
        "native_rule": "strict_C11_translations_match_the_same_archived_cases",
        "call_rule": "forward_only_declaration_order_acyclic_depth_at_most_4_no_recursion",
        "cost_rule": "learned_abstractions_reduce_definition_statements_at_identical_dispatch",
        "authority": "D0_offline_no_platform_submission_or_deployment",
        "registered_at": REGISTERED_AT,
    }
    output.mkdir(parents=True, exist_ok=False)
    _write_document(output / "experiment-manifest.json", manifest)
    for task in tasks.values():
        root = output / "tasks" / task.task_id
        _write_document(root / "contract.json", task.contract_document)
        _write_document(root / "cases.json", task.case_set_document)
        _write_document(root / "program.json", task.program.to_document())
        _write_text(root / "program.lai", render_program(task.program))
    for cycle, vocabulary in enumerate(vocabularies):
        _write_document(output / "vocabularies" / f"cycle-{cycle}.json", vocabulary.to_document())

    cycle_rows: list[JsonValue] = []
    results: dict[str, dict[int, Mapping[str, JsonValue]]] = {task_id: {} for task_id in tasks}
    for cycle, vocabulary in enumerate(vocabularies):
        passed = 0
        dispatches = 0
        definitions = 0
        for task in tasks.values():
            encoded = encode_program(task.program, vocabulary)
            cases = [item.to_document() for item in task.cases]
            case_results: list[JsonValue] = []
            task_dispatches = 0
            task_steps = 0
            task_calls = 0
            trace_index = max(range(len(task.cases)), key=lambda index: (len(task.cases[index].nums), -index))
            for case_index, case in enumerate(task.cases):
                core = execute_program(task.program, case.nums, case.target)
                actual = execute_program(encoded, case.nums, case.target, vocabulary, trace=case_index == trace_index)
                if core.value != case.expected or actual.value != core.value:
                    raise FunctionExperimentError(f"function validity failed for {task.task_id} cycle {cycle}")
                if actual.dispatches != core.dispatches:
                    raise FunctionExperimentError(f"function encoding changed dispatch for {task.task_id} cycle {cycle}")
                passed += 1
                task_dispatches += actual.dispatches
                task_steps += actual.steps
                task_calls += actual.calls
                case_results.append(
                    {
                        "case_id": case.to_document()["case_id"],
                        "actual": actual.value,
                        "matches_oracle": True,
                        "matches_core_lowering": True,
                        "dispatches": actual.dispatches,
                        "steps": actual.steps,
                        "calls": actual.calls,
                        "maximum_depth": actual.maximum_depth,
                    }
                )
                if case_index == trace_index:
                    _write_document(
                        output / "cycles" / f"cycle-{cycle}" / task.task_id / "trace.json",
                        {
                            "schema_version": TRACE_SCHEMA_VERSION,
                            "task_id": task.task_id,
                            "cycle": cycle,
                            "case_id": case.to_document()["case_id"],
                            "events": [dict(event) for event in actual.trace],
                            "truncated": actual.trace_truncated,
                        },
                    )
            validity: dict[str, JsonValue] = {
                "schema_version": VALIDITY_SCHEMA_VERSION,
                "task_id": task.task_id,
                "partition": task.partition,
                "cycle": cycle,
                "core_program_id": task.program.program_id,
                "encoded_program_id": content_id(encoded.to_document(encoded=True)),
                "vocabulary_id": vocabulary.vocabulary_id,
                "learned_entry_ids": sorted(set(learned_uses(encoded))),
                "learned_static_uses": len(learned_uses(encoded)),
                "declared_functions": len(encoded.functions),
                "definition_statements": encoded.definition_statements,
                "static_call_depth": call_depth(encoded, vocabulary),
                "call_graph": {name: list(callees) for name, callees in call_graph(encoded).items()},
                "cases_passed": len(task.cases),
                "cases_total": len(task.cases),
                "all_outputs_match_oracle": True,
                "total_dispatches": task_dispatches,
                "total_steps": task_steps,
                "total_calls": task_calls,
                "case_results": case_results,
            }
            root = output / "cycles" / f"cycle-{cycle}" / task.task_id
            _write_document(root / "encoded-program.json", encoded.to_document(encoded=True))
            _write_text(root / "program.lai", render_program(encoded, vocabulary))
            _write_text(root / "program.c", generate_c_source(encoded, vocabulary, cases))
            _write_document(root / "validity.json", validity)
            results[task.task_id][cycle] = validity
            dispatches += task_dispatches
            definitions += encoded.definition_statements
        new_entry: JsonValue = None
        if cycle:
            new_entry = next(iter(set(vocabulary.by_id()) - set(vocabularies[cycle - 1].by_id())))
        cycle_rows.append(
            {
                "cycle": cycle,
                "vocabulary_id": vocabulary.vocabulary_id,
                "entry_count": len(vocabulary.entries),
                "new_entry_id": new_entry,
                "cases_passed": passed,
                "total_dispatches": dispatches,
                "total_definition_statements": definitions,
            }
        )

    transfer: dict[str, JsonValue] = {}
    for task_id in ("highest_altitude", "sum_absolute_deviation", "max_increasing_difference"):
        baseline = results[task_id][0]
        final = results[task_id][2]
        transfer[task_id] = {
            "partition": tasks[task_id].partition,
            "cycle_0_definition_statements": int(baseline["definition_statements"]),
            "cycle_2_definition_statements": int(final["definition_statements"]),
            "definition_statement_reduction": int(baseline["definition_statements"]) - int(final["definition_statements"]),
            "cycle_0_dispatches": int(baseline["total_dispatches"]),
            "cycle_2_dispatches": int(final["total_dispatches"]),
            "dispatch_change": int(final["total_dispatches"]) - int(baseline["total_dispatches"]),
            "learned_entry_ids": list(final["learned_entry_ids"]),
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
        "unlearned_local_functions": ["max_absolute_pair", "min_of"],
        "maximum_static_call_depth": max(call_depth(task.program) for task in tasks.values()),
        "all_valid": True,
        "validity_scope": "trusted_interpreter_all_cycles",
        "generated_c_sources": len(tasks) * len(vocabularies),
        "native_validation_required_for_compiled_claim": True,
        "official_platform_submission_performed": False,
        "limitations": [
            "local_contract_equivalence_not_official_leetcode_acceptance",
            "learned_abstractions_reduce_definitions_without_reducing_dispatch",
            "functions_are_pure_and_return_only_scalars_in_this_epoch",
            "no_recursion_indirect_calls_function_values_or_mutual_reference",
            "synthetic_deterministic_cases_not_hidden_platform_tests",
            "no_heap_vectors_strings_maps_or_graphs",
        ],
    }
    report_id = content_id(report)
    _write_document(output / "run-report.json", {"schema_version": RUN_RECORD_SCHEMA_VERSION, "report_id": report_id, "report": report})
    return _report_from_record(_read_object(output / "run-report.json"))


def replay_function_experiment(bundle_directory: str | Path) -> FunctionReplayReport:
    source = Path(bundle_directory)
    if not source.is_dir():
        raise FunctionExperimentError(f"function bundle does not exist: {source}")
    source_report = _report_from_record(_read_object(source / "run-report.json"))
    with tempfile.TemporaryDirectory(prefix="laicode-function-replay-") as directory:
        replay = Path(directory) / "bundle"
        replay_report = run_function_experiment(replay)
        source_files = sorted(path.relative_to(source) for path in source.rglob("*") if path.is_file())
        replay_files = sorted(path.relative_to(replay) for path in replay.rglob("*") if path.is_file())
        if source_files != replay_files:
            raise FunctionExperimentError("function replay inventory differs")
        for relative in source_files:
            if (source / relative).read_bytes() != (replay / relative).read_bytes():
                raise FunctionExperimentError(f"function replay mismatch in {relative.as_posix()}")
        if source_report.report_id != replay_report.report_id:
            raise FunctionExperimentError("function replay report identity differs")
    return FunctionReplayReport(source_report.report_id, replay_report.report_id, len(source_files))


def _sha256_bytes(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _parse_native_output(value: str) -> tuple[int, str]:
    fields: dict[str, str] = {}
    for line in value.splitlines():
        if "=" not in line:
            raise FunctionExperimentError("native function output is invalid")
        key, item = line.split("=", 1)
        if key in fields:
            raise FunctionExperimentError("native function output has duplicate fields")
        fields[key] = item
    if set(fields) != {"cases", "checksum"}:
        raise FunctionExperimentError("native function output fields are invalid")
    try:
        cases = int(fields["cases"])
    except ValueError as error:
        raise FunctionExperimentError("native function case count is invalid") from error
    checksum = fields["checksum"]
    if cases < 1 or len(checksum) != 16 or any(item not in "0123456789abcdef" for item in checksum):
        raise FunctionExperimentError("native function result is invalid")
    return cases, checksum


def validate_function_native(bundle_directory: str | Path, output_directory: str | Path, *, compiler: str = "cc") -> FunctionNativeReport:
    bundle, output = Path(bundle_directory), Path(output_directory)
    if output.exists():
        raise FunctionExperimentError(f"native function output exists: {output}")
    replay = replay_function_experiment(bundle)
    compiler_path = shutil.which(compiler)
    if compiler_path is None:
        raise FunctionExperimentError(f"C compiler {compiler!r} is not installed")
    version = subprocess.run((compiler_path, "--version"), check=False, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True).stdout.strip()
    tasks = registered_function_tasks()
    platform_tasks = ("highest_altitude", "sum_absolute_deviation", "max_increasing_difference")
    learning_tasks = ("sum_absolute", "count_large_absolute", "max_absolute", "max_prefix_sum")
    selections = [(cycle, task_id) for cycle in range(3) for task_id in platform_tasks] + [(2, task_id) for task_id in learning_tasks]
    output.mkdir(parents=True, exist_ok=False)
    translations: list[JsonValue] = []
    cases_passed = 0
    for cycle, task_id in selections:
        source = bundle / "cycles" / f"cycle-{cycle}" / task_id / "program.c"
        artifact = output / "artifacts" / f"cycle-{cycle}--{task_id}"
        artifact.parent.mkdir(parents=True, exist_ok=True)
        compilation = subprocess.run((compiler_path, *COMPILER_FLAGS, str(source), "-o", str(artifact)), check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if compilation.returncode != 0:
            raise FunctionExperimentError(f"generated function C failed for {task_id} cycle {cycle}: {compilation.stderr.strip()}")
        execution = subprocess.run((str(artifact),), check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if execution.returncode != 0:
            raise FunctionExperimentError(f"generated function C validity failed for {task_id} cycle {cycle}: exit {execution.returncode}")
        case_count, checksum = _parse_native_output(execution.stdout)
        if case_count != len(tasks[task_id].cases):
            raise FunctionExperimentError("generated function C case count differs")
        cases_passed += case_count
        translations.append(
            {
                "cycle": cycle,
                "task_id": task_id,
                "source_sha256": _sha256_bytes(source.read_bytes()),
                "artifact_sha256": _sha256_bytes(artifact.read_bytes()),
                "artifact_bytes": len(artifact.read_bytes()),
                "cases_passed": case_count,
                "checksum": checksum,
                "valid": True,
            }
        )
    checksums: dict[str, set[str]] = {}
    for translation in translations:
        assert isinstance(translation, dict)
        checksums.setdefault(str(translation["task_id"]), set()).add(str(translation["checksum"]))
    if any(len(values) != 1 for values in checksums.values()):
        raise FunctionExperimentError("generated function C checksums differ across cycles")
    report: dict[str, JsonValue] = {
        "schema_version": NATIVE_REPORT_SCHEMA_VERSION,
        "source_function_report_id": replay.source_report_id,
        "host": {"system": platform.system(), "release": platform.release(), "machine": platform.machine()},
        "compiler": {"requested": compiler, "resolved_path": compiler_path, "version": version, "flags": list(COMPILER_FLAGS)},
        "translations": translations,
        "translations_passed": len(translations),
        "cases_passed": cases_passed,
        "checksum_stable_across_cycles": True,
        "all_valid": True,
        "performance_claim": False,
    }
    report_id = content_id(report)
    _write_document(output / "native-report.json", {"schema_version": NATIVE_RECORD_SCHEMA_VERSION, "report_id": report_id, "report": report})
    return FunctionNativeReport(report_id, compiler_path, len(translations), cases_passed, True)


def smoke_function_language(output_directory: str | Path, *, compiler: str = "cc") -> tuple[FunctionExperimentReport, FunctionReplayReport, FunctionNativeReport]:
    output = Path(output_directory)
    if output.exists():
        raise FunctionExperimentError(f"function smoke output exists: {output}")
    bundle, native = output / "bundle", output / "native"
    report = run_function_experiment(bundle)
    replay = replay_function_experiment(bundle)
    host = validate_function_native(bundle, native, compiler=compiler)
    return report, replay, host
