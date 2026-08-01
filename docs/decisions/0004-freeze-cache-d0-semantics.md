# Decision 0004: Freeze deterministic cache semantics for prototype D0

- **Status:** accepted for prototype v0
- **Date:** 2026-08-01
- **Owners:** project owner; implementation delegated to Codex
- **Reviewers:** project-owner review deferred; independent experiment review
  required before confirmatory use
- **Scope:** cache benchmark E0/E1 at `(R2/R3, M1, G0/G1, L0/L1, D0; F0/F1)`

## Context

The working prototype needs one precise executable target before candidate
generation, statistics, or deployment machinery can be meaningful. Wall-clock
latency would make byte-for-byte replay host-dependent, and a vague cache model
would make LRU/LFU/FIFO comparisons irreproducible.

## Decision

Freeze these prototype-v0 semantics:

- Cache objects have unit size and stable string keys. Capacity is an exact
  positive object count.
- A trace is an ordered sequence of accesses. Its zero-based sequence number is
  logical time; candidates cannot read a clock or randomness source.
- The simulator owns resident state, insertion time, last-access time, frequency,
  and pin state. A candidate receives an immutable snapshot only when a miss on a
  full cache requires eviction.
- Event pin declarations are workload intent. The effective pinned set is their
  intersection with the policy-specific resident set. If no resident object is
  evictable, insertion is blocked and no candidate is called.
- LRU chooses minimum `(last_access, inserted_at, key)`. FIFO chooses minimum
  `(inserted_at, key)`. LFU chooses minimum
  `(frequency, last_access, inserted_at, key)`.
- All three registered primitives are pure and total over the contract domain.
  Their semantic decision cost is the number of evictable entries inspected.
- An external shield validates every proposed victim. Invalid output or a policy
  exception records a violation and applies reviewed LRU fallback. The candidate
  cannot alter the shield, cache state, metrics, or trace.
- Promotion quality is integer miss ratio in parts per million. The practical
  effect is an absolute miss-ratio reduction, also in parts per million.
  Deterministic semantic decision cost replaces wall-clock latency as the
  protected D0 metric; wall time may be reported only as non-replayable cost.
- Synthetic traces use a specified SplitMix64 generator, scenario name, seed,
  event count, and capacity. No host-language random generator participates.
- Partitions are temporal and identity-separated: search, operational holdout,
  historical regression, prospective future, and research audit. Operational
  selection receives aggregate holdout results. Research audit is evaluated
  only after the offline decision is frozen and never changes that decision.
- The initial smoke study is exploratory. It may demonstrate deterministic
  offline search and selection, but it is not a confirmatory generalization or
  deployment result.

## Consequences

- Every functional result and promotion input is exactly replayable.
- Unit-size objects omit byte-size admission and variable-cost eviction effects.
- LFU frequency resets on insertion and has no aging in v0.
- Semantic decision cost is suitable for deterministic regression protection,
  not a claim about production latency.
- Synthetic workload conclusions remain scoped to the registered scenarios.

## Alternatives considered

### Promote on measured nanoseconds

Rejected for D0 because host load, frequency scaling, interpreter state, and
measurement noise prevent exact decision replay.

### Use Python's pseudorandom generator

Rejected because its implementation is not the language-neutral benchmark
contract. A tiny specified SplitMix64 generator is easier to port and audit.

### Give each policy private adaptive state

Deferred because it complicates recovery, identity, and attribution. All v0
features remain simulator-owned snapshot data.

### Use research-audit performance to choose the winner

Rejected because it would consume the audit as operational evidence and make a
post-freeze generalization estimate impossible.

## Validation evidence

- [Deterministic generator, hand-checked policy, invariant, and shield tests](../../tests/test_cache.py)
- [Partition, comparison, audit, and evaluator meta-tests](../../tests/test_evaluation.py)
- [Full run and byte-exact replay tests](../../tests/test_prototype.py)
- [Cross-interface R2/R3 artifact identity tests](../../tests/test_kernel.py)
- [Machine-readable trace, snapshot, result, and evaluation schemas](../../schemas/README.md)

## Revisit criteria

Start a new schema/kernel version before adding variable object sizes, admission
control, frequency aging, candidate-private state, concurrency, measured latency
as a promotion metric, public traces, or D1 shadow execution.

## 2026-08-01 D1 reuse note

[Decision 0006](0006-use-counterfactual-shadow-before-serving.md) reuses these
exact cache semantics in an independent counterfactual twin; it does not change
the candidate language, metrics, state ownership, or tie-breaking. The new D1
lease/checkpoint/report schemas version the lifecycle extension separately.
