"""Fixed cache-policy semantic kernel and typed construction protocol.

This module is the first executable slice of Decision 0002. The authoritative
candidate is a closed semantic object, never imported source code. R2 complete
program documents and R3 incremental actions lower to the same artifact bytes.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping, NoReturn

from .canonical import (
    CanonicalizationError,
    JsonValue,
    canonical_json_bytes,
    content_id,
    load_json_strict,
)
from .contracts import ContractValidationError, ValidatedContract, validate_contract


KERNEL_VERSION = "CachePolicyKernelV0"
PROGRAM_SCHEMA_VERSION = "CacheStrategySelectionV0"
PROGRAM_STATE_SCHEMA_VERSION = "CachePolicyProgramStateV0"
ACTION_SCHEMA_VERSION = "CachePolicyActionV0"
ACTION_RESULT_SCHEMA_VERSION = "CachePolicyActionResultV0"
ARTIFACT_SCHEMA_VERSION = "CachePolicyArtifactV0"

ROOT_HOLE_ID = "root"
ROOT_TYPE = "CacheKeyV0"
ROOT_SCOPE = ("snapshot",)
ROOT_OBLIGATIONS = ("result_is_evictable", "result_is_not_pinned")
REGISTERED_STRATEGIES = ("fifo", "lfu", "lru")
MAX_ACTION_BYTES = 65_536


class KernelError(ValueError):
    """Raised when a contract, program, or session is incompatible with v0."""


class CommitError(KernelError):
    """Raised when an incomplete or abandoned branch is committed."""


def _fail(path: str, message: str) -> NoReturn:
    raise KernelError(f"{path}: {message}")


def _object(
    value: Any,
    path: str,
    required: Iterable[str],
) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        _fail(path, "expected an object")
    required_set = set(required)
    missing = sorted(required_set - value.keys())
    unknown = sorted(value.keys() - required_set)
    if missing:
        _fail(path, f"missing required field(s): {', '.join(missing)}")
    if unknown:
        _fail(path, f"unknown field(s): {', '.join(unknown)}")
    return value


def _string(value: Any, path: str, *, maximum: int = 256) -> str:
    if not isinstance(value, str):
        _fail(path, "expected a string")
    if not value:
        _fail(path, "must not be empty")
    if len(value) > maximum:
        _fail(path, f"must not exceed {maximum} Unicode scalar values")
    return value


def _transport_document(data: bytes | str | Mapping[str, Any]) -> dict[str, Any]:
    if isinstance(data, bytes):
        if len(data) > MAX_ACTION_BYTES:
            _fail("$", f"input exceeds {MAX_ACTION_BYTES} bytes")
        try:
            value = load_json_strict(data)
        except CanonicalizationError as error:
            raise KernelError(str(error)) from error
    elif isinstance(data, str):
        try:
            encoded = data.encode("utf-8")
        except UnicodeEncodeError as error:
            raise KernelError("$: input is not valid UTF-8") from error
        if len(encoded) > MAX_ACTION_BYTES:
            _fail("$", f"input exceeds {MAX_ACTION_BYTES} bytes")
        try:
            value = load_json_strict(data)
        except CanonicalizationError as error:
            raise KernelError(str(error)) from error
    elif isinstance(data, Mapping):
        value = dict(data)
        try:
            canonical_json_bytes(value)
        except CanonicalizationError as error:
            raise KernelError(str(error)) from error
    else:
        _fail("$", "expected a JSON object or UTF-8 JSON transport")

    if not isinstance(value, dict):
        _fail("$", "expected an object")
    return value


@dataclass(frozen=True)
class ContractKernelPolicy:
    contract_id: str
    allowed_strategy_ids: tuple[str, ...]
    search_evidence_ids: tuple[str, ...]
    maximum_representation: str
    root_obligations: tuple[str, ...]


def _policy_from_contract(contract: ValidatedContract) -> ContractKernelPolicy:
    try:
        verified_contract = validate_contract(contract.to_dict())
    except (
        AssertionError,
        ContractValidationError,
        KeyError,
        TypeError,
        UnicodeError,
        ValueError,
    ) as error:
        raise KernelError("contract does not contain a validated v0 document") from error
    if (
        verified_contract.epoch_id != contract.epoch_id
        or verified_contract.canonical_bytes != contract.canonical_bytes
    ):
        _fail("$.contract_id", "validated contract identity does not match its bytes")

    document = verified_contract.to_dict()
    subject = document["subject"]
    mutation = document["mutation"]
    profiles = document["profiles"]
    evidence = document["evidence"]
    constraints = document["constraints"]
    assert isinstance(subject, dict)
    assert isinstance(mutation, dict)
    assert isinstance(profiles, dict)
    assert isinstance(evidence, dict)
    assert isinstance(constraints, list)

    expected_subject = {
        "kind": "pure_function",
        "entrypoint": "cache.select_victim",
        "input_schema": "CacheSnapshotV0",
        "output_schema": "CacheKeyV0",
        "state": "none",
    }
    for field, expected in expected_subject.items():
        if subject[field] != expected:
            _fail(
                f"$.subject.{field}",
                f"kernel {KERNEL_VERSION} requires {expected!r}",
            )

    if mutation["candidate_ir"] != PROGRAM_SCHEMA_VERSION:
        _fail(
            "$.mutation.candidate_ir",
            f"kernel requires {PROGRAM_SCHEMA_VERSION!r}",
        )
    if mutation["level"] != "M1" or mutation["kind"] != "strategy_selection":
        _fail("$.mutation", "kernel v0 requires M1 strategy_selection authority")

    maximum = profiles["maximum_reviewed"]
    assert isinstance(maximum, dict)
    maximum_representation = maximum["r"]
    assert isinstance(maximum_representation, str)

    allowed = mutation["allowed_strategy_ids"]
    assert isinstance(allowed, list)
    strategy_ids = tuple(str(item) for item in allowed)
    unknown_strategies = sorted(set(strategy_ids) - set(REGISTERED_STRATEGIES))
    if unknown_strategies:
        _fail(
            "$.mutation.allowed_strategy_ids",
            "kernel has no semantics for: " + ", ".join(unknown_strategies),
        )

    constraints_by_id: dict[str, Mapping[str, Any]] = {}
    for constraint in constraints:
        assert isinstance(constraint, dict)
        constraint_id = constraint["id"]
        assert isinstance(constraint_id, str)
        constraints_by_id[constraint_id] = constraint
    missing_obligations = sorted(set(ROOT_OBLIGATIONS) - constraints_by_id.keys())
    if missing_obligations:
        _fail(
            "$.constraints",
            "kernel requires obligation(s): " + ", ".join(missing_obligations),
        )
    required_constraint_semantics = {
        "result_is_evictable": "cache.result_is_evictable.v0",
        "result_is_not_pinned": "cache.result_is_not_pinned.v0",
    }
    for constraint_id, oracle in required_constraint_semantics.items():
        constraint = constraints_by_id[constraint_id]
        if (
            constraint["enforcement"] != "runtime_enforce"
            or constraint["oracle"] != oracle
            or constraint["failure_action"] != "fallback"
        ):
            _fail(
                "$.constraints",
                f"{constraint_id!r} does not match kernel v0 enforcement semantics",
            )

    available_evidence: list[str] = []
    for partition_name, partition in evidence.items():
        assert isinstance(partition_name, str) and isinstance(partition, dict)
        if partition["candidate_access"]:
            available_evidence.append(partition_name)

    return ContractKernelPolicy(
        contract_id=contract.epoch_id,
        allowed_strategy_ids=strategy_ids,
        search_evidence_ids=tuple(sorted(available_evidence)),
        maximum_representation=maximum_representation,
        root_obligations=ROOT_OBLIGATIONS,
    )


@dataclass(frozen=True)
class Hole:
    hole_id: str = ROOT_HOLE_ID
    expected_type: str = ROOT_TYPE
    allowed_effects: tuple[str, ...] = ()
    scope: tuple[str, ...] = ROOT_SCOPE
    obligations: tuple[str, ...] = ROOT_OBLIGATIONS

    def to_document(self) -> dict[str, JsonValue]:
        return {
            "node": "hole",
            "hole_id": self.hole_id,
            "expected_type": self.expected_type,
            "allowed_effects": list(self.allowed_effects),
            "scope": list(self.scope),
            "obligations": list(self.obligations),
        }


@dataclass(frozen=True)
class SelectStrategy:
    strategy_id: str

    @property
    def result_type(self) -> str:
        return ROOT_TYPE

    @property
    def effects(self) -> tuple[str, ...]:
        return ()

    def to_document(self) -> dict[str, JsonValue]:
        return {
            "schema_version": PROGRAM_SCHEMA_VERSION,
            "op": "select_strategy",
            "strategy_id": self.strategy_id,
        }


ProgramNode = Hole | SelectStrategy


@dataclass(frozen=True)
class ProgramState:
    contract_id: str
    root: ProgramNode
    abandoned: bool = False

    @classmethod
    def initial(
        cls,
        contract_id: str,
        obligations: tuple[str, ...],
    ) -> "ProgramState":
        return cls(
            contract_id=contract_id,
            root=Hole(obligations=obligations),
        )

    @property
    def status(self) -> str:
        if self.abandoned:
            return "abandoned"
        if isinstance(self.root, Hole):
            return "open"
        return "complete"

    @property
    def open_holes(self) -> tuple[Hole, ...]:
        if self.abandoned or not isinstance(self.root, Hole):
            return ()
        return (self.root,)

    @property
    def proof_obligations(self) -> tuple[str, ...]:
        if self.abandoned or not isinstance(self.root, Hole):
            return ()
        return self.root.obligations

    def to_document(self) -> dict[str, JsonValue]:
        return {
            "schema_version": PROGRAM_STATE_SCHEMA_VERSION,
            "kernel_version": KERNEL_VERSION,
            "contract_id": self.contract_id,
            "status": self.status,
            "root": self.root.to_document(),
        }

    @property
    def state_id(self) -> str:
        return content_id(self.to_document())


@dataclass(frozen=True)
class ActionResult:
    state: ProgramState
    accepted: bool
    action_id: str | None
    type_and_effect_delta: Mapping[str, JsonValue] | None
    diagnostics: tuple[Mapping[str, JsonValue], ...]

    def to_document(self) -> dict[str, JsonValue]:
        return {
            "schema_version": ACTION_RESULT_SCHEMA_VERSION,
            "state_id": self.state.state_id,
            "accepted": self.accepted,
            "action_id": self.action_id,
            "type_and_effect_delta": (
                dict(self.type_and_effect_delta)
                if self.type_and_effect_delta is not None
                else None
            ),
            "open_holes": [hole.to_document() for hole in self.state.open_holes],
            "proof_obligations": list(self.state.proof_obligations),
            "structured_diagnostics": [dict(item) for item in self.diagnostics],
            "action_cost": {"semantic_steps": 1},
        }


@dataclass(frozen=True)
class CandidateArtifact:
    contract_id: str
    program: SelectStrategy

    def to_document(self) -> dict[str, JsonValue]:
        return {
            "schema_version": ARTIFACT_SCHEMA_VERSION,
            "kernel_version": KERNEL_VERSION,
            "contract_id": self.contract_id,
            "program": self.program.to_document(),
        }

    @property
    def canonical_bytes(self) -> bytes:
        return canonical_json_bytes(self.to_document())

    @property
    def artifact_id(self) -> str:
        return content_id(self.to_document())


def _decode_complete_program(
    data: bytes | str | Mapping[str, Any],
    policy: ContractKernelPolicy,
) -> SelectStrategy:
    document = _transport_document(data)
    program = _object(
        document,
        "$",
        {"schema_version", "op", "strategy_id"},
    )
    if program["schema_version"] != PROGRAM_SCHEMA_VERSION:
        _fail("$.schema_version", f"expected {PROGRAM_SCHEMA_VERSION!r}")
    if program["op"] != "select_strategy":
        _fail("$.op", "expected 'select_strategy'")
    strategy_id = _string(program["strategy_id"], "$.strategy_id")
    if strategy_id not in policy.allowed_strategy_ids:
        _fail("$.strategy_id", f"strategy {strategy_id!r} is not contract-authorized")
    return SelectStrategy(strategy_id=strategy_id)


def compile_complete_program(
    contract: ValidatedContract,
    data: bytes | str | Mapping[str, Any],
) -> CandidateArtifact:
    """Compile an R2 complete program into the fixed-kernel artifact format."""

    policy = _policy_from_contract(contract)
    if int(policy.maximum_representation[1:]) < 2:
        _fail("$.profiles.maximum_reviewed.r", "R2 program input is not reviewed")
    program = _decode_complete_program(data, policy)
    return CandidateArtifact(contract_id=policy.contract_id, program=program)


class ConstructionSession:
    """An R3 typed construction episode over one immutable program state."""

    def __init__(
        self,
        policy: ContractKernelPolicy,
        permitted_evidence: tuple[str, ...],
    ) -> None:
        self._policy = policy
        self._permitted_evidence = permitted_evidence
        self._state = ProgramState.initial(
            policy.contract_id,
            policy.root_obligations,
        )

    @classmethod
    def open(
        cls,
        contract: ValidatedContract,
        *,
        action_schema: str = ACTION_SCHEMA_VERSION,
        permitted_evidence: Iterable[str] = (),
    ) -> "ConstructionSession":
        policy = _policy_from_contract(contract)
        if int(policy.maximum_representation[1:]) < 3:
            _fail("$.profiles.maximum_reviewed.r", "R3 actions are not reviewed")
        if action_schema != ACTION_SCHEMA_VERSION:
            _fail("$.action_schema", f"expected {ACTION_SCHEMA_VERSION!r}")

        requested = tuple(sorted(set(permitted_evidence)))
        unavailable = sorted(set(requested) - set(policy.search_evidence_ids))
        if unavailable:
            _fail(
                "$.permitted_evidence",
                f"evidence is not candidate-accessible: {', '.join(unavailable)}",
            )
        return cls(policy=policy, permitted_evidence=requested)

    @property
    def state(self) -> ProgramState:
        return self._state

    @property
    def permitted_evidence(self) -> tuple[str, ...]:
        return self._permitted_evidence

    def _rejected(self, action_id: str | None, code: str, message: str) -> ActionResult:
        return ActionResult(
            state=self._state,
            accepted=False,
            action_id=action_id,
            type_and_effect_delta=None,
            diagnostics=({"code": code, "message": message},),
        )

    def step(self, data: bytes | str | Mapping[str, Any]) -> ActionResult:
        """Apply one action, returning structured rejection without state change."""

        try:
            document = _transport_document(data)
            action_id = content_id(document)
        except KernelError as error:
            return self._rejected(None, "invalid_action_transport", str(error))

        try:
            envelope = _object(document, "$", {"schema_version", "action", "payload"})
            if envelope["schema_version"] != ACTION_SCHEMA_VERSION:
                _fail("$.schema_version", f"expected {ACTION_SCHEMA_VERSION!r}")
            action = _string(envelope["action"], "$.action")
            payload = envelope["payload"]

            if self._state.abandoned:
                _fail("$.action", "branch is already abandoned")
            if action == "fill_hole":
                return self._fill_hole(action_id, payload)
            if action == "abandon_branch":
                return self._abandon_branch(action_id, payload)
            _fail("$.action", f"unknown action {action!r}")
        except KernelError as error:
            return self._rejected(action_id, "action_rejected", str(error))

    def _fill_hole(self, action_id: str, value: Any) -> ActionResult:
        payload = _object(value, "$.payload", {"hole_id", "constructor"})
        hole_id = _string(payload["hole_id"], "$.payload.hole_id")
        if not isinstance(self._state.root, Hole):
            _fail("$.payload.hole_id", "program has no open hole")
        if hole_id != self._state.root.hole_id:
            _fail("$.payload.hole_id", f"unknown open hole {hole_id!r}")

        constructor = _object(
            payload["constructor"],
            "$.payload.constructor",
            {"op", "strategy_id"},
        )
        if constructor["op"] != "select_strategy":
            _fail("$.payload.constructor.op", "unknown constructor")
        strategy_id = _string(
            constructor["strategy_id"],
            "$.payload.constructor.strategy_id",
        )
        if strategy_id not in self._policy.allowed_strategy_ids:
            _fail(
                "$.payload.constructor.strategy_id",
                f"strategy {strategy_id!r} is not contract-authorized",
            )

        program = SelectStrategy(strategy_id=strategy_id)
        if program.result_type != self._state.root.expected_type:
            _fail("$.payload.constructor", "constructor type does not match the hole")
        if not set(program.effects).issubset(self._state.root.allowed_effects):
            _fail("$.payload.constructor", "constructor widens the allowed effects")

        self._state = ProgramState(
            contract_id=self._policy.contract_id,
            root=program,
        )
        return ActionResult(
            state=self._state,
            accepted=True,
            action_id=action_id,
            type_and_effect_delta={
                "filled_hole": hole_id,
                "produced_type": program.result_type,
                "added_effects": list(program.effects),
            },
            diagnostics=(),
        )

    def _abandon_branch(self, action_id: str, value: Any) -> ActionResult:
        payload = _object(value, "$.payload", {"reason"})
        _string(payload["reason"], "$.payload.reason", maximum=1024)
        self._state = ProgramState(
            contract_id=self._policy.contract_id,
            root=self._state.root,
            abandoned=True,
        )
        return ActionResult(
            state=self._state,
            accepted=True,
            action_id=action_id,
            type_and_effect_delta=None,
            diagnostics=(),
        )

    def commit(self) -> CandidateArtifact:
        if self._state.abandoned:
            raise CommitError("cannot commit an abandoned branch")
        if isinstance(self._state.root, Hole):
            raise CommitError("cannot commit a program with open holes")
        return CandidateArtifact(
            contract_id=self._policy.contract_id,
            program=self._state.root,
        )


def render_program(program: SelectStrategy) -> str:
    """Return the deterministic human-readable projection of a program."""

    return (
        "select_victim(snapshot: CacheSnapshotV0) -> CacheKeyV0 = "
        f"reviewed::{program.strategy_id}(snapshot)"
    )


def graph_program(program: SelectStrategy) -> dict[str, JsonValue]:
    """Return a deterministic graph projection of the authoritative program."""

    return {
        "schema_version": "CachePolicyGraphV0",
        "nodes": [
            {
                "id": "root",
                "op": "select_strategy",
                "strategy_id": program.strategy_id,
                "result_type": program.result_type,
                "effects": list(program.effects),
            }
        ],
        "edges": [],
    }
