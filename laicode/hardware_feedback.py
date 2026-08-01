"""Replicated host evidence and target-specific vocabulary lifecycle decisions."""

from __future__ import annotations

import hashlib
import platform
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

from .canonical import (
    CanonicalizationError,
    JsonValue,
    canonical_json_bytes,
    content_id,
    load_json_strict,
)
from .language_benchmark import (
    HOST_RECORD_SCHEMA_VERSION as COMPARATOR_HOST_RECORD_SCHEMA_VERSION,
    HOST_REPORT_SCHEMA_VERSION as COMPARATOR_HOST_REPORT_SCHEMA_VERSION,
    PITS,
    _load_machine_state,
    _parse_runner_output,
    prepare_comparator_package,
    replay_comparator_package,
    run_comparator_benchmark,
)
from .machine_experiment import (
    MachineExperimentError,
    replay_machine_experiment,
    run_machine_experiment,
)
from .machine_language import MachineVocabulary


TARGET_SCHEMA_VERSION = "MachineHardwareTargetV0"
STUDY_MANIFEST_SCHEMA_VERSION = "HardwareFeedbackStudyManifestV0"
AGGREGATE_SCHEMA_VERSION = "HardwareFeedbackAggregateV0"
TARGET_PROFILE_SCHEMA_VERSION = "HardwareVocabularyTargetProfileV0"
DECISION_SCHEMA_VERSION = "HardwareVocabularyLifecycleDecisionV0"
RUN_REPORT_SCHEMA_VERSION = "HardwareFeedbackRunReportV0"
RUN_RECORD_SCHEMA_VERSION = "HardwareFeedbackRunReportRecordV0"
REPLAY_SCHEMA_VERSION = "HardwareFeedbackReplayV0"

DEFAULT_SESSION_COUNT = 5
DEFAULT_MINIMUM_IMPROVEMENT_PPM = 50_000
DEFAULT_REQUIRED_WIN_RATE_PPM = 800_000


@dataclass(frozen=True)
class HardwareFeedbackReport:
    report_id: str
    study_manifest_id: str
    target_id: str
    session_count: int
    selected_cycles_by_pit: Mapping[str, int]
    deployment_performed: bool


@dataclass(frozen=True)
class HardwareFeedbackReplay:
    source_report_id: str
    replay_report_id: str
    session_reports_verified: int
    files_verified: int

    def to_document(self) -> dict[str, JsonValue]:
        return {
            "schema_version": REPLAY_SCHEMA_VERSION,
            "source_report_id": self.source_report_id,
            "replay_report_id": self.replay_report_id,
            "session_reports_verified": self.session_reports_verified,
            "files_verified": self.files_verified,
            "decision_exact_match": True,
            "host_timings_rerun": False,
        }


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


def _cpu_model() -> str:
    try:
        for line in Path("/proc/cpuinfo").read_text(encoding="utf-8").splitlines():
            if line.startswith("model name") and ":" in line:
                return line.split(":", 1)[1].strip()
    except OSError:
        pass
    return platform.processor() or "unknown"


def _tool_version(tool_path: str) -> str:
    result = subprocess.run(
        (tool_path, "--version"),
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    if result.returncode != 0 or not result.stdout.strip():
        raise MachineExperimentError("cannot identify the LAIcode backend compiler")
    return result.stdout.strip()


def _target_document(
    comparator_manifest: Mapping[str, JsonValue],
) -> dict[str, JsonValue]:
    cc_path = shutil.which("cc")
    if cc_path is None:
        raise MachineExperimentError("required LAIcode C backend compiler is absent")
    protocol = comparator_manifest.get("protocol")
    if not isinstance(protocol, dict):
        raise MachineExperimentError("comparator protocol is invalid")
    flags = protocol.get("compiler_flags")
    if not isinstance(flags, list) or not all(isinstance(item, str) for item in flags):
        raise MachineExperimentError("comparator compiler flags are invalid")
    return {
        "schema_version": TARGET_SCHEMA_VERSION,
        "system": platform.system(),
        "release": platform.release(),
        "machine": platform.machine(),
        "cpu_model": _cpu_model(),
        "backend": "GeneratedCVolatileSwitchInterpreterV0",
        "compiler": {
            "requested": "cc",
            "resolved_path": cc_path,
            "version": _tool_version(cc_path),
            "flags": flags,
        },
    }


def _study_manifest(
    *,
    source_machine_report_id: str,
    comparator_package_id: str,
    target: Mapping[str, JsonValue],
    sessions: int,
    minimum_improvement_ppm: int,
    required_win_rate_ppm: int,
) -> dict[str, JsonValue]:
    return {
        "schema_version": STUDY_MANIFEST_SCHEMA_VERSION,
        "study_name": "target-specific-vocabulary-feedback-h1-v0",
        "study_mode": "exploratory_replicated_host_feedback",
        "source_machine_report_id": source_machine_report_id,
        "comparator_package_id": comparator_package_id,
        "target_id": content_id(dict(target)),
        "target": dict(target),
        "session_count": sessions,
        "session_order": "sequential_matched_adapter_sessions",
        "policy": {
            "baseline_cycle": 0,
            "candidate_cycles": [1, 2],
            "minimum_median_improvement_ppm": minimum_improvement_ppm,
            "required_paired_win_rate_ppm": required_win_rate_ppm,
            "required_paired_wins": (
                sessions * required_win_rate_ppm + 999_999
            )
            // 1_000_000,
            "deterministic_token_reduction_required": True,
            "selection_rule": (
                "eligible_cycle_with_lowest_median_of_session_medians_then_cycle"
            ),
            "fallback_cycle": 0,
        },
        "authority": {
            "mutation": "activate_or_retire_existing_transparent_entries_only",
            "primitive_semantics_change": False,
            "new_entry_generation": False,
            "deployment": "D0_offline_profile_only",
            "autonomous_deployment": False,
        },
        "pits": [pit_id for pit_id, _, _ in PITS],
        "negative_results": "retained",
        "registered_at": "2026-08-01T00:00:00Z",
    }


def _median(values: Sequence[int]) -> int:
    if not values:
        raise MachineExperimentError("cannot aggregate an empty measurement set")
    ordered = sorted(values)
    return ordered[len(ordered) // 2]


def _verified_report_record(path: Path) -> Mapping[str, JsonValue]:
    record = _read_object(path)
    if set(record) != {"schema_version", "report_id", "report"}:
        raise MachineExperimentError("host session report record has invalid fields")
    if record["schema_version"] != COMPARATOR_HOST_RECORD_SCHEMA_VERSION:
        raise MachineExperimentError("host session report record has an unknown schema")
    report_id = record["report_id"]
    report = record["report"]
    if not isinstance(report_id, str) or not isinstance(report, dict):
        raise MachineExperimentError("host session report record is invalid")
    if report.get("schema_version") != COMPARATOR_HOST_REPORT_SCHEMA_VERSION:
        raise MachineExperimentError("host session report has an unknown schema")
    if content_id(report) != report_id:
        raise MachineExperimentError("host session report identity mismatch")
    return report


def _complete_adapters(
    report: Mapping[str, JsonValue],
) -> dict[str, Mapping[str, JsonValue]]:
    values = report.get("adapter_results")
    if not isinstance(values, list):
        raise MachineExperimentError("host session omits adapter results")
    complete: dict[str, Mapping[str, JsonValue]] = {}
    for value in values:
        if not isinstance(value, dict):
            raise MachineExperimentError("host session adapter result is invalid")
        if value.get("status") != "complete":
            continue
        adapter_id = value.get("adapter_id")
        if not isinstance(adapter_id, str) or adapter_id in complete:
            raise MachineExperimentError("host session adapter identity is invalid")
        complete[adapter_id] = value
    return complete


def _validate_session_target(
    report: Mapping[str, JsonValue],
    manifest: Mapping[str, JsonValue],
) -> None:
    if report.get("package_id") != manifest.get("comparator_package_id"):
        raise MachineExperimentError("host session uses a different comparator package")
    if report.get("correctness_passed") is not True:
        raise MachineExperimentError("host session did not pass correctness")
    target = manifest.get("target")
    host = report.get("host")
    if not isinstance(target, dict) or not isinstance(host, dict):
        raise MachineExperimentError("host session target payload is invalid")
    for field in ("system", "release", "machine", "cpu_model"):
        if host.get(field) != target.get(field):
            raise MachineExperimentError(
                f"host session target mismatch in {field}"
            )
    compiler = target.get("compiler")
    if not isinstance(compiler, dict):
        raise MachineExperimentError("study compiler target is invalid")
    complete = _complete_adapters(report)
    for cycle in range(3):
        adapter = complete.get(f"laicode_cycle_{cycle}")
        if adapter is None:
            raise MachineExperimentError("host session omits a LAIcode cycle")
        if (
            adapter.get("tool") != compiler.get("requested")
            or adapter.get("tool_path") != compiler.get("resolved_path")
            or adapter.get("tool_version") != compiler.get("version")
        ):
            raise MachineExperimentError("host session compiler target mismatch")


def _session_median(
    report: Mapping[str, JsonValue],
    adapter_id: str,
    pit_id: str,
) -> int:
    adapter = _complete_adapters(report).get(adapter_id)
    if adapter is None:
        raise MachineExperimentError(f"host session omits {adapter_id}")
    pits = adapter.get("pits")
    if not isinstance(pits, dict):
        raise MachineExperimentError("host session pit results are invalid")
    pit = pits.get(pit_id)
    if not isinstance(pit, dict):
        raise MachineExperimentError(f"host session omits pit {pit_id}")
    steady = pit.get("steady_state")
    if not isinstance(steady, dict):
        raise MachineExperimentError("host session steady-state result is invalid")
    median = steady.get("median_ns")
    if isinstance(median, bool) or not isinstance(median, int) or median < 1:
        raise MachineExperimentError("host session median is invalid")
    return median


def _token_counts(
    comparator_manifest: Mapping[str, JsonValue],
) -> dict[int, dict[str, int]]:
    evolution = comparator_manifest.get("language_evolution")
    if not isinstance(evolution, list):
        raise MachineExperimentError("comparator evolution evidence is invalid")
    result: dict[int, dict[str, int]] = {}
    for value in evolution:
        if not isinstance(value, dict):
            raise MachineExperimentError("comparator evolution row is invalid")
        cycle = value.get("cycle")
        counts = value.get("weighted_dispatch_tokens_by_pit")
        if isinstance(cycle, bool) or not isinstance(cycle, int) or not isinstance(counts, dict):
            raise MachineExperimentError("comparator evolution row is invalid")
        result[cycle] = {
            str(key): int(item) for key, item in counts.items()
        }
    if set(result) != {0, 1, 2}:
        raise MachineExperimentError("comparator package omits a learning cycle")
    return result


def _aggregate_documents(
    manifest: Mapping[str, JsonValue],
    comparator_manifest: Mapping[str, JsonValue],
    session_reports: Sequence[Mapping[str, JsonValue]],
    vocabularies: tuple[MachineVocabulary, MachineVocabulary, MachineVocabulary],
) -> tuple[
    dict[str, JsonValue],
    dict[str, JsonValue],
    dict[str, JsonValue],
    dict[str, JsonValue],
]:
    policy = manifest.get("policy")
    if not isinstance(policy, dict):
        raise MachineExperimentError("hardware feedback policy is invalid")
    minimum_improvement = int(policy["minimum_median_improvement_ppm"])
    required_wins = int(policy["required_paired_wins"])
    token_counts = _token_counts(comparator_manifest)
    session_ids = [content_id(dict(report)) for report in session_reports]
    pit_aggregates: dict[str, JsonValue] = {}
    selected_cycles: dict[str, int] = {}
    for pit_id, _, _ in PITS:
        baseline_values = [
            _session_median(report, "laicode_cycle_0", pit_id)
            for report in session_reports
        ]
        cycle_rows: list[dict[str, JsonValue]] = []
        eligible_cycles = [0]
        for cycle in range(3):
            values = [
                _session_median(report, f"laicode_cycle_{cycle}", pit_id)
                for report in session_reports
            ]
            improvements = [
                (baseline - candidate) * 1_000_000 // baseline
                for baseline, candidate in zip(
                    baseline_values, values, strict=True
                )
            ]
            wins = sum(candidate < baseline for baseline, candidate in zip(
                baseline_values, values, strict=True
            ))
            token_reduction = token_counts[0][pit_id] - token_counts[cycle][pit_id]
            reasons: list[JsonValue] = []
            if cycle == 0:
                eligible = True
                reasons.append("registered_fallback")
            else:
                if token_reduction <= 0:
                    reasons.append("no_deterministic_token_reduction")
                if wins < required_wins:
                    reasons.append("paired_win_gate_failed")
                if _median(improvements) < minimum_improvement:
                    reasons.append("median_improvement_gate_failed")
                eligible = not reasons
                if eligible:
                    reasons.append("all_stability_gates_passed")
                    eligible_cycles.append(cycle)
            cycle_rows.append(
                {
                    "cycle": cycle,
                    "vocabulary_id": vocabularies[cycle].vocabulary_id,
                    "entry_count": len(vocabularies[cycle].entries),
                    "weighted_dispatch_tokens": token_counts[cycle][pit_id],
                    "deterministic_token_reduction_vs_cycle_0": token_reduction,
                    "session_median_ns": values,
                    "median_of_session_medians_ns": _median(values),
                    "paired_improvement_ppm_vs_cycle_0": improvements,
                    "median_improvement_ppm_vs_cycle_0": _median(improvements),
                    "paired_wins_vs_cycle_0": wins,
                    "eligible": eligible,
                    "eligibility_reasons": reasons,
                }
            )
        selected = min(
            eligible_cycles,
            key=lambda cycle: (
                int(cycle_rows[cycle]["median_of_session_medians_ns"]),
                cycle,
            ),
        )
        selected_cycles[pit_id] = selected
        pit_aggregates[pit_id] = {
            "cycle_evidence": cycle_rows,
            "eligible_cycles": eligible_cycles,
            "selected_cycle": selected,
            "selected_vocabulary_id": vocabularies[selected].vocabulary_id,
        }
    aggregate: dict[str, JsonValue] = {
        "schema_version": AGGREGATE_SCHEMA_VERSION,
        "study_manifest_id": content_id(dict(manifest)),
        "target_id": manifest["target_id"],
        "comparator_package_id": manifest["comparator_package_id"],
        "session_report_ids": session_ids,
        "session_count": len(session_reports),
        "pit_aggregates": pit_aggregates,
        "all_correctness_checks_passed": True,
        "negative_results_retained": True,
    }
    final_entry_ids = set(vocabularies[2].by_id())
    profile_pits: dict[str, JsonValue] = {}
    for pit_id, _, _ in PITS:
        selected = selected_cycles[pit_id]
        active_ids = sorted(vocabularies[selected].by_id())
        retired_ids = sorted(final_entry_ids - set(active_ids))
        profile_pits[pit_id] = {
            "selected_cycle": selected,
            "selected_vocabulary_id": vocabularies[selected].vocabulary_id,
            "active_entry_ids": active_ids,
            "retired_entry_ids": retired_ids,
            "fallback_to_primitives": selected == 0,
            "retirement_is_profile_exclusion_not_deletion": True,
        }
    profile: dict[str, JsonValue] = {
        "schema_version": TARGET_PROFILE_SCHEMA_VERSION,
        "target_id": manifest["target_id"],
        "source_final_vocabulary_id": vocabularies[2].vocabulary_id,
        "aggregate_id": content_id(aggregate),
        "profiles_by_pit": profile_pits,
        "primitive_kernel_unchanged": True,
        "deployment_authority": "D0_offline_profile_only",
    }
    decision: dict[str, JsonValue] = {
        "schema_version": DECISION_SCHEMA_VERSION,
        "study_manifest_id": content_id(dict(manifest)),
        "aggregate_id": content_id(aggregate),
        "target_profile_id": content_id(profile),
        "selected_cycles_by_pit": selected_cycles,
        "outcome": "target_specific_profile_frozen_offline",
        "selection_rule": policy["selection_rule"],
        "primitive_semantics_changed": False,
        "vocabulary_entries_deleted": False,
        "new_entries_generated_from_host_timing": False,
        "deployment_performed": False,
        "authority": "D0_offline_only",
    }
    report: dict[str, JsonValue] = {
        "schema_version": RUN_REPORT_SCHEMA_VERSION,
        "status": "complete",
        "claim_level": "exploratory_single_target_replicated_feedback_only",
        "study_manifest_id": content_id(dict(manifest)),
        "target_id": manifest["target_id"],
        "aggregate_id": content_id(aggregate),
        "target_profile_id": content_id(profile),
        "lifecycle_decision_id": content_id(decision),
        "session_report_ids": session_ids,
        "session_count": len(session_reports),
        "selected_cycles_by_pit": selected_cycles,
        "decision_replay_supported": True,
        "host_timings_exactly_replayable": False,
        "deployment_performed": False,
        "limitations": [
            "single_cpu_os_and_compiler_target",
            "sequential_sessions_not_independent_machines",
            "synthetic_u64_pipeline_pits_only",
            "no_energy_or_hardware_counter_evidence",
            "profile_routing_requires_external_workload_classification",
            "no_online_or_autonomous_deployment",
        ],
    }
    return aggregate, profile, decision, report


def _report_from_record(value: Mapping[str, JsonValue]) -> HardwareFeedbackReport:
    if set(value) != {"schema_version", "report_id", "report"}:
        raise MachineExperimentError("hardware feedback run record has invalid fields")
    if value["schema_version"] != RUN_RECORD_SCHEMA_VERSION:
        raise MachineExperimentError("hardware feedback run record has an unknown schema")
    report_id = value["report_id"]
    report = value["report"]
    if not isinstance(report_id, str) or not isinstance(report, dict):
        raise MachineExperimentError("hardware feedback run record is invalid")
    if report.get("schema_version") != RUN_REPORT_SCHEMA_VERSION:
        raise MachineExperimentError("hardware feedback run report has an unknown schema")
    if content_id(report) != report_id:
        raise MachineExperimentError("hardware feedback run identity mismatch")
    selected = report.get("selected_cycles_by_pit")
    if not isinstance(selected, dict):
        raise MachineExperimentError("hardware feedback run omits selected cycles")
    return HardwareFeedbackReport(
        report_id=report_id,
        study_manifest_id=str(report["study_manifest_id"]),
        target_id=str(report["target_id"]),
        session_count=int(report["session_count"]),
        selected_cycles_by_pit={str(key): int(item) for key, item in selected.items()},
        deployment_performed=bool(report["deployment_performed"]),
    )


def resolve_target_vocabulary(
    profile: Mapping[str, JsonValue],
    pit_id: str,
    vocabularies: Sequence[MachineVocabulary],
) -> MachineVocabulary:
    """Resolve and verify the offline vocabulary selected for a known pit.

    Workload classification is deliberately outside this function. Callers
    must supply a registered pit identity rather than allowing timing evidence
    to guess a workload class at execution time.
    """

    if profile.get("schema_version") != TARGET_PROFILE_SCHEMA_VERSION:
        raise MachineExperimentError("target vocabulary profile has an unknown schema")
    if len(vocabularies) != 3:
        raise MachineExperimentError("target resolver requires cycles 0, 1, and 2")
    profiles = profile.get("profiles_by_pit")
    if not isinstance(profiles, dict):
        raise MachineExperimentError("target vocabulary profile omits pit mappings")
    pit = profiles.get(pit_id)
    if not isinstance(pit, dict):
        raise MachineExperimentError(f"target vocabulary profile has no pit {pit_id!r}")
    cycle = pit.get("selected_cycle")
    if isinstance(cycle, bool) or not isinstance(cycle, int) or not 0 <= cycle < 3:
        raise MachineExperimentError("target vocabulary profile selects an invalid cycle")
    vocabulary = vocabularies[cycle]
    if pit.get("selected_vocabulary_id") != vocabulary.vocabulary_id:
        raise MachineExperimentError("target vocabulary identity differs")
    active = pit.get("active_entry_ids")
    retired = pit.get("retired_entry_ids")
    if active != sorted(vocabulary.by_id()):
        raise MachineExperimentError("target active vocabulary entries differ")
    final_ids = set(vocabularies[2].by_id())
    if retired != sorted(final_ids - set(vocabulary.by_id())):
        raise MachineExperimentError("target retired vocabulary entries differ")
    if pit.get("fallback_to_primitives") is not (cycle == 0):
        raise MachineExperimentError("target primitive fallback flag differs")
    return vocabulary


def run_hardware_feedback_study(
    machine_bundle: str | Path,
    comparator_package: str | Path,
    output_directory: str | Path,
    *,
    sessions: int = DEFAULT_SESSION_COUNT,
    minimum_improvement_ppm: int = DEFAULT_MINIMUM_IMPROVEMENT_PPM,
    required_win_rate_ppm: int = DEFAULT_REQUIRED_WIN_RATE_PPM,
) -> HardwareFeedbackReport:
    if sessions < 3 or sessions % 2 == 0:
        raise MachineExperimentError("hardware feedback sessions must be an odd integer of at least 3")
    if not 0 <= minimum_improvement_ppm <= 1_000_000:
        raise MachineExperimentError("minimum hardware improvement is invalid")
    if not 500_000 <= required_win_rate_ppm <= 1_000_000:
        raise MachineExperimentError("required paired win rate is invalid")
    machine = Path(machine_bundle)
    package = Path(comparator_package)
    output = Path(output_directory)
    if output.exists():
        raise MachineExperimentError(f"hardware feedback output already exists: {output}")
    machine_replay = replay_machine_experiment(machine)
    package_replay = replay_comparator_package(machine, package)
    comparator_manifest = _read_object(package / "benchmark-manifest.json")
    target = _target_document(comparator_manifest)
    manifest = _study_manifest(
        source_machine_report_id=machine_replay.source_report_id,
        comparator_package_id=package_replay.package_id,
        target=target,
        sessions=sessions,
        minimum_improvement_ppm=minimum_improvement_ppm,
        required_win_rate_ppm=required_win_rate_ppm,
    )
    output.mkdir(parents=True, exist_ok=False)
    _write_document(output / "study-manifest.json", manifest)
    session_reports: list[Mapping[str, JsonValue]] = []
    for index in range(1, sessions + 1):
        session_output = output / "sessions" / f"session-{index:03d}"
        run_comparator_benchmark(machine, package, session_output)
        session_report = _verified_report_record(
            session_output / "benchmark-report.json"
        )
        _validate_session_target(session_report, manifest)
        session_reports.append(session_report)
    _, _, _, vocabularies = _load_machine_state(machine)
    aggregate, profile, decision, report = _aggregate_documents(
        manifest, comparator_manifest, session_reports, vocabularies
    )
    _write_document(output / "aggregate.json", aggregate)
    _write_document(output / "target-profile.json", profile)
    _write_document(output / "lifecycle-decision.json", decision)
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


def _verify_session_files(
    session: Path,
    package: Path,
    comparator_manifest: Mapping[str, JsonValue],
    report: Mapping[str, JsonValue],
) -> int:
    protocol = comparator_manifest.get("protocol")
    adapters = comparator_manifest.get("adapters")
    if not isinstance(protocol, dict) or not isinstance(adapters, list):
        raise MachineExperimentError("comparator manifest cannot verify a session")
    trials = int(protocol["steady_state_trials"])
    source_by_adapter = {
        str(item["id"]): str(item["source"])
        for item in adapters
        if isinstance(item, dict)
    }
    verified = 1
    for adapter_id, adapter in _complete_adapters(report).items():
        pits = adapter.get("pits")
        if not isinstance(pits, dict):
            raise MachineExperimentError("session adapter pits are invalid")
        for pit_id, _, _ in PITS:
            raw_path = session / "raw" / f"{adapter_id}--{pit_id}.txt"
            try:
                raw_value = raw_path.read_text(encoding="utf-8")
            except OSError as error:
                raise MachineExperimentError("session raw evidence is missing") from error
            try:
                checksum, raw_ns = _parse_runner_output(raw_value, trials)
            except MachineExperimentError as error:
                raise MachineExperimentError(
                    "session raw evidence is invalid"
                ) from error
            pit = pits.get(pit_id)
            if not isinstance(pit, dict):
                raise MachineExperimentError("session pit evidence is missing")
            steady = pit.get("steady_state")
            if (
                checksum != pit.get("checksum")
                or not isinstance(steady, dict)
                or raw_ns != steady.get("raw_ns")
            ):
                raise MachineExperimentError("session raw evidence differs from report")
            verified += 1
        if adapter.get("build_kind") == "ahead_of_time_c11":
            artifact_path = session / "artifacts" / adapter_id
            archived_artifact = True
        else:
            source_relative = source_by_adapter.get(adapter_id)
            if source_relative is None:
                raise MachineExperimentError("session adapter source is unknown")
            artifact_path = package / source_relative
            archived_artifact = False
        try:
            artifact_bytes = artifact_path.read_bytes()
        except OSError as error:
            raise MachineExperimentError("session runnable artifact is missing") from error
        if (
            len(artifact_bytes) != adapter.get("runnable_artifact_bytes")
            or _sha256_bytes(artifact_bytes) != adapter.get("runnable_artifact_sha256")
        ):
            raise MachineExperimentError("session runnable artifact differs")
        if archived_artifact:
            verified += 1
    return verified


def replay_hardware_feedback_study(
    machine_bundle: str | Path,
    comparator_package: str | Path,
    study_directory: str | Path,
) -> HardwareFeedbackReplay:
    machine = Path(machine_bundle)
    package = Path(comparator_package)
    study = Path(study_directory)
    if not study.is_dir():
        raise MachineExperimentError(f"hardware feedback study does not exist: {study}")
    machine_replay = replay_machine_experiment(machine)
    package_replay = replay_comparator_package(machine, package)
    manifest = _read_object(study / "study-manifest.json")
    if manifest.get("schema_version") != STUDY_MANIFEST_SCHEMA_VERSION:
        raise MachineExperimentError("hardware feedback study has an unknown schema")
    if manifest.get("source_machine_report_id") != machine_replay.source_report_id:
        raise MachineExperimentError("hardware feedback source machine differs")
    if manifest.get("comparator_package_id") != package_replay.package_id:
        raise MachineExperimentError("hardware feedback comparator package differs")
    target = manifest.get("target")
    if not isinstance(target, dict) or content_id(target) != manifest.get("target_id"):
        raise MachineExperimentError("hardware feedback target identity differs")
    current_target = _target_document(_read_object(package / "benchmark-manifest.json"))
    if current_target != target:
        raise MachineExperimentError("current hardware target differs from study target")
    session_count = manifest.get("session_count")
    if isinstance(session_count, bool) or not isinstance(session_count, int):
        raise MachineExperimentError("hardware feedback session count is invalid")
    comparator_manifest = _read_object(package / "benchmark-manifest.json")
    session_reports: list[Mapping[str, JsonValue]] = []
    files_verified = 1
    for index in range(1, session_count + 1):
        session = study / "sessions" / f"session-{index:03d}"
        report = _verified_report_record(session / "benchmark-report.json")
        _validate_session_target(report, manifest)
        files_verified += _verify_session_files(
            session, package, comparator_manifest, report
        )
        session_reports.append(report)
    _, _, _, vocabularies = _load_machine_state(machine)
    aggregate, profile, decision, report = _aggregate_documents(
        manifest, comparator_manifest, session_reports, vocabularies
    )
    expected = {
        "aggregate.json": aggregate,
        "target-profile.json": profile,
        "lifecycle-decision.json": decision,
        "run-report.json": {
            "schema_version": RUN_RECORD_SCHEMA_VERSION,
            "report_id": content_id(report),
            "report": report,
        },
    }
    for relative, value in expected.items():
        if (study / relative).read_bytes() != canonical_json_bytes(value) + b"\n":
            raise MachineExperimentError(f"hardware feedback replay mismatch in {relative}")
        files_verified += 1
    source_report = _report_from_record(_read_object(study / "run-report.json"))
    return HardwareFeedbackReplay(
        source_report_id=source_report.report_id,
        replay_report_id=content_id(report),
        session_reports_verified=session_count,
        files_verified=files_verified,
    )


def smoke_hardware_feedback(
    output_directory: str | Path,
    *,
    sessions: int = DEFAULT_SESSION_COUNT,
    scale: int = 50,
    trials: int = 7,
    warmups: int = 3,
    startup_trials: int = 5,
) -> tuple[HardwareFeedbackReport, HardwareFeedbackReplay]:
    output = Path(output_directory)
    if output.exists():
        raise MachineExperimentError(f"hardware feedback smoke output exists: {output}")
    machine = output / "machine"
    package = output / "comparator-package"
    study = output / "feedback-study"
    run_machine_experiment(machine)
    prepare_comparator_package(
        machine,
        package,
        scale=scale,
        trials=trials,
        warmups=warmups,
        startup_trials=startup_trials,
    )
    report = run_hardware_feedback_study(
        machine,
        package,
        study,
        sessions=sessions,
    )
    replay = replay_hardware_feedback_study(machine, package, study)
    return report, replay
