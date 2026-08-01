"""End-to-end exploratory D0 prototype runner and full decision replay."""

from __future__ import annotations

import hashlib
import platform
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Mapping

from .canonical import (
    CanonicalizationError,
    JsonValue,
    canonical_json_bytes,
    content_id,
    load_json_strict,
)
from .contracts import ValidatedContract, load_contract
from .evaluation import (
    DEFAULT_TRACE_SPECS,
    AuditReport,
    EvidenceCatalog,
    EvaluatorMetaTestReport,
    PartitionEvaluation,
    PromotionDecision,
    PromotionPolicy,
    compare_for_promotion,
    run_evaluator_meta_tests,
)
from .kernel import (
    ACTION_SCHEMA_VERSION,
    KERNEL_VERSION,
    PROGRAM_SCHEMA_VERSION,
    CandidateArtifact,
    compile_complete_program,
)
from .provenance import (
    AppendOnlyLedger,
    CandidateManifest,
    ProvenanceError,
    baseline_manifest,
    enumerated_manifest,
)


EXPERIMENT_MANIFEST_SCHEMA_VERSION = "CacheExperimentManifestV0"
IMPLEMENTATION_MANIFEST_SCHEMA_VERSION = "ImplementationManifestV0"
OFFLINE_DECISION_SCHEMA_VERSION = "OfflineSelectionDecisionV0"
RUN_REPORT_SCHEMA_VERSION = "PrototypeRunReportV0"
RUN_REPORT_RECORD_SCHEMA_VERSION = "PrototypeRunReportRecordV0"
REPLAY_REPORT_SCHEMA_VERSION = "PrototypeReplayReportV0"


class PrototypeError(ValueError):
    """Raised when a run cannot satisfy the frozen D0 prototype protocol."""


def _enforce_contract_expiry(contract: ValidatedContract) -> None:
    value = contract.to_dict()["expires_at"]
    assert isinstance(value, str)
    expires_at = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(
        tzinfo=timezone.utc
    )
    if datetime.now(timezone.utc) >= expires_at:
        raise PrototypeError(f"evolution contract expired at {value}")


def _safe_name(identifier: str) -> str:
    if not identifier.startswith("sha256:"):
        raise PrototypeError(f"not a content ID: {identifier!r}")
    return identifier.removeprefix("sha256:") + ".json"


def _write_document(path: Path, document: JsonValue) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = canonical_json_bytes(document) + b"\n"
    with path.open("xb") as handle:
        handle.write(data)
        handle.flush()


def _read_document(path: Path) -> JsonValue:
    try:
        return load_json_strict(path.read_bytes())
    except (OSError, CanonicalizationError) as error:
        raise PrototypeError(f"cannot read canonical document {path}: {error}") from error


def implementation_manifest() -> dict[str, JsonValue]:
    root = Path(__file__).resolve().parents[1]
    paths = sorted((root / "laicode").glob("*.py")) + sorted(
        (root / "schemas").glob("*.schema.json")
    )
    files: dict[str, JsonValue] = {}
    for path in paths:
        relative = path.relative_to(root).as_posix()
        files[relative] = "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
    return {
        "schema_version": IMPLEMENTATION_MANIFEST_SCHEMA_VERSION,
        "runtime": "python",
        "runtime_version": platform.python_version(),
        "dependency_profile": "stdlib_only",
        "files": files,
    }


@dataclass(frozen=True)
class ExperimentManifest:
    contract_id: str
    evidence_catalog_id: str
    archived_evidence_catalog_id: str
    implementation_id: str
    candidate_ids: tuple[str, ...]
    artifact_ids: tuple[str, ...]
    promotion_policy: PromotionPolicy

    def to_document(self) -> dict[str, JsonValue]:
        return {
            "schema_version": EXPERIMENT_MANIFEST_SCHEMA_VERSION,
            "experiment_name": "cache-e1-exploratory-smoke-v0",
            "title": "Deterministic external selection among reviewed cache strategies",
            "study_mode": "exploratory",
            "research_question": (
                "Can an external D0 supervisor select a reviewed cache strategy "
                "under temporal workload drift with replayable evidence?"
            ),
            "hypothesis": (
                "LFU reduces miss ratio on scan-resistant future traces relative "
                "to the original LRU baseline without hard-constraint or "
                "deterministic decision-cost regression."
            ),
            "falsification_condition": (
                "No challenger passes every registered gate, any invalid victim "
                "escapes the shield, audit evidence enters selection, or replay "
                "does not reproduce the exact decision."
            ),
            "repository_revision": "working-tree-content-addressed",
            "implementation_id": self.implementation_id,
            "contract_id": self.contract_id,
            "evidence_catalog_id": self.evidence_catalog_id,
            "archived_evidence_catalog_id": self.archived_evidence_catalog_id,
            "stage": "E1",
            "system_profile": {
                "r": "R2",
                "m": "M1",
                "g": "G1",
                "l": "L0",
                "d": "D0",
                "f": "F0",
            },
            "maximum_authorized_ceiling": {"m": "M1", "d": "D0"},
            "kernel_version": KERNEL_VERSION,
            "program_schema": PROGRAM_SCHEMA_VERSION,
            "action_schema": ACTION_SCHEMA_VERSION,
            "generator": {
                "id": "strategy_enumerator",
                "version": "v0",
                "strategy_ids": ["fifo", "lfu", "lru"],
                "learner_update": "none",
            },
            "candidate_ids": list(self.candidate_ids),
            "artifact_ids": list(self.artifact_ids),
            "partition_method": "identity_separated_temporal_scenarios",
            "trace_specs": [spec.to_document() for spec in DEFAULT_TRACE_SPECS],
            "primary_outcome": {
                "id": "miss_ratio",
                "unit": "parts_per_million",
                "direction": "minimize",
            },
            "protected_outcome": {
                "id": "decision_cost",
                "unit": "semantic_steps",
                "statistic": "p99_nearest_rank",
                "direction": "minimize",
            },
            "hard_constraints": [
                "candidate_violations_equal_zero",
                "policy_errors_equal_zero",
            ],
            "promotion_policy": self.promotion_policy.to_document(),
            "baselines": ["original_lru", "fifo", "lfu"],
            "comparison_budget": self.promotion_policy.maximum_comparisons,
            "audit_use": "post_decision_report_only",
            "analysis_command": "python3 -m laicode replay-prototype RUN_DIR",
            "registered_at": "2026-08-01T00:00:00Z",
        }

    @property
    def manifest_id(self) -> str:
        return content_id(self.to_document())


@dataclass(frozen=True)
class OfflineSelectionDecision:
    experiment_manifest_id: str
    original_candidate_id: str
    original_artifact_id: str
    comparison_decision_ids: tuple[str, ...]
    search_ranking_artifact_ids: tuple[str, ...]
    selected_candidate_id: str
    selected_artifact_id: str
    selected_strategy_id: str
    outcome: str

    def to_document(self) -> dict[str, JsonValue]:
        return {
            "schema_version": OFFLINE_DECISION_SCHEMA_VERSION,
            "experiment_manifest_id": self.experiment_manifest_id,
            "original_candidate_id": self.original_candidate_id,
            "original_artifact_id": self.original_artifact_id,
            "comparison_decision_ids": list(self.comparison_decision_ids),
            "search_ranking_artifact_ids": list(self.search_ranking_artifact_ids),
            "selected_candidate_id": self.selected_candidate_id,
            "selected_artifact_id": self.selected_artifact_id,
            "selected_strategy_id": self.selected_strategy_id,
            "outcome": self.outcome,
            "selection_rule": (
                "all_gates_then_largest_primary_improvement_then_lower_risk_then_id"
            ),
            "deployment_authority": "D0_offline_only",
            "research_audit_evaluation_ids": [],
        }

    @property
    def decision_id(self) -> str:
        return content_id(self.to_document())


class BudgetTracker:
    def __init__(self, contract: ValidatedContract) -> None:
        document = contract.to_dict()
        budgets = document["budgets"]
        mutation = document["mutation"]
        comparison = document["comparison"]
        assert (
            isinstance(budgets, dict)
            and isinstance(mutation, dict)
            and isinstance(comparison, dict)
        )
        per_candidate = budgets["per_candidate"]
        per_epoch = budgets["per_epoch"]
        assert isinstance(per_candidate, dict) and isinstance(per_epoch, dict)
        self._candidate_limit = min(
            int(per_epoch["candidates"]),
            int(comparison["candidate_churn_limit"]),
        )
        self._per_candidate_query_limit = int(per_candidate["evaluator_queries"])
        self._epoch_query_limit = int(per_epoch["evaluator_queries"])
        self._artifact_byte_limit = int(mutation["max_artifact_bytes"])
        self._candidate_ids: set[str] = set()
        self._artifact_bytes: dict[str, int] = {}
        self._queries: dict[str, int] = {}
        self._meta_queries = 0

    def register_candidate(
        self,
        candidate: CandidateManifest,
        artifact: CandidateArtifact,
    ) -> None:
        if candidate.candidate_id in self._candidate_ids:
            raise PrototypeError(f"duplicate candidate {candidate.candidate_id}")
        if candidate.artifact_id != artifact.artifact_id:
            raise PrototypeError("candidate manifest and artifact identity differ")
        if len(artifact.canonical_bytes) > self._artifact_byte_limit:
            raise PrototypeError("candidate artifact exceeds contract size limit")
        if len(self._candidate_ids) + 1 > self._candidate_limit:
            raise PrototypeError("candidate budget exhausted")
        self._candidate_ids.add(candidate.candidate_id)
        self._artifact_bytes[artifact.artifact_id] = len(artifact.canonical_bytes)
        self._queries.setdefault(artifact.artifact_id, 0)

    def charge(self, evaluation: PartitionEvaluation) -> None:
        amount = len(evaluation.trace_ids)
        current = self._queries.get(evaluation.artifact_id)
        if current is None:
            raise PrototypeError("evaluation refers to an unregistered artifact")
        if current + amount > self._per_candidate_query_limit:
            raise PrototypeError("per-candidate evaluator-query budget exhausted")
        if (
            sum(self._queries.values()) + self._meta_queries + amount
            > self._epoch_query_limit
        ):
            raise PrototypeError("per-epoch evaluator-query budget exhausted")
        self._queries[evaluation.artifact_id] = current + amount

    def charge_meta_evaluation(self, queries: int) -> None:
        if queries < 0:
            raise PrototypeError("meta-evaluator query charge cannot be negative")
        if sum(self._queries.values()) + self._meta_queries + queries > self._epoch_query_limit:
            raise PrototypeError("per-epoch evaluator-query budget exhausted")
        self._meta_queries += queries

    def to_document(self) -> dict[str, JsonValue]:
        return {
            "candidate_count": len(self._candidate_ids),
            "candidate_limit": self._candidate_limit,
            "evaluator_queries_total": sum(self._queries.values()) + self._meta_queries,
            "meta_evaluator_queries": self._meta_queries,
            "evaluator_query_limit": self._epoch_query_limit,
            "evaluator_queries_by_artifact": dict(sorted(self._queries.items())),
            "artifact_bytes_by_id": dict(sorted(self._artifact_bytes.items())),
            "network_bytes": 0,
            "model_tokens": 0,
            "money_microusd": 0,
            "wall_and_cpu_budget_enforcement": "not_yet_isolated_at_D0",
        }


@dataclass(frozen=True)
class PrototypeRunReport:
    implementation_id: str
    contract_id: str
    experiment_manifest_id: str
    evidence_catalog_id: str
    archived_evidence_catalog_id: str
    evaluator_meta_report_id: str
    offline_decision_id: str
    selected_candidate_id: str
    selected_artifact_id: str
    selected_strategy_id: str
    comparison_decision_ids: tuple[str, ...]
    prospective_evaluation_ids: tuple[str, ...]
    audit_report_id: str
    audit_evaluation_ids: tuple[str, ...]
    all_candidate_ids: tuple[str, ...]
    all_artifact_ids: tuple[str, ...]
    all_trace_ids: tuple[str, ...]
    all_evaluation_ids: tuple[str, ...]
    ledger_id: str
    final_event_id: str
    budget: Mapping[str, JsonValue]
    audit_primary_improvement_ppm: int
    prospective_primary_improvement_ppm: int
    archived_payload_bytes: int

    def to_document(self) -> dict[str, JsonValue]:
        return {
            "schema_version": RUN_REPORT_SCHEMA_VERSION,
            "status": "complete",
            "claim_level": "exploratory_D0_workflow_only",
            "implementation_id": self.implementation_id,
            "contract_id": self.contract_id,
            "experiment_manifest_id": self.experiment_manifest_id,
            "evidence_catalog_id": self.evidence_catalog_id,
            "archived_evidence_catalog_id": self.archived_evidence_catalog_id,
            "evaluator_meta_report_id": self.evaluator_meta_report_id,
            "offline_decision_id": self.offline_decision_id,
            "selected_candidate_id": self.selected_candidate_id,
            "selected_artifact_id": self.selected_artifact_id,
            "selected_strategy_id": self.selected_strategy_id,
            "comparison_decision_ids": list(self.comparison_decision_ids),
            "prospective_evaluation_ids": list(self.prospective_evaluation_ids),
            "audit_report_id": self.audit_report_id,
            "audit_evaluation_ids": list(self.audit_evaluation_ids),
            "inventory": {
                "candidate_ids": list(self.all_candidate_ids),
                "artifact_ids": list(self.all_artifact_ids),
                "trace_ids": list(self.all_trace_ids),
                "evaluation_ids": list(self.all_evaluation_ids),
            },
            "ledger_id": self.ledger_id,
            "final_event_id": self.final_event_id,
            "budget": dict(self.budget),
            "audit_primary_improvement_ppm": self.audit_primary_improvement_ppm,
            "prospective_primary_improvement_ppm": (
                self.prospective_primary_improvement_ppm
            ),
            "archived_payload_bytes_before_report": self.archived_payload_bytes,
            "deployment_performed": False,
            "research_audit_used_for_selection": False,
            "limitations": [
                "synthetic_traces_only",
                "exploratory_not_confirmatory",
                "no_process_isolation_or_containment_claim",
                "no_wall_clock_performance_promotion_metric",
                "no_candidate_private_state",
            ],
        }

    @property
    def report_id(self) -> str:
        return content_id(self.to_document())

    def to_record(self) -> dict[str, JsonValue]:
        return {
            "schema_version": RUN_REPORT_RECORD_SCHEMA_VERSION,
            "report_id": self.report_id,
            "report": self.to_document(),
        }


def _compile_strategies(
    contract: ValidatedContract,
) -> dict[str, CandidateArtifact]:
    document = contract.to_dict()
    mutation = document["mutation"]
    assert isinstance(mutation, dict)
    allowed = mutation["allowed_strategy_ids"]
    assert isinstance(allowed, list)
    return {
        str(strategy): compile_complete_program(
            contract,
            {
                "schema_version": PROGRAM_SCHEMA_VERSION,
                "op": "select_strategy",
                "strategy_id": strategy,
            },
        )
        for strategy in allowed
    }


def _select_offline(
    *,
    experiment_manifest_id: str,
    baseline: CandidateManifest,
    candidates: Mapping[str, CandidateManifest],
    search_evaluations: Mapping[str, PartitionEvaluation],
    comparisons: Iterable[PromotionDecision],
) -> OfflineSelectionDecision:
    comparison_items = tuple(comparisons)
    eligible = [item for item in comparison_items if item.outcome == "eligible"]
    if eligible:
        selected_comparison = sorted(
            eligible,
            key=lambda item: (
                -item.primary_improvement_ppm,
                item.protected_regression_ppm,
                item.challenger_artifact_id,
            ),
        )[0]
        selected_manifest = candidates[selected_comparison.challenger_artifact_id]
        outcome = "challenger_selected_offline"
    else:
        selected_manifest = baseline
        outcome = "baseline_retained_offline"
    ranking = tuple(
        evaluation.artifact_id
        for evaluation in sorted(
            search_evaluations.values(),
            key=lambda item: (
                item.metrics.miss_ratio_ppm,
                item.metrics.p99_decision_steps,
                item.artifact_id,
            ),
        )
    )
    return OfflineSelectionDecision(
        experiment_manifest_id=experiment_manifest_id,
        original_candidate_id=baseline.candidate_id,
        original_artifact_id=baseline.artifact_id,
        comparison_decision_ids=tuple(item.decision_id for item in comparison_items),
        search_ranking_artifact_ids=ranking,
        selected_candidate_id=selected_manifest.candidate_id,
        selected_artifact_id=selected_manifest.artifact_id,
        selected_strategy_id=selected_manifest.to_strategy,
        outcome=outcome,
    )


def _archive_evaluation(
    output: Path,
    evaluation: PartitionEvaluation,
) -> None:
    _write_document(
        output / "evaluations" / _safe_name(evaluation.evaluation_id),
        evaluation.to_document(),
    )


def run_prototype(
    contract_path: str | Path,
    output_directory: str | Path,
    *,
    _allow_expired_contract_for_replay: bool = False,
) -> PrototypeRunReport:
    output = Path(output_directory)
    if output.exists():
        raise PrototypeError(f"output directory already exists: {output}")
    contract = load_contract(contract_path)
    if not _allow_expired_contract_for_replay:
        _enforce_contract_expiry(contract)
    output.mkdir(parents=True, exist_ok=False)
    catalog = EvidenceCatalog()
    archived_catalog_id = content_id(
        catalog.to_document(disclose_audit_specs=True)
    )
    policy = PromotionPolicy.from_contract(contract)
    artifacts = _compile_strategies(contract)
    if "lru" not in artifacts:
        raise PrototypeError("the reviewed LRU baseline is not authorized")

    baseline = baseline_manifest(
        artifacts["lru"],
        evidence_catalog_id=catalog.prefreeze_catalog_id,
    )
    candidate_by_artifact: dict[str, CandidateManifest] = {
        artifacts["lru"].artifact_id: baseline
    }
    for strategy, artifact in artifacts.items():
        if strategy == "lru":
            continue
        candidate_by_artifact[artifact.artifact_id] = enumerated_manifest(
            artifact,
            parent_id=baseline.candidate_id,
            evidence_catalog_id=catalog.prefreeze_catalog_id,
        )
    candidate_by_strategy = {
        item.to_strategy: item for item in candidate_by_artifact.values()
    }
    implementation = implementation_manifest()
    implementation_id = content_id(implementation)
    experiment = ExperimentManifest(
        contract_id=contract.epoch_id,
        evidence_catalog_id=catalog.prefreeze_catalog_id,
        archived_evidence_catalog_id=archived_catalog_id,
        implementation_id=implementation_id,
        candidate_ids=tuple(sorted(item.candidate_id for item in candidate_by_artifact.values())),
        artifact_ids=tuple(sorted(candidate_by_artifact)),
        promotion_policy=policy,
    )
    challenger_count = len(candidate_by_artifact) - 1
    if challenger_count > policy.maximum_comparisons:
        raise PrototypeError("authorized strategies exceed the comparison budget")
    ledger = AppendOnlyLedger(output / "ledger.jsonl")
    budget = BudgetTracker(contract)
    all_evaluations: dict[str, PartitionEvaluation] = {}

    ledger.append(
        "run_started",
        payload={
            "contract_id": contract.epoch_id,
            "evidence_catalog_id": catalog.prefreeze_catalog_id,
            "implementation_id": implementation_id,
        },
    )
    ledger.append(
        "manifest_frozen",
        payload={"experiment_manifest_id": experiment.manifest_id},
    )

    evaluator_meta_report = run_evaluator_meta_tests()
    budget.charge_meta_evaluation(evaluator_meta_report.evaluator_queries)
    ledger.append(
        "evaluator_validated",
        payload={
            "meta_report_id": evaluator_meta_report.report_id,
            "passed": evaluator_meta_report.passed,
            "evaluator_queries": evaluator_meta_report.evaluator_queries,
        },
    )

    for strategy in sorted(candidate_by_strategy):
        candidate = candidate_by_strategy[strategy]
        artifact = artifacts[strategy]
        budget.register_candidate(candidate, artifact)
        common = {
            "strategy_id": strategy,
            "parent_ids": list(candidate.parent_ids),
        }
        ledger.append(
            "candidate_proposed",
            candidate_id=candidate.candidate_id,
            artifact_id=artifact.artifact_id,
            payload=common,
        )
        ledger.append(
            "candidate_built",
            candidate_id=candidate.candidate_id,
            artifact_id=artifact.artifact_id,
            payload={"artifact_bytes": len(artifact.canonical_bytes)},
        )
        ledger.append(
            "candidate_verified",
            candidate_id=candidate.candidate_id,
            artifact_id=artifact.artifact_id,
            payload={"type": "CacheKeyV0", "effects": [], "static_gates_pass": True},
        )

    search_evaluations: dict[str, PartitionEvaluation] = {}
    operational: dict[str, PartitionEvaluation] = {}
    historical: dict[str, PartitionEvaluation] = {}
    for strategy in sorted(artifacts):
        artifact = artifacts[strategy]
        candidate = candidate_by_strategy[strategy]
        search = catalog.evaluate_search(artifact)
        budget.charge(search)
        search_evaluations[artifact.artifact_id] = search
        all_evaluations[search.evaluation_id] = search
        ledger.append(
            "search_evaluated",
            candidate_id=candidate.candidate_id,
            artifact_id=artifact.artifact_id,
            payload={
                "evaluation_id": search.evaluation_id,
                "aggregate_disclosure_id": content_id(search.aggregate_disclosure()),
            },
        )

        operational_result = catalog.evaluate_operational(artifact)
        budget.charge(operational_result)
        operational[artifact.artifact_id] = operational_result
        all_evaluations[operational_result.evaluation_id] = operational_result
        ledger.append(
            "operationally_evaluated",
            candidate_id=candidate.candidate_id,
            artifact_id=artifact.artifact_id,
            payload={"evaluation_id": operational_result.evaluation_id},
        )

        historical_result = catalog.evaluate_historical(artifact)
        budget.charge(historical_result)
        historical[artifact.artifact_id] = historical_result
        all_evaluations[historical_result.evaluation_id] = historical_result
        ledger.append(
            "historically_evaluated",
            candidate_id=candidate.candidate_id,
            artifact_id=artifact.artifact_id,
            payload={"evaluation_id": historical_result.evaluation_id},
        )

    baseline_artifact_id = artifacts["lru"].artifact_id
    comparison_decisions: list[PromotionDecision] = []
    for strategy in sorted(artifacts):
        if strategy == "lru":
            continue
        artifact = artifacts[strategy]
        candidate = candidate_by_strategy[strategy]
        decision = compare_for_promotion(
            champion_operational=operational[baseline_artifact_id],
            challenger_operational=operational[artifact.artifact_id],
            champion_historical=historical[baseline_artifact_id],
            challenger_historical=historical[artifact.artifact_id],
            policy=policy,
        )
        comparison_decisions.append(decision)
        event_type = (
            "candidate_eligible" if decision.outcome == "eligible" else "candidate_rejected"
        )
        ledger.append(
            event_type,
            candidate_id=candidate.candidate_id,
            artifact_id=artifact.artifact_id,
            payload={
                "comparison_decision_id": decision.decision_id,
                "reasons": list(decision.reasons),
            },
        )
    if len(comparison_decisions) > policy.maximum_comparisons:
        raise PrototypeError("comparison budget exhausted")

    offline_decision = _select_offline(
        experiment_manifest_id=experiment.manifest_id,
        baseline=baseline,
        candidates=candidate_by_artifact,
        search_evaluations=search_evaluations,
        comparisons=comparison_decisions,
    )
    selected_artifact = artifacts[offline_decision.selected_strategy_id]
    ledger.append(
        "offline_champion_selected",
        candidate_id=offline_decision.selected_candidate_id,
        artifact_id=offline_decision.selected_artifact_id,
        payload={
            "offline_decision_id": offline_decision.decision_id,
            "outcome": offline_decision.outcome,
            "deployment": False,
        },
    )
    ledger.append(
        "decision_frozen",
        candidate_id=offline_decision.selected_candidate_id,
        artifact_id=offline_decision.selected_artifact_id,
        payload={
            "offline_decision_id": offline_decision.decision_id,
            "research_audit_evaluation_ids": [],
        },
    )

    post_decision_artifacts = tuple(
        {
            artifact.artifact_id: artifact
            for artifact in (artifacts["lru"], selected_artifact)
        }.values()
    )
    prospective: list[PartitionEvaluation] = []
    for artifact in post_decision_artifacts:
        evaluation = catalog.evaluate_prospective(
            artifact,
            frozen_decision_id=offline_decision.decision_id,
        )
        budget.charge(evaluation)
        prospective.append(evaluation)
        all_evaluations[evaluation.evaluation_id] = evaluation
        candidate = candidate_by_artifact[artifact.artifact_id]
        ledger.append(
            "prospective_evaluated",
            candidate_id=candidate.candidate_id,
            artifact_id=artifact.artifact_id,
            payload={"evaluation_id": evaluation.evaluation_id},
        )

    audit = catalog.evaluate_research_audit(
        post_decision_artifacts,
        frozen_decision_id=offline_decision.decision_id,
    )
    for evaluation in audit.evaluations:
        budget.charge(evaluation)
        all_evaluations[evaluation.evaluation_id] = evaluation
    ledger.append(
        "research_audit_consumed",
        payload={
            "offline_decision_id": offline_decision.decision_id,
            "audit_report_id": audit.report_id,
            "used_for_selection": False,
        },
    )

    _write_document(output / "contract.json", contract.to_dict())
    _write_document(output / "implementation.json", implementation)
    _write_document(output / "experiment-manifest.json", experiment.to_document())
    _write_document(
        output / "evaluator-meta-report.json",
        evaluator_meta_report.to_document(),
    )
    _write_document(
        output / "evidence-catalog.json",
        catalog.to_document(disclose_audit_specs=True),
    )
    for artifact in artifacts.values():
        _write_document(
            output / "artifacts" / _safe_name(artifact.artifact_id),
            artifact.to_document(),
        )
    for candidate in candidate_by_artifact.values():
        _write_document(
            output / "candidates" / _safe_name(candidate.candidate_id),
            candidate.to_record(),
        )
    archived_traces = catalog.archive_traces_after_freeze()
    all_trace_ids: list[str] = []
    for partition, traces in archived_traces.items():
        for trace in traces:
            all_trace_ids.append(trace.trace_id)
            _write_document(
                output / "traces" / partition / _safe_name(trace.trace_id),
                trace.to_document(),
            )
    for evaluation in all_evaluations.values():
        _archive_evaluation(output, evaluation)
    for decision in comparison_decisions:
        _write_document(
            output / "comparisons" / _safe_name(decision.decision_id),
            decision.to_document(),
        )
    _write_document(output / "offline-decision.json", offline_decision.to_document())
    _write_document(output / "audit-report.json", audit.to_document())

    final_event = ledger.append(
        "run_completed",
        candidate_id=offline_decision.selected_candidate_id,
        artifact_id=offline_decision.selected_artifact_id,
        payload={
            "offline_decision_id": offline_decision.decision_id,
            "audit_report_id": audit.report_id,
            "evaluator_meta_report_id": evaluator_meta_report.report_id,
            "prospective_evaluation_ids": [item.evaluation_id for item in prospective],
        },
    )
    archived_payload_bytes = sum(
        path.stat().st_size for path in output.rglob("*") if path.is_file()
    )
    audit_by_artifact = {item.artifact_id: item for item in audit.evaluations}
    prospective_by_artifact = {item.artifact_id: item for item in prospective}
    report = PrototypeRunReport(
        implementation_id=implementation_id,
        contract_id=contract.epoch_id,
        experiment_manifest_id=experiment.manifest_id,
        evidence_catalog_id=catalog.prefreeze_catalog_id,
        archived_evidence_catalog_id=archived_catalog_id,
        evaluator_meta_report_id=evaluator_meta_report.report_id,
        offline_decision_id=offline_decision.decision_id,
        selected_candidate_id=offline_decision.selected_candidate_id,
        selected_artifact_id=offline_decision.selected_artifact_id,
        selected_strategy_id=offline_decision.selected_strategy_id,
        comparison_decision_ids=tuple(
            item.decision_id for item in comparison_decisions
        ),
        prospective_evaluation_ids=tuple(
            item.evaluation_id for item in prospective
        ),
        audit_report_id=audit.report_id,
        audit_evaluation_ids=tuple(
            item.evaluation_id for item in audit.evaluations
        ),
        all_candidate_ids=tuple(
            sorted(item.candidate_id for item in candidate_by_artifact.values())
        ),
        all_artifact_ids=tuple(sorted(candidate_by_artifact)),
        all_trace_ids=tuple(sorted(all_trace_ids)),
        all_evaluation_ids=tuple(sorted(all_evaluations)),
        ledger_id=ledger.ledger_id,
        final_event_id=final_event.event_id,
        budget=budget.to_document(),
        audit_primary_improvement_ppm=(
            audit_by_artifact[baseline_artifact_id].metrics.miss_ratio_ppm
            - audit_by_artifact[selected_artifact.artifact_id].metrics.miss_ratio_ppm
        ),
        prospective_primary_improvement_ppm=(
            prospective_by_artifact[baseline_artifact_id].metrics.miss_ratio_ppm
            - prospective_by_artifact[
                selected_artifact.artifact_id
            ].metrics.miss_ratio_ppm
        ),
        archived_payload_bytes=archived_payload_bytes,
    )
    _write_document(output / "run-report.json", report.to_record())
    total_bytes = sum(path.stat().st_size for path in output.rglob("*") if path.is_file())
    contract_document = contract.to_dict()
    budgets = contract_document["budgets"]
    assert isinstance(budgets, dict)
    per_epoch = budgets["per_epoch"]
    assert isinstance(per_epoch, dict)
    if total_bytes > int(per_epoch["storage_bytes"]):
        raise PrototypeError("run bundle exceeds the per-epoch storage budget")
    return report


@dataclass(frozen=True)
class ReplayReport:
    source_report_id: str
    replay_report_id: str
    files_verified: int

    def to_document(self) -> dict[str, JsonValue]:
        return {
            "schema_version": REPLAY_REPORT_SCHEMA_VERSION,
            "source_report_id": self.source_report_id,
            "replay_report_id": self.replay_report_id,
            "files_verified": self.files_verified,
            "exact_match": True,
        }


def _verify_report_record(path: Path) -> tuple[str, Mapping[str, JsonValue]]:
    value = _read_document(path)
    if not isinstance(value, dict) or set(value) != {
        "schema_version",
        "report_id",
        "report",
    }:
        raise PrototypeError("run report record has invalid fields")
    if value["schema_version"] != RUN_REPORT_RECORD_SCHEMA_VERSION:
        raise PrototypeError("run report record has an unknown schema")
    report = value["report"]
    if not isinstance(report, dict):
        raise PrototypeError("run report payload is not an object")
    report_id = value["report_id"]
    if not isinstance(report_id, str) or content_id(report) != report_id:
        raise PrototypeError("run report identity mismatch")
    return report_id, report


def replay_prototype(bundle_directory: str | Path) -> ReplayReport:
    source = Path(bundle_directory)
    if not source.is_dir():
        raise PrototypeError(f"run bundle does not exist: {source}")
    source_report_id, source_report = _verify_report_record(
        source / "run-report.json"
    )
    final_event_id = source_report.get("final_event_id")
    ledger_id = source_report.get("ledger_id")
    if not isinstance(final_event_id, str) or not isinstance(ledger_id, str):
        raise PrototypeError("run report omits ledger identity")
    ledger = AppendOnlyLedger(source / "ledger.jsonl")
    ledger.verify_expected_final_event(final_event_id)
    if ledger.ledger_id != ledger_id:
        raise PrototypeError("ledger snapshot identity mismatch")

    with tempfile.TemporaryDirectory(prefix="laicode-replay-") as directory:
        replay = Path(directory) / "bundle"
        replay_report = run_prototype(
            source / "contract.json",
            replay,
            _allow_expired_contract_for_replay=True,
        )
        source_files = sorted(
            path.relative_to(source) for path in source.rglob("*") if path.is_file()
        )
        replay_files = sorted(
            path.relative_to(replay) for path in replay.rglob("*") if path.is_file()
        )
        if source_files != replay_files:
            raise PrototypeError("bundle inventory does not match deterministic replay")
        for relative in source_files:
            if (source / relative).read_bytes() != (replay / relative).read_bytes():
                raise PrototypeError(f"replay mismatch in {relative.as_posix()}")
        return ReplayReport(
            source_report_id=source_report_id,
            replay_report_id=replay_report.report_id,
            files_verified=len(source_files),
        )
