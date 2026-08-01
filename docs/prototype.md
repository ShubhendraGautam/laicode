# Working D0 prototype

## Demonstrated scope

Prototype v0 implements one complete, bounded evolution loop at
`(R2, M1, G1, L0, D0; F0)`. Candidate artifacts are data in a closed semantic
kernel, not imported source or plugins. The fixed generator enumerates the three
reviewed strategies LRU, FIFO, and LFU; it does not update a learner or call a
model.

The supervisor:

1. strictly validates and content-addresses the evolution contract;
2. commits the experiment, implementation, candidates, and evidence identities;
3. runs an eight-case evaluator meta-suite before candidate search;
4. evaluates every candidate on identity-separated search, operational
   holdout, and historical-regression partitions;
5. applies the frozen constrained comparison rule outside candidate authority;
6. freezes one offline D0 decision with no research-audit inputs;
7. evaluates the original and selected artifacts prospectively;
8. consumes the research audit once, after the decision;
9. archives canonical inputs, full per-event results, failures, costs,
   decisions, and a hash-chained lifecycle ledger; and
10. reruns from the archived contract and requires every file to match byte for
    byte.

The cache model, tie-breaks, shield, SplitMix64 traces, metrics, and evidence
rules are frozen in [Decision 0004](decisions/0004-freeze-cache-d0-semantics.md).
The local integrity model is frozen in
[Decision 0005](decisions/0005-use-hash-chained-ledger-at-d0.md).

## One-command reproduction

Use an output path that does not exist:

```sh
python3 -m laicode smoke-prototype \
  examples/contracts/cache-policy-v0.json /tmp/laicode-prototype
```

A successful run prints a content-derived report ID, `selected=lfu`, the
verified file count, and `exact=true`. Run and replay can also be invoked
separately:

```sh
python3 -m laicode run-prototype \
  examples/contracts/cache-policy-v0.json /tmp/laicode-run
python3 -m laicode replay-prototype /tmp/laicode-run
```

The bundle contains:

- `contract.json`, implementation and experiment manifests;
- sealed-then-archived evidence catalog and all ten trace payloads;
- three immutable candidate records and three evaluated artifacts;
- evaluator meta-report, thirteen partition evaluations, two comparisons,
  offline decision, prospective results, and audit report;
- canonical hash-chained `ledger.jsonl`; and
- a content-addressed `run-report.json` that pins the final ledger event and
  full inventory.

Changing, deleting, reordering, truncating, or adding a material bundle file
causes replay to fail.

## Exploratory result

On the frozen synthetic traces, the external rule rejects FIFO and selects LFU
offline against the original LRU baseline. LFU improves operational-holdout miss
ratio by 31,250 parts per million and has no historical-regression increase. The
post-decision research audit shows the same 31,250 ppm improvement.

The prospective recency-shift partition reverses the result: LFU is worse than
LRU by 187,500 ppm. This is intentionally preserved as negative future evidence.
The run performs no deployment and the audit never changes the earlier
selection.

## Claim boundary and residual risks

This artifact supports a functional and exactly replayable exploratory D0
workflow claim only. It does not support:

- production isolation or adversarial containment;
- a confirmatory false-promotion or generalization claim;
- autonomous deployment, shadow traffic, canary, or rollback;
- arbitrary candidate code, dependencies, private state, learned abstractions,
  or model-driven generation;
- wall-clock performance promotion; or
- authenticated non-repudiation against a maintainer who can replace both the
  bundle and its expected identities.

Candidate/query/churn/artifact/storage limits and contract expiry are enforced.
CPU, wall-time, and memory are not independently isolated at D0; this is
reported in every D0 run. A separate
[D1 counterfactual-shadow milestone](working-alternative.md) now adds bounded
worker processes and revocation for the same closed IR. Before M2/M3, D2, or any
production containment claim, the remaining syscall isolation, statistical
calibration, independent review, and served-state recovery gates in the
[design checklist](design-checklist.md) remain mandatory.
