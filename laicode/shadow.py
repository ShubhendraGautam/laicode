"""D1 counterfactual cache shadow with bounded leases and exact replay."""

from __future__ import annotations

import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path

from .cache import MAX_TRACE_BYTES, CacheTrace, SimulationResult, decode_trace
from .canonical import JsonValue, canonical_json_bytes, content_id, load_json_strict
from .contracts import ValidatedContract, load_contract
from .isolation import IsolationError, WorkerLimits, evaluate_artifact_isolated
from .kernel import CandidateArtifact, compile_complete_program
from .prototype import implementation_manifest, replay_prototype
from .provenance import AppendOnlyLedger, ProvenanceError


SHADOW_LEASE_SCHEMA_VERSION = "CacheShadowLeaseV0"
SHADOW_CHECKPOINT_SCHEMA_VERSION = "CacheShadowCheckpointV0"
SHADOW_REPORT_SCHEMA_VERSION = "CacheShadowRunReportV0"
SHADOW_REPORT_RECORD_SCHEMA_VERSION = "CacheShadowRunReportRecordV0"
SHADOW_REPLAY_SCHEMA_VERSION = "CacheShadowReplayReportV0"
MAX_SHADOW_EVENTS = 4096


class ShadowError(ValueError):
    """Raised when D1 shadow execution cannot satisfy its frozen protocol."""


def _read(path: Path) -> JsonValue:
    try:
        return load_json_strict(path.read_bytes())
    except (OSError, ValueError) as error:
        raise ShadowError(f"cannot read {path}: {error}") from error


def _read_trace(path: Path) -> CacheTrace:
    try:
        with path.open("rb") as handle:
            data = handle.read(MAX_TRACE_BYTES + 1)
    except OSError as error:
        raise ShadowError(f"cannot read trace {path}: {error}") from error
    if len(data) > MAX_TRACE_BYTES:
        raise ShadowError(f"trace exceeds {MAX_TRACE_BYTES} bytes")
    return decode_trace(data)


def _write(path: Path, document: JsonValue) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as handle:
        handle.write(canonical_json_bytes(document) + b"\n")
        handle.flush()


def _safe_name(identifier: str) -> str:
    if (
        not identifier.startswith("sha256:")
        or len(identifier) != 71
        or any(character not in "0123456789abcdef" for character in identifier[7:])
    ):
        raise ShadowError(f"invalid content ID {identifier!r}")
    return identifier[7:] + ".json"


def _record(path: Path, record_schema: str, payload_schema: str) -> tuple[str, dict]:
    value = _read(path)
    if not isinstance(value, dict) or set(value) != {
        "schema_version",
        "report_id",
        "report",
    }:
        raise ShadowError(f"{path.name} has invalid record fields")
    if value["schema_version"] != record_schema:
        raise ShadowError(f"{path.name} has an unknown record schema")
    report = value["report"]
    report_id = value["report_id"]
    if (
        not isinstance(report, dict)
        or report.get("schema_version") != payload_schema
        or not isinstance(report_id, str)
        or content_id(report) != report_id
    ):
        raise ShadowError(f"{path.name} has an invalid report identity")
    return report_id, report


def _load_artifact(
    source: Path,
    identifier: str,
    contract: ValidatedContract,
) -> CandidateArtifact:
    value = _read(source / "artifacts" / _safe_name(identifier))
    if not isinstance(value, dict) or set(value) != {
        "schema_version",
        "kernel_version",
        "contract_id",
        "program",
    }:
        raise ShadowError("source artifact has invalid fields")
    artifact = compile_complete_program(contract, value["program"])
    if artifact.artifact_id != identifier or artifact.to_document() != value:
        raise ShadowError("source artifact identity or contract binding mismatch")
    return artifact


@dataclass(frozen=True)
class ShadowLease:
    source_run_report_id: str
    contract_id: str
    champion_artifact_id: str
    challenger_artifact_id: str
    trace_id: str
    maximum_events: int
    minimum_events: int
    checkpoint_interval: int
    regression_tolerance_ppm: int
    worker_limits: WorkerLimits

    def to_document(self) -> dict[str, JsonValue]:
        return {
            "schema_version": SHADOW_LEASE_SCHEMA_VERSION,
            "source_run_report_id": self.source_run_report_id,
            "contract_id": self.contract_id,
            "champion_artifact_id": self.champion_artifact_id,
            "challenger_artifact_id": self.challenger_artifact_id,
            "trace_id": self.trace_id,
            "mode": "D1_counterfactual_stateful_shadow",
            "served_artifact_id": self.champion_artifact_id,
            "maximum_events": self.maximum_events,
            "minimum_events": self.minimum_events,
            "checkpoint_interval": self.checkpoint_interval,
            "rollback_triggers": {
                "hard_constraint_failure": True,
                "miss_ratio_regression_ppm": self.regression_tolerance_ppm,
                "worker_failure": True,
            },
            "worker_limits": self.worker_limits.to_document(),
            "capabilities": {
                "filesystem": "deny",
                "network": "deny",
                "process": "deny",
                "clock": "deny",
                "randomness": "deny",
                "environment": "deny",
                "credentials": "deny",
                "model": "deny",
                "external_services": "deny",
            },
            "candidate_may_extend_lease": False,
            "served_effects_authorized": False,
        }

    @property
    def lease_id(self) -> str:
        return content_id(self.to_document())


@dataclass(frozen=True)
class ShadowCheckpoint:
    event_count: int
    champion_result_id: str
    challenger_result_id: str
    champion_miss_ratio_ppm: int
    challenger_miss_ratio_ppm: int
    regression_ppm: int
    hard_constraints_pass: bool
    action: str

    def to_document(self) -> dict[str, JsonValue]:
        return {
            "schema_version": SHADOW_CHECKPOINT_SCHEMA_VERSION,
            "event_count": self.event_count,
            "champion_result_id": self.champion_result_id,
            "challenger_result_id": self.challenger_result_id,
            "champion_miss_ratio_ppm": self.champion_miss_ratio_ppm,
            "challenger_miss_ratio_ppm": self.challenger_miss_ratio_ppm,
            "regression_ppm": self.regression_ppm,
            "hard_constraints_pass": self.hard_constraints_pass,
            "action": self.action,
        }

    @property
    def checkpoint_id(self) -> str:
        return content_id(self.to_document())


@dataclass(frozen=True)
class ShadowRunReport:
    implementation_id: str
    source_run_report_id: str
    contract_id: str
    lease_id: str
    trace_id: str
    champion_artifact_id: str
    challenger_artifact_id: str
    champion_result_id: str
    challenger_result_id: str
    checkpoint_ids: tuple[str, ...]
    disposition: str
    observed_events: int
    revoked_at_event_count: int | None
    final_event_id: str
    ledger_id: str
    archived_payload_bytes: int

    def to_document(self) -> dict[str, JsonValue]:
        return {
            "schema_version": SHADOW_REPORT_SCHEMA_VERSION,
            "status": "complete",
            "claim_level": "D1_counterfactual_shadow_only",
            "implementation_id": self.implementation_id,
            "source_run_report_id": self.source_run_report_id,
            "contract_id": self.contract_id,
            "lease_id": self.lease_id,
            "trace_id": self.trace_id,
            "champion_artifact_id": self.champion_artifact_id,
            "challenger_artifact_id": self.challenger_artifact_id,
            "served_artifact_id": self.champion_artifact_id,
            "champion_result_id": self.champion_result_id,
            "challenger_result_id": self.challenger_result_id,
            "checkpoint_ids": list(self.checkpoint_ids),
            "disposition": self.disposition,
            "observed_events": self.observed_events,
            "revoked_at_event_count": self.revoked_at_event_count,
            "final_event_id": self.final_event_id,
            "ledger_id": self.ledger_id,
            "archived_payload_bytes_before_report": self.archived_payload_bytes,
            "challenger_served_effects": False,
            "deployment_performed": False,
            "promotion_performed": False,
            "last_known_good_preserved": True,
            "limitations": [
                "local_synthetic_or_imported_trace_only",
                "closed_reviewed_candidate_ir_only",
                "no_network_syscall_sandbox_claim",
                "event_count_lease_not_trusted_wall_clock",
                "shadow_revocation_not_served_state_rollback",
            ],
        }

    @property
    def report_id(self) -> str:
        return content_id(self.to_document())

    def to_record(self) -> dict[str, JsonValue]:
        return {
            "schema_version": SHADOW_REPORT_RECORD_SCHEMA_VERSION,
            "report_id": self.report_id,
            "report": self.to_document(),
        }


def _prefix(trace: CacheTrace, event_count: int) -> CacheTrace:
    return decode_trace(
        CacheTrace(
            name=f"shadow-prefix-{event_count}",
            scenario=trace.scenario,
            seed=trace.seed,
            capacity=trace.capacity,
            events=trace.events[:event_count],
        ).to_document()
    )


def _archive_result(
    output: Path,
    results: dict[str, SimulationResult],
    result: SimulationResult,
) -> None:
    if result.result_id in results:
        return
    results[result.result_id] = result
    _write(
        output / "results" / _safe_name(result.result_id),
        result.to_document(),
    )


def run_shadow(
    source_run_directory: str | Path,
    trace: CacheTrace | str | Path,
    output_directory: str | Path,
    *,
    minimum_events: int = 64,
    checkpoint_interval: int = 32,
    regression_tolerance_ppm: int = 50_000,
) -> ShadowRunReport:
    source = Path(source_run_directory)
    output = Path(output_directory)
    if output.exists():
        raise ShadowError(f"output directory already exists: {output}")
    if not source.is_dir():
        raise ShadowError(f"source run does not exist: {source}")
    if source.resolve() in output.resolve().parents:
        raise ShadowError("shadow output cannot be nested inside its source run")
    if minimum_events < 1 or checkpoint_interval < 1:
        raise ShadowError("shadow observation and checkpoint sizes must be positive")
    if not 0 <= regression_tolerance_ppm <= 1_000_000:
        raise ShadowError("shadow regression tolerance must be between 0 and 1000000")

    replay_prototype(source)
    source_report_id, source_report = _record(
        source / "run-report.json",
        "PrototypeRunReportRecordV0",
        "PrototypeRunReportV0",
    )
    decision = _read(source / "offline-decision.json")
    if not isinstance(decision, dict):
        raise ShadowError("offline decision is not an object")
    decision_id = content_id(decision)
    if source_report.get("offline_decision_id") != decision_id:
        raise ShadowError("source report and offline decision do not agree")
    champion_id = decision.get("original_artifact_id")
    challenger_id = decision.get("selected_artifact_id")
    if not isinstance(champion_id, str) or not isinstance(challenger_id, str):
        raise ShadowError("offline decision omits artifact identities")

    contract = load_contract(source / "contract.json")
    champion = _load_artifact(source, champion_id, contract)
    challenger = _load_artifact(source, challenger_id, contract)
    active_trace = trace if isinstance(trace, CacheTrace) else _read_trace(Path(trace))
    if len(active_trace.events) > MAX_SHADOW_EVENTS:
        raise ShadowError(f"D1 shadow traces are limited to {MAX_SHADOW_EVENTS} events")
    if len(active_trace.events) < minimum_events:
        raise ShadowError("trace is shorter than the minimum shadow observation")

    limits = WorkerLimits.from_contract(contract)
    lease = ShadowLease(
        source_run_report_id=source_report_id,
        contract_id=contract.epoch_id,
        champion_artifact_id=champion.artifact_id,
        challenger_artifact_id=challenger.artifact_id,
        trace_id=active_trace.trace_id,
        maximum_events=len(active_trace.events),
        minimum_events=minimum_events,
        checkpoint_interval=checkpoint_interval,
        regression_tolerance_ppm=regression_tolerance_ppm,
        worker_limits=limits,
    )
    output.mkdir(parents=True, exist_ok=False)
    shutil.copytree(source, output / "source-run")
    implementation = implementation_manifest()
    implementation_id = content_id(implementation)
    _write(output / "implementation.json", implementation)
    _write(output / "trace.json", active_trace.to_document())
    _write(output / "lease.json", lease.to_document())
    ledger = AppendOnlyLedger(output / "ledger.jsonl")
    ledger.append(
        "shadow_run_started",
        artifact_id=champion.artifact_id,
        payload={
            "source_run_report_id": source_report_id,
            "trace_id": active_trace.trace_id,
            "implementation_id": implementation_id,
        },
    )
    ledger.append(
        "shadow_lease_issued",
        artifact_id=challenger.artifact_id,
        payload={"lease_id": lease.lease_id, "served_artifact_id": champion.artifact_id},
    )

    results: dict[str, SimulationResult] = {}
    checkpoints: list[ShadowCheckpoint] = []
    challenger_last: SimulationResult | None = None
    disposition = "lease_expired_no_promotion"
    revoked_at: int | None = None
    checkpoint_counts = list(
        range(minimum_events, len(active_trace.events) + 1, checkpoint_interval)
    )
    if checkpoint_counts[-1] != len(active_trace.events):
        checkpoint_counts.append(len(active_trace.events))
    for event_count in checkpoint_counts:
        prefix = _prefix(active_trace, event_count)
        try:
            champion_result = evaluate_artifact_isolated(
                contract,
                champion,
                prefix,
                limits=limits,
            )
            challenger_result = evaluate_artifact_isolated(
                contract,
                challenger,
                prefix,
                limits=limits,
            )
        except IsolationError as error:
            ledger.append(
                "incident",
                artifact_id=challenger.artifact_id,
                payload={
                    "category": "shadow_worker_failure",
                    "event_count": event_count,
                    "diagnostic": str(error)[:1024],
                },
            )
            ledger.append(
                "shadow_lease_revoked",
                artifact_id=challenger.artifact_id,
                payload={
                    "lease_id": lease.lease_id,
                    "reason": "worker_failure",
                    "event_count": event_count,
                },
            )
            raise ShadowError(
                "shadow worker failure revoked the lease; champion remained unchanged"
            ) from error
        _archive_result(output, results, champion_result)
        _archive_result(output, results, challenger_result)
        challenger_last = challenger_result
        hard_pass = (
            challenger_result.metrics.candidate_violations == 0
            and challenger_result.metrics.policy_errors == 0
        )
        regression = (
            challenger_result.metrics.miss_ratio_ppm
            - champion_result.metrics.miss_ratio_ppm
        )
        if not hard_pass:
            action = "revoke_hard_constraint"
            disposition = "revoked_hard_constraint"
            revoked_at = event_count
        elif regression > regression_tolerance_ppm:
            action = "revoke_regression"
            disposition = "revoked_regression"
            revoked_at = event_count
        elif event_count == len(active_trace.events):
            action = "expire_without_promotion"
        else:
            action = "continue_shadow"
        checkpoint = ShadowCheckpoint(
            event_count=event_count,
            champion_result_id=champion_result.result_id,
            challenger_result_id=challenger_result.result_id,
            champion_miss_ratio_ppm=champion_result.metrics.miss_ratio_ppm,
            challenger_miss_ratio_ppm=challenger_result.metrics.miss_ratio_ppm,
            regression_ppm=regression,
            hard_constraints_pass=hard_pass,
            action=action,
        )
        checkpoints.append(checkpoint)
        _write(
            output / "checkpoints" / _safe_name(checkpoint.checkpoint_id),
            checkpoint.to_document(),
        )
        ledger.append(
            "shadow_checkpoint",
            artifact_id=challenger.artifact_id,
            payload={
                "checkpoint_id": checkpoint.checkpoint_id,
                "event_count": event_count,
                "action": action,
            },
        )
        if revoked_at is not None:
            ledger.append(
                "shadow_lease_revoked",
                artifact_id=challenger.artifact_id,
                payload={
                    "lease_id": lease.lease_id,
                    "reason": disposition,
                    "event_count": event_count,
                },
            )
            break
    if revoked_at is None:
        ledger.append(
            "shadow_lease_expired",
            artifact_id=challenger.artifact_id,
            payload={
                "lease_id": lease.lease_id,
                "event_count": len(active_trace.events),
                "promotion": False,
            },
        )

    try:
        champion_full = evaluate_artifact_isolated(
            contract,
            champion,
            active_trace,
            limits=limits,
        )
    except IsolationError as error:
        ledger.append(
            "incident",
            artifact_id=champion.artifact_id,
            payload={
                "category": "trusted_evaluator_failure",
                "event_count": len(active_trace.events),
                "diagnostic": str(error)[:1024],
            },
        )
        raise ShadowError(
            "trusted champion evaluation failed; no complete D1 report was issued"
        ) from error
    _archive_result(output, results, champion_full)
    assert challenger_last is not None
    ledger.append(
        "shadow_recovery_verified",
        artifact_id=champion.artifact_id,
        payload={
            "last_known_good_artifact_id": champion.artifact_id,
            "champion_result_id": champion_full.result_id,
            "served_effects_from_challenger": False,
        },
    )
    final_event = ledger.append(
        "shadow_run_completed",
        artifact_id=champion.artifact_id,
        payload={
            "lease_id": lease.lease_id,
            "disposition": disposition,
            "challenger_result_id": challenger_last.result_id,
        },
    )
    archived_bytes = sum(
        path.stat().st_size for path in output.rglob("*") if path.is_file()
    )
    report = ShadowRunReport(
        implementation_id=implementation_id,
        source_run_report_id=source_report_id,
        contract_id=contract.epoch_id,
        lease_id=lease.lease_id,
        trace_id=active_trace.trace_id,
        champion_artifact_id=champion.artifact_id,
        challenger_artifact_id=challenger.artifact_id,
        champion_result_id=champion_full.result_id,
        challenger_result_id=challenger_last.result_id,
        checkpoint_ids=tuple(item.checkpoint_id for item in checkpoints),
        disposition=disposition,
        observed_events=(
            revoked_at if revoked_at is not None else len(active_trace.events)
        ),
        revoked_at_event_count=revoked_at,
        final_event_id=final_event.event_id,
        ledger_id=ledger.ledger_id,
        archived_payload_bytes=archived_bytes,
    )
    _write(output / "shadow-report.json", report.to_record())
    contract_document = contract.to_dict()
    budgets = contract_document["budgets"]
    assert isinstance(budgets, dict)
    per_epoch = budgets["per_epoch"]
    assert isinstance(per_epoch, dict)
    total_bytes = sum(
        path.stat().st_size for path in output.rglob("*") if path.is_file()
    )
    if total_bytes > int(per_epoch["storage_bytes"]):
        raise ShadowError("shadow bundle exceeds the contract storage budget")
    return report


@dataclass(frozen=True)
class ShadowReplayReport:
    source_report_id: str
    replay_report_id: str
    files_verified: int

    def to_document(self) -> dict[str, JsonValue]:
        return {
            "schema_version": SHADOW_REPLAY_SCHEMA_VERSION,
            "source_report_id": self.source_report_id,
            "replay_report_id": self.replay_report_id,
            "files_verified": self.files_verified,
            "exact_match": True,
        }


def replay_shadow(bundle_directory: str | Path) -> ShadowReplayReport:
    source = Path(bundle_directory)
    if not source.is_dir():
        raise ShadowError(f"shadow bundle does not exist: {source}")
    source_report_id, report = _record(
        source / "shadow-report.json",
        SHADOW_REPORT_RECORD_SCHEMA_VERSION,
        SHADOW_REPORT_SCHEMA_VERSION,
    )
    final_event_id = report.get("final_event_id")
    ledger_id = report.get("ledger_id")
    if not isinstance(final_event_id, str) or not isinstance(ledger_id, str):
        raise ShadowError("shadow report omits ledger identity")
    ledger = AppendOnlyLedger(source / "ledger.jsonl")
    try:
        ledger.verify_expected_final_event(final_event_id)
    except ProvenanceError as error:
        raise ShadowError(str(error)) from error
    if ledger.ledger_id != ledger_id:
        raise ShadowError("shadow ledger snapshot identity mismatch")
    lease = _read(source / "lease.json")
    if not isinstance(lease, dict) or content_id(lease) != report.get("lease_id"):
        raise ShadowError("shadow lease identity mismatch")
    minimum_events = lease.get("minimum_events")
    checkpoint_interval = lease.get("checkpoint_interval")
    triggers = lease.get("rollback_triggers")
    if (
        not isinstance(minimum_events, int)
        or isinstance(minimum_events, bool)
        or not isinstance(checkpoint_interval, int)
        or isinstance(checkpoint_interval, bool)
        or not isinstance(triggers, dict)
        or not isinstance(triggers.get("miss_ratio_regression_ppm"), int)
    ):
        raise ShadowError("shadow lease has invalid replay parameters")

    with tempfile.TemporaryDirectory(prefix="laicode-shadow-replay-") as directory:
        replay = Path(directory) / "bundle"
        replay_report = run_shadow(
            source / "source-run",
            source / "trace.json",
            replay,
            minimum_events=minimum_events,
            checkpoint_interval=checkpoint_interval,
            regression_tolerance_ppm=triggers["miss_ratio_regression_ppm"],
        )
        source_files = sorted(
            path.relative_to(source) for path in source.rglob("*") if path.is_file()
        )
        replay_files = sorted(
            path.relative_to(replay) for path in replay.rglob("*") if path.is_file()
        )
        if source_files != replay_files:
            raise ShadowError("shadow bundle inventory does not match replay")
        for relative in source_files:
            if (source / relative).read_bytes() != (replay / relative).read_bytes():
                raise ShadowError(f"shadow replay mismatch in {relative.as_posix()}")
        return ShadowReplayReport(
            source_report_id=source_report_id,
            replay_report_id=replay_report.report_id,
            files_verified=len(source_files),
        )
