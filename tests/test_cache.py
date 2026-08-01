from __future__ import annotations

import copy
import unittest

from laicode.cache import (
    AccessEvent,
    CacheEntry,
    CacheError,
    CacheSnapshot,
    CacheTrace,
    PolicyDecision,
    SplitMix64,
    decode_trace,
    generate_trace,
    select_strategy,
    simulate,
    simulate_artifact,
)
from laicode.contracts import load_contract
from laicode.kernel import compile_complete_program

from .test_kernel import CONTRACT_PATH, PROGRAM_PATH


def trace_from_keys(
    keys: list[str],
    *,
    capacity: int,
    pins: dict[int, tuple[str, ...]] | None = None,
) -> CacheTrace:
    pinned = pins or {}
    return CacheTrace(
        name="hand-trace",
        scenario="mixed_bursts",
        seed=0,
        capacity=capacity,
        events=tuple(
            AccessEvent(sequence=index, key=key, pinned_keys=pinned.get(index, ()))
            for index, key in enumerate(keys)
        ),
    )


class CacheSemanticsTests(unittest.TestCase):
    def test_splitmix64_reference_vector(self) -> None:
        random = SplitMix64(0)
        self.assertEqual(
            [random.next_u64() for _ in range(3)],
            [
                0xE220A8397B1DCDAF,
                0x6E789E6AA1B965F4,
                0x06C45D188009454F,
            ],
        )

    def test_generated_trace_is_deterministic_and_round_trips(self) -> None:
        first = generate_trace("scan_resistance", 17, event_count=256)
        second = generate_trace("scan_resistance", 17, event_count=256)
        decoded = decode_trace(first.canonical_bytes)

        self.assertEqual(first, second)
        self.assertEqual(decoded, first)
        self.assertEqual(decoded.trace_id, first.trace_id)

    def test_trace_decoder_normalizes_pin_sets(self) -> None:
        document = generate_trace("mixed_bursts", 3, event_count=8).to_document()
        events = document["events"]
        assert isinstance(events, list)
        event = events[0]
        assert isinstance(event, dict)
        event["pinned_keys"] = ["z", "a"]

        decoded = decode_trace(document)

        self.assertEqual(decoded.events[0].pinned_keys, ("a", "z"))

    def test_trace_decoder_rejects_ambiguous_or_noncontiguous_events(self) -> None:
        document = generate_trace("mixed_bursts", 3, event_count=8).to_document()
        duplicate = copy.deepcopy(document)
        duplicate_events = duplicate["events"]
        assert isinstance(duplicate_events, list)
        duplicate_event = duplicate_events[0]
        assert isinstance(duplicate_event, dict)
        duplicate_event["pinned_keys"] = ["a", "a"]
        with self.assertRaisesRegex(CacheError, "duplicates"):
            decode_trace(duplicate)

        noncontiguous = copy.deepcopy(document)
        noncontiguous_events = noncontiguous["events"]
        assert isinstance(noncontiguous_events, list)
        second = noncontiguous_events[1]
        assert isinstance(second, dict)
        second["sequence"] = 9
        with self.assertRaisesRegex(CacheError, "contiguous sequence"):
            decode_trace(noncontiguous)

    def test_reference_policy_tie_breaking_is_exact(self) -> None:
        snapshot = CacheSnapshot(
            sequence=10,
            capacity=3,
            requested_key="new",
            entries=(
                CacheEntry("a", inserted_at=0, last_access=8, frequency=5),
                CacheEntry("b", inserted_at=1, last_access=4, frequency=1),
                CacheEntry("c", inserted_at=2, last_access=6, frequency=1),
            ),
            evictable_keys=("a", "b", "c"),
            pinned_keys=(),
        )

        self.assertEqual(select_strategy("lru", snapshot).selected_key, "b")
        self.assertEqual(select_strategy("fifo", snapshot).selected_key, "a")
        self.assertEqual(select_strategy("lfu", snapshot).selected_key, "b")
        for strategy in ("lru", "fifo", "lfu"):
            self.assertEqual(select_strategy(strategy, snapshot).semantic_steps, 3)

    def test_simple_trace_has_hand_checked_results(self) -> None:
        trace = trace_from_keys(["a", "b", "a", "c"], capacity=2)

        lru = simulate(
            trace,
            subject_id="subject-lru",
            strategy_id="lru",
            selector=lambda snapshot: select_strategy("lru", snapshot),
        )
        fifo = simulate(
            trace,
            subject_id="subject-fifo",
            strategy_id="fifo",
            selector=lambda snapshot: select_strategy("fifo", snapshot),
        )

        self.assertEqual((lru.metrics.hits, lru.metrics.misses), (1, 3))
        self.assertEqual(lru.final_resident_keys, ("a", "c"))
        self.assertEqual(fifo.final_resident_keys, ("b", "c"))
        self.assertEqual(lru.metrics.miss_ratio_ppm, 750_000)

    def test_pin_shield_prevents_pinned_eviction(self) -> None:
        trace = trace_from_keys(
            ["a", "b", "c"],
            capacity=2,
            pins={2: ("a",)},
        )
        result = simulate(
            trace,
            subject_id="bad-policy",
            strategy_id="meta-invalid",
            selector=lambda snapshot: PolicyDecision("a", 1),
        )

        self.assertEqual(result.metrics.candidate_violations, 1)
        self.assertEqual(result.metrics.fallbacks, 1)
        self.assertEqual(result.final_resident_keys, ("a", "c"))
        decision = result.observations[-1]
        self.assertEqual(decision.violation, "invalid_victim")
        self.assertTrue(decision.used_fallback)
        self.assertEqual(decision.applied_choice, "b")

    def test_all_pinned_cache_blocks_without_calling_candidate(self) -> None:
        trace = trace_from_keys(
            ["a", "b", "c"],
            capacity=2,
            pins={2: ("a", "b")},
        )
        calls = 0

        def selector(snapshot: CacheSnapshot) -> PolicyDecision:
            nonlocal calls
            calls += 1
            return PolicyDecision("a", 1)

        result = simulate(
            trace,
            subject_id="not-called",
            strategy_id="meta",
            selector=selector,
        )

        self.assertEqual(calls, 0)
        self.assertEqual(result.metrics.blocked_insertions, 1)
        self.assertEqual(result.metrics.policy_invocations, 0)
        self.assertEqual(result.final_resident_keys, ("a", "b"))

    def test_policy_error_is_contained_and_falls_back(self) -> None:
        trace = trace_from_keys(["a", "b", "c"], capacity=2)

        def crashing(_: CacheSnapshot) -> PolicyDecision:
            raise RuntimeError("candidate crash")

        result = simulate(
            trace,
            subject_id="crash",
            strategy_id="meta-crash",
            selector=crashing,
        )

        self.assertEqual(result.metrics.policy_errors, 1)
        self.assertEqual(result.metrics.candidate_violations, 1)
        self.assertEqual(result.observations[-1].violation, "policy_error")

    def test_artifact_simulation_is_exactly_replayable(self) -> None:
        artifact = compile_complete_program(
            load_contract(CONTRACT_PATH),
            PROGRAM_PATH.read_bytes(),
        )
        trace = generate_trace("scan_resistance", 29, event_count=256)

        first = simulate_artifact(artifact, trace)
        second = simulate_artifact(artifact, trace)

        self.assertEqual(first, second)
        self.assertEqual(first.result_id, second.result_id)
        self.assertEqual(
            first.metrics.hits + first.metrics.misses,
            first.metrics.accesses,
        )
        self.assertEqual(len(first.observations), len(trace.events))

    def test_scan_resistance_scenario_distinguishes_policies(self) -> None:
        trace = generate_trace("scan_resistance", 41, event_count=512)
        results = {
            strategy: simulate(
                trace,
                subject_id=strategy,
                strategy_id=strategy,
                selector=lambda snapshot, selected=strategy: select_strategy(
                    selected, snapshot
                ),
            )
            for strategy in ("lru", "fifo", "lfu")
        }

        self.assertLess(
            results["lfu"].metrics.miss_ratio_ppm,
            results["lru"].metrics.miss_ratio_ppm,
        )


if __name__ == "__main__":
    unittest.main()
