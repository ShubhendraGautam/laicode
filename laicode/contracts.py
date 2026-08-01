"""Validation and identity for the proposed evolution-contract v0 schema."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Mapping, NoReturn

from .canonical import (
    CanonicalizationError,
    JsonValue,
    canonical_json_bytes,
    load_json_strict,
)


SCHEMA_VERSION = "laicode.evolution-contract.v0"
MAX_CONTRACT_BYTES = 1_048_576

_IDENTIFIER = re.compile(r"^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*$")
_SCHEMA_ID = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]*V[0-9]+$")
_UTC_TIMESTAMP = re.compile(
    r"^[0-9]{4}-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12][0-9]|3[01])"
    r"T(?:[01][0-9]|2[0-3]):[0-5][0-9]:[0-5][0-9]Z$"
)

_PROFILE_LEVELS: dict[str, tuple[str, ...]] = {
    "r": ("R0", "R1", "R2", "R3", "R4", "R5"),
    "m": ("M0", "M1", "M2", "M3", "M4", "M5"),
    "g": ("G0", "G1", "G2", "G3", "G4", "G5"),
    "l": ("L0", "L1", "L2", "L3", "L4", "L5"),
    "d": ("D0", "D1", "D2", "D3", "D4", "D5"),
    "f": ("F0", "F1", "F2", "F3"),
}

_CAPABILITY_FIELDS = {
    "default",
    "filesystem",
    "network",
    "process",
    "clock",
    "randomness",
    "environment",
    "credentials",
    "model",
    "external_services",
}

_AMBIENT_CAPABILITY_VALUES = {"deny", "brokered_read", "brokered_call"}
_REQUIRED_EVIDENCE_PARTITIONS = {
    "search",
    "operational_holdout",
    "research_audit",
    "prospective",
    "historical_regression",
}
_REQUIRED_HALT_CONDITIONS = {
    "budget_exhaustion",
    "contract_expiry",
    "evaluator_failure",
    "evidence_integrity_failure",
}


class ContractValidationError(ValueError):
    """Raised when a document does not satisfy the v0 contract semantics."""


@dataclass(frozen=True)
class ValidatedContract:
    """An immutable canonical contract value and its content-derived epoch ID."""

    canonical_bytes: bytes
    epoch_id: str

    def to_dict(self) -> dict[str, JsonValue]:
        # The bytes were produced from validated JSON, so stdlib decoding is safe
        # here and returns a fresh, caller-owned document.
        value = json.loads(self.canonical_bytes)
        assert isinstance(value, dict)
        return value


def _fail(path: str, message: str) -> NoReturn:
    raise ContractValidationError(f"{path}: {message}")


def _object(
    value: Any,
    path: str,
    required: Iterable[str],
    optional: Iterable[str] = (),
) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        _fail(path, "expected an object")
    required_set = set(required)
    allowed = required_set | set(optional)
    missing = sorted(required_set - value.keys())
    unknown = sorted(value.keys() - allowed)
    if missing:
        _fail(path, f"missing required field(s): {', '.join(missing)}")
    if unknown:
        _fail(path, f"unknown field(s): {', '.join(unknown)}")
    return value


def _string(value: Any, path: str, *, pattern: re.Pattern[str] | None = None) -> str:
    if not isinstance(value, str):
        _fail(path, "expected a string")
    if not value:
        _fail(path, "must not be empty")
    if pattern is not None and pattern.fullmatch(value) is None:
        _fail(path, f"invalid value {value!r}")
    return value


def _enum(value: Any, path: str, allowed: Iterable[str]) -> str:
    text = _string(value, path)
    allowed_set = set(allowed)
    if text not in allowed_set:
        _fail(path, f"expected one of {', '.join(sorted(allowed_set))}; got {text!r}")
    return text


def _integer(value: Any, path: str, *, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        _fail(path, "expected an integer")
    if value < minimum:
        _fail(path, f"must be at least {minimum}")
    return value


def _boolean(value: Any, path: str) -> bool:
    if not isinstance(value, bool):
        _fail(path, "expected a boolean")
    return value


def _string_list(value: Any, path: str, *, allow_empty: bool = False) -> list[str]:
    if not isinstance(value, list):
        _fail(path, "expected an array")
    if not value and not allow_empty:
        _fail(path, "must contain at least one item")
    result: list[str] = []
    for index, item in enumerate(value):
        result.append(_string(item, f"{path}[{index}]", pattern=_IDENTIFIER))
    if len(result) != len(set(result)):
        _fail(path, "must not contain duplicates")
    return result


def _validate_subject(value: Any) -> None:
    subject = _object(
        value,
        "$.subject",
        {
            "kind",
            "entrypoint",
            "input_schema",
            "output_schema",
            "correctness_oracle",
            "fallback",
            "state",
        },
    )
    _enum(subject["kind"], "$.subject.kind", {"pure_function"})
    _string(subject["entrypoint"], "$.subject.entrypoint", pattern=_IDENTIFIER)
    _string(subject["input_schema"], "$.subject.input_schema", pattern=_SCHEMA_ID)
    _string(subject["output_schema"], "$.subject.output_schema", pattern=_SCHEMA_ID)
    _string(
        subject["correctness_oracle"],
        "$.subject.correctness_oracle",
        pattern=_IDENTIFIER,
    )
    _string(subject["fallback"], "$.subject.fallback", pattern=_IDENTIFIER)
    _enum(subject["state"], "$.subject.state", {"none"})


def _validate_profile(value: Any, path: str) -> dict[str, str]:
    profile = _object(value, path, _PROFILE_LEVELS.keys())
    return {
        axis: _enum(profile[axis], f"{path}.{axis}", levels)
        for axis, levels in _PROFILE_LEVELS.items()
    }


def _validate_profiles(value: Any) -> tuple[dict[str, str], dict[str, str]]:
    profiles = _object(value, "$.profiles", {"initial", "maximum_reviewed"})
    initial = _validate_profile(profiles["initial"], "$.profiles.initial")
    maximum = _validate_profile(
        profiles["maximum_reviewed"], "$.profiles.maximum_reviewed"
    )
    for axis, levels in _PROFILE_LEVELS.items():
        if levels.index(initial[axis]) > levels.index(maximum[axis]):
            _fail(
                f"$.profiles.initial.{axis}",
                f"{initial[axis]} exceeds reviewed maximum {maximum[axis]}",
            )
    return initial, maximum


def _validate_mutation(value: Any, maximum_profile: Mapping[str, str]) -> None:
    mutation = _object(
        value,
        "$.mutation",
        {
            "level",
            "kind",
            "candidate_ir",
            "allowed_strategy_ids",
            "mutable_regions",
            "max_artifact_bytes",
        },
    )
    level = _enum(mutation["level"], "$.mutation.level", _PROFILE_LEVELS["m"][:4])
    if _PROFILE_LEVELS["m"].index(level) > _PROFILE_LEVELS["m"].index(
        maximum_profile["m"]
    ):
        _fail("$.mutation.level", "exceeds profiles.maximum_reviewed.m")
    kind = _enum(
        mutation["kind"],
        "$.mutation.kind",
        {"none", "strategy_selection", "typed_parameters", "typed_ir"},
    )
    expected_kind = {
        "M0": "none",
        "M1": "strategy_selection",
        "M2": "typed_parameters",
        "M3": "typed_ir",
    }[level]
    if kind != expected_kind:
        _fail("$.mutation.kind", f"{level} requires {expected_kind!r}")
    _string(mutation["candidate_ir"], "$.mutation.candidate_ir", pattern=_SCHEMA_ID)
    strategies = _string_list(
        mutation["allowed_strategy_ids"],
        "$.mutation.allowed_strategy_ids",
        allow_empty=level != "M1",
    )
    if level == "M0" and strategies:
        _fail("$.mutation.allowed_strategy_ids", "M0 must not authorize strategies")
    regions = _string_list(
        mutation["mutable_regions"],
        "$.mutation.mutable_regions",
        allow_empty=level == "M0",
    )
    if level == "M0" and regions:
        _fail("$.mutation.mutable_regions", "M0 must not authorize mutable regions")
    _integer(
        mutation["max_artifact_bytes"],
        "$.mutation.max_artifact_bytes",
        minimum=1,
    )


def _validate_capabilities(value: Any) -> Mapping[str, str]:
    capabilities = _object(value, "$.capabilities", _CAPABILITY_FIELDS)
    result: dict[str, str] = {}
    for field in sorted(_CAPABILITY_FIELDS):
        result[field] = _enum(
            capabilities[field],
            f"$.capabilities.{field}",
            _AMBIENT_CAPABILITY_VALUES,
        )
    if result["default"] != "deny":
        _fail("$.capabilities.default", "v0 contracts must deny undeclared effects")
    return result


def _validate_constraints(value: Any) -> None:
    if not isinstance(value, list) or not value:
        _fail("$.constraints", "expected a non-empty array")
    identifiers: list[str] = []
    allowed_failures = {
        "prove": {"reject_candidate"},
        "runtime_enforce": {"fallback", "terminate_candidate"},
        "test": {"reject_candidate", "halt_epoch"},
        "statistically_monitor": {"rollback", "halt_epoch"},
    }
    for index, item in enumerate(value):
        path = f"$.constraints[{index}]"
        constraint = _object(
            item, path, {"id", "enforcement", "oracle", "failure_action"}
        )
        identifiers.append(_string(constraint["id"], f"{path}.id", pattern=_IDENTIFIER))
        enforcement = _enum(
            constraint["enforcement"], f"{path}.enforcement", allowed_failures
        )
        _string(constraint["oracle"], f"{path}.oracle", pattern=_IDENTIFIER)
        _enum(
            constraint["failure_action"],
            f"{path}.failure_action",
            allowed_failures[enforcement],
        )
    if len(identifiers) != len(set(identifiers)):
        _fail("$.constraints", "constraint IDs must be unique")


def _validate_objectives(value: Any) -> None:
    if not isinstance(value, list) or not value:
        _fail("$.objectives", "expected a non-empty array")
    identifiers: list[str] = []
    roles: list[str] = []
    fields = {
        "id",
        "direction",
        "role",
        "unit",
        "population",
        "denominator",
        "window",
        "missing_data",
        "practical_delta_ppm",
        "noninferiority_tolerance_ppm",
    }
    for index, item in enumerate(value):
        path = f"$.objectives[{index}]"
        objective = _object(item, path, fields)
        identifiers.append(_string(objective["id"], f"{path}.id", pattern=_IDENTIFIER))
        _enum(objective["direction"], f"{path}.direction", {"minimize", "maximize"})
        roles.append(
            _enum(
                objective["role"],
                f"{path}.role",
                {"primary", "protected", "secondary"},
            )
        )
        for field in ("unit", "population", "denominator", "window"):
            _string(objective[field], f"{path}.{field}", pattern=_IDENTIFIER)
        _enum(
            objective["missing_data"],
            f"{path}.missing_data",
            {"reject_candidate", "worst_case"},
        )
        _integer(objective["practical_delta_ppm"], f"{path}.practical_delta_ppm")
        _integer(
            objective["noninferiority_tolerance_ppm"],
            f"{path}.noninferiority_tolerance_ppm",
        )
    if len(identifiers) != len(set(identifiers)):
        _fail("$.objectives", "objective IDs must be unique")
    if roles.count("primary") != 1:
        _fail("$.objectives", "exactly one primary objective is required")


def _validate_comparison(value: Any) -> None:
    comparison = _object(
        value,
        "$.comparison",
        {
            "method",
            "uncertainty_method",
            "epoch_error_budget_ppm",
            "maximum_comparisons",
            "minimum_events_per_partition",
            "historical_regression_tolerance_ppm",
            "candidate_churn_limit",
            "promotion_limit",
            "tie_breaker",
        },
    )
    _enum(comparison["method"], "$.comparison.method", {"constrained"})
    _enum(
        comparison["uncertainty_method"],
        "$.comparison.uncertainty_method",
        {"deterministic_exact_exploratory"},
    )
    for field in (
        "epoch_error_budget_ppm",
        "historical_regression_tolerance_ppm",
    ):
        value = _integer(comparison[field], f"$.comparison.{field}")
        if value > 1_000_000:
            _fail(f"$.comparison.{field}", "must not exceed 1000000 ppm")
    for field in (
        "maximum_comparisons",
        "minimum_events_per_partition",
        "candidate_churn_limit",
        "promotion_limit",
    ):
        _integer(comparison[field], f"$.comparison.{field}", minimum=1)
    _enum(
        comparison["tie_breaker"],
        "$.comparison.tie_breaker",
        {"lower_risk_then_simpler"},
    )


def _validate_evidence(value: Any) -> None:
    evidence = _object(value, "$.evidence", _REQUIRED_EVIDENCE_PARTITIONS)
    for name in sorted(_REQUIRED_EVIDENCE_PARTITIONS):
        path = f"$.evidence.{name}"
        partition = _object(
            evidence[name], path, {"source", "candidate_access", "disclosure"}
        )
        _string(partition["source"], f"{path}.source", pattern=_IDENTIFIER)
        candidate_access = _boolean(
            partition["candidate_access"], f"{path}.candidate_access"
        )
        disclosure = _enum(
            partition["disclosure"],
            f"{path}.disclosure",
            {"none", "aggregate", "full"},
        )
        if name != "search" and candidate_access:
            _fail(
                f"{path}.candidate_access",
                "only search evidence may enter generation",
            )
        if name == "research_audit" and disclosure != "none":
            _fail(f"{path}.disclosure", "research audit must remain undisclosed")


_PER_CANDIDATE_BUDGET_FIELDS = {
    "cpu_milliseconds",
    "wall_milliseconds",
    "memory_bytes",
    "storage_bytes",
    "processes",
    "network_bytes",
    "evaluator_queries",
    "model_tokens",
    "money_microusd",
}
_PER_EPOCH_BUDGET_FIELDS = _PER_CANDIDATE_BUDGET_FIELDS | {"candidates"}


def _validate_budget(value: Any, path: str, fields: set[str]) -> Mapping[str, int]:
    budget = _object(value, path, fields)
    result: dict[str, int] = {}
    for field in sorted(fields):
        positive_fields = {
            "cpu_milliseconds",
            "wall_milliseconds",
            "memory_bytes",
            "storage_bytes",
            "processes",
            "evaluator_queries",
            "candidates",
        }
        minimum = 1 if field in positive_fields else 0
        result[field] = _integer(budget[field], f"{path}.{field}", minimum=minimum)
    return result


def _validate_budgets(value: Any, capabilities: Mapping[str, str]) -> None:
    budgets = _object(value, "$.budgets", {"per_candidate", "per_epoch"})
    per_candidate = _validate_budget(
        budgets["per_candidate"],
        "$.budgets.per_candidate",
        _PER_CANDIDATE_BUDGET_FIELDS,
    )
    per_epoch = _validate_budget(
        budgets["per_epoch"], "$.budgets.per_epoch", _PER_EPOCH_BUDGET_FIELDS
    )
    if capabilities["network"] == "deny" and (
        per_candidate["network_bytes"] != 0 or per_epoch["network_bytes"] != 0
    ):
        _fail("$.budgets", "network_bytes must be zero when network is denied")
    for field in _PER_CANDIDATE_BUDGET_FIELDS:
        if per_candidate[field] > per_epoch[field]:
            _fail(
                f"$.budgets.per_candidate.{field}",
                "must not exceed the corresponding per-epoch budget",
            )


def _validate_comparison_budget_consistency(
    comparison_value: Any,
    budgets_value: Any,
) -> None:
    assert isinstance(comparison_value, dict)
    assert isinstance(budgets_value, dict)
    per_epoch = budgets_value["per_epoch"]
    assert isinstance(per_epoch, dict)
    if comparison_value["candidate_churn_limit"] > per_epoch["candidates"]:
        _fail(
            "$.comparison.candidate_churn_limit",
            "must not exceed budgets.per_epoch.candidates",
        )
    if comparison_value["maximum_comparisons"] >= per_epoch["candidates"]:
        _fail(
            "$.comparison.maximum_comparisons",
            "must leave room for the baseline candidate in the epoch budget",
        )
    if comparison_value["promotion_limit"] > comparison_value["candidate_churn_limit"]:
        _fail(
            "$.comparison.promotion_limit",
            "must not exceed candidate_churn_limit",
        )


def _validate_halt_conditions(value: Any) -> None:
    conditions = _string_list(value, "$.halt_conditions")
    unknown = sorted(set(conditions) - _REQUIRED_HALT_CONDITIONS)
    if unknown:
        _fail("$.halt_conditions", f"unsupported condition(s): {', '.join(unknown)}")
    missing = sorted(_REQUIRED_HALT_CONDITIONS - set(conditions))
    if missing:
        _fail(
            "$.halt_conditions",
            f"missing mandatory condition(s): {', '.join(missing)}",
        )


def validate_contract(document: JsonValue) -> ValidatedContract:
    """Validate a decoded document and return its canonical immutable value."""

    try:
        canonical = canonical_json_bytes(document)
    except CanonicalizationError as error:
        raise ContractValidationError(str(error)) from error

    root = _object(
        document,
        "$",
        {
            "schema_version",
            "name",
            "epoch",
            "expires_at",
            "subject",
            "profiles",
            "mutation",
            "capabilities",
            "constraints",
            "objectives",
            "comparison",
            "evidence",
            "budgets",
            "halt_conditions",
        },
    )
    if root["schema_version"] != SCHEMA_VERSION:
        _fail("$.schema_version", f"expected {SCHEMA_VERSION!r}")
    _string(root["name"], "$.name", pattern=_IDENTIFIER)
    _string(root["epoch"], "$.epoch", pattern=_IDENTIFIER)
    expires_at = _string(root["expires_at"], "$.expires_at", pattern=_UTC_TIMESTAMP)
    try:
        datetime.strptime(expires_at, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError as error:
        _fail("$.expires_at", f"invalid UTC timestamp: {error}")
    _validate_subject(root["subject"])
    _, maximum = _validate_profiles(root["profiles"])
    _validate_mutation(root["mutation"], maximum)
    capabilities = _validate_capabilities(root["capabilities"])
    _validate_constraints(root["constraints"])
    _validate_objectives(root["objectives"])
    _validate_comparison(root["comparison"])
    _validate_evidence(root["evidence"])
    _validate_budgets(root["budgets"], capabilities)
    _validate_comparison_budget_consistency(root["comparison"], root["budgets"])
    _validate_halt_conditions(root["halt_conditions"])

    digest = hashlib.sha256(canonical).hexdigest()
    return ValidatedContract(
        canonical_bytes=canonical,
        epoch_id=f"sha256:{digest}",
    )


def load_contract(path: str | Path) -> ValidatedContract:
    """Read and validate a contract from a size-bounded UTF-8 JSON file."""

    contract_path = Path(path)
    data = contract_path.read_bytes()
    if len(data) > MAX_CONTRACT_BYTES:
        raise ContractValidationError(
            f"$: contract is {len(data)} bytes; maximum is {MAX_CONTRACT_BYTES}"
        )
    try:
        document = load_json_strict(data)
    except CanonicalizationError as error:
        raise ContractValidationError(str(error)) from error
    return validate_contract(document)
