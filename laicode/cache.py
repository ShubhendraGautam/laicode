"""Deterministic cache benchmark, reference policies, and output shield."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Callable, Iterable, Mapping, NoReturn

from .canonical import (
    CanonicalizationError,
    JsonValue,
    canonical_json_bytes,
    content_id,
    load_json_strict,
)
from .kernel import CandidateArtifact, REGISTERED_STRATEGIES


TRACE_SCHEMA_VERSION = "CacheTraceV0"
SNAPSHOT_SCHEMA_VERSION = "CacheSnapshotV0"
SIMULATION_SCHEMA_VERSION = "CacheSimulationResultV0"
METRICS_SCHEMA_VERSION = "CacheMetricsV0"
OBSERVATION_SCHEMA_VERSION = "CacheObservationV0"
PRNG_VERSION = "SplitMix64V0"
MAX_TRACE_BYTES = 16 * 1024 * 1024
MAX_TRACE_EVENTS = 100_000

_MASK_64 = (1 << 64) - 1
_MAX_JSON_SEED = (1 << 63) - 1
_KEY_PATTERN = re.compile(r"^[a-z][a-z0-9]*(?:[_-][a-z0-9]+)*$")
_SCENARIOS = {"scan_resistance", "recency_shift", "mixed_bursts"}


class CacheError(ValueError):
    """Raised when a trace or cache operation violates prototype semantics."""


def _fail(path: str, message: str) -> NoReturn:
    raise CacheError(f"{path}: {message}")


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


def _string(value: Any, path: str) -> str:
    if not isinstance(value, str) or not value:
        _fail(path, "expected a non-empty string")
    return value


def _key(value: Any, path: str) -> str:
    key = _string(value, path)
    if len(key) > 64 or _KEY_PATTERN.fullmatch(key) is None:
        _fail(path, f"invalid cache key {key!r}")
    return key


def _integer(value: Any, path: str, *, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        _fail(path, "expected an integer")
    if value < minimum:
        _fail(path, f"must be at least {minimum}")
    return value


class SplitMix64:
    """Small, fully specified generator used only to create benchmark traces."""

    def __init__(self, seed: int) -> None:
        if not 0 <= seed <= _MASK_64:
            raise CacheError("seed must be an unsigned 64-bit integer")
        self._state = seed

    def next_u64(self) -> int:
        self._state = (self._state + 0x9E3779B97F4A7C15) & _MASK_64
        value = self._state
        value = ((value ^ (value >> 30)) * 0xBF58476D1CE4E5B9) & _MASK_64
        value = ((value ^ (value >> 27)) * 0x94D049BB133111EB) & _MASK_64
        return (value ^ (value >> 31)) & _MASK_64

    def randbelow(self, bound: int) -> int:
        if bound <= 0:
            raise CacheError("randbelow bound must be positive")
        threshold = ((1 << 64) - bound) % bound
        while True:
            value = self.next_u64()
            if value >= threshold:
                return value % bound


@dataclass(frozen=True)
class AccessEvent:
    sequence: int
    key: str
    pinned_keys: tuple[str, ...] = ()

    def to_document(self) -> dict[str, JsonValue]:
        return {
            "sequence": self.sequence,
            "key": self.key,
            "pinned_keys": list(self.pinned_keys),
        }


@dataclass(frozen=True)
class CacheTrace:
    name: str
    scenario: str
    seed: int
    capacity: int
    events: tuple[AccessEvent, ...]

    def to_document(self) -> dict[str, JsonValue]:
        return {
            "schema_version": TRACE_SCHEMA_VERSION,
            "generator": PRNG_VERSION,
            "name": self.name,
            "scenario": self.scenario,
            "seed": self.seed,
            "capacity": self.capacity,
            "event_count": len(self.events),
            "events": [event.to_document() for event in self.events],
        }

    @property
    def canonical_bytes(self) -> bytes:
        return canonical_json_bytes(self.to_document())

    @property
    def trace_id(self) -> str:
        return content_id(self.to_document())


def _decode_document(data: bytes | str | Mapping[str, Any]) -> dict[str, Any]:
    if isinstance(data, bytes):
        if len(data) > MAX_TRACE_BYTES:
            _fail("$", f"trace exceeds {MAX_TRACE_BYTES} bytes")
        try:
            value = load_json_strict(data)
        except CanonicalizationError as error:
            raise CacheError(str(error)) from error
    elif isinstance(data, str):
        try:
            encoded = data.encode("utf-8")
        except UnicodeEncodeError as error:
            raise CacheError("$: input is not valid UTF-8") from error
        if len(encoded) > MAX_TRACE_BYTES:
            _fail("$", f"trace exceeds {MAX_TRACE_BYTES} bytes")
        try:
            value = load_json_strict(data)
        except CanonicalizationError as error:
            raise CacheError(str(error)) from error
    elif isinstance(data, Mapping):
        value = dict(data)
        try:
            canonical_json_bytes(value)
        except CanonicalizationError as error:
            raise CacheError(str(error)) from error
    else:
        _fail("$", "expected a JSON object or UTF-8 JSON transport")
    if not isinstance(value, dict):
        _fail("$", "expected an object")
    return value


def decode_trace(data: bytes | str | Mapping[str, Any]) -> CacheTrace:
    document = _decode_document(data)
    trace = _object(
        document,
        "$",
        {
            "schema_version",
            "generator",
            "name",
            "scenario",
            "seed",
            "capacity",
            "event_count",
            "events",
        },
    )
    if trace["schema_version"] != TRACE_SCHEMA_VERSION:
        _fail("$.schema_version", f"expected {TRACE_SCHEMA_VERSION!r}")
    if trace["generator"] != PRNG_VERSION:
        _fail("$.generator", f"expected {PRNG_VERSION!r}")
    name = _key(trace["name"], "$.name")
    scenario = _string(trace["scenario"], "$.scenario")
    if scenario not in _SCENARIOS:
        _fail("$.scenario", f"unsupported scenario {scenario!r}")
    seed = _integer(trace["seed"], "$.seed")
    if seed > _MAX_JSON_SEED:
        _fail("$.seed", "must fit in the canonical signed 64-bit JSON profile")
    capacity = _integer(trace["capacity"], "$.capacity", minimum=1)
    if capacity > 1024:
        _fail("$.capacity", "must not exceed 1024")
    event_count = _integer(trace["event_count"], "$.event_count", minimum=1)
    if event_count > MAX_TRACE_EVENTS:
        _fail("$.event_count", f"must not exceed {MAX_TRACE_EVENTS}")
    raw_events = trace["events"]
    if not isinstance(raw_events, list):
        _fail("$.events", "expected an array")
    if len(raw_events) != event_count:
        _fail("$.event_count", "does not match the events array length")

    events: list[AccessEvent] = []
    for index, raw_event in enumerate(raw_events):
        path = f"$.events[{index}]"
        event = _object(raw_event, path, {"sequence", "key", "pinned_keys"})
        sequence = _integer(event["sequence"], f"{path}.sequence")
        if sequence != index:
            _fail(f"{path}.sequence", f"expected contiguous sequence {index}")
        key = _key(event["key"], f"{path}.key")
        raw_pinned = event["pinned_keys"]
        if not isinstance(raw_pinned, list):
            _fail(f"{path}.pinned_keys", "expected an array")
        pinned = tuple(
            sorted(
                _key(item, f"{path}.pinned_keys[{item_index}]")
                for item_index, item in enumerate(raw_pinned)
            )
        )
        if len(pinned) != len(set(pinned)):
            _fail(f"{path}.pinned_keys", "must not contain duplicates")
        events.append(AccessEvent(sequence=sequence, key=key, pinned_keys=pinned))

    return CacheTrace(
        name=name,
        scenario=scenario,
        seed=seed,
        capacity=capacity,
        events=tuple(events),
    )


def _scenario_key(
    scenario: str,
    sequence: int,
    event_count: int,
    random: SplitMix64,
) -> str:
    if scenario == "scan_resistance":
        offset = sequence % 64
        if offset < 40:
            return f"hot_{random.randbelow(4)}"
        return f"scan_{sequence // 64}_{offset - 40}"

    if scenario == "recency_shift":
        phase = 0 if sequence < event_count // 2 else 1
        if random.randbelow(100) < 88:
            return f"phase_{phase}_hot_{random.randbelow(6)}"
        return f"phase_{phase}_cold_{sequence}"

    phase = (sequence // 80) % 3
    offset = sequence % 80
    if phase == 0:
        return f"burst_a_{random.randbelow(3)}"
    if phase == 1 and offset < 48:
        return f"mixed_scan_{sequence // 80}_{offset}"
    return f"burst_b_{random.randbelow(5)}"


def _scenario_pins(
    scenario: str,
    sequence: int,
    event_count: int,
) -> tuple[str, ...]:
    if sequence % 97 not in {0, 1, 2, 3}:
        return ()
    if scenario == "scan_resistance":
        return ("hot_0",)
    if scenario == "recency_shift":
        phase = 0 if sequence < event_count // 2 else 1
        return (f"phase_{phase}_hot_0",)
    return ("burst_a_0",)


def generate_trace(
    scenario: str,
    seed: int,
    *,
    event_count: int = 512,
    capacity: int = 8,
    name: str | None = None,
) -> CacheTrace:
    if scenario not in _SCENARIOS:
        raise CacheError(f"unsupported scenario {scenario!r}")
    if not 0 <= seed <= _MAX_JSON_SEED:
        raise CacheError("seed must fit in the canonical signed 64-bit JSON profile")
    if not 1 <= event_count <= MAX_TRACE_EVENTS:
        raise CacheError(f"event_count must be between 1 and {MAX_TRACE_EVENTS}")
    if not 1 <= capacity <= 1024:
        raise CacheError("capacity must be between 1 and 1024")
    random = SplitMix64(seed)
    events = tuple(
        AccessEvent(
            sequence=sequence,
            key=_scenario_key(scenario, sequence, event_count, random),
            pinned_keys=_scenario_pins(scenario, sequence, event_count),
        )
        for sequence in range(event_count)
    )
    trace = CacheTrace(
        name=name or f"{scenario}-{seed}",
        scenario=scenario,
        seed=seed,
        capacity=capacity,
        events=events,
    )
    return decode_trace(trace.to_document())


@dataclass(frozen=True)
class CacheEntry:
    key: str
    inserted_at: int
    last_access: int
    frequency: int

    def to_document(self) -> dict[str, JsonValue]:
        return {
            "key": self.key,
            "inserted_at": self.inserted_at,
            "last_access": self.last_access,
            "frequency": self.frequency,
        }


@dataclass(frozen=True)
class CacheSnapshot:
    sequence: int
    capacity: int
    requested_key: str
    entries: tuple[CacheEntry, ...]
    evictable_keys: tuple[str, ...]
    pinned_keys: tuple[str, ...]

    def to_document(self) -> dict[str, JsonValue]:
        return {
            "schema_version": SNAPSHOT_SCHEMA_VERSION,
            "sequence": self.sequence,
            "capacity": self.capacity,
            "requested_key": self.requested_key,
            "entries": [entry.to_document() for entry in self.entries],
            "evictable_keys": list(self.evictable_keys),
            "pinned_keys": list(self.pinned_keys),
        }

    @property
    def snapshot_id(self) -> str:
        return content_id(self.to_document())


@dataclass(frozen=True)
class PolicyDecision:
    selected_key: str
    semantic_steps: int


PolicySelector = Callable[[CacheSnapshot], PolicyDecision]


def select_strategy(strategy_id: str, snapshot: CacheSnapshot) -> PolicyDecision:
    if strategy_id not in REGISTERED_STRATEGIES:
        raise CacheError(f"unknown strategy {strategy_id!r}")
    if not snapshot.evictable_keys:
        raise CacheError("policy called outside non-empty evictable domain")
    by_key = {entry.key: entry for entry in snapshot.entries}
    entries = [by_key[key] for key in snapshot.evictable_keys]

    if strategy_id == "lru":
        selected = min(
            entries,
            key=lambda entry: (entry.last_access, entry.inserted_at, entry.key),
        )
    elif strategy_id == "fifo":
        selected = min(entries, key=lambda entry: (entry.inserted_at, entry.key))
    else:
        selected = min(
            entries,
            key=lambda entry: (
                entry.frequency,
                entry.last_access,
                entry.inserted_at,
                entry.key,
            ),
        )
    return PolicyDecision(
        selected_key=selected.key,
        semantic_steps=len(entries),
    )


@dataclass(frozen=True)
class CacheObservation:
    sequence: int
    request_key: str
    outcome: str
    snapshot_id: str | None
    candidate_choice: str | None
    applied_choice: str | None
    used_fallback: bool
    violation: str | None
    semantic_steps: int
    resident_keys_after: tuple[str, ...]

    def to_document(self) -> dict[str, JsonValue]:
        return {
            "schema_version": OBSERVATION_SCHEMA_VERSION,
            "sequence": self.sequence,
            "request_key": self.request_key,
            "outcome": self.outcome,
            "snapshot_id": self.snapshot_id,
            "candidate_choice": self.candidate_choice,
            "applied_choice": self.applied_choice,
            "used_fallback": self.used_fallback,
            "violation": self.violation,
            "semantic_steps": self.semantic_steps,
            "resident_keys_after": list(self.resident_keys_after),
        }


def _parts_per_million(numerator: int, denominator: int) -> int:
    if denominator <= 0:
        raise CacheError("metric denominator must be positive")
    return numerator * 1_000_000 // denominator


def _nearest_rank_percentile(values: list[int], percentile: int) -> int:
    if not values:
        return 0
    ordered = sorted(values)
    rank = (percentile * len(ordered) + 99) // 100
    return ordered[max(0, rank - 1)]


@dataclass(frozen=True)
class CacheMetrics:
    accesses: int
    hits: int
    misses: int
    evictions: int
    blocked_insertions: int
    policy_invocations: int
    candidate_violations: int
    policy_errors: int
    fallbacks: int
    miss_ratio_ppm: int
    invalid_decision_rate_ppm: int
    total_decision_steps: int
    p99_decision_steps: int

    def to_document(self) -> dict[str, JsonValue]:
        return {
            "schema_version": METRICS_SCHEMA_VERSION,
            "accesses": self.accesses,
            "hits": self.hits,
            "misses": self.misses,
            "evictions": self.evictions,
            "blocked_insertions": self.blocked_insertions,
            "policy_invocations": self.policy_invocations,
            "candidate_violations": self.candidate_violations,
            "policy_errors": self.policy_errors,
            "fallbacks": self.fallbacks,
            "miss_ratio_ppm": self.miss_ratio_ppm,
            "invalid_decision_rate_ppm": self.invalid_decision_rate_ppm,
            "total_decision_steps": self.total_decision_steps,
            "p99_decision_steps": self.p99_decision_steps,
        }


@dataclass(frozen=True)
class SimulationResult:
    subject_id: str
    strategy_id: str
    trace_id: str
    metrics: CacheMetrics
    observations: tuple[CacheObservation, ...]
    final_resident_keys: tuple[str, ...]

    def to_document(self) -> dict[str, JsonValue]:
        return {
            "schema_version": SIMULATION_SCHEMA_VERSION,
            "subject_id": self.subject_id,
            "strategy_id": self.strategy_id,
            "trace_id": self.trace_id,
            "metrics": self.metrics.to_document(),
            "observations": [item.to_document() for item in self.observations],
            "final_resident_keys": list(self.final_resident_keys),
        }

    @property
    def result_id(self) -> str:
        return content_id(self.to_document())


def simulate(
    trace: CacheTrace,
    *,
    subject_id: str,
    strategy_id: str,
    selector: PolicySelector,
) -> SimulationResult:
    residents: dict[str, CacheEntry] = {}
    observations: list[CacheObservation] = []
    hits = 0
    misses = 0
    evictions = 0
    blocked_insertions = 0
    policy_invocations = 0
    candidate_violations = 0
    policy_errors = 0
    fallbacks = 0
    decision_costs: list[int] = []

    for event in trace.events:
        if event.key in residents:
            hits += 1
            prior = residents[event.key]
            residents[event.key] = CacheEntry(
                key=prior.key,
                inserted_at=prior.inserted_at,
                last_access=event.sequence,
                frequency=prior.frequency + 1,
            )
            observations.append(
                CacheObservation(
                    sequence=event.sequence,
                    request_key=event.key,
                    outcome="hit",
                    snapshot_id=None,
                    candidate_choice=None,
                    applied_choice=None,
                    used_fallback=False,
                    violation=None,
                    semantic_steps=0,
                    resident_keys_after=tuple(sorted(residents)),
                )
            )
            continue

        misses += 1
        if len(residents) < trace.capacity:
            residents[event.key] = CacheEntry(
                key=event.key,
                inserted_at=event.sequence,
                last_access=event.sequence,
                frequency=1,
            )
            observations.append(
                CacheObservation(
                    sequence=event.sequence,
                    request_key=event.key,
                    outcome="miss_insert",
                    snapshot_id=None,
                    candidate_choice=None,
                    applied_choice=None,
                    used_fallback=False,
                    violation=None,
                    semantic_steps=0,
                    resident_keys_after=tuple(sorted(residents)),
                )
            )
            continue

        pinned = tuple(sorted(set(event.pinned_keys) & residents.keys()))
        evictable = tuple(sorted(residents.keys() - set(pinned)))
        snapshot = CacheSnapshot(
            sequence=event.sequence,
            capacity=trace.capacity,
            requested_key=event.key,
            entries=tuple(residents[key] for key in sorted(residents)),
            evictable_keys=evictable,
            pinned_keys=pinned,
        )

        if not evictable:
            blocked_insertions += 1
            observations.append(
                CacheObservation(
                    sequence=event.sequence,
                    request_key=event.key,
                    outcome="miss_blocked",
                    snapshot_id=snapshot.snapshot_id,
                    candidate_choice=None,
                    applied_choice=None,
                    used_fallback=False,
                    violation=None,
                    semantic_steps=0,
                    resident_keys_after=tuple(sorted(residents)),
                )
            )
            continue

        policy_invocations += 1
        violation: str | None = None
        candidate_choice: str | None = None
        candidate_steps = 0
        try:
            decision = selector(snapshot)
            if not isinstance(decision, PolicyDecision):
                violation = "invalid_output"
            elif (
                not isinstance(decision.selected_key, str)
                or len(decision.selected_key) > 64
                or _KEY_PATTERN.fullmatch(decision.selected_key) is None
            ):
                violation = "invalid_output"
            else:
                candidate_choice = decision.selected_key
            if isinstance(decision, PolicyDecision) and (
                isinstance(decision.semantic_steps, bool)
                or not isinstance(decision.semantic_steps, int)
                or decision.semantic_steps < 0
            ):
                violation = "invalid_cost"
            elif isinstance(decision, PolicyDecision):
                candidate_steps = decision.semantic_steps
        except MemoryError:
            raise
        except Exception:  # candidate-facing failures are converted to evidence
            violation = "policy_error"
            policy_errors += 1

        if violation is None and candidate_choice not in evictable:
            violation = "invalid_victim"
        if violation is None and candidate_choice in pinned:
            violation = "pinned_victim"

        used_fallback = violation is not None
        if used_fallback:
            candidate_violations += 1
            fallbacks += 1
            fallback = select_strategy("lru", snapshot)
            applied_choice = fallback.selected_key
            semantic_steps = candidate_steps + fallback.semantic_steps
        else:
            assert candidate_choice is not None
            applied_choice = candidate_choice
            semantic_steps = candidate_steps

        decision_costs.append(semantic_steps)
        residents.pop(applied_choice)
        residents[event.key] = CacheEntry(
            key=event.key,
            inserted_at=event.sequence,
            last_access=event.sequence,
            frequency=1,
        )
        evictions += 1
        observations.append(
            CacheObservation(
                sequence=event.sequence,
                request_key=event.key,
                outcome="miss_evict",
                snapshot_id=snapshot.snapshot_id,
                candidate_choice=candidate_choice,
                applied_choice=applied_choice,
                used_fallback=used_fallback,
                violation=violation,
                semantic_steps=semantic_steps,
                resident_keys_after=tuple(sorted(residents)),
            )
        )

    accesses = len(trace.events)
    metrics = CacheMetrics(
        accesses=accesses,
        hits=hits,
        misses=misses,
        evictions=evictions,
        blocked_insertions=blocked_insertions,
        policy_invocations=policy_invocations,
        candidate_violations=candidate_violations,
        policy_errors=policy_errors,
        fallbacks=fallbacks,
        miss_ratio_ppm=_parts_per_million(misses, accesses),
        invalid_decision_rate_ppm=(
            _parts_per_million(candidate_violations, policy_invocations)
            if policy_invocations
            else 0
        ),
        total_decision_steps=sum(decision_costs),
        p99_decision_steps=_nearest_rank_percentile(decision_costs, 99),
    )
    return SimulationResult(
        subject_id=subject_id,
        strategy_id=strategy_id,
        trace_id=trace.trace_id,
        metrics=metrics,
        observations=tuple(observations),
        final_resident_keys=tuple(sorted(residents)),
    )


def simulate_artifact(
    artifact: CandidateArtifact,
    trace: CacheTrace,
) -> SimulationResult:
    strategy_id = artifact.program.strategy_id
    return simulate(
        trace,
        subject_id=artifact.artifact_id,
        strategy_id=strategy_id,
        selector=lambda snapshot: select_strategy(strategy_id, snapshot),
    )
