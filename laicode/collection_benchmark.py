"""Replayable A1 owned-vector and typed-record language study."""

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
from .collection_language import (
    ARRAY_I64,
    I64,
    VECTOR_I64,
    EMPTY_COLLECTION_VOCABULARY,
    Assign,
    CollectionProgram,
    CollectionVocabulary,
    Expression,
    ForRange,
    If,
    Let,
    OwnVector,
    Push,
    RecordField,
    Return,
    ReturnType,
    VECTOR_RETURN,
    encode_program,
    execute_program,
    extend_vocabulary,
    generate_c_source,
    intrinsic_uses,
    learn_collection_intrinsic,
    render_program,
    validate_program,
)


TASK_SCHEMA_VERSION = "CollectionTaskContractV1"
CASE_SET_SCHEMA_VERSION = "CollectionCaseSetV1"
EXPERIMENT_SCHEMA_VERSION = "CollectionLanguageExperimentV1"
VALIDITY_SCHEMA_VERSION = "CollectionValidityReportV1"
TRACE_SCHEMA_VERSION = "CollectionExecutionTraceV1"
RUN_REPORT_SCHEMA_VERSION = "CollectionLanguageRunReportV1"
RUN_RECORD_SCHEMA_VERSION = "CollectionLanguageRunReportRecordV1"
NATIVE_REPORT_SCHEMA_VERSION = "CollectionNativeValidityReportV1"
NATIVE_RECORD_SCHEMA_VERSION = "CollectionNativeValidityReportRecordV1"
REPLAY_SCHEMA_VERSION = "CollectionLanguageReplayV1"
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


class CollectionExperimentError(RuntimeError):
    """Raised when the A1 collection-language study cannot be reproduced."""


def _value_document(value: object) -> JsonValue:
    if isinstance(value, tuple):
        return [_value_document(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _value_document(item) for key, item in value.items()}
    if isinstance(value, (bool, int, str)) or value is None:
        return value
    raise CollectionExperimentError("collection result is not canonical JSON")


@dataclass(frozen=True)
class CollectionCase:
    nums: tuple[int, ...]
    target: int
    expected: JsonValue

    def to_document(self) -> dict[str, JsonValue]:
        payload: dict[str, JsonValue] = {
            "nums": list(self.nums),
            "target": self.target,
            "expected": self.expected,
        }
        return {"case_id": content_id(payload), **payload}


@dataclass(frozen=True)
class CollectionTask:
    task_id: str
    partition: str
    description: str
    platform_contract: str | None
    program: CollectionProgram
    cases: tuple[CollectionCase, ...]

    @property
    def contract_document(self) -> dict[str, JsonValue]:
        return {
            "schema_version": TASK_SCHEMA_VERSION,
            "task_id": self.task_id,
            "partition": self.partition,
            "description": self.description,
            "platform_contract": self.platform_contract,
            "parameters": [
                {"name": "nums", "type": ARRAY_I64},
                {"name": "target", "type": I64},
            ],
            "return_type": self.program.return_type.to_document(),
            "maximum_input_elements": 256,
            "oracle": "independent_python_reference_v1",
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
            "generator": "splitmix64_collection_cases_v1",
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


Oracle = Callable[[Sequence[int], int], JsonValue]


def _copy_oracle(nums: Sequence[int], target: int) -> JsonValue:
    del target
    return list(nums)


def _reverse_oracle(nums: Sequence[int], target: int) -> JsonValue:
    del target
    return list(reversed(nums))


def _positive_oracle(nums: Sequence[int], target: int) -> JsonValue:
    del target
    return [item for item in nums if item > 0]


def _not_target_oracle(nums: Sequence[int], target: int) -> JsonValue:
    return [item for item in nums if item != target]


def _remove_record_oracle(nums: Sequence[int], target: int) -> JsonValue:
    values = [item for item in nums if item != target]
    return {"values": values, "length": len(values)}


def _running_sum_oracle(nums: Sequence[int], target: int) -> JsonValue:
    del target
    total = 0
    values: list[int] = []
    for item in nums:
        total += item
        values.append(total)
    return values


def _move_zeroes_oracle(nums: Sequence[int], target: int) -> JsonValue:
    del target
    nonzero = [item for item in nums if item != 0]
    return nonzero + [0] * (len(nums) - len(nonzero))


def _cases(seed: int, oracle: Oracle, *, target_mode: str) -> tuple[CollectionCase, ...]:
    random = _SplitMix64(seed)
    arrays = [
        (),
        (0,),
        (1,),
        (-1,),
        (0, 1, 0, 3, 12),
        (2, 2, 3, 2),
        (-3, -1, 0, 2, 4),
        (5, -2, 7, -4, 0, 6),
    ]
    while len(arrays) < 32:
        length = random.integer(0, 24)
        arrays.append(tuple(random.integer(-12, 12) for _ in range(length)))
    result: list[CollectionCase] = []
    for index, nums in enumerate(arrays):
        if target_mode == "zero":
            target = 0
        elif nums and index % 2 == 0:
            target = nums[random.integer(0, len(nums) - 1)]
        else:
            target = random.integer(-12, 12)
        result.append(CollectionCase(nums, target, oracle(nums, target)))
    return tuple(result)


def _v(name: str) -> Expression:
    return Expression("var", name=name)


def _c(value: int) -> Expression:
    return Expression("const", value=value)


def _e(op: str, *arguments: Expression) -> Expression:
    return Expression(op, tuple(arguments))


def _vector_return(name: str = "out") -> Return:
    return Return((("value", _v(name)),))


def _copy_program() -> CollectionProgram:
    return CollectionProgram(
        "copy_array",
        VECTOR_RETURN,
        (
            OwnVector("out", _e("len", _v("nums"))),
            ForRange("i", _c(0), _e("len", _v("nums")), (Push("out", _e("get", _v("nums"), _v("i"))),)),
            _vector_return(),
        ),
    )


def _reverse_program() -> CollectionProgram:
    reverse_index = _e("sub", _e("sub", _e("len", _v("nums")), _c(1)), _v("i"))
    return CollectionProgram(
        "reverse_array",
        VECTOR_RETURN,
        (
            OwnVector("out", _e("len", _v("nums"))),
            ForRange("i", _c(0), _e("len", _v("nums")), (Push("out", _e("get", _v("nums"), reverse_index)),)),
            _vector_return(),
        ),
    )


def _filter_program(task_id: str, condition: Expression) -> CollectionProgram:
    return CollectionProgram(
        task_id,
        VECTOR_RETURN,
        (
            OwnVector("out", _e("len", _v("nums"))),
            ForRange(
                "i",
                _c(0),
                _e("len", _v("nums")),
                (If(condition, (Push("out", _e("get", _v("nums"), _v("i"))),), ()),),
            ),
            _vector_return(),
        ),
    )


def _remove_record_program() -> CollectionProgram:
    return_type = ReturnType(
        "record",
        "collection_result",
        (RecordField("values", VECTOR_I64), RecordField("length", I64)),
    )
    condition = _e("ne", _e("get", _v("nums"), _v("i")), _v("target"))
    return CollectionProgram(
        "remove_element",
        return_type,
        (
            OwnVector("out", _e("len", _v("nums"))),
            ForRange("i", _c(0), _e("len", _v("nums")), (If(condition, (Push("out", _e("get", _v("nums"), _v("i"))),), ()),)),
            Return((("values", _v("out")), ("length", _e("len", _v("out"))))),
        ),
    )


def _running_sum_program() -> CollectionProgram:
    return CollectionProgram(
        "running_sum",
        VECTOR_RETURN,
        (
            OwnVector("out", _e("len", _v("nums"))),
            Let("total", _c(0)),
            ForRange(
                "i",
                _c(0),
                _e("len", _v("nums")),
                (
                    Assign("total", _e("add", _v("total"), _e("get", _v("nums"), _v("i")))),
                    Push("out", _v("total")),
                ),
            ),
            _vector_return(),
        ),
    )


def _move_zeroes_program() -> CollectionProgram:
    condition = _e("ne", _e("get", _v("nums"), _v("i")), _c(0))
    return CollectionProgram(
        "move_zeroes",
        VECTOR_RETURN,
        (
            OwnVector("out", _e("len", _v("nums"))),
            ForRange("i", _c(0), _e("len", _v("nums")), (If(condition, (Push("out", _e("get", _v("nums"), _v("i"))),), ()),)),
            Let("zeros", _e("sub", _e("len", _v("nums")), _e("len", _v("out")))),
            ForRange("j", _c(0), _v("zeros"), (Push("out", _c(0)),)),
            _vector_return(),
        ),
    )


def registered_collection_tasks() -> dict[str, CollectionTask]:
    programs = {
        "copy_array": _copy_program(),
        "reverse_array": _reverse_program(),
        "filter_positive": _filter_program("filter_positive", _e("gt", _e("get", _v("nums"), _v("i")), _c(0))),
        "filter_not_target": _filter_program("filter_not_target", _e("ne", _e("get", _v("nums"), _v("i")), _v("target"))),
        "remove_element": _remove_record_program(),
        "running_sum": _running_sum_program(),
        "move_zeroes": _move_zeroes_program(),
    }
    specifications = (
        ("copy_array", "learning_cycle_1", "construct an owned copy of the input", None, _copy_oracle, "random", 0xA101),
        ("reverse_array", "learning_cycle_1", "construct the input in reverse order", None, _reverse_oracle, "random", 0xA102),
        ("filter_positive", "learning_cycle_2", "retain positive input values in stable order", None, _positive_oracle, "zero", 0xA103),
        ("filter_not_target", "learning_cycle_2", "retain values unequal to target", None, _not_target_oracle, "random", 0xA104),
        ("remove_element", "protected_holdout", "return retained values and their logical length", "LeetCode 27-style value-plus-length contract", _remove_record_oracle, "random", 0xA105),
        ("running_sum", "protected_holdout", "construct inclusive prefix sums", "LeetCode 1480-style contract", _running_sum_oracle, "zero", 0xA106),
        ("move_zeroes", "postfreeze_audit", "stably move zero values to the end", "LeetCode 283-style functional contract", _move_zeroes_oracle, "zero", 0xA107),
    )
    tasks: dict[str, CollectionTask] = {}
    for task_id, partition, description, platform_contract, oracle, target_mode, seed in specifications:
        task = CollectionTask(task_id, partition, description, platform_contract, programs[task_id], _cases(seed, oracle, target_mode=target_mode))
        validate_program(task.program)
        for case in task.cases:
            actual = _value_document(execute_program(task.program, case.nums, case.target).value)
            if actual != case.expected:
                raise AssertionError(f"registered collection oracle differs for {task_id}")
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
        raise CollectionExperimentError(f"cannot read {path}: {error}") from error
    if not isinstance(value, dict):
        raise CollectionExperimentError(f"expected an object in {path}")
    return value


def _evidence_catalog_id(tasks: Sequence[CollectionTask], cycle: int) -> str:
    return content_id(
        {
            "schema_version": "CollectionLearningEvidenceCatalogV1",
            "cycle": cycle,
            "disclosure": "prefreeze_training_only",
            "tasks": [
                {"task_id": task.task_id, "contract_id": task.contract_id, "program_id": task.program.program_id, "case_set_id": task.case_set_id}
                for task in sorted(tasks, key=lambda item: item.task_id)
            ],
        }
    )


def _build_vocabularies(tasks: Mapping[str, CollectionTask]) -> tuple[CollectionVocabulary, ...]:
    primitive = EMPTY_COLLECTION_VOCABULARY
    first_tasks = [tasks["copy_array"], tasks["reverse_array"]]
    first = learn_collection_intrinsic([task.program for task in first_tasks], primitive, evidence_catalog_id=_evidence_catalog_id(first_tasks, 1), cycle=1)
    cycle_1 = extend_vocabulary(primitive, first)
    second_tasks = first_tasks + [tasks["filter_positive"], tasks["filter_not_target"]]
    second = learn_collection_intrinsic([task.program for task in second_tasks], cycle_1, evidence_catalog_id=_evidence_catalog_id(second_tasks, 2), cycle=2)
    cycle_2 = extend_vocabulary(cycle_1, second)
    if first.kind != "push_indexed" or second.kind != "append_indexed_if":
        raise CollectionExperimentError("registered A1 growth motifs changed")
    return primitive, cycle_1, cycle_2


@dataclass(frozen=True)
class CollectionExperimentReport:
    report_id: str
    task_count: int
    case_count: int
    cycle_count: int
    final_vocabulary_id: str
    all_valid: bool


@dataclass(frozen=True)
class CollectionReplayReport:
    source_report_id: str
    replay_report_id: str
    files_verified: int

    def to_document(self) -> dict[str, JsonValue]:
        return {"schema_version": REPLAY_SCHEMA_VERSION, "source_report_id": self.source_report_id, "replay_report_id": self.replay_report_id, "files_verified": self.files_verified, "exact_match": True}


@dataclass(frozen=True)
class CollectionNativeReport:
    report_id: str
    compiler: str
    translations_passed: int
    cases_passed: int
    all_valid: bool


def _report_from_record(record: Mapping[str, JsonValue]) -> CollectionExperimentReport:
    if set(record) != {"schema_version", "report_id", "report"} or record.get("schema_version") != RUN_RECORD_SCHEMA_VERSION:
        raise CollectionExperimentError("collection run record is invalid")
    report_id, report = record["report_id"], record["report"]
    if not isinstance(report_id, str) or not isinstance(report, dict) or content_id(report) != report_id or report.get("schema_version") != RUN_REPORT_SCHEMA_VERSION:
        raise CollectionExperimentError("collection run report identity differs")
    return CollectionExperimentReport(report_id, int(report["task_count"]), int(report["case_count"]), int(report["cycle_count"]), str(report["final_vocabulary_id"]), bool(report["all_valid"]))


def run_collection_experiment(output_directory: str | Path) -> CollectionExperimentReport:
    output = Path(output_directory)
    if output.exists():
        raise CollectionExperimentError(f"collection output already exists: {output}")
    tasks = registered_collection_tasks()
    vocabularies = _build_vocabularies(tasks)
    manifest: dict[str, JsonValue] = {
        "schema_version": EXPERIMENT_SCHEMA_VERSION,
        "experiment_name": "owned-vector-record-language-growth-a1-v1",
        "question": "can bounded owned outputs and records preserve validity while learned statement forms transfer",
        "kernel": "OwnedVectorRecordKernelV1",
        "cycles": [0, 1, 2],
        "learning_partitions": {"cycle_1": ["copy_array", "reverse_array"], "cycle_2": ["filter_positive", "filter_not_target"]},
        "protected_holdout": ["remove_element", "running_sum"],
        "postfreeze_audit": ["move_zeroes"],
        "validity_rule": "all_cycle_interpreter_cases_match_independent_oracle",
        "native_rule": "strict_C11_translations_match_the_same_archived_cases",
        "memory_rule": "input_immutable_owned_vectors_bounded_to_256_i64_elements",
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
        for task in tasks.values():
            encoded = encode_program(task.program, vocabulary)
            cases = [item.to_document() for item in task.cases]
            case_results: list[JsonValue] = []
            task_dispatches = 0
            task_steps = 0
            trace_index = max(range(len(task.cases)), key=lambda index: (len(task.cases[index].nums), -index))
            for case_index, case in enumerate(task.cases):
                core = execute_program(task.program, case.nums, case.target)
                actual = execute_program(encoded, case.nums, case.target, vocabulary, trace=case_index == trace_index)
                core_value = _value_document(core.value)
                actual_value = _value_document(actual.value)
                if core_value != case.expected or actual_value != core_value:
                    raise CollectionExperimentError(f"collection validity failed for {task.task_id} cycle {cycle}")
                passed += 1
                task_dispatches += actual.dispatches
                task_steps += actual.steps
                case_results.append({"case_id": case.to_document()["case_id"], "actual": actual_value, "matches_oracle": True, "matches_core_lowering": True, "dispatches": actual.dispatches, "steps": actual.steps})
                if case_index == trace_index:
                    _write_document(output / "cycles" / f"cycle-{cycle}" / task.task_id / "trace.json", {"schema_version": TRACE_SCHEMA_VERSION, "task_id": task.task_id, "cycle": cycle, "case_id": case.to_document()["case_id"], "events": [dict(event) for event in actual.trace], "truncated": actual.trace_truncated})
            validity: dict[str, JsonValue] = {
                "schema_version": VALIDITY_SCHEMA_VERSION,
                "task_id": task.task_id,
                "partition": task.partition,
                "cycle": cycle,
                "core_program_id": task.program.program_id,
                "encoded_program_id": content_id(encoded.to_document(encoded=True)),
                "vocabulary_id": vocabulary.vocabulary_id,
                "intrinsic_entry_ids": sorted(set(intrinsic_uses(encoded))),
                "intrinsic_static_uses": len(intrinsic_uses(encoded)),
                "cases_passed": len(task.cases),
                "cases_total": len(task.cases),
                "all_outputs_match_oracle": True,
                "total_dispatches": task_dispatches,
                "total_steps": task_steps,
                "case_results": case_results,
            }
            root = output / "cycles" / f"cycle-{cycle}" / task.task_id
            _write_document(root / "encoded-program.json", encoded.to_document(encoded=True))
            _write_text(root / "program.lai", render_program(encoded, vocabulary))
            _write_text(root / "program.c", generate_c_source(encoded, vocabulary, cases))
            _write_document(root / "validity.json", validity)
            results[task.task_id][cycle] = validity
            dispatches += task_dispatches
        new_entry: JsonValue = None
        if cycle:
            new_entry = next(iter(set(vocabulary.by_id()) - set(vocabularies[cycle - 1].by_id())))
        cycle_rows.append({"cycle": cycle, "vocabulary_id": vocabulary.vocabulary_id, "entry_count": len(vocabulary.entries), "new_entry_id": new_entry, "cases_passed": passed, "total_dispatches": dispatches})

    transfer: dict[str, JsonValue] = {}
    for task_id in ("remove_element", "move_zeroes"):
        baseline = int(results[task_id][0]["total_dispatches"])
        final = int(results[task_id][2]["total_dispatches"])
        transfer[task_id] = {"partition": tasks[task_id].partition, "cycle_0_dispatches": baseline, "cycle_2_dispatches": final, "dispatch_reduction": baseline - final, "all_cycles_valid": True}
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
        "record_tasks": ["remove_element"],
        "vector_tasks": [task_id for task_id, task in tasks.items() if task.program.return_type.kind == "vector"],
        "all_valid": True,
        "validity_scope": "trusted_interpreter_all_cycles",
        "generated_c_sources": len(tasks) * len(vocabularies),
        "native_validation_required_for_compiled_claim": True,
        "official_platform_submission_performed": False,
        "limitations": [
            "local_contract_equivalence_not_official_leetcode_acceptance",
            "owned_vectors_are_bounded_and_lower_to_fixed_local_C_storage",
            "one_owned_vector_field_per_record",
            "synthetic_deterministic_cases_not_hidden_platform_tests",
            "learned_intrinsics_preserve_fixed_transparent_lowering",
            "no_heap_strings_maps_graphs_functions_or_recursion",
        ],
    }
    report_id = content_id(report)
    _write_document(output / "run-report.json", {"schema_version": RUN_RECORD_SCHEMA_VERSION, "report_id": report_id, "report": report})
    return _report_from_record(_read_object(output / "run-report.json"))


def replay_collection_experiment(bundle_directory: str | Path) -> CollectionReplayReport:
    source = Path(bundle_directory)
    if not source.is_dir():
        raise CollectionExperimentError(f"collection bundle does not exist: {source}")
    source_report = _report_from_record(_read_object(source / "run-report.json"))
    with tempfile.TemporaryDirectory(prefix="laicode-collection-replay-") as directory:
        replay = Path(directory) / "bundle"
        replay_report = run_collection_experiment(replay)
        source_files = sorted(path.relative_to(source) for path in source.rglob("*") if path.is_file())
        replay_files = sorted(path.relative_to(replay) for path in replay.rglob("*") if path.is_file())
        if source_files != replay_files:
            raise CollectionExperimentError("collection replay inventory differs")
        for relative in source_files:
            if (source / relative).read_bytes() != (replay / relative).read_bytes():
                raise CollectionExperimentError(f"collection replay mismatch in {relative.as_posix()}")
        if source_report.report_id != replay_report.report_id:
            raise CollectionExperimentError("collection replay report identity differs")
    return CollectionReplayReport(source_report.report_id, replay_report.report_id, len(source_files))


def _sha256_bytes(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _parse_native_output(value: str) -> tuple[int, str]:
    fields: dict[str, str] = {}
    for line in value.splitlines():
        if "=" not in line:
            raise CollectionExperimentError("native collection output is invalid")
        key, item = line.split("=", 1)
        if key in fields:
            raise CollectionExperimentError("native collection output has duplicate fields")
        fields[key] = item
    if set(fields) != {"cases", "checksum"}:
        raise CollectionExperimentError("native collection output fields are invalid")
    try:
        cases = int(fields["cases"])
    except ValueError as error:
        raise CollectionExperimentError("native collection case count is invalid") from error
    checksum = fields["checksum"]
    if cases < 1 or len(checksum) != 16 or any(item not in "0123456789abcdef" for item in checksum):
        raise CollectionExperimentError("native collection result is invalid")
    return cases, checksum


def validate_collection_native(bundle_directory: str | Path, output_directory: str | Path, *, compiler: str = "cc") -> CollectionNativeReport:
    bundle, output = Path(bundle_directory), Path(output_directory)
    if output.exists():
        raise CollectionExperimentError(f"native collection output exists: {output}")
    replay = replay_collection_experiment(bundle)
    compiler_path = shutil.which(compiler)
    if compiler_path is None:
        raise CollectionExperimentError(f"C compiler {compiler!r} is not installed")
    version = subprocess.run((compiler_path, "--version"), check=False, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True).stdout.strip()
    tasks = registered_collection_tasks()
    selections = [(cycle, task_id) for cycle in range(3) for task_id in ("remove_element", "running_sum", "move_zeroes")] + [(2, task_id) for task_id in ("copy_array", "reverse_array", "filter_positive", "filter_not_target")]
    output.mkdir(parents=True, exist_ok=False)
    translations: list[JsonValue] = []
    cases_passed = 0
    for cycle, task_id in selections:
        source = bundle / "cycles" / f"cycle-{cycle}" / task_id / "program.c"
        artifact = output / "artifacts" / f"cycle-{cycle}--{task_id}"
        artifact.parent.mkdir(parents=True, exist_ok=True)
        compilation = subprocess.run((compiler_path, *COMPILER_FLAGS, str(source), "-o", str(artifact)), check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if compilation.returncode != 0:
            raise CollectionExperimentError(f"generated collection C failed for {task_id} cycle {cycle}: {compilation.stderr.strip()}")
        execution = subprocess.run((str(artifact),), check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if execution.returncode != 0:
            raise CollectionExperimentError(f"generated collection C validity failed for {task_id} cycle {cycle}: exit {execution.returncode}")
        case_count, checksum = _parse_native_output(execution.stdout)
        if case_count != len(tasks[task_id].cases):
            raise CollectionExperimentError("generated collection C case count differs")
        cases_passed += case_count
        translations.append({"cycle": cycle, "task_id": task_id, "source_sha256": _sha256_bytes(source.read_bytes()), "artifact_sha256": _sha256_bytes(artifact.read_bytes()), "artifact_bytes": len(artifact.read_bytes()), "cases_passed": case_count, "checksum": checksum, "valid": True})
    report: dict[str, JsonValue] = {
        "schema_version": NATIVE_REPORT_SCHEMA_VERSION,
        "source_collection_report_id": replay.source_report_id,
        "host": {"system": platform.system(), "release": platform.release(), "machine": platform.machine()},
        "compiler": {"requested": compiler, "resolved_path": compiler_path, "version": version, "flags": list(COMPILER_FLAGS)},
        "translations": translations,
        "translations_passed": len(translations),
        "cases_passed": cases_passed,
        "all_valid": True,
        "performance_claim": False,
    }
    report_id = content_id(report)
    _write_document(output / "native-report.json", {"schema_version": NATIVE_RECORD_SCHEMA_VERSION, "report_id": report_id, "report": report})
    return CollectionNativeReport(report_id, compiler_path, len(translations), cases_passed, True)


def smoke_collection_language(output_directory: str | Path, *, compiler: str = "cc") -> tuple[CollectionExperimentReport, CollectionReplayReport, CollectionNativeReport]:
    output = Path(output_directory)
    if output.exists():
        raise CollectionExperimentError(f"collection smoke output exists: {output}")
    bundle, native = output / "bundle", output / "native"
    report = run_collection_experiment(bundle)
    replay = replay_collection_experiment(bundle)
    host = validate_collection_native(bundle, native, compiler=compiler)
    return report, replay, host
