# Implementation status

**Status:** working D0/D1 cache alternative, E-H0/A0/A1 evolving languages, B0 comparator laboratory, and H1 hardware-feedback lifecycle
**Reviewed against:** [design checklist](design-checklist.md) on 2026-08-01

The checklist is an evidence-gate system, not a backlog. The prototype now
completes a coherent D0 slice across several gates; it does not imply that the
full gate, the research program, or deployment readiness is complete.

## Gate review

| Gate | State | Executable evidence or blocker |
| --- | --- | --- |
| Gate 0 — research identity | documented; owner review open | Definitions, thesis, profiles, non-goals, benchmark, and claims ladder are in the [research charter](research-charter.md). Project-owner and independent-review fields remain open. |
| Gate 1 — novelty | open | The [prior-art map](prior-art.md) is a seed, not a dated systematic corpus. No novelty claim is authorized. |
| Gate 2 — evolution semantics | R4/L2 vocabulary lifecycle slice implemented | Strict [machine schemas](../schemas/README.md), canonical identities, the closed cache kernel, R2/R3 construction, and an E-H0 typed word kernel with transparent learned superinstructions are executable. A0 adds typed i64 arrays, pairs, locals, checked arithmetic/indexing, structured control flow, and transparent cross-task expression intrinsics. A1 is a separate epoch with bounded owned vectors, typed records, and transparent learned statement intrinsics. H1 can activate or retire existing entries in an offline target profile without changing or deleting their lowering. Primitive-semantic evolution, cross-epoch migration, and ambient effects remain open. |
| Gate 3 — root of trust | partial D1 evidence | Closed artifacts execute in a subprocess with external CPU/wall/address-space/output/file/process limits, a sanitized environment, strict worker protocol, and independent reference validation. There is no syscall/network sandbox, signing service, hostile native-code claim, or production containment report. |
| Gate 4 — evaluator integrity | exploratory D0 slice implemented | Five identity-separated partitions, aggregate disclosure, one-shot post-freeze audit, exact integer metrics, an eight-case evaluator meta-suite, shields/fallbacks, query budgets, and partition-substitution tests exist. Statistical calibration, leakage analysis, tails/slices, and confirmatory power remain open. |
| Gate 5 — lifecycle/provenance | local D0 slice implemented | Content-derived candidates/artifacts, complete lifecycle events, canonical JSONL hash chaining, locked/fsynced appends, mutation/reorder/truncation tests, and exact decision replay exist. H1 adds target/pit-specific activation and retirement records while preserving excluded entries and negative evidence. Authenticated remote provenance and a full deploy/rollback state machine do not. |
| Gate 6 — experiments | six exploratory manifests implemented | Cache D0, machine-language E-H0, comparator B0, hardware-feedback H1, algorithm-language A0, and collection-language A1 freeze distinct questions, protected partitions, baselines, fairness rules, metrics, and replay commands. A1 separates indexed/conditional-append learning tasks, protected Remove Element/Running Sum holdouts, and a post-freeze Move Zeroes audit. None satisfies confirmatory design requirements. |
| Gate 7 — cost | expanded exploratory evidence | E-H0 charges ALU, dispatch, definition, verification, compilation, encoded bytes, and library bytes. B0 archives raw runtime/build/startup distributions, normalized throughput, variability, source/artifact size, and peak RSS. H1 aggregates paired runtime gains but requires deterministic dispatch-token reduction before promotion. A0/A1 report exact interpreter dispatch/step changes and generated/native artifact identities without making a native speed claim. A1 additionally freezes owned-capacity limits but does not measure allocation or copying cost beyond dispatch/steps. Energy, runtime-installation size, hardware counters, and human effort remain unmeasured. |
| Gate 8 — deployment/recovery | D1 shadow slice implemented | An event-count lease runs an independent counterfactual twin, monitors hard constraints and regression externally, revokes a failing challenger, and verifies the original champion remained unchanged. No challenger serves effects; D2 canary, wall-clock leases, and served-state rollback remain prohibited. |
| Gate 9 — data/governance | synthetic-only slice | All traces are deterministic synthetic data. Ownership roles, incident process, and release governance remain open. |
| Gate 10 — reproducibility | CI, nightly host smoke, and local replay implemented | Pull requests and `main` run the complete suite on Python 3.10/3.14. A scheduled Ubuntu 24.04 job runs the five-session H1 study plus A0 and A1 language/native-validity studies, retaining evidence for 30 days. One-command cache, E-H0, B0, H1, A0, and A1 runs archive evidence; deterministic packages regenerate byte for byte. H1 exactly rederives its decision without rerunning timing, while A0 and A1 each regenerate 138 files and all generated C sources exactly. Independent-person and independent-machine reproduction remain open. |

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

The [working hardware-shaped language](working-machine-language.md) adds a
separate R4/L2 experiment. Two execution-learned operations persist across
cycles and change the next proposal space. On the protected holdout, learned
total cost is 26,698 units versus 35,349 fixed-human, 46,715 primitive-only,
and 46,881 seeded-random. It wins the post-freeze audit, while an unrelated
future workload retains a 12,665 versus 12,499 negative-transfer result. The
same primitive and learned bytecodes compile to generated C, produce identical
checksums, and archive raw host timings without allowing timing noise into the
selection identity.

The [cross-language benchmark laboratory](language-benchmarks.md) compares
LAIcode cycles 0/1/2 under one backend and descriptively compares the current
cycle with direct C11/GCC, C11/Clang, Python 3, and Node JavaScript. All seven
adapters match the trusted checksum on reuse, audit-transfer, and no-reuse
shift pits. Learned cycles beat cycle 0 on reuse/audit in the first release
runs, direct C remains substantially faster, cycle 2 regresses under shift, and
absolute/cycle ordering varies across host sessions. The nine-file generated
source package replays exactly; timing never changes selection.

The [replicated hardware-feedback lifecycle](hardware-feedback.md) closes a
bounded H1 loop from real-host evidence to an offline target profile. Its first
five-session run selects cycle 2 for reuse and audit transfer, but falls back to
primitive cycle 0 for no-reuse shift. Eligibility requires deterministic token
reduction, at least 80% paired wins, and at least 5% median paired improvement.
The resolver rejects unknown workload pits, and no execution or deployment
authority is granted.

The [visible algorithm language](algorithm-language.md) adds a structured A0
kernel and makes growth directly inspectable. Across seven tasks and 224 cases,
cycle 1 learns a transparent array-element comparison and cycle 2 learns a
transparent array-element accumulation. All cases match independent oracles in
all cycles. Learned entries transfer to protected binary search and maximum
subarray plus the post-freeze two-sum audit, reducing exact interpreter dispatch
by 99, 184, and 600 respectively. Twenty-one C sources are generated; 13
representative translations compile under strict C11 warnings and pass 416
native case executions. This is local contract equivalence, not official
LeetCode acceptance.

The [owned-vector and typed-record language](collection-language.md) advances to
a separate A1 kernel epoch. Seven tasks and 224 cases construct bounded outputs
across three cycles. Cycle 1 learns indexed append and cycle 2 learns conditional
indexed append from identity-separated training tasks. Total interpreter
dispatch falls from 20,473 to 18,859 to 17,854. The learned forms transfer to
protected Remove Element and post-freeze Move Zeroes, reducing dispatch by 542
and 618 while all outputs remain oracle-identical. Remove Element returns a
statically checked values-and-length record; Running Sum demonstrates computed
vector construction without reusing the learned vocabulary. Twenty-one C
sources are generated; 13 representative translations pass 416 native cases.

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
- [Decision 0007](decisions/0007-study-hardware-shaped-vocabulary-evolution.md):
  E-H0 may evolve transparent typed vocabulary over a fixed semantic kernel and
  must test matched alternatives, overhead, replay, transfer, and host evidence.
- [Decision 0008](decisions/0008-separate-learning-curves-from-language-comparisons.md):
  B0 must separate causal within-backend learning curves from descriptive
  ecosystem comparisons while sharing exact semantic checksums.
- [Decision 0009](decisions/0009-use-replicated-hardware-feedback-for-target-profiles.md):
  H1 may freeze pit-specific offline vocabulary profiles from replicated,
  checksum-valid host sessions under deterministic reuse and paired stability
  gates.
- [Decision 0010](decisions/0010-add-a-typed-algorithm-language.md): A0 may add
  typed structured algorithms and transparent cross-task expression intrinsics,
  with local platform-style validity bounded by independent oracles and strict
  generated-C checks.
- [Decision 0011](decisions/0011-add-owned-vectors-and-typed-records.md): A1 may
  add bounded locally owned vectors, one-vector typed records, and transparent
  statement intrinsics under immutable-input and strict native-validity rules.

## Next safe frontier

Keep all learned-language authority at D0 and cache challenger authority at D1.
The next A2 language frontier is bounded user-defined functions and a static
call graph, followed separately by depth-bounded recursion and then strings or
graph storage; each capability needs a new kernel epoch and protected task
family. The next H2 frontier is independent machines and toolchains, randomized session
order, calibrated uncertainty, energy/hardware counters, a second backend,
broader property-generated kernels, drift-triggered profile reevaluation, and
independent reproduction. Primitive-semantic
evolution, effects, compiler self-hosting, or D2 authority require a new
decision. The cache track separately still needs a local key/value adapter,
stronger containment, trusted leases, rollback, and human-authorized canarying.
