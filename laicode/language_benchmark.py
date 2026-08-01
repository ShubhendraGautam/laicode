"""Cross-language comparator laboratory for the evolving machine language."""

from __future__ import annotations

import hashlib
import os
import platform
import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping

from .canonical import (
    CanonicalizationError,
    JsonValue,
    canonical_json_bytes,
    content_id,
    load_json_strict,
)
from .machine_experiment import (
    MachineCorpus,
    MachineExperimentError,
    replay_machine_experiment,
    registered_corpora,
)
from .machine_language import (
    EMPTY_VOCABULARY,
    MachineVocabulary,
    WordInstruction,
    encode_program,
    execute_program,
    learn_one_superinstruction,
)


BENCHMARK_MANIFEST_SCHEMA_VERSION = "LanguageComparatorManifestV0"
REFERENCE_RESULTS_SCHEMA_VERSION = "LanguageComparatorReferenceResultsV0"
PACKAGE_RECORD_SCHEMA_VERSION = "LanguageComparatorPackageRecordV0"
HOST_REPORT_SCHEMA_VERSION = "LanguageComparatorHostReportV0"
HOST_RECORD_SCHEMA_VERSION = "LanguageComparatorHostReportRecordV0"
REPLAY_SCHEMA_VERSION = "LanguageComparatorReplayV0"

DEFAULT_BENCHMARK_TRIALS = 7
DEFAULT_BENCHMARK_SCALE = 50
DEFAULT_WARMUP_RUNS = 3
DEFAULT_STARTUP_TRIALS = 5
CHECKSUM_INITIAL = 0x6A09E667F3BCC909
WORD_MASK = (1 << 64) - 1

PITS = (
    ("reuse_holdout", "operational-holdout", "learned patterns in new contexts"),
    ("audit_transfer", "research-audit", "post-freeze unseen-context transfer"),
    ("shift_no_reuse", "future-shift", "workload shift without learned reuse"),
)

_OPCODE = {
    "xor_const": 1,
    "add_const": 2,
    "multiply_const": 3,
    "and_const": 4,
    "or_const": 5,
    "xor_shift_right": 6,
    "rotate_left": 7,
}


@dataclass(frozen=True)
class ComparatorPackageReport:
    package_id: str
    source_machine_report_id: str
    files_written: int


@dataclass(frozen=True)
class ComparatorReplayReport:
    package_id: str
    files_verified: int

    def to_document(self) -> dict[str, JsonValue]:
        return {
            "schema_version": REPLAY_SCHEMA_VERSION,
            "package_id": self.package_id,
            "files_verified": self.files_verified,
            "exact_match": True,
        }


@dataclass(frozen=True)
class ComparatorHostReport:
    report_id: str
    package_id: str
    completed_adapters: tuple[str, ...]
    skipped_adapters: tuple[str, ...]
    correctness_passed: bool


def _write_document(path: Path, value: JsonValue) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as handle:
        handle.write(canonical_json_bytes(value) + b"\n")
        handle.flush()


def _read_document(path: Path) -> JsonValue:
    try:
        return load_json_strict(path.read_bytes())
    except (OSError, CanonicalizationError) as error:
        raise MachineExperimentError(f"cannot read {path}: {error}") from error


def _read_object(path: Path) -> Mapping[str, JsonValue]:
    value = _read_document(path)
    if not isinstance(value, dict):
        raise MachineExperimentError(f"expected an object in {path}")
    return value


def _sha256_bytes(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _load_vocabulary(path: Path) -> MachineVocabulary:
    value = _read_object(path)
    try:
        return MachineVocabulary.from_document(value)
    except ValueError as error:
        raise MachineExperimentError(f"cannot decode vocabulary {path}: {error}") from error


def _load_machine_state(
    machine_bundle: Path,
) -> tuple[
    str,
    str,
    dict[str, MachineCorpus],
    tuple[MachineVocabulary, MachineVocabulary, MachineVocabulary],
]:
    replay = replay_machine_experiment(machine_bundle)
    run_record = _read_object(machine_bundle / "run-report.json")
    report = run_record.get("report")
    if not isinstance(report, dict):
        raise MachineExperimentError("source machine run report is invalid")
    evidence_catalog_id = report.get("evidence_catalog_id")
    if not isinstance(evidence_catalog_id, str):
        raise MachineExperimentError("source machine report omits evidence identity")

    frozen = registered_corpora()
    corpora: dict[str, MachineCorpus] = {}
    for _, corpus_name, _ in PITS:
        document = _read_object(machine_bundle / "corpora" / f"{corpus_name}.json")
        corpus = MachineCorpus.from_document(document)
        if corpus.to_document() != frozen[corpus_name].to_document():
            raise MachineExperimentError("source corpus differs from registered workload")
        corpora[corpus_name] = corpus

    primitive = _load_vocabulary(machine_bundle / "vocabularies" / "primitive.json")
    learned_cycle_2 = _load_vocabulary(
        machine_bundle / "vocabularies" / "learned.json"
    )
    cycle_1 = learn_one_superinstruction(
        frozen["training-cycle-1"].programs,
        EMPTY_VOCABULARY,
        evidence_catalog_id=evidence_catalog_id,
        cycle=1,
    )
    cycle_record = _read_object(machine_bundle / "cycles" / "cycle-1.json")
    if cycle_record.get("output_vocabulary_id") != cycle_1.vocabulary_id:
        raise MachineExperimentError("cycle-1 vocabulary cannot be reconstructed")
    if primitive != EMPTY_VOCABULARY:
        raise MachineExperimentError("primitive comparator is not the empty vocabulary")
    if len(cycle_1.entries) != 1 or len(learned_cycle_2.entries) != 2:
        raise MachineExperimentError("source machine run has an unexpected learning depth")
    return (
        replay.source_report_id,
        evidence_catalog_id,
        corpora,
        (primitive, cycle_1, learned_cycle_2),
    )


def _rotl(value: int, amount: int) -> int:
    return ((value << amount) | (value >> (64 - amount))) & WORD_MASK


def _reference_result(corpus: MachineCorpus, scale: int) -> tuple[str, int]:
    checksum = CHECKSUM_INITIAL
    invocations = 0
    for program_index, item in enumerate(corpus.programs):
        count = item.executions * scale
        for iteration in range(count):
            output = execute_program(item.program, iteration + program_index + 1)
            checksum = _rotl(checksum ^ output, 1)
        invocations += count
    return f"{checksum:016x}", invocations


def _c_apply(instruction: WordInstruction, variable: str = "v") -> str:
    operand = f"UINT64_C(0x{instruction.operand:016x})"
    if instruction.op == "xor_const":
        return f"{variable} ^= {operand};"
    if instruction.op == "add_const":
        return f"{variable} += {operand};"
    if instruction.op == "multiply_const":
        return f"{variable} *= {operand};"
    if instruction.op == "and_const":
        return f"{variable} &= {operand};"
    if instruction.op == "or_const":
        return f"{variable} |= {operand};"
    if instruction.op == "xor_shift_right":
        return f"{variable} ^= {variable} >> {instruction.operand};"
    if instruction.op == "rotate_left":
        return (
            f"{variable} = ({variable} << {instruction.operand}) | "
            f"({variable} >> {64 - instruction.operand});"
        )
    raise MachineExperimentError(f"cannot emit C operation {instruction.op!r}")


def _c_protocol_tail(
    workload_names: Iterable[str],
    *,
    trials: int,
    warmups: int,
) -> str:
    names = tuple(workload_names)
    rows = ", ".join(names)
    return f'''
typedef uint64_t (*Workload)(void);
static Workload workloads[] = {{{rows}}};

static uint64_t now_ns(void) {{
    struct timespec value;
    if (clock_gettime(CLOCK_MONOTONIC, &value) != 0) return 0;
    return (uint64_t)value.tv_sec * UINT64_C(1000000000) + (uint64_t)value.tv_nsec;
}}

int main(int argc, char **argv) {{
    if (argc == 2 && strcmp(argv[1], "probe") == 0) {{
        puts("ready");
        return 0;
    }}
    if (argc != 2) return 2;
    char *end = NULL;
    unsigned long pit = strtoul(argv[1], &end, 10);
    if (!end || *end != '\\0' || pit >= {len(names)}) return 2;
    for (unsigned warmup = 0; warmup < {warmups}; ++warmup) (void)workloads[pit]();
    uint64_t checksum = workloads[pit]();
    uint64_t values[{trials}];
    for (unsigned trial = 0; trial < {trials}; ++trial) {{
        uint64_t start = now_ns();
        uint64_t current = workloads[pit]();
        uint64_t end_ns = now_ns();
        if (start == 0 || end_ns <= start || current != checksum) return 3;
        values[trial] = end_ns - start;
    }}
    printf("checksum=%016" PRIx64 "\\n", checksum);
    printf("ns=");
    for (unsigned i = 0; i < {trials}; ++i) printf("%s%" PRIu64, i ? "," : "", values[i]);
    printf("\\n");
    return 0;
}}
'''


def _generate_c_direct(
    corpora: Mapping[str, MachineCorpus],
    *,
    scale: int,
    trials: int,
    warmups: int,
) -> str:
    functions: list[str] = []
    names: list[str] = []
    for pit_index, (_, corpus_name, _) in enumerate(PITS):
        name = f"workload_{pit_index}"
        names.append(name)
        rows = [
            f"static uint64_t {name}(void) {{",
            f"    uint64_t checksum = UINT64_C(0x{CHECKSUM_INITIAL:016x});",
        ]
        corpus = corpora[corpus_name]
        for program_index, item in enumerate(corpus.programs):
            rows.append(
                f"    for (uint64_t j = 0; j < UINT64_C({item.executions * scale}); ++j) {{"
            )
            rows.append(f"        uint64_t v = j + UINT64_C({program_index + 1});")
            rows.extend(
                f"        {_c_apply(instruction)}"
                for instruction in item.program.instructions
            )
            rows.append("        checksum = rotl64(checksum ^ v, 1);")
            rows.append("    }")
        rows.extend(("    measurement_sink = checksum;", "    return checksum;", "}"))
        functions.append("\n".join(rows))
    return f'''#define _POSIX_C_SOURCE 200809L
#include <inttypes.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

static volatile uint64_t measurement_sink;
static inline uint64_t rotl64(uint64_t value, unsigned amount) {{
    return (value << amount) | (value >> (64U - amount));
}}

{chr(10).join(functions)}
{_c_protocol_tail(names, trials=trials, warmups=warmups)}'''


def _c_encoded_array(
    name: str,
    corpus_program,
    vocabulary: MachineVocabulary,
    macro_opcodes: Mapping[str, int],
) -> str:
    encoded = encode_program(corpus_program, vocabulary)
    rows: list[str] = []
    for token in encoded.tokens:
        if token.primitive is not None:
            rows.append(
                f"    {{{_OPCODE[token.primitive.op]}, "
                f"UINT64_C(0x{token.primitive.operand:016x})}},"
            )
        else:
            assert token.entry_id is not None
            rows.append(f"    {{{macro_opcodes[token.entry_id]}, UINT64_C(0)}},")
    return f"static const volatile Instruction {name}[] = {{\n" + "\n".join(rows) + "\n};"


def _generate_c_laicode(
    corpora: Mapping[str, MachineCorpus],
    vocabulary: MachineVocabulary,
    *,
    scale: int,
    trials: int,
    warmups: int,
) -> str:
    macro_opcodes = {
        entry.entry_id: 32 + index for index, entry in enumerate(vocabulary.entries)
    }
    arrays: list[str] = []
    functions: list[str] = []
    names: list[str] = []
    for pit_index, (_, corpus_name, _) in enumerate(PITS):
        corpus = corpora[corpus_name]
        name = f"workload_{pit_index}"
        names.append(name)
        rows = [
            f"static uint64_t {name}(void) {{",
            f"    uint64_t checksum = UINT64_C(0x{CHECKSUM_INITIAL:016x});",
        ]
        for program_index, item in enumerate(corpus.programs):
            array_name = f"pit_{pit_index}_program_{program_index}"
            arrays.append(
                _c_encoded_array(array_name, item.program, vocabulary, macro_opcodes)
            )
            rows.append(
                f"    for (uint64_t j = 0; j < UINT64_C({item.executions * scale}); ++j) {{"
            )
            rows.append(
                f"        uint64_t v = run({array_name}, "
                f"sizeof({array_name}) / sizeof({array_name}[0]), "
                f"j + UINT64_C({program_index + 1}));"
            )
            rows.append("        checksum = rotl64(checksum ^ v, 1);")
            rows.append("    }")
        rows.extend(("    measurement_sink = checksum;", "    return checksum;", "}"))
        functions.append("\n".join(rows))
    macro_cases = [
        f"            case {macro_opcodes[entry.entry_id]}: "
        + " ".join(_c_apply(instruction) for instruction in entry.lowering)
        + " break;"
        for entry in vocabulary.entries
    ]
    return f'''#define _POSIX_C_SOURCE 200809L
#include <inttypes.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

typedef struct {{ uint8_t op; uint64_t arg; }} Instruction;
static volatile uint64_t measurement_sink;
static inline uint64_t rotl64(uint64_t value, unsigned amount) {{
    return (value << amount) | (value >> (64U - amount));
}}

__attribute__((noinline))
static uint64_t run(const volatile Instruction *code, size_t count, uint64_t v) {{
    for (size_t pc = 0; pc < count; ++pc) {{
        uint8_t op = code[pc].op;
        uint64_t arg = code[pc].arg;
        switch (op) {{
            case 1: v ^= arg; break;
            case 2: v += arg; break;
            case 3: v *= arg; break;
            case 4: v &= arg; break;
            case 5: v |= arg; break;
            case 6: v ^= v >> arg; break;
            case 7: v = rotl64(v, (unsigned)arg); break;
{chr(10).join(macro_cases)}
            default: return UINT64_MAX;
        }}
    }}
    return v;
}}

{chr(10).join(arrays)}
{chr(10).join(functions)}
{_c_protocol_tail(names, trials=trials, warmups=warmups)}'''


def _python_apply(instruction: WordInstruction) -> str:
    operand = instruction.operand
    if instruction.op == "xor_const":
        return f"v ^= 0x{operand:016x}"
    if instruction.op == "add_const":
        return f"v = (v + 0x{operand:016x}) & MASK"
    if instruction.op == "multiply_const":
        return f"v = (v * 0x{operand:016x}) & MASK"
    if instruction.op == "and_const":
        return f"v &= 0x{operand:016x}"
    if instruction.op == "or_const":
        return f"v |= 0x{operand:016x}"
    if instruction.op == "xor_shift_right":
        return f"v ^= v >> {operand}"
    if instruction.op == "rotate_left":
        return f"v = ((v << {operand}) | (v >> {64 - operand})) & MASK"
    raise MachineExperimentError(f"cannot emit Python operation {instruction.op!r}")


def _generate_python_direct(
    corpora: Mapping[str, MachineCorpus],
    *,
    scale: int,
    trials: int,
    warmups: int,
) -> str:
    functions: list[str] = []
    names: list[str] = []
    for pit_index, (_, corpus_name, _) in enumerate(PITS):
        name = f"workload_{pit_index}"
        names.append(name)
        rows = [f"def {name}():", f"    checksum = 0x{CHECKSUM_INITIAL:016x}"]
        for program_index, item in enumerate(corpora[corpus_name].programs):
            rows.append(f"    for j in range({item.executions * scale}):")
            rows.append(f"        v = j + {program_index + 1}")
            rows.extend(
                f"        {_python_apply(instruction)}"
                for instruction in item.program.instructions
            )
            rows.append("        checksum = rotl64(checksum ^ v, 1)")
        rows.append("    return checksum")
        functions.append("\n".join(rows))
    return f'''import sys
import time

MASK = (1 << 64) - 1

def rotl64(value, amount):
    return ((value << amount) | (value >> (64 - amount))) & MASK

{chr(10).join(functions)}

WORKLOADS = ({", ".join(names)},)

def main():
    if len(sys.argv) == 2 and sys.argv[1] == "probe":
        print("ready")
        return 0
    if len(sys.argv) != 2:
        return 2
    try:
        pit = int(sys.argv[1])
        workload = WORKLOADS[pit]
    except (ValueError, IndexError):
        return 2
    for _ in range({warmups}):
        workload()
    checksum = workload()
    values = []
    for _ in range({trials}):
        start = time.perf_counter_ns()
        current = workload()
        end = time.perf_counter_ns()
        if current != checksum or end <= start:
            return 3
        values.append(end - start)
    print(f"checksum={{checksum:016x}}")
    print("ns=" + ",".join(str(value) for value in values))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
'''


def _javascript_apply(instruction: WordInstruction) -> str:
    operand = instruction.operand
    if instruction.op == "xor_const":
        return f"v ^= 0x{operand:016x}n;"
    if instruction.op == "add_const":
        return f"v = BigInt.asUintN(64, v + 0x{operand:016x}n);"
    if instruction.op == "multiply_const":
        return f"v = BigInt.asUintN(64, v * 0x{operand:016x}n);"
    if instruction.op == "and_const":
        return f"v &= 0x{operand:016x}n;"
    if instruction.op == "or_const":
        return f"v |= 0x{operand:016x}n;"
    if instruction.op == "xor_shift_right":
        return f"v ^= v >> {operand}n;"
    if instruction.op == "rotate_left":
        return f"v = ((v << {operand}n) | (v >> {64 - operand}n)) & MASK;"
    raise MachineExperimentError(f"cannot emit JavaScript operation {instruction.op!r}")


def _generate_javascript_direct(
    corpora: Mapping[str, MachineCorpus],
    *,
    scale: int,
    trials: int,
    warmups: int,
) -> str:
    functions: list[str] = []
    names: list[str] = []
    for pit_index, (_, corpus_name, _) in enumerate(PITS):
        name = f"workload{pit_index}"
        names.append(name)
        rows = [f"function {name}() {{", f"  let checksum = 0x{CHECKSUM_INITIAL:016x}n;"]
        for program_index, item in enumerate(corpora[corpus_name].programs):
            rows.append(f"  for (let j = 0; j < {item.executions * scale}; ++j) {{")
            rows.append(f"    let v = BigInt(j + {program_index + 1});")
            rows.extend(
                f"    {_javascript_apply(instruction)}"
                for instruction in item.program.instructions
            )
            rows.append("    checksum = rotl64(checksum ^ v, 1n);")
            rows.append("  }")
        rows.extend(("  return checksum;", "}"))
        functions.append("\n".join(rows))
    return f'''"use strict";
const MASK = (1n << 64n) - 1n;
function rotl64(value, amount) {{
  return ((value << amount) | (value >> (64n - amount))) & MASK;
}}

{chr(10).join(functions)}

const workloads = [{", ".join(names)}];
if (process.argv.length === 3 && process.argv[2] === "probe") {{
  console.log("ready");
  process.exit(0);
}}
if (process.argv.length !== 3) process.exit(2);
const pit = Number(process.argv[2]);
if (!Number.isInteger(pit) || pit < 0 || pit >= workloads.length) process.exit(2);
const workload = workloads[pit];
for (let warmup = 0; warmup < {warmups}; ++warmup) workload();
const checksum = workload();
const values = [];
for (let trial = 0; trial < {trials}; ++trial) {{
  const start = process.hrtime.bigint();
  const current = workload();
  const end = process.hrtime.bigint();
  if (current !== checksum || end <= start) process.exit(3);
  values.push(end - start);
}}
console.log("checksum=" + checksum.toString(16).padStart(16, "0"));
console.log("ns=" + values.map(value => value.toString()).join(","));
'''


def _adapter_specs() -> list[dict[str, JsonValue]]:
    return [
        {
            "id": "laicode_cycle_0",
            "language": "laicode_e_h0",
            "learning_cycle": 0,
            "execution_model": "generated_c_switch_interpreter",
            "source": "sources/laicode-cycle-0.c",
            "tool": "cc",
            "tool_kind": "c_compiler",
            "required": True,
        },
        {
            "id": "laicode_cycle_1",
            "language": "laicode_e_h0",
            "learning_cycle": 1,
            "execution_model": "generated_c_switch_interpreter",
            "source": "sources/laicode-cycle-1.c",
            "tool": "cc",
            "tool_kind": "c_compiler",
            "required": True,
        },
        {
            "id": "laicode_cycle_2",
            "language": "laicode_e_h0",
            "learning_cycle": 2,
            "execution_model": "generated_c_switch_interpreter",
            "source": "sources/laicode-cycle-2.c",
            "tool": "cc",
            "tool_kind": "c_compiler",
            "required": True,
        },
        {
            "id": "c_gcc_o2",
            "language": "c11",
            "learning_cycle": None,
            "execution_model": "direct_ahead_of_time_native",
            "source": "sources/c-direct.c",
            "tool": "gcc",
            "tool_kind": "c_compiler",
            "required": False,
        },
        {
            "id": "c_clang_o2",
            "language": "c11",
            "learning_cycle": None,
            "execution_model": "direct_ahead_of_time_native",
            "source": "sources/c-direct.c",
            "tool": "clang",
            "tool_kind": "c_compiler",
            "required": False,
        },
        {
            "id": "python_3_direct",
            "language": "python3",
            "learning_cycle": None,
            "execution_model": "direct_interpreted_source",
            "source": "sources/python-direct.py",
            "tool": "python3",
            "tool_kind": "interpreter",
            "required": True,
        },
        {
            "id": "javascript_node_direct",
            "language": "javascript",
            "learning_cycle": None,
            "execution_model": "direct_jit_bigint",
            "source": "sources/javascript-direct.js",
            "tool": "node",
            "tool_kind": "interpreter",
            "required": False,
        },
    ]


def _manifest(
    *,
    source_machine_report_id: str,
    evidence_catalog_id: str,
    corpora: Mapping[str, MachineCorpus],
    vocabularies: tuple[MachineVocabulary, MachineVocabulary, MachineVocabulary],
    scale: int,
    trials: int,
    warmups: int,
    startup_trials: int,
) -> dict[str, JsonValue]:
    evolution: list[JsonValue] = []
    for cycle, vocabulary in enumerate(vocabularies):
        weighted_tokens = {
            pit_id: sum(
                len(encode_program(item.program, vocabulary).tokens) * item.executions
                for item in corpora[corpus_name].programs
            )
            for pit_id, corpus_name, _ in PITS
        }
        evolution.append(
            {
                "cycle": cycle,
                "vocabulary_id": vocabulary.vocabulary_id,
                "entry_count": len(vocabulary.entries),
                "weighted_dispatch_tokens_by_pit": weighted_tokens,
            }
        )
    return {
        "schema_version": BENCHMARK_MANIFEST_SCHEMA_VERSION,
        "benchmark_name": "laicode-cross-language-b0-v0",
        "study_mode": "exploratory_host_benchmark",
        "source_machine_report_id": source_machine_report_id,
        "evidence_catalog_id": evidence_catalog_id,
        "question": (
            "How does LAIcode change over two learning cycles, and how does its "
            "current generated-C interpreter compare with mature direct languages?"
        ),
        "claim_separation": {
            "learning_curve": "compare_laicode_cycles_only",
            "ecosystem_comparison": "descriptive_not_causal_language_ranking",
        },
        "pits": [
            {
                "id": pit_id,
                "corpus_name": corpus_name,
                "corpus_id": corpora[corpus_name].corpus_id,
                "purpose": purpose,
            }
            for pit_id, corpus_name, purpose in PITS
        ],
        "protocol": {
            "scale": scale,
            "steady_state_trials": trials,
            "warmup_runs": warmups,
            "startup_trials": startup_trials,
            "aot_build_trials": startup_trials,
            "checksum": "rotl1_xor_fold_over_identical_u64_pipeline_outputs",
            "inputs": "j_plus_one_based_program_index",
            "compiler_flags": ["-O2", "-std=c11", "-Wall", "-Wextra", "-Werror"],
            "timer": "language_monotonic_nanosecond_clock",
            "trial_summary": "median_with_raw_trials_mad_and_spread",
        },
        "fairness_rules": [
            "identical_program_semantics_inputs_and_pipeline_invocation_counts",
            "all_checksums_must_match_trusted_python_kernel_reference",
            "same_scale_warmups_and_trial_count_for_every_adapter",
            "laicode_cycles_share_backend_compiler_and_flags",
            "direct_languages_may_use_normal_mature_runtime_optimization",
            "build_startup_runtime_memory_source_and_artifact_costs_are_separate",
            "runtime_installation_size_and_energy_are_not_counted",
            "noisy_host_results_never_modify_deterministic_language_selection",
        ],
        "metrics": [
            "steady_state_nanoseconds",
            "picoseconds_per_pipeline_invocation",
            "trial_mad_parts_per_million",
            "trial_spread_parts_per_million",
            "build_nanoseconds",
            "cold_start_nanoseconds",
            "maximum_resident_kibibytes",
            "source_bytes",
            "runnable_artifact_bytes",
            "semantic_checksum",
        ],
        "language_evolution": evolution,
        "adapters": _adapter_specs(),
        "limitations": [
            "synthetic_u64_pipelines_only",
            "single_host_and_process_scheduler",
            "laicode_uses_generated_c_interpreter_not_custom_native_isa",
            "python_and_javascript_use_high_level_integer_semantics_to_preserve_u64",
            "runtime_installation_size_energy_and_human_effort_excluded",
            "exploratory_no_statistical_language_superiority_claim",
        ],
        "registered_at": "2026-08-01T00:00:00Z",
    }


def prepare_comparator_package(
    machine_bundle: str | Path,
    output_directory: str | Path,
    *,
    scale: int = DEFAULT_BENCHMARK_SCALE,
    trials: int = DEFAULT_BENCHMARK_TRIALS,
    warmups: int = DEFAULT_WARMUP_RUNS,
    startup_trials: int = DEFAULT_STARTUP_TRIALS,
) -> ComparatorPackageReport:
    if scale < 1:
        raise MachineExperimentError("benchmark scale must be positive")
    if trials < 3 or trials % 2 == 0:
        raise MachineExperimentError("benchmark trials must be an odd integer of at least 3")
    if warmups < 1:
        raise MachineExperimentError("benchmark warmups must be positive")
    if startup_trials < 3 or startup_trials % 2 == 0:
        raise MachineExperimentError("startup trials must be an odd integer of at least 3")
    source = Path(machine_bundle)
    output = Path(output_directory)
    if output.exists():
        raise MachineExperimentError(f"comparator package already exists: {output}")
    (
        source_report_id,
        evidence_catalog_id,
        corpora,
        vocabularies,
    ) = _load_machine_state(source)
    manifest = _manifest(
        source_machine_report_id=source_report_id,
        evidence_catalog_id=evidence_catalog_id,
        corpora=corpora,
        vocabularies=vocabularies,
        scale=scale,
        trials=trials,
        warmups=warmups,
        startup_trials=startup_trials,
    )
    references: dict[str, JsonValue] = {}
    for pit_id, corpus_name, _ in PITS:
        checksum, invocations = _reference_result(corpora[corpus_name], scale)
        references[pit_id] = {
            "corpus_id": corpora[corpus_name].corpus_id,
            "checksum": checksum,
            "pipeline_invocations": invocations,
        }
    reference_document: dict[str, JsonValue] = {
        "schema_version": REFERENCE_RESULTS_SCHEMA_VERSION,
        "source_machine_report_id": source_report_id,
        "results_by_pit": references,
    }
    sources = {
        "sources/laicode-cycle-0.c": _generate_c_laicode(
            corpora, vocabularies[0], scale=scale, trials=trials, warmups=warmups
        ),
        "sources/laicode-cycle-1.c": _generate_c_laicode(
            corpora, vocabularies[1], scale=scale, trials=trials, warmups=warmups
        ),
        "sources/laicode-cycle-2.c": _generate_c_laicode(
            corpora, vocabularies[2], scale=scale, trials=trials, warmups=warmups
        ),
        "sources/c-direct.c": _generate_c_direct(
            corpora, scale=scale, trials=trials, warmups=warmups
        ),
        "sources/python-direct.py": _generate_python_direct(
            corpora, scale=scale, trials=trials, warmups=warmups
        ),
        "sources/javascript-direct.js": _generate_javascript_direct(
            corpora, scale=scale, trials=trials, warmups=warmups
        ),
    }
    inventory: dict[str, JsonValue] = {
        "benchmark_manifest_id": content_id(manifest),
        "reference_results_id": content_id(reference_document),
        "source_sha256_by_path": {
            path: _sha256_bytes(text.encode("utf-8"))
            for path, text in sorted(sources.items())
        },
    }
    package_id = content_id(inventory)
    output.mkdir(parents=True, exist_ok=False)
    _write_document(output / "benchmark-manifest.json", manifest)
    _write_document(output / "reference-results.json", reference_document)
    for relative, text_value in sources.items():
        path = output / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(text_value)
    _write_document(
        output / "package-record.json",
        {
            "schema_version": PACKAGE_RECORD_SCHEMA_VERSION,
            "package_id": package_id,
            "inventory": inventory,
        },
    )
    file_count = sum(1 for path in output.rglob("*") if path.is_file())
    return ComparatorPackageReport(package_id, source_report_id, file_count)


def _package_id(package: Path) -> str:
    record = _read_object(package / "package-record.json")
    if set(record) != {"schema_version", "package_id", "inventory"}:
        raise MachineExperimentError("comparator package record has invalid fields")
    if record["schema_version"] != PACKAGE_RECORD_SCHEMA_VERSION:
        raise MachineExperimentError("comparator package record has an unknown schema")
    package_id = record["package_id"]
    inventory = record["inventory"]
    if not isinstance(package_id, str) or not isinstance(inventory, dict):
        raise MachineExperimentError("comparator package record is invalid")
    if content_id(inventory) != package_id:
        raise MachineExperimentError("comparator package identity differs")
    return package_id


def replay_comparator_package(
    machine_bundle: str | Path,
    package_directory: str | Path,
) -> ComparatorReplayReport:
    package = Path(package_directory)
    if not package.is_dir():
        raise MachineExperimentError(f"comparator package does not exist: {package}")
    package_id = _package_id(package)
    manifest = _read_object(package / "benchmark-manifest.json")
    protocol = manifest.get("protocol")
    if not isinstance(protocol, dict):
        raise MachineExperimentError("comparator manifest protocol is invalid")
    try:
        scale = int(protocol["scale"])
        trials = int(protocol["steady_state_trials"])
        warmups = int(protocol["warmup_runs"])
        startup_trials = int(protocol["startup_trials"])
    except (KeyError, TypeError, ValueError) as error:
        raise MachineExperimentError("comparator protocol cannot be replayed") from error
    with tempfile.TemporaryDirectory(prefix="laicode-comparator-replay-") as directory:
        replay = Path(directory) / "package"
        replay_report = prepare_comparator_package(
            machine_bundle,
            replay,
            scale=scale,
            trials=trials,
            warmups=warmups,
            startup_trials=startup_trials,
        )
        source_files = sorted(
            path.relative_to(package) for path in package.rglob("*") if path.is_file()
        )
        replay_files = sorted(
            path.relative_to(replay) for path in replay.rglob("*") if path.is_file()
        )
        if source_files != replay_files:
            raise MachineExperimentError("comparator package inventory differs on replay")
        for relative in source_files:
            if (package / relative).read_bytes() != (replay / relative).read_bytes():
                raise MachineExperimentError(
                    f"comparator replay mismatch in {relative.as_posix()}"
                )
        if replay_report.package_id != package_id:
            raise MachineExperimentError("comparator package ID differs on replay")
        return ComparatorReplayReport(package_id, len(source_files))


def _median(values: list[int]) -> int:
    return sorted(values)[len(values) // 2]


def _trial_summary(
    values: list[int],
    *,
    denominator: int,
    normalization_unit: str,
) -> dict[str, JsonValue]:
    median = _median(values)
    deviations = [abs(value - median) for value in values]
    return {
        "raw_ns": values,
        "minimum_ns": min(values),
        "median_ns": median,
        "maximum_ns": max(values),
        "mad_ns": _median(deviations),
        "mad_parts_per_million": _median(deviations) * 1_000_000 // median,
        "spread_parts_per_million": (max(values) - min(values)) * 1_000_000 // median,
        "normalization_unit": normalization_unit,
        "picoseconds_per_normalization_unit": median * 1000 // denominator,
    }


def _parse_runner_output(value: str, trials: int) -> tuple[str, list[int]]:
    fields: dict[str, str] = {}
    for line in value.splitlines():
        if "=" not in line:
            raise MachineExperimentError("comparator emitted an invalid output line")
        key, item = line.split("=", 1)
        if key in fields:
            raise MachineExperimentError("comparator emitted a duplicate output field")
        fields[key] = item
    if set(fields) != {"checksum", "ns"}:
        raise MachineExperimentError("comparator emitted invalid output fields")
    try:
        timings = [int(item) for item in fields["ns"].split(",")]
    except ValueError as error:
        raise MachineExperimentError("comparator emitted an invalid timing") from error
    if len(timings) != trials or any(item <= 0 for item in timings):
        raise MachineExperimentError("comparator emitted incomplete trials")
    checksum = fields["checksum"]
    if len(checksum) != 16 or any(item not in "0123456789abcdef" for item in checksum):
        raise MachineExperimentError("comparator emitted an invalid checksum")
    return checksum, timings


def _tool_version(tool_path: str) -> str:
    result = subprocess.run(
        (tool_path, "--version"),
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    if result.returncode != 0 or not result.stdout.strip():
        raise MachineExperimentError(f"cannot identify comparator tool {tool_path}")
    return result.stdout.strip()


def _run_checked(command: tuple[str, ...], env: Mapping[str, str]) -> tuple[str, int]:
    start = time.perf_counter_ns()
    result = subprocess.run(
        command,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
    )
    end = time.perf_counter_ns()
    if result.returncode != 0:
        raise MachineExperimentError(
            f"comparator command failed ({result.returncode}): {result.stderr.strip()}"
        )
    return result.stdout, end - start


def _measure_startup(
    command_prefix: tuple[str, ...],
    trials: int,
    env: Mapping[str, str],
) -> list[int]:
    values: list[int] = []
    for _ in range(trials):
        output, elapsed = _run_checked(command_prefix + ("probe",), env)
        if output != "ready\n":
            raise MachineExperimentError("comparator startup probe failed")
        values.append(elapsed)
    return values


def _measure_rss_kib(
    command: tuple[str, ...],
    env: Mapping[str, str],
) -> int | None:
    time_tool = Path("/usr/bin/time")
    if not time_tool.is_file():
        return None
    with tempfile.TemporaryDirectory(prefix="laicode-comparator-rss-") as directory:
        output_path = Path(directory) / "rss.txt"
        result = subprocess.run(
            (str(time_tool), "-f", "%M", "-o", str(output_path), *command),
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
        )
        if result.returncode != 0:
            raise MachineExperimentError(
                "comparator RSS measurement failed: " + result.stderr.strip()
            )
        try:
            value = int(output_path.read_text(encoding="utf-8").strip())
        except (OSError, ValueError) as error:
            raise MachineExperimentError("comparator RSS output is invalid") from error
        if value < 1:
            raise MachineExperimentError("comparator RSS must be positive")
        return value


def _cpu_model() -> str:
    try:
        for line in Path("/proc/cpuinfo").read_text(encoding="utf-8").splitlines():
            if line.startswith("model name") and ":" in line:
                return line.split(":", 1)[1].strip()
    except OSError:
        pass
    return platform.processor() or "unknown"


def run_comparator_benchmark(
    machine_bundle: str | Path,
    package_directory: str | Path,
    output_directory: str | Path,
) -> ComparatorHostReport:
    package = Path(package_directory)
    output = Path(output_directory)
    if output.exists():
        raise MachineExperimentError(f"comparator output already exists: {output}")
    replay = replay_comparator_package(machine_bundle, package)
    manifest = _read_object(package / "benchmark-manifest.json")
    references = _read_object(package / "reference-results.json")
    protocol = manifest.get("protocol")
    adapters = manifest.get("adapters")
    results_by_pit = references.get("results_by_pit")
    if not isinstance(protocol, dict) or not isinstance(adapters, list) or not isinstance(results_by_pit, dict):
        raise MachineExperimentError("comparator package payload is invalid")
    trials = int(protocol["steady_state_trials"])
    startup_trials = int(protocol["startup_trials"])
    flags = tuple(str(value) for value in protocol["compiler_flags"])

    output.mkdir(parents=True, exist_ok=False)
    artifacts = output / "artifacts"
    raw = output / "raw"
    artifacts.mkdir()
    raw.mkdir()
    environment = os.environ.copy()
    environment.update({"LC_ALL": "C", "PYTHONHASHSEED": "0"})
    adapter_results: list[dict[str, JsonValue]] = []
    completed: list[str] = []
    skipped: list[str] = []
    for adapter_value in adapters:
        if not isinstance(adapter_value, dict):
            raise MachineExperimentError("comparator adapter specification is invalid")
        adapter_id = str(adapter_value["id"])
        tool = str(adapter_value["tool"])
        required = adapter_value["required"] is True
        tool_path = shutil.which(tool)
        if tool_path is None:
            if required:
                raise MachineExperimentError(f"required comparator tool {tool!r} is absent")
            skipped.append(adapter_id)
            adapter_results.append(
                {
                    "adapter_id": adapter_id,
                    "status": "skipped_tool_unavailable",
                    "tool": tool,
                }
            )
            continue
        source_path = package / str(adapter_value["source"])
        source_bytes = source_path.stat().st_size
        tool_kind = str(adapter_value["tool_kind"])
        build_ns = 0
        build_measurement: dict[str, JsonValue] | None = None
        if tool_kind == "c_compiler":
            artifact_path = artifacts / adapter_id
            build_values: list[int] = []
            for _ in range(startup_trials):
                compile_start = time.perf_counter_ns()
                compilation = subprocess.run(
                    (tool_path, *flags, str(source_path), "-o", str(artifact_path)),
                    check=False,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    env=environment,
                )
                build_values.append(time.perf_counter_ns() - compile_start)
                if compilation.returncode != 0:
                    raise MachineExperimentError(
                        f"cannot build {adapter_id}: {compilation.stderr.strip()}"
                    )
            build_ns = _median(build_values)
            build_measurement = _trial_summary(
                build_values,
                denominator=1,
                normalization_unit="aot_build",
            )
            command_prefix = (str(artifact_path),)
            build_kind = "ahead_of_time_c11"
        elif tool_kind == "interpreter":
            artifact_path = source_path
            command_prefix = (tool_path, str(source_path))
            build_kind = "interpreted_no_ahead_of_time_build"
        else:
            raise MachineExperimentError(f"unknown comparator tool kind {tool_kind!r}")
        startup_ns = _measure_startup(command_prefix, startup_trials, environment)
        pit_results: dict[str, JsonValue] = {}
        for pit_index, (pit_id, _, _) in enumerate(PITS):
            reference = results_by_pit.get(pit_id)
            if not isinstance(reference, dict):
                raise MachineExperimentError("comparator reference pit is missing")
            command = command_prefix + (str(pit_index),)
            stdout, process_wall_ns = _run_checked(command, environment)
            (raw / f"{adapter_id}--{pit_id}.txt").write_text(
                stdout, encoding="utf-8"
            )
            checksum, steady_ns = _parse_runner_output(stdout, trials)
            expected_checksum = reference.get("checksum")
            invocations = reference.get("pipeline_invocations")
            if checksum != expected_checksum or not isinstance(invocations, int):
                raise MachineExperimentError(
                    f"semantic checksum mismatch for {adapter_id} on {pit_id}"
                )
            pit_results[pit_id] = {
                "checksum": checksum,
                "checksum_matches_reference": True,
                "pipeline_invocations": invocations,
                "steady_state": _trial_summary(
                    steady_ns,
                    denominator=invocations,
                    normalization_unit="pipeline_invocation",
                ),
                "benchmark_process_wall_ns": process_wall_ns,
                "maximum_resident_kibibytes": _measure_rss_kib(command, environment),
            }
        artifact_data = artifact_path.read_bytes()
        adapter_results.append(
            {
                "adapter_id": adapter_id,
                "status": "complete",
                "language": adapter_value["language"],
                "learning_cycle": adapter_value["learning_cycle"],
                "execution_model": adapter_value["execution_model"],
                "tool": tool,
                "tool_path": tool_path,
                "tool_version": _tool_version(tool_path),
                "build_kind": build_kind,
                "build_ns": build_ns,
                "build_measurement": build_measurement,
                "source_bytes": source_bytes,
                "source_sha256": _sha256_bytes(source_path.read_bytes()),
                "runnable_artifact_bytes": len(artifact_data),
                "runnable_artifact_sha256": _sha256_bytes(artifact_data),
                "runtime_installation_bytes_included": False,
                "cold_start": _trial_summary(
                    startup_ns,
                    denominator=1,
                    normalization_unit="process_start",
                ),
                "pits": pit_results,
            }
        )
        completed.append(adapter_id)

    complete_results = {
        str(item["adapter_id"]): item
        for item in adapter_results
        if item["status"] == "complete"
    }
    learning_curve: dict[str, JsonValue] = {}
    rankings: dict[str, JsonValue] = {}
    for pit_id, _, _ in PITS:
        curve: list[JsonValue] = []
        for cycle in range(3):
            adapter_id = f"laicode_cycle_{cycle}"
            item = complete_results[adapter_id]
            pits_value = item["pits"]
            assert isinstance(pits_value, dict)
            pit = pits_value[pit_id]
            assert isinstance(pit, dict)
            steady = pit["steady_state"]
            assert isinstance(steady, dict)
            curve.append(
                {
                    "cycle": cycle,
                    "adapter_id": adapter_id,
                    "median_ns": steady["median_ns"],
                    "picoseconds_per_pipeline_invocation": steady[
                        "picoseconds_per_normalization_unit"
                    ],
                }
            )
        learning_curve[pit_id] = curve
        ranking_rows: list[tuple[int, str]] = []
        for adapter_id, item in complete_results.items():
            pits_value = item["pits"]
            assert isinstance(pits_value, dict)
            pit = pits_value[pit_id]
            assert isinstance(pit, dict)
            steady = pit["steady_state"]
            assert isinstance(steady, dict)
            ranking_rows.append((int(steady["median_ns"]), adapter_id))
        rankings[pit_id] = [
            {"rank": rank, "adapter_id": adapter_id, "median_ns": median_ns}
            for rank, (median_ns, adapter_id) in enumerate(sorted(ranking_rows), start=1)
        ]

    report: dict[str, JsonValue] = {
        "schema_version": HOST_REPORT_SCHEMA_VERSION,
        "package_id": replay.package_id,
        "deterministic_package_exactly_replayed_before_measurement": True,
        "host": {
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
            "cpu_model": _cpu_model(),
            "python_controller": platform.python_version(),
        },
        "completed_adapter_ids": completed,
        "skipped_adapter_ids": skipped,
        "correctness_passed": True,
        "adapter_results": adapter_results,
        "learning_curve_by_pit": learning_curve,
        "descriptive_ecosystem_ranking_by_pit": rankings,
        "interpretation": {
            "learning_curve_is_primary_for_evolution": True,
            "ecosystem_ranking_is_descriptive_only": True,
            "timing_used_for_language_selection": False,
            "early_losses_and_non_monotonic_results_retained": True,
        },
        "limitations": manifest["limitations"],
    }
    report_id = content_id(report)
    _write_document(
        output / "benchmark-report.json",
        {
            "schema_version": HOST_RECORD_SCHEMA_VERSION,
            "report_id": report_id,
            "report": report,
        },
    )
    return ComparatorHostReport(
        report_id=report_id,
        package_id=replay.package_id,
        completed_adapters=tuple(completed),
        skipped_adapters=tuple(skipped),
        correctness_passed=True,
    )
