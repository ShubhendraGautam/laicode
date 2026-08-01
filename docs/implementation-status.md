# Implementation status

**Status:** working D0 selector plus bounded D1 counterfactual shadow
**Reviewed against:** [design checklist](design-checklist.md) on 2026-08-01

The checklist is an evidence-gate system, not a backlog. The prototype now
completes a coherent D0 slice across several gates; it does not imply that the
full gate, the research program, or deployment readiness is complete.

## Gate review

| Gate | State | Executable evidence or blocker |
| --- | --- | --- |
| Gate 0 — research identity | documented; owner review open | Definitions, thesis, profiles, non-goals, benchmark, and claims ladder are in the [research charter](research-charter.md). Project-owner and independent-review fields remain open. |
| Gate 1 — novelty | open | The [prior-art map](prior-art.md) is a seed, not a dated systematic corpus. No novelty claim is authorized. |
| Gate 2 — evolution semantics | D0 slice implemented | Strict [machine schemas](../schemas/README.md), canonical identities, a closed LRU/FIFO/LFU kernel, R2/R3 construction, contract expiry, default-deny effects, and authorization tests are executable. Learned abstractions, epoch migration, and broader mutation remain open. |
| Gate 3 — root of trust | partial D1 evidence | Closed artifacts execute in a subprocess with external CPU/wall/address-space/output/file/process limits, a sanitized environment, strict worker protocol, and independent reference validation. There is no syscall/network sandbox, signing service, hostile native-code claim, or production containment report. |
| Gate 4 — evaluator integrity | exploratory D0 slice implemented | Five identity-separated partitions, aggregate disclosure, one-shot post-freeze audit, exact integer metrics, an eight-case evaluator meta-suite, shields/fallbacks, query budgets, and partition-substitution tests exist. Statistical calibration, leakage analysis, tails/slices, and confirmatory power remain open. |
| Gate 5 — lifecycle/provenance | local D0 slice implemented | Content-derived candidates/artifacts, complete lifecycle events, canonical JSONL hash chaining, locked/fsynced appends, mutation/reorder/truncation tests, and exact decision replay exist. Authenticated remote provenance and a full deploy/rollback state machine do not. |
| Gate 6 — experiments | exploratory manifest implemented | The run freezes a question, hypothesis, falsifier, profiles, traces, baselines, metrics, thresholds, budgets, and analysis command. It is explicitly exploratory and does not satisfy confirmatory design requirements. |
| Gate 7 — cost | partial | Candidate count, artifact bytes, evaluator queries, network, model-token, money, and archive storage are recorded. CPU, wall time, memory, energy, and human effort are not independently measured or enforced. |
| Gate 8 — deployment/recovery | D1 shadow slice implemented | An event-count lease runs an independent counterfactual twin, monitors hard constraints and regression externally, revokes a failing challenger, and verifies the original champion remained unchanged. No challenger serves effects; D2 canary, wall-clock leases, and served-state rollback remain prohibited. |
| Gate 9 — data/governance | synthetic-only slice | All traces are deterministic synthetic data. Ownership roles, incident process, and release governance remain open. |
| Gate 10 — reproducibility | local smoke implemented | A one-command smoke run archives full raw evidence and verifies a byte-for-byte fresh replay. Clean-environment and independent-person reproduction remain open. |

## Working result

The complete D0 workflow is described in [Working D0 prototype](prototype.md).
It validates the evaluator before search, evaluates LRU/FIFO/LFU under frozen
budgets, rejects FIFO, and selects LFU offline. Research-audit evidence is absent
from the frozen selection record. LFU improves the audit scan workload by
31,250 ppm but regresses on the prospective recency-shift workload by 187,500
ppm. No deployment occurs.

The [working alternative](working-alternative.md) advances the selected LFU
artifact into a resource-bounded D1 counterfactual shadow. On the default
recency-shift stream, its lease is revoked at 192 observed events while the
original LRU artifact remains the sole served champion. A non-regressing scan
workload exercises lease expiry without promotion.

The implementation has strict schemas for the contract, kernel/action/state,
traces, snapshots, simulation results, partition evaluations, evidence catalog,
candidate and ledger records, comparisons, audit, experiment/implementation
manifests, offline decision, evaluator meta-report, and run report.

## Decisions in force

- [Decision 0001](decisions/0001-external-judge.md): the candidate cannot change
  its judge.
- [Decision 0002](decisions/0002-model-native-language-planes.md): governance,
  kernel semantics, and future learned abstractions are separate.
- [Decision 0003](decisions/0003-prototype-runtime.md): Python standard library
  is accepted for D0, without a security-sandbox claim.
- [Decision 0004](decisions/0004-freeze-cache-d0-semantics.md): deterministic
  cache and evidence semantics are frozen for prototype v0.
- [Decision 0005](decisions/0005-use-hash-chained-ledger-at-d0.md): local
  content-addressed provenance and exact replay are accepted at D0.
- [Decision 0006](decisions/0006-use-counterfactual-shadow-before-serving.md):
  closed artifacts must earn D1 evidence without served effects before any D2
  proposal.

## Next safe frontier

Keep challenger authority at D1. The next implementation work should add a local
key/value adapter around the stable champion, syscall-level containment for any
broader candidate language, trusted wall-clock leases, an independently
monitored human-authorized D2 canary, served-state rollback, confirmatory
comparison calibration, and independent review.
