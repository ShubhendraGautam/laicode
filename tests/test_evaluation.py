from __future__ import annotations

import unittest

from laicode.contracts import load_contract
from laicode.evaluation import (
    HISTORICAL_REGRESSION,
    OPERATIONAL_HOLDOUT,
    RESEARCH_AUDIT,
    SEARCH,
    AuditReport,
    EvidenceCatalog,
    EvaluationError,
    PromotionPolicy,
    compare_for_promotion,
    run_evaluator_meta_tests,
)
from laicode.kernel import CandidateArtifact, compile_complete_program

from .test_kernel import CONTRACT_PATH


def artifact(strategy_id: str) -> CandidateArtifact:
    return compile_complete_program(
        load_contract(CONTRACT_PATH),
        {
            "schema_version": "CacheStrategySelectionV0",
            "op": "select_strategy",
            "strategy_id": strategy_id,
        },
    )


class PartitionedEvaluationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.contract = load_contract(CONTRACT_PATH)
        cls.artifacts = {
            strategy: artifact(strategy) for strategy in ("lru", "fifo", "lfu")
        }

    def test_catalog_has_identity_separated_required_partitions(self) -> None:
        catalog = EvidenceCatalog()
        document = catalog.to_document(disclose_audit_specs=False)
        partitions = document["partitions"]
        assert isinstance(partitions, dict)

        self.assertEqual(
            set(partitions),
            {
                "search",
                "operational_holdout",
                "research_audit",
                "prospective",
                "historical_regression",
            },
        )
        audit = partitions[RESEARCH_AUDIT]
        assert isinstance(audit, dict)
        self.assertEqual(len(audit["trace_ids"]), 2)
        self.assertFalse(audit["specs_disclosed"])
        disclosed = catalog.to_document(disclose_audit_specs=True)
        self.assertNotEqual(document, disclosed)

    def test_evaluator_meta_suite_passes_before_search(self) -> None:
        report = run_evaluator_meta_tests()

        self.assertTrue(report.passed)
        self.assertEqual(report.evaluator_queries, 8)
        self.assertEqual(len(report.checks), 8)
        self.assertEqual(len(report.evidence_result_ids), 8)

    def test_generator_view_contains_search_only(self) -> None:
        catalog = EvidenceCatalog()
        traces = catalog.search_traces()

        self.assertEqual(len(traces), 2)
        self.assertTrue(all(trace.name.startswith(f"{SEARCH}-") for trace in traces))

    def test_evaluations_are_deterministic_and_partition_bound(self) -> None:
        catalog = EvidenceCatalog()
        first = catalog.evaluate_operational(self.artifacts["lru"])
        second = catalog.evaluate_operational(self.artifacts["lru"])

        self.assertEqual(first, second)
        self.assertEqual(first.evaluation_id, second.evaluation_id)
        self.assertEqual(first.partition, OPERATIONAL_HOLDOUT)
        self.assertEqual(first.metrics.accesses, 256)
        self.assertTrue(first.metrics.hard_constraints_pass)

    def test_lfu_passes_registered_gates_and_fifo_does_not(self) -> None:
        catalog = EvidenceCatalog()
        policy = PromotionPolicy.from_contract(self.contract)
        operational = {
            name: catalog.evaluate_operational(item)
            for name, item in self.artifacts.items()
        }
        historical = {
            name: catalog.evaluate_historical(item)
            for name, item in self.artifacts.items()
        }

        fifo = compare_for_promotion(
            champion_operational=operational["lru"],
            challenger_operational=operational["fifo"],
            champion_historical=historical["lru"],
            challenger_historical=historical["fifo"],
            policy=policy,
        )
        lfu = compare_for_promotion(
            champion_operational=operational["lru"],
            challenger_operational=operational["lfu"],
            champion_historical=historical["lru"],
            challenger_historical=historical["lfu"],
            policy=policy,
        )

        self.assertEqual(fifo.outcome, "rejected")
        self.assertEqual(fifo.reasons, ("primary_effect_below_threshold",))
        self.assertEqual(lfu.outcome, "eligible")
        self.assertEqual(lfu.primary_improvement_ppm, 31_250)
        self.assertEqual(lfu.historical_regression_ppm, 0)
        self.assertEqual(lfu.to_document()["research_audit_evaluation_ids"], [])

    def test_aggregate_holdout_disclosure_omits_cases(self) -> None:
        evaluation = EvidenceCatalog().evaluate_operational(self.artifacts["lfu"])
        disclosure = evaluation.aggregate_disclosure()

        self.assertEqual(disclosure["results"], [])
        self.assertFalse(disclosure["observations_included"])
        self.assertIn("evaluation_id", disclosure)

    def test_research_audit_requires_frozen_decision_and_is_one_shot(self) -> None:
        catalog = EvidenceCatalog()
        with self.assertRaisesRegex(EvaluationError, "frozen decision"):
            catalog.evaluate_research_audit(
                (self.artifacts["lru"],),
                frozen_decision_id="not-frozen",
            )

        report = catalog.evaluate_research_audit(
            (self.artifacts["lru"], self.artifacts["lfu"]),
            frozen_decision_id="sha256:" + "a" * 64,
        )

        self.assertIsInstance(report, AuditReport)
        self.assertEqual(len(report.evaluations), 2)
        self.assertTrue(
            all(item.partition == RESEARCH_AUDIT for item in report.evaluations)
        )
        with self.assertRaisesRegex(EvaluationError, "already been consumed"):
            catalog.evaluate_research_audit(
                (self.artifacts["lfu"],),
                frozen_decision_id="sha256:" + "a" * 64,
            )

    def test_audit_traces_cannot_be_archived_before_freeze_and_consumption(self) -> None:
        catalog = EvidenceCatalog()
        with self.assertRaisesRegex(EvaluationError, "cannot be archived"):
            catalog.archive_traces_after_freeze()

    def test_promotion_rejects_partition_substitution(self) -> None:
        catalog = EvidenceCatalog()
        search = catalog.evaluate_search(self.artifacts["lru"])
        operational = catalog.evaluate_operational(self.artifacts["lfu"])
        historical_lru = catalog.evaluate_historical(self.artifacts["lru"])
        historical_lfu = catalog.evaluate_historical(self.artifacts["lfu"])

        self.assertEqual(search.partition, SEARCH)
        self.assertEqual(historical_lru.partition, HISTORICAL_REGRESSION)
        with self.assertRaisesRegex(EvaluationError, "wrong partition"):
            compare_for_promotion(
                champion_operational=search,
                challenger_operational=operational,
                champion_historical=historical_lru,
                challenger_historical=historical_lfu,
                policy=PromotionPolicy.from_contract(self.contract),
            )

    def test_prospective_evaluation_is_post_decision_only(self) -> None:
        catalog = EvidenceCatalog()
        with self.assertRaisesRegex(EvaluationError, "frozen decision"):
            catalog.evaluate_prospective(
                self.artifacts["lfu"],
                frozen_decision_id="pending",
            )
        result = catalog.evaluate_prospective(
            self.artifacts["lfu"],
            frozen_decision_id="sha256:" + "b" * 64,
        )
        self.assertEqual(result.partition, "prospective")


if __name__ == "__main__":
    unittest.main()
