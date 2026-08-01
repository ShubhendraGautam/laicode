"""Partitioned deterministic evaluation and external promotion policy."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping

from .cache import (
    AccessEvent,
    CacheSnapshot,
    CacheTrace,
    PolicyDecision,
    SimulationResult,
    generate_trace,
    select_strategy,
    simulate,
    simulate_artifact,
)
from .canonical import JsonValue, canonical_json_bytes, content_id
from .contracts import ValidatedContract
from .kernel import CandidateArtifact


EVIDENCE_CATALOG_SCHEMA_VERSION = "CacheEvidenceCatalogV0"
PARTITION_EVALUATION_SCHEMA_VERSION = "CachePartitionEvaluationV0"
EVALUATION_METRICS_SCHEMA_VERSION = "CacheEvaluationMetricsV0"
PROMOTION_DECISION_SCHEMA_VERSION = "CachePromotionDecisionV0"
AUDIT_REPORT_SCHEMA_VERSION = "CacheAuditReportV0"
PROMOTION_RULE_VERSION = "CacheConstrainedPromotionV0"
EVALUATOR_META_REPORT_SCHEMA_VERSION = "EvaluatorMetaTestReportV0"
EVALUATOR_META_SUITE_VERSION = "CacheEvaluatorMetaSuiteV0"

SEARCH = "search"
OPERATIONAL_HOLDOUT = "operational_holdout"
RESEARCH_AUDIT = "research_audit"
PROSPECTIVE = "prospective"
HISTORICAL_REGRESSION = "historical_regression"
PARTITIONS = (
    SEARCH,
    OPERATIONAL_HOLDOUT,
    RESEARCH_AUDIT,
    PROSPECTIVE,
    HISTORICAL_REGRESSION,
)


class EvaluationError(ValueError):
    """Raised when evidence or promotion inputs violate the frozen protocol."""


@dataclass(frozen=True)
class EvaluatorMetaTestReport:
    checks: tuple[tuple[str, bool], ...]
    evidence_result_ids: tuple[str, ...]
    evaluator_queries: int

    @property
    def passed(self) -> bool:
        return all(passed for _, passed in self.checks)

    def to_document(self) -> dict[str, JsonValue]:
        return {
            "schema_version": EVALUATOR_META_REPORT_SCHEMA_VERSION,
            "suite_version": EVALUATOR_META_SUITE_VERSION,
            "passed": self.passed,
            "checks": [
                {"id": name, "passed": passed} for name, passed in self.checks
            ],
            "evidence_result_ids": list(self.evidence_result_ids),
            "evaluator_queries": self.evaluator_queries,
        }

    @property
    def report_id(self) -> str:
        return content_id(self.to_document())


def run_evaluator_meta_tests() -> EvaluatorMetaTestReport:
    scan = generate_trace("scan_resistance", 101, event_count=128)
    shift = generate_trace("recency_shift", 103, event_count=128)

    def run(trace: CacheTrace, strategy: str) -> SimulationResult:
        return simulate(
            trace,
            subject_id=f"meta-{strategy}",
            strategy_id=strategy,
            selector=lambda snapshot: select_strategy(strategy, snapshot),
        )

    lru_scan_first = run(scan, "lru")
    lru_scan_second = run(scan, "lru")
    lfu_scan = run(scan, "lfu")
    lru_shift = run(shift, "lru")
    lfu_shift = run(shift, "lfu")

    shield_trace = CacheTrace(
        name="meta-shield",
        scenario="mixed_bursts",
        seed=0,
        capacity=2,
        events=(
            AccessEvent(0, "a"),
            AccessEvent(1, "b"),
            AccessEvent(2, "c", ("a",)),
        ),
    )
    invalid = simulate(
        shield_trace,
        subject_id="meta-invalid",
        strategy_id="meta-invalid",
        selector=lambda _: PolicyDecision("a", 1),
    )

    def crash(_: CacheSnapshot) -> PolicyDecision:
        raise RuntimeError("expected meta-test crash")

    crashing = simulate(
        shield_trace,
        subject_id="meta-crash",
        strategy_id="meta-crash",
        selector=crash,
    )
    all_pinned_trace = CacheTrace(
        name="meta-all-pinned",
        scenario="mixed_bursts",
        seed=0,
        capacity=2,
        events=(
            AccessEvent(0, "a"),
            AccessEvent(1, "b"),
            AccessEvent(2, "c", ("a", "b")),
        ),
    )
    all_pinned = simulate(
        all_pinned_trace,
        subject_id="meta-domain",
        strategy_id="meta-domain",
        selector=lambda _: PolicyDecision("a", 1),
    )
    results = (
        lru_scan_first,
        lru_scan_second,
        lfu_scan,
        lru_shift,
        lfu_shift,
        invalid,
        crashing,
        all_pinned,
    )
    checks = (
        ("exact_replay", lru_scan_first == lru_scan_second),
        (
            "known_scan_improvement_direction",
            lfu_scan.metrics.miss_ratio_ppm < lru_scan_first.metrics.miss_ratio_ppm,
        ),
        (
            "known_shift_regression_direction",
            lfu_shift.metrics.miss_ratio_ppm > lru_shift.metrics.miss_ratio_ppm,
        ),
        (
            "invalid_output_shielded",
            invalid.metrics.candidate_violations == 1
            and invalid.metrics.fallbacks == 1
            and "a" in invalid.final_resident_keys,
        ),
        (
            "policy_error_shielded",
            crashing.metrics.policy_errors == 1
            and crashing.metrics.fallbacks == 1,
        ),
        (
            "empty_domain_not_invoked",
            all_pinned.metrics.blocked_insertions == 1
            and all_pinned.metrics.policy_invocations == 0,
        ),
        (
            "metric_denominators_complete",
            all(
                result.metrics.hits + result.metrics.misses
                == result.metrics.accesses
                for result in results
            ),
        ),
        (
            "no_unshielded_test_violation",
            invalid.observations[-1].applied_choice == "b",
        ),
    )
    report = EvaluatorMetaTestReport(
        checks=checks,
        evidence_result_ids=tuple(result.result_id for result in results),
        evaluator_queries=len(results),
    )
    if not report.passed:
        failed = ", ".join(name for name, passed in checks if not passed)
        raise EvaluationError(f"evaluator meta-suite failed: {failed}")
    return report


@dataclass(frozen=True)
class TraceSpec:
    partition: str
    scenario: str
    seed: int
    event_count: int = 128
    capacity: int = 8

    def to_document(self) -> dict[str, JsonValue]:
        return {
            "partition": self.partition,
            "scenario": self.scenario,
            "seed": self.seed,
            "event_count": self.event_count,
            "capacity": self.capacity,
        }


DEFAULT_TRACE_SPECS = (
    TraceSpec(SEARCH, "scan_resistance", 11),
    TraceSpec(SEARCH, "scan_resistance", 17),
    TraceSpec(OPERATIONAL_HOLDOUT, "scan_resistance", 23),
    TraceSpec(OPERATIONAL_HOLDOUT, "scan_resistance", 29),
    TraceSpec(HISTORICAL_REGRESSION, "mixed_bursts", 31),
    TraceSpec(HISTORICAL_REGRESSION, "mixed_bursts", 37),
    TraceSpec(PROSPECTIVE, "recency_shift", 41),
    TraceSpec(PROSPECTIVE, "recency_shift", 43),
    TraceSpec(RESEARCH_AUDIT, "scan_resistance", 47),
    TraceSpec(RESEARCH_AUDIT, "scan_resistance", 53),
)


@dataclass(frozen=True)
class EvaluationMetrics:
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

    @property
    def hard_constraints_pass(self) -> bool:
        return self.candidate_violations == 0 and self.policy_errors == 0

    def to_document(self) -> dict[str, JsonValue]:
        return {
            "schema_version": EVALUATION_METRICS_SCHEMA_VERSION,
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
            "hard_constraints_pass": self.hard_constraints_pass,
        }


def _ppm(numerator: int, denominator: int) -> int:
    if denominator <= 0:
        raise EvaluationError("metric denominator must be positive")
    return numerator * 1_000_000 // denominator


def _p99(values: list[int]) -> int:
    if not values:
        return 0
    ordered = sorted(values)
    rank = (99 * len(ordered) + 99) // 100
    return ordered[max(0, rank - 1)]


def aggregate_results(results: Iterable[SimulationResult]) -> EvaluationMetrics:
    items = tuple(results)
    if not items:
        raise EvaluationError("cannot aggregate an empty result set")
    accesses = sum(item.metrics.accesses for item in items)
    policy_invocations = sum(item.metrics.policy_invocations for item in items)
    decision_steps = [
        observation.semantic_steps
        for item in items
        for observation in item.observations
        if observation.outcome == "miss_evict"
    ]
    violations = sum(item.metrics.candidate_violations for item in items)
    return EvaluationMetrics(
        accesses=accesses,
        hits=sum(item.metrics.hits for item in items),
        misses=sum(item.metrics.misses for item in items),
        evictions=sum(item.metrics.evictions for item in items),
        blocked_insertions=sum(item.metrics.blocked_insertions for item in items),
        policy_invocations=policy_invocations,
        candidate_violations=violations,
        policy_errors=sum(item.metrics.policy_errors for item in items),
        fallbacks=sum(item.metrics.fallbacks for item in items),
        miss_ratio_ppm=_ppm(sum(item.metrics.misses for item in items), accesses),
        invalid_decision_rate_ppm=(
            _ppm(violations, policy_invocations) if policy_invocations else 0
        ),
        total_decision_steps=sum(item.metrics.total_decision_steps for item in items),
        p99_decision_steps=_p99(decision_steps),
    )


@dataclass(frozen=True)
class PartitionEvaluation:
    partition: str
    artifact_id: str
    strategy_id: str
    trace_ids: tuple[str, ...]
    results: tuple[SimulationResult, ...]
    metrics: EvaluationMetrics

    def to_document(self, *, include_observations: bool = True) -> dict[str, JsonValue]:
        return {
            "schema_version": PARTITION_EVALUATION_SCHEMA_VERSION,
            "partition": self.partition,
            "artifact_id": self.artifact_id,
            "strategy_id": self.strategy_id,
            "trace_ids": list(self.trace_ids),
            "result_ids": [result.result_id for result in self.results],
            "metrics": self.metrics.to_document(),
            "results": (
                [result.to_document() for result in self.results]
                if include_observations
                else []
            ),
            "observations_included": include_observations,
        }

    @property
    def evaluation_id(self) -> str:
        return content_id(self.to_document())

    def aggregate_disclosure(self) -> dict[str, JsonValue]:
        document = self.to_document(include_observations=False)
        document["evaluation_id"] = self.evaluation_id
        return document


class EvidenceCatalog:
    """Trusted partition manager for one deterministic exploratory study."""

    def __init__(self, specs: Iterable[TraceSpec] = DEFAULT_TRACE_SPECS) -> None:
        grouped: dict[str, list[CacheTrace]] = {name: [] for name in PARTITIONS}
        spec_items = tuple(specs)
        for spec in spec_items:
            if spec.partition not in grouped:
                raise EvaluationError(f"unknown evidence partition {spec.partition!r}")
            grouped[spec.partition].append(
                generate_trace(
                    spec.scenario,
                    spec.seed,
                    event_count=spec.event_count,
                    capacity=spec.capacity,
                    name=f"{spec.partition}-{spec.scenario}-{spec.seed}",
                )
            )
        for partition, traces in grouped.items():
            if not traces:
                raise EvaluationError(f"partition {partition!r} has no traces")
        all_ids = [trace.trace_id for traces in grouped.values() for trace in traces]
        if len(all_ids) != len(set(all_ids)):
            raise EvaluationError("evidence partitions contain duplicate trace identities")
        self._specs = spec_items
        self._traces = {key: tuple(value) for key, value in grouped.items()}
        self._audit_consumed = False

    def to_document(self, *, disclose_audit_specs: bool) -> dict[str, JsonValue]:
        partitions: dict[str, JsonValue] = {}
        for partition in PARTITIONS:
            traces = self._traces[partition]
            if partition == RESEARCH_AUDIT and not disclose_audit_specs:
                partitions[partition] = {
                    "count": len(traces),
                    "trace_ids": [trace.trace_id for trace in traces],
                    "specs_disclosed": False,
                }
            else:
                partition_specs = [
                    spec.to_document()
                    for spec in self._specs
                    if spec.partition == partition
                ]
                partitions[partition] = {
                    "count": len(traces),
                    "trace_ids": [trace.trace_id for trace in traces],
                    "specs": partition_specs,
                    "specs_disclosed": True,
                }
        return {
            "schema_version": EVIDENCE_CATALOG_SCHEMA_VERSION,
            "partitions": partitions,
        }

    @property
    def prefreeze_catalog_id(self) -> str:
        return content_id(self.to_document(disclose_audit_specs=False))

    def search_traces(self) -> tuple[CacheTrace, ...]:
        return self._traces[SEARCH]

    def _evaluate(self, artifact: CandidateArtifact, partition: str) -> PartitionEvaluation:
        traces = self._traces[partition]
        results = tuple(simulate_artifact(artifact, trace) for trace in traces)
        return PartitionEvaluation(
            partition=partition,
            artifact_id=artifact.artifact_id,
            strategy_id=artifact.program.strategy_id,
            trace_ids=tuple(trace.trace_id for trace in traces),
            results=results,
            metrics=aggregate_results(results),
        )

    def evaluate_search(self, artifact: CandidateArtifact) -> PartitionEvaluation:
        return self._evaluate(artifact, SEARCH)

    def evaluate_operational(
        self,
        artifact: CandidateArtifact,
    ) -> PartitionEvaluation:
        return self._evaluate(artifact, OPERATIONAL_HOLDOUT)

    def evaluate_historical(
        self,
        artifact: CandidateArtifact,
    ) -> PartitionEvaluation:
        return self._evaluate(artifact, HISTORICAL_REGRESSION)

    def evaluate_prospective(
        self,
        artifact: CandidateArtifact,
        *,
        frozen_decision_id: str,
    ) -> PartitionEvaluation:
        if not frozen_decision_id.startswith("sha256:"):
            raise EvaluationError("prospective evaluation requires a frozen decision ID")
        return self._evaluate(artifact, PROSPECTIVE)

    def evaluate_research_audit(
        self,
        artifacts: Iterable[CandidateArtifact],
        *,
        frozen_decision_id: str,
    ) -> "AuditReport":
        if self._audit_consumed:
            raise EvaluationError("research audit has already been consumed")
        if not frozen_decision_id.startswith("sha256:"):
            raise EvaluationError("research audit requires a frozen decision ID")
        self._audit_consumed = True
        evaluations = tuple(
            self._evaluate(artifact, RESEARCH_AUDIT) for artifact in artifacts
        )
        return AuditReport(
            frozen_decision_id=frozen_decision_id,
            evaluations=evaluations,
        )

    def archive_traces_after_freeze(self) -> Mapping[str, tuple[CacheTrace, ...]]:
        if not self._audit_consumed:
            raise EvaluationError("audit traces cannot be archived before audit consumption")
        return dict(self._traces)


@dataclass(frozen=True)
class PromotionPolicy:
    practical_delta_ppm: int
    protected_tolerance_ppm: int
    historical_regression_tolerance_ppm: int
    minimum_events: int
    maximum_comparisons: int
    epoch_error_budget_ppm: int

    @classmethod
    def from_contract(cls, contract: ValidatedContract) -> "PromotionPolicy":
        document = contract.to_dict()
        objectives = document["objectives"]
        comparison = document["comparison"]
        assert isinstance(objectives, list) and isinstance(comparison, dict)
        primary = [
            item
            for item in objectives
            if isinstance(item, dict) and item["role"] == "primary"
        ]
        protected = [
            item
            for item in objectives
            if isinstance(item, dict) and item["role"] == "protected"
        ]
        if len(primary) != 1 or primary[0]["id"] != "miss_ratio":
            raise EvaluationError("prototype requires miss_ratio as the primary objective")
        if len(protected) != 1 or protected[0]["id"] != "decision_cost":
            raise EvaluationError("prototype requires protected decision_cost")
        return cls(
            practical_delta_ppm=int(primary[0]["practical_delta_ppm"]),
            protected_tolerance_ppm=int(
                protected[0]["noninferiority_tolerance_ppm"]
            ),
            historical_regression_tolerance_ppm=int(
                comparison["historical_regression_tolerance_ppm"]
            ),
            minimum_events=int(comparison["minimum_events_per_partition"]),
            maximum_comparisons=int(comparison["maximum_comparisons"]),
            epoch_error_budget_ppm=int(comparison["epoch_error_budget_ppm"]),
        )

    def to_document(self) -> dict[str, JsonValue]:
        return {
            "rule_version": PROMOTION_RULE_VERSION,
            "practical_delta_ppm": self.practical_delta_ppm,
            "protected_tolerance_ppm": self.protected_tolerance_ppm,
            "historical_regression_tolerance_ppm": (
                self.historical_regression_tolerance_ppm
            ),
            "minimum_events": self.minimum_events,
            "maximum_comparisons": self.maximum_comparisons,
            "epoch_error_budget_ppm": self.epoch_error_budget_ppm,
            "uncertainty_method": "deterministic_exact_exploratory",
        }


def _relative_regression_ppm(champion: int, challenger: int) -> int:
    if challenger <= champion:
        return 0
    if champion == 0:
        return 1_000_000
    return (challenger - champion) * 1_000_000 // champion


@dataclass(frozen=True)
class PromotionDecision:
    champion_artifact_id: str
    challenger_artifact_id: str
    operational_champion_evaluation_id: str
    operational_challenger_evaluation_id: str
    historical_champion_evaluation_id: str
    historical_challenger_evaluation_id: str
    outcome: str
    reasons: tuple[str, ...]
    primary_improvement_ppm: int
    protected_regression_ppm: int
    historical_regression_ppm: int
    policy: PromotionPolicy

    def to_document(self) -> dict[str, JsonValue]:
        return {
            "schema_version": PROMOTION_DECISION_SCHEMA_VERSION,
            "rule_version": PROMOTION_RULE_VERSION,
            "champion_artifact_id": self.champion_artifact_id,
            "challenger_artifact_id": self.challenger_artifact_id,
            "operational_champion_evaluation_id": (
                self.operational_champion_evaluation_id
            ),
            "operational_challenger_evaluation_id": (
                self.operational_challenger_evaluation_id
            ),
            "historical_champion_evaluation_id": (
                self.historical_champion_evaluation_id
            ),
            "historical_challenger_evaluation_id": (
                self.historical_challenger_evaluation_id
            ),
            "outcome": self.outcome,
            "reasons": list(self.reasons),
            "primary_improvement_ppm": self.primary_improvement_ppm,
            "protected_regression_ppm": self.protected_regression_ppm,
            "historical_regression_ppm": self.historical_regression_ppm,
            "policy": self.policy.to_document(),
            "research_audit_evaluation_ids": [],
        }

    @property
    def decision_id(self) -> str:
        return content_id(self.to_document())


def compare_for_promotion(
    *,
    champion_operational: PartitionEvaluation,
    challenger_operational: PartitionEvaluation,
    champion_historical: PartitionEvaluation,
    challenger_historical: PartitionEvaluation,
    policy: PromotionPolicy,
) -> PromotionDecision:
    if champion_operational.partition != OPERATIONAL_HOLDOUT:
        raise EvaluationError("champion operational evidence has wrong partition")
    if challenger_operational.partition != OPERATIONAL_HOLDOUT:
        raise EvaluationError("challenger operational evidence has wrong partition")
    if champion_historical.partition != HISTORICAL_REGRESSION:
        raise EvaluationError("champion historical evidence has wrong partition")
    if challenger_historical.partition != HISTORICAL_REGRESSION:
        raise EvaluationError("challenger historical evidence has wrong partition")
    if champion_operational.artifact_id != champion_historical.artifact_id:
        raise EvaluationError("champion evidence refers to different artifacts")
    if challenger_operational.artifact_id != challenger_historical.artifact_id:
        raise EvaluationError("challenger evidence refers to different artifacts")

    primary_improvement = (
        champion_operational.metrics.miss_ratio_ppm
        - challenger_operational.metrics.miss_ratio_ppm
    )
    protected_regression = _relative_regression_ppm(
        champion_operational.metrics.p99_decision_steps,
        challenger_operational.metrics.p99_decision_steps,
    )
    historical_regression = (
        challenger_historical.metrics.miss_ratio_ppm
        - champion_historical.metrics.miss_ratio_ppm
    )

    reasons: list[str] = []
    if not challenger_operational.metrics.hard_constraints_pass:
        reasons.append("operational_hard_constraint_failure")
    if not challenger_historical.metrics.hard_constraints_pass:
        reasons.append("historical_hard_constraint_failure")
    if challenger_operational.metrics.accesses < policy.minimum_events:
        reasons.append("insufficient_operational_events")
    if challenger_historical.metrics.accesses < policy.minimum_events:
        reasons.append("insufficient_historical_events")
    if primary_improvement < policy.practical_delta_ppm:
        reasons.append("primary_effect_below_threshold")
    if protected_regression > policy.protected_tolerance_ppm:
        reasons.append("protected_metric_regression")
    if historical_regression > policy.historical_regression_tolerance_ppm:
        reasons.append("historical_regression")

    outcome = "eligible" if not reasons else "rejected"
    if not reasons:
        reasons.append("all_registered_gates_passed")
    return PromotionDecision(
        champion_artifact_id=champion_operational.artifact_id,
        challenger_artifact_id=challenger_operational.artifact_id,
        operational_champion_evaluation_id=champion_operational.evaluation_id,
        operational_challenger_evaluation_id=challenger_operational.evaluation_id,
        historical_champion_evaluation_id=champion_historical.evaluation_id,
        historical_challenger_evaluation_id=challenger_historical.evaluation_id,
        outcome=outcome,
        reasons=tuple(reasons),
        primary_improvement_ppm=primary_improvement,
        protected_regression_ppm=protected_regression,
        historical_regression_ppm=historical_regression,
        policy=policy,
    )


@dataclass(frozen=True)
class AuditReport:
    frozen_decision_id: str
    evaluations: tuple[PartitionEvaluation, ...]

    def to_document(self) -> dict[str, JsonValue]:
        return {
            "schema_version": AUDIT_REPORT_SCHEMA_VERSION,
            "frozen_decision_id": self.frozen_decision_id,
            "evaluations": [item.to_document() for item in self.evaluations],
        }

    @property
    def report_id(self) -> str:
        return content_id(self.to_document())


def canonical_evaluation_bytes(evaluation: PartitionEvaluation) -> bytes:
    return canonical_json_bytes(evaluation.to_document())
