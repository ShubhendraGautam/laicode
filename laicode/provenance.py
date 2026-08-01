"""Immutable candidate manifests and a local hash-chained append-only ledger."""

from __future__ import annotations

import fcntl
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, NoReturn

from .canonical import (
    CanonicalizationError,
    JsonValue,
    canonical_json_bytes,
    content_id,
    load_json_strict,
)
from .kernel import (
    ACTION_SCHEMA_VERSION,
    KERNEL_VERSION,
    PROGRAM_SCHEMA_VERSION,
    CandidateArtifact,
)


CANDIDATE_MANIFEST_SCHEMA_VERSION = "CandidateManifestV0"
CANDIDATE_RECORD_SCHEMA_VERSION = "CandidateRecordV0"
LEDGER_EVENT_SCHEMA_VERSION = "LedgerEventV0"
LEDGER_RECORD_SCHEMA_VERSION = "LedgerRecordV0"
LEDGER_SNAPSHOT_SCHEMA_VERSION = "LedgerSnapshotV0"
MAX_LEDGER_BYTES = 64 * 1024 * 1024
MAX_LEDGER_LINE_BYTES = 1024 * 1024

_CONTENT_ID = re.compile(r"^sha256:[0-9a-f]{64}$")
_IDENTIFIER = re.compile(r"^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*$")
_EVENT_TYPES = {
    "run_started",
    "manifest_frozen",
    "evaluator_validated",
    "candidate_proposed",
    "candidate_built",
    "candidate_verified",
    "search_evaluated",
    "operationally_evaluated",
    "historically_evaluated",
    "candidate_eligible",
    "candidate_rejected",
    "offline_champion_selected",
    "decision_frozen",
    "prospective_evaluated",
    "research_audit_consumed",
    "run_completed",
    "shadow_run_started",
    "shadow_lease_issued",
    "shadow_checkpoint",
    "shadow_lease_revoked",
    "shadow_lease_expired",
    "shadow_recovery_verified",
    "shadow_run_completed",
    "incident",
}


class ProvenanceError(ValueError):
    """Raised when an identity, manifest, or ledger chain is invalid."""


def _fail(path: str, message: str) -> NoReturn:
    raise ProvenanceError(f"{path}: {message}")


def _object(value: Any, path: str, fields: Iterable[str]) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        _fail(path, "expected an object")
    expected = set(fields)
    missing = sorted(expected - value.keys())
    unknown = sorted(value.keys() - expected)
    if missing:
        _fail(path, f"missing required field(s): {', '.join(missing)}")
    if unknown:
        _fail(path, f"unknown field(s): {', '.join(unknown)}")
    return value


def _string(value: Any, path: str, *, identifier: bool = False) -> str:
    if not isinstance(value, str) or not value:
        _fail(path, "expected a non-empty string")
    if identifier and _IDENTIFIER.fullmatch(value) is None:
        _fail(path, f"invalid identifier {value!r}")
    return value


def _content_id(value: Any, path: str) -> str:
    text = _string(value, path)
    if _CONTENT_ID.fullmatch(text) is None:
        _fail(path, "expected a sha256 content ID")
    return text


def _optional_content_id(value: Any, path: str) -> str | None:
    if value is None:
        return None
    return _content_id(value, path)


def _integer(value: Any, path: str, *, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        _fail(path, "expected an integer")
    if value < minimum:
        _fail(path, f"must be at least {minimum}")
    return value


def _string_tuple(value: Any, path: str, *, ids: bool = False) -> tuple[str, ...]:
    if not isinstance(value, list):
        _fail(path, "expected an array")
    items = tuple(
        _content_id(item, f"{path}[{index}]")
        if ids
        else _string(item, f"{path}[{index}]", identifier=True)
        for index, item in enumerate(value)
    )
    if len(items) != len(set(items)):
        _fail(path, "must not contain duplicates")
    return items


@dataclass(frozen=True)
class CandidateManifest:
    artifact_id: str
    epoch_id: str
    parent_ids: tuple[str, ...]
    generator_id: str
    generator_version: str
    generator_seed: int
    generation_input_ids: tuple[str, ...]
    representation_level: str
    feedback_treatment: str
    learner_update_level: str
    learner_update_mechanisms: tuple[str, ...]
    mutation_level: str
    generator_level: str
    deployment_level: str
    authorized_mutation_ceiling: str
    authorized_deployment_ceiling: str
    from_strategy: str | None
    to_strategy: str
    construction_trace_id: str | None = None

    def to_document(self) -> dict[str, JsonValue]:
        return {
            "schema_version": CANDIDATE_MANIFEST_SCHEMA_VERSION,
            "artifact_id": self.artifact_id,
            "epoch_id": self.epoch_id,
            "parent_ids": list(self.parent_ids),
            "generator": {
                "id": self.generator_id,
                "version": self.generator_version,
                "seed": self.generator_seed,
            },
            "generation_input_ids": list(self.generation_input_ids),
            "representation": {
                "level": self.representation_level,
                "kernel_version": KERNEL_VERSION,
                "program_schema": PROGRAM_SCHEMA_VERSION,
                "action_schema": ACTION_SCHEMA_VERSION,
            },
            "feedback_treatment": self.feedback_treatment,
            "learner_update": {
                "level": self.learner_update_level,
                "mechanisms": list(self.learner_update_mechanisms),
            },
            "actual_profile": {
                "r": self.representation_level,
                "m": self.mutation_level,
                "g": self.generator_level,
                "l": self.learner_update_level,
                "d": self.deployment_level,
                "f": self.feedback_treatment,
            },
            "authorized_ceiling": {
                "m": self.authorized_mutation_ceiling,
                "d": self.authorized_deployment_ceiling,
            },
            "mutation_report": {
                "kind": "strategy_selection",
                "from_strategy": self.from_strategy,
                "to_strategy": self.to_strategy,
            },
            "construction_trace_id": self.construction_trace_id,
            "build_environment": {
                "runtime": "PythonStdlibControlPlaneV0",
                "dependencies": [],
            },
            "capability_request": {
                "effects": [],
            },
        }

    @property
    def canonical_bytes(self) -> bytes:
        return canonical_json_bytes(self.to_document())

    @property
    def candidate_id(self) -> str:
        return content_id(self.to_document())

    def to_record(self) -> dict[str, JsonValue]:
        return {
            "schema_version": CANDIDATE_RECORD_SCHEMA_VERSION,
            "candidate_id": self.candidate_id,
            "manifest": self.to_document(),
        }


def baseline_manifest(
    artifact: CandidateArtifact,
    *,
    evidence_catalog_id: str,
) -> CandidateManifest:
    return CandidateManifest(
        artifact_id=artifact.artifact_id,
        epoch_id=artifact.contract_id,
        parent_ids=(),
        generator_id="manual_baseline",
        generator_version="v0",
        generator_seed=0,
        generation_input_ids=(artifact.contract_id, evidence_catalog_id),
        representation_level="R2",
        feedback_treatment="F0",
        learner_update_level="L0",
        learner_update_mechanisms=(),
        mutation_level="M0",
        generator_level="G0",
        deployment_level="D0",
        authorized_mutation_ceiling="M1",
        authorized_deployment_ceiling="D0",
        from_strategy=None,
        to_strategy=artifact.program.strategy_id,
    )


def enumerated_manifest(
    artifact: CandidateArtifact,
    *,
    parent_id: str,
    evidence_catalog_id: str,
) -> CandidateManifest:
    return CandidateManifest(
        artifact_id=artifact.artifact_id,
        epoch_id=artifact.contract_id,
        parent_ids=(parent_id,),
        generator_id="strategy_enumerator",
        generator_version="v0",
        generator_seed=0,
        generation_input_ids=(artifact.contract_id, evidence_catalog_id),
        representation_level="R2",
        feedback_treatment="F0",
        learner_update_level="L0",
        learner_update_mechanisms=(),
        mutation_level="M1",
        generator_level="G1",
        deployment_level="D0",
        authorized_mutation_ceiling="M1",
        authorized_deployment_ceiling="D0",
        from_strategy="lru",
        to_strategy=artifact.program.strategy_id,
    )


def decode_candidate_record(data: bytes | str | Mapping[str, Any]) -> CandidateManifest:
    try:
        if isinstance(data, Mapping):
            value: Any = dict(data)
            canonical_json_bytes(value)
        else:
            value = load_json_strict(data)
    except CanonicalizationError as error:
        raise ProvenanceError(str(error)) from error
    record = _object(value, "$", {"schema_version", "candidate_id", "manifest"})
    if record["schema_version"] != CANDIDATE_RECORD_SCHEMA_VERSION:
        _fail("$.schema_version", f"expected {CANDIDATE_RECORD_SCHEMA_VERSION!r}")
    recorded_id = _content_id(record["candidate_id"], "$.candidate_id")
    manifest = _object(
        record["manifest"],
        "$.manifest",
        {
            "schema_version",
            "artifact_id",
            "epoch_id",
            "parent_ids",
            "generator",
            "generation_input_ids",
            "representation",
            "feedback_treatment",
            "learner_update",
            "actual_profile",
            "authorized_ceiling",
            "mutation_report",
            "construction_trace_id",
            "build_environment",
            "capability_request",
        },
    )
    if manifest["schema_version"] != CANDIDATE_MANIFEST_SCHEMA_VERSION:
        _fail(
            "$.manifest.schema_version",
            f"expected {CANDIDATE_MANIFEST_SCHEMA_VERSION!r}",
        )
    generator = _object(
        manifest["generator"],
        "$.manifest.generator",
        {"id", "version", "seed"},
    )
    representation = _object(
        manifest["representation"],
        "$.manifest.representation",
        {"level", "kernel_version", "program_schema", "action_schema"},
    )
    if representation["kernel_version"] != KERNEL_VERSION:
        _fail("$.manifest.representation.kernel_version", "unknown kernel version")
    if representation["program_schema"] != PROGRAM_SCHEMA_VERSION:
        _fail("$.manifest.representation.program_schema", "unknown program schema")
    if representation["action_schema"] != ACTION_SCHEMA_VERSION:
        _fail("$.manifest.representation.action_schema", "unknown action schema")
    learner = _object(
        manifest["learner_update"],
        "$.manifest.learner_update",
        {"level", "mechanisms"},
    )
    profile = _object(
        manifest["actual_profile"],
        "$.manifest.actual_profile",
        {"r", "m", "g", "l", "d", "f"},
    )
    ceiling = _object(
        manifest["authorized_ceiling"],
        "$.manifest.authorized_ceiling",
        {"m", "d"},
    )
    mutation = _object(
        manifest["mutation_report"],
        "$.manifest.mutation_report",
        {"kind", "from_strategy", "to_strategy"},
    )
    if mutation["kind"] != "strategy_selection":
        _fail("$.manifest.mutation_report.kind", "expected strategy_selection")
    build = _object(
        manifest["build_environment"],
        "$.manifest.build_environment",
        {"runtime", "dependencies"},
    )
    if build["runtime"] != "PythonStdlibControlPlaneV0" or build["dependencies"] != []:
        _fail("$.manifest.build_environment", "unexpected build environment")
    capabilities = _object(
        manifest["capability_request"],
        "$.manifest.capability_request",
        {"effects"},
    )
    if capabilities["effects"] != []:
        _fail("$.manifest.capability_request.effects", "v0 candidates are pure")

    from_strategy_value = mutation["from_strategy"]
    if from_strategy_value is not None:
        from_strategy = _string(
            from_strategy_value,
            "$.manifest.mutation_report.from_strategy",
            identifier=True,
        )
    else:
        from_strategy = None
    construction_trace_id = _optional_content_id(
        manifest["construction_trace_id"],
        "$.manifest.construction_trace_id",
    )
    decoded = CandidateManifest(
        artifact_id=_content_id(manifest["artifact_id"], "$.manifest.artifact_id"),
        epoch_id=_content_id(manifest["epoch_id"], "$.manifest.epoch_id"),
        parent_ids=_string_tuple(
            manifest["parent_ids"], "$.manifest.parent_ids", ids=True
        ),
        generator_id=_string(
            generator["id"], "$.manifest.generator.id", identifier=True
        ),
        generator_version=_string(
            generator["version"],
            "$.manifest.generator.version",
            identifier=True,
        ),
        generator_seed=_integer(generator["seed"], "$.manifest.generator.seed"),
        generation_input_ids=_string_tuple(
            manifest["generation_input_ids"],
            "$.manifest.generation_input_ids",
            ids=True,
        ),
        representation_level=_string(
            representation["level"], "$.manifest.representation.level"
        ),
        feedback_treatment=_string(
            manifest["feedback_treatment"], "$.manifest.feedback_treatment"
        ),
        learner_update_level=_string(
            learner["level"], "$.manifest.learner_update.level"
        ),
        learner_update_mechanisms=_string_tuple(
            learner["mechanisms"], "$.manifest.learner_update.mechanisms"
        ),
        mutation_level=_string(profile["m"], "$.manifest.actual_profile.m"),
        generator_level=_string(profile["g"], "$.manifest.actual_profile.g"),
        deployment_level=_string(profile["d"], "$.manifest.actual_profile.d"),
        authorized_mutation_ceiling=_string(
            ceiling["m"], "$.manifest.authorized_ceiling.m"
        ),
        authorized_deployment_ceiling=_string(
            ceiling["d"], "$.manifest.authorized_ceiling.d"
        ),
        from_strategy=from_strategy,
        to_strategy=_string(
            mutation["to_strategy"],
            "$.manifest.mutation_report.to_strategy",
            identifier=True,
        ),
        construction_trace_id=construction_trace_id,
    )
    if profile["r"] != decoded.representation_level:
        _fail("$.manifest.actual_profile.r", "does not match representation level")
    if profile["l"] != decoded.learner_update_level:
        _fail("$.manifest.actual_profile.l", "does not match learner update level")
    if profile["f"] != decoded.feedback_treatment:
        _fail("$.manifest.actual_profile.f", "does not match feedback treatment")
    if decoded.candidate_id != recorded_id:
        _fail("$.candidate_id", "does not match canonical manifest content")
    return decoded


@dataclass(frozen=True)
class LedgerEvent:
    sequence: int
    previous_event_id: str | None
    event_type: str
    candidate_id: str | None
    artifact_id: str | None
    payload: Mapping[str, JsonValue]

    def to_document(self) -> dict[str, JsonValue]:
        return {
            "schema_version": LEDGER_EVENT_SCHEMA_VERSION,
            "sequence": self.sequence,
            "previous_event_id": self.previous_event_id,
            "event_type": self.event_type,
            "candidate_id": self.candidate_id,
            "artifact_id": self.artifact_id,
            "payload": dict(self.payload),
        }

    @property
    def event_id(self) -> str:
        return content_id(self.to_document())

    def to_record(self) -> dict[str, JsonValue]:
        return {
            "schema_version": LEDGER_RECORD_SCHEMA_VERSION,
            "event_id": self.event_id,
            "event": self.to_document(),
        }


def _decode_ledger_record(value: Any, expected_sequence: int, previous: str | None) -> LedgerEvent:
    record = _object(value, "$", {"schema_version", "event_id", "event"})
    if record["schema_version"] != LEDGER_RECORD_SCHEMA_VERSION:
        _fail("$.schema_version", f"expected {LEDGER_RECORD_SCHEMA_VERSION!r}")
    event_id = _content_id(record["event_id"], "$.event_id")
    event = _object(
        record["event"],
        "$.event",
        {
            "schema_version",
            "sequence",
            "previous_event_id",
            "event_type",
            "candidate_id",
            "artifact_id",
            "payload",
        },
    )
    if event["schema_version"] != LEDGER_EVENT_SCHEMA_VERSION:
        _fail("$.event.schema_version", f"expected {LEDGER_EVENT_SCHEMA_VERSION!r}")
    sequence = _integer(event["sequence"], "$.event.sequence")
    if sequence != expected_sequence:
        _fail("$.event.sequence", f"expected {expected_sequence}, got {sequence}")
    previous_id = _optional_content_id(
        event["previous_event_id"], "$.event.previous_event_id"
    )
    if previous_id != previous:
        _fail("$.event.previous_event_id", "does not match prior event")
    event_type = _string(event["event_type"], "$.event.event_type", identifier=True)
    if event_type not in _EVENT_TYPES:
        _fail("$.event.event_type", f"unknown event type {event_type!r}")
    candidate_id = _optional_content_id(event["candidate_id"], "$.event.candidate_id")
    artifact_id = _optional_content_id(event["artifact_id"], "$.event.artifact_id")
    payload = event["payload"]
    if not isinstance(payload, dict):
        _fail("$.event.payload", "expected an object")
    decoded = LedgerEvent(
        sequence=sequence,
        previous_event_id=previous_id,
        event_type=event_type,
        candidate_id=candidate_id,
        artifact_id=artifact_id,
        payload=payload,
    )
    if decoded.event_id != event_id:
        _fail("$.event_id", "does not match canonical event content")
    return decoded


class AppendOnlyLedger:
    """Single-file canonical JSONL ledger with a validated hash chain."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _parse(data: bytes) -> tuple[LedgerEvent, ...]:
        if len(data) > MAX_LEDGER_BYTES:
            raise ProvenanceError("ledger exceeds maximum size")
        if data and not data.endswith(b"\n"):
            raise ProvenanceError("ledger has a truncated final record")
        events: list[LedgerEvent] = []
        previous: str | None = None
        for sequence, line in enumerate(data.splitlines()):
            if len(line) > MAX_LEDGER_LINE_BYTES:
                raise ProvenanceError(f"ledger line {sequence} exceeds maximum size")
            try:
                value = load_json_strict(line)
            except CanonicalizationError as error:
                raise ProvenanceError(f"ledger line {sequence}: {error}") from error
            if canonical_json_bytes(value) != line:
                raise ProvenanceError(f"ledger line {sequence} is not canonical JSON")
            event = _decode_ledger_record(value, sequence, previous)
            events.append(event)
            previous = event.event_id
        return tuple(events)

    def read_all(self) -> tuple[LedgerEvent, ...]:
        if not self.path.exists():
            return ()
        with self.path.open("rb") as handle:
            fcntl.flock(handle.fileno(), fcntl.LOCK_SH)
            data = handle.read(MAX_LEDGER_BYTES + 1)
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        return self._parse(data)

    def append(
        self,
        event_type: str,
        *,
        candidate_id: str | None = None,
        artifact_id: str | None = None,
        payload: Mapping[str, JsonValue] | None = None,
    ) -> LedgerEvent:
        if event_type not in _EVENT_TYPES:
            raise ProvenanceError(f"unknown event type {event_type!r}")
        if candidate_id is not None:
            _content_id(candidate_id, "$.candidate_id")
        if artifact_id is not None:
            _content_id(artifact_id, "$.artifact_id")
        payload_value = dict(payload or {})
        try:
            payload_bytes = canonical_json_bytes(payload_value)
            detached_payload = load_json_strict(payload_bytes)
        except CanonicalizationError as error:
            raise ProvenanceError(str(error)) from error
        assert isinstance(detached_payload, dict)

        with self.path.open("a+b") as handle:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            handle.seek(0)
            existing = self._parse(handle.read(MAX_LEDGER_BYTES + 1))
            previous = existing[-1].event_id if existing else None
            event = LedgerEvent(
                sequence=len(existing),
                previous_event_id=previous,
                event_type=event_type,
                candidate_id=candidate_id,
                artifact_id=artifact_id,
                payload=detached_payload,
            )
            line = canonical_json_bytes(event.to_record()) + b"\n"
            if len(line) > MAX_LEDGER_LINE_BYTES:
                raise ProvenanceError("ledger record exceeds maximum line size")
            handle.seek(0, os.SEEK_END)
            handle.write(line)
            handle.flush()
            os.fsync(handle.fileno())
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        return event

    @property
    def ledger_id(self) -> str:
        return content_id(
            {
                "schema_version": LEDGER_SNAPSHOT_SCHEMA_VERSION,
                "event_ids": [event.event_id for event in self.read_all()],
            }
        )

    def verify_expected_final_event(self, expected_event_id: str) -> None:
        events = self.read_all()
        actual = events[-1].event_id if events else None
        if actual != expected_event_id:
            raise ProvenanceError(
                f"final event mismatch: expected {expected_event_id}, got {actual}"
            )
