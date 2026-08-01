"""Generated-C host adapter for the hardware-shaped language experiment."""

from __future__ import annotations

import hashlib
import platform
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from .canonical import JsonValue, canonical_json_bytes, content_id, load_json_strict
from .machine_experiment import (
    MachineExperimentError,
    registered_corpora,
    replay_machine_experiment,
)
from .machine_language import (
    MachineVocabulary,
    WordInstruction,
    encode_program,
)


HARDWARE_REPORT_SCHEMA_VERSION = "MachineHostMeasurementV0"
HARDWARE_RECORD_SCHEMA_VERSION = "MachineHostMeasurementRecordV0"
DEFAULT_TRIALS = 9
DEFAULT_SCALE = 1000

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
class MachineHardwareReport:
    report_id: str
    primitive_median_ns: int
    learned_median_ns: int
    learned_trial_wins: int
    trials: int
    checksums_match: bool
    model_direction_agrees: bool


def _read_object(path: Path) -> Mapping[str, JsonValue]:
    try:
        value = load_json_strict(path.read_bytes())
    except (OSError, ValueError) as error:
        raise MachineExperimentError(f"cannot read {path}: {error}") from error
    if not isinstance(value, dict):
        raise MachineExperimentError(f"expected an object in {path}")
    return value


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
    raise MachineExperimentError(f"cannot emit operation {instruction.op!r}")


def _encoded_array(
    name: str,
    program,
    vocabulary: MachineVocabulary,
    macro_opcodes: Mapping[str, int],
) -> str:
    encoded = encode_program(program, vocabulary)
    rows: list[str] = []
    for token in encoded.tokens:
        if token.primitive is not None:
            rows.append(
                "    {"
                f"{_OPCODE[token.primitive.op]}, "
                f"UINT64_C(0x{token.primitive.operand:016x})"
                "},"
            )
        else:
            assert token.entry_id is not None
            rows.append(f"    {{{macro_opcodes[token.entry_id]}, UINT64_C(0)}},")
    return (
        f"static const volatile Instruction {name}[] = {{\n"
        + "\n".join(rows)
        + "\n};\n"
    )


def generate_c_measurement_source(
    primitive: MachineVocabulary,
    learned: MachineVocabulary,
    *,
    trials: int = DEFAULT_TRIALS,
    scale: int = DEFAULT_SCALE,
) -> str:
    if trials < 3 or trials % 2 == 0:
        raise MachineExperimentError("hardware trials must be an odd integer of at least 3")
    if scale < 1:
        raise MachineExperimentError("hardware scale must be positive")
    corpus = registered_corpora()["operational-holdout"]
    macro_opcodes = {
        entry.entry_id: 32 + index
        for index, entry in enumerate(learned.entries)
    }
    arrays: list[str] = []
    for index, item in enumerate(corpus.programs):
        arrays.append(
            _encoded_array(
                f"primitive_{index}", item.program, primitive, macro_opcodes
            )
        )
        arrays.append(
            _encoded_array(
                f"learned_{index}", item.program, learned, macro_opcodes
            )
        )
    macro_cases = []
    for entry in learned.entries:
        body = " ".join(_c_apply(item) for item in entry.lowering)
        macro_cases.append(
            f"            case {macro_opcodes[entry.entry_id]}: {body} break;"
        )
    workload_rows: list[str] = []
    for index, item in enumerate(corpus.programs):
        count = item.executions * scale
        workload_rows.append(
            "    for (uint64_t j = 0; j < UINT64_C("
            f"{count}); ++j) {{\n"
            f"        const volatile Instruction *code = which ? learned_{index} : primitive_{index};\n"
            f"        size_t count = which ? (sizeof(learned_{index}) / sizeof(learned_{index}[0])) : "
            f"(sizeof(primitive_{index}) / sizeof(primitive_{index}[0]));\n"
            f"        uint64_t out = run(code, count, j + UINT64_C({index + 1}));\n"
            "        checksum = rotl64(checksum ^ out, 1);\n"
            "    }"
        )
    return f'''#define _POSIX_C_SOURCE 200809L
#include <inttypes.h>
#include <stdint.h>
#include <stdio.h>
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
static uint64_t workload(int which) {{
    uint64_t checksum = UINT64_C(0x6a09e667f3bcc909);
{chr(10).join(workload_rows)}
    measurement_sink = checksum;
    return checksum;
}}

static uint64_t now_ns(void) {{
    struct timespec value;
    if (clock_gettime(CLOCK_MONOTONIC, &value) != 0) return 0;
    return (uint64_t)value.tv_sec * UINT64_C(1000000000) + (uint64_t)value.tv_nsec;
}}

int main(void) {{
    uint64_t primitive[{trials}], learned[{trials}];
    uint64_t primitive_checksum = workload(0);
    uint64_t learned_checksum = workload(1);
    for (unsigned trial = 0; trial < {trials}; ++trial) {{
        int first = (int)(trial & 1U);
        uint64_t start = now_ns();
        (void)workload(first);
        uint64_t middle = now_ns();
        (void)workload(!first);
        uint64_t end = now_ns();
        if (start == 0 || middle < start || end < middle) return 3;
        if (first == 0) {{
            primitive[trial] = middle - start;
            learned[trial] = end - middle;
        }} else {{
            learned[trial] = middle - start;
            primitive[trial] = end - middle;
        }}
    }}
    printf("primitive_checksum=%016" PRIx64 "\\n", primitive_checksum);
    printf("learned_checksum=%016" PRIx64 "\\n", learned_checksum);
    printf("primitive_ns=");
    for (unsigned i = 0; i < {trials}; ++i) printf("%s%" PRIu64, i ? "," : "", primitive[i]);
    printf("\\nlearned_ns=");
    for (unsigned i = 0; i < {trials}; ++i) printf("%s%" PRIu64, i ? "," : "", learned[i]);
    printf("\\n");
    return primitive_checksum == learned_checksum ? 0 : 4;
}}
'''


def _parse_output(value: str, trials: int) -> tuple[str, str, list[int], list[int]]:
    fields: dict[str, str] = {}
    for line in value.splitlines():
        if "=" not in line:
            raise MachineExperimentError("native runner emitted an invalid line")
        key, item = line.split("=", 1)
        fields[key] = item
    if set(fields) != {
        "primitive_checksum",
        "learned_checksum",
        "primitive_ns",
        "learned_ns",
    }:
        raise MachineExperimentError("native runner emitted invalid fields")
    try:
        primitive = [int(item) for item in fields["primitive_ns"].split(",")]
        learned = [int(item) for item in fields["learned_ns"].split(",")]
    except ValueError as error:
        raise MachineExperimentError("native runner emitted invalid timing") from error
    if (
        len(primitive) != trials
        or len(learned) != trials
        or any(item <= 0 for item in primitive + learned)
    ):
        raise MachineExperimentError("native runner emitted incomplete timing trials")
    return (
        fields["primitive_checksum"],
        fields["learned_checksum"],
        primitive,
        learned,
    )


def _median(values: list[int]) -> int:
    return sorted(values)[len(values) // 2]


def _cpu_model() -> str:
    try:
        for line in Path("/proc/cpuinfo").read_text(encoding="utf-8").splitlines():
            if line.startswith("model name") and ":" in line:
                return line.split(":", 1)[1].strip()
    except OSError:
        pass
    return platform.processor() or "unknown"


def measure_machine_hardware(
    bundle_directory: str | Path,
    output_directory: str | Path,
    *,
    compiler: str = "cc",
    trials: int = DEFAULT_TRIALS,
    scale: int = DEFAULT_SCALE,
) -> MachineHardwareReport:
    source_bundle = Path(bundle_directory)
    output = Path(output_directory)
    if output.exists():
        raise MachineExperimentError(f"hardware output already exists: {output}")
    replay = replay_machine_experiment(source_bundle)
    compiler_path = shutil.which(compiler)
    if compiler_path is None:
        raise MachineExperimentError(f"C compiler {compiler!r} is not installed")

    primitive_document = _read_object(
        source_bundle / "vocabularies" / "primitive.json"
    )
    learned_document = _read_object(
        source_bundle / "vocabularies" / "learned.json"
    )
    primitive = MachineVocabulary.from_document(primitive_document)
    learned = MachineVocabulary.from_document(learned_document)
    source = generate_c_measurement_source(
        primitive,
        learned,
        trials=trials,
        scale=scale,
    )

    output.mkdir(parents=True, exist_ok=False)
    source_path = output / "measurement.c"
    binary_path = output / "measurement-runner"
    source_path.write_text(source, encoding="utf-8")
    flags = ("-O2", "-std=c11", "-Wall", "-Wextra", "-Werror")
    compilation = subprocess.run(
        (compiler_path, *flags, str(source_path), "-o", str(binary_path)),
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if compilation.returncode != 0:
        raise MachineExperimentError(
            "generated C compilation failed: " + compilation.stderr.strip()
        )
    compiler_version = subprocess.run(
        (compiler_path, "--version"),
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    ).stdout.strip()
    execution = subprocess.run(
        (str(binary_path),),
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if execution.returncode != 0:
        raise MachineExperimentError(
            "native measurement failed: " + execution.stderr.strip()
        )
    primitive_checksum, learned_checksum, primitive_ns, learned_ns = _parse_output(
        execution.stdout, trials
    )
    checksums_match = primitive_checksum == learned_checksum
    if not checksums_match:
        raise MachineExperimentError("primitive and learned native checksums differ")

    primitive_evaluation = _read_object(
        source_bundle
        / "evaluations"
        / "operational-holdout--primitive.json"
    )
    learned_evaluation = _read_object(
        source_bundle / "evaluations" / "operational-holdout--learned.json"
    )
    primitive_cost = primitive_evaluation["cost"]
    learned_cost = learned_evaluation["cost"]
    assert isinstance(primitive_cost, dict) and isinstance(learned_cost, dict)
    primitive_runtime = int(primitive_cost["runtime_units"])
    learned_runtime = int(learned_cost["runtime_units"])
    primitive_median = _median(primitive_ns)
    learned_median = _median(learned_ns)
    learned_wins = sum(
        learned_value < primitive_value
        for primitive_value, learned_value in zip(primitive_ns, learned_ns, strict=True)
    )
    model_predicts_learned = learned_runtime < primitive_runtime
    host_observes_learned = learned_median < primitive_median
    report: dict[str, JsonValue] = {
        "schema_version": HARDWARE_REPORT_SCHEMA_VERSION,
        "source_run_report_id": replay.source_report_id,
        "source_bundle_exactly_replayed_before_measurement": True,
        "adapter": "GeneratedCVolatileSwitchInterpreterV0",
        "compiler": {
            "requested": compiler,
            "resolved_path": compiler_path,
            "version": compiler_version,
            "flags": list(flags),
        },
        "host": {
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
            "cpu_model": _cpu_model(),
        },
        "measurement": {
            "clock": "CLOCK_MONOTONIC",
            "trials": trials,
            "scale": scale,
            "order": "alternating_primitive_first_and_learned_first",
            "primitive_ns": primitive_ns,
            "learned_ns": learned_ns,
            "primitive_median_ns": primitive_median,
            "learned_median_ns": learned_median,
            "learned_trial_wins": learned_wins,
            "primitive_checksum": primitive_checksum,
            "learned_checksum": learned_checksum,
            "checksums_match": checksums_match,
        },
        "deterministic_model": {
            "primitive_runtime_units": primitive_runtime,
            "learned_runtime_units": learned_runtime,
            "predicts_learned_faster": model_predicts_learned,
        },
        "result": {
            "host_observes_learned_faster_at_median": host_observes_learned,
            "model_direction_agrees": model_predicts_learned == host_observes_learned,
            "majority_of_trials_agree": learned_wins > trials // 2,
            "used_for_deterministic_identity_or_selection": False,
        },
        "artifacts": {
            "source_sha256": "sha256:"
            + hashlib.sha256(source_path.read_bytes()).hexdigest(),
            "binary_sha256": "sha256:"
            + hashlib.sha256(binary_path.read_bytes()).hexdigest(),
            "raw_stdout_sha256": "sha256:"
            + hashlib.sha256(execution.stdout.encode("utf-8")).hexdigest(),
        },
        "limitations": [
            "single_noisy_host",
            "generated_c_not_direct_isa_superinstruction",
            "compiler_and_os_scheduling_may_change_results",
            "timing_is_not_exactly_replayable",
        ],
    }
    report_id = content_id(report)
    (output / "compiler-version.txt").write_text(
        compiler_version + "\n", encoding="utf-8"
    )
    (output / "raw-stdout.txt").write_text(execution.stdout, encoding="utf-8")
    (output / "measurement.json").write_bytes(
        canonical_json_bytes(
            {
                "schema_version": HARDWARE_RECORD_SCHEMA_VERSION,
                "report_id": report_id,
                "report": report,
            }
        )
        + b"\n"
    )
    return MachineHardwareReport(
        report_id=report_id,
        primitive_median_ns=primitive_median,
        learned_median_ns=learned_median,
        learned_trial_wins=learned_wins,
        trials=trials,
        checksums_match=checksums_match,
        model_direction_agrees=model_predicts_learned == host_observes_learned,
    )
