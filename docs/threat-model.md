# Threat model

**Status:** initial threat model for representation levels R0–R3, mutation levels
M0–M3, generators G0–G4, learner updates L0–L2, and deployment levels D0–D3
**Last updated:** 2026-07-31
**Owner:** to assign
**Next review:** before implementation or 2027-01-31, whichever comes first

## 1. Scope

This threat model covers a bounded evolutionary programming system in which
untrusted generators propose program candidates and a trusted supervisor decides
whether those candidates may execute or receive traffic.

It covers accidental defects, metric gaming, poisoned observations, malicious
candidate behavior, containment failure, operational mistakes, and statistical
false promotion. These are considered together because an evaluator cannot rely
on a generated candidate’s intent.

This document does not claim that arbitrary self-modifying programs can be made
safe. The initial system restricts candidate syntax, effects, state, evidence
access, and deployment authority.

## 2. Interpretation of “immutable”

The specification and judge are **candidate-immutable**, not permanently frozen.
Authorized maintainers may correct an evaluator, rotate credentials, patch the
supervisor, or change the objective. Any such change:

1. creates a new signed contract or evaluator version;
2. starts a new evolution epoch;
3. is recorded outside candidate authority;
4. reruns necessary baselines; and
5. avoids comparing scores across epochs unless a bridging evaluation supports
   that comparison.

This permits maintenance without letting the subject of evaluation rewrite the
conditions of success.

## 3. Protected assets

- Correctness and declared safety invariants.
- Integrity of objectives, constraints, metrics, denominators, and stop rules.
- Confidentiality and statistical validity of operational holdouts and research
  audit data.
- Integrity and availability of the observation and candidate ledgers.
- User data, credentials, private inputs, and model/provider secrets.
- Service availability and last-known-good recovery capability.
- CPU, memory, storage, network, model-token, and monetary budgets.
- Artifact identity: evaluated bytes must equal deployed bytes.
- Semantic identity: canonical program/action decoding must have one versioned
  meaning across learner, checker, evaluator, and runtime.
- Integrity and recoverability of learner checkpoints, search state, retrieval
  memory, and learned abstraction libraries.
- Research validity, including raw failures and negative results.
- Maintainer authority, signing keys, and break-glass controls.

## 4. Trust assumptions

| Component | Trust | Rationale |
| --- | --- | --- |
| Contract owner and signing process | trusted governance | defines authorized behavior and epoch changes |
| Contract compiler and policy engine | trusted code | interprets and enforces the boundary |
| Candidate semantic kernel/action validator | trusted code | defines canonical programs, types, effects, actions, and lowering |
| Evaluators and trusted metric collectors | trusted but fallible | provide the operational judge |
| Promotion and rollback controller | trusted code | grants and revokes execution authority |
| Artifact registry and append-only ledger | trusted storage | binds decisions to immutable artifacts |
| Host kernel, sandbox runtime, compiler used for guarantees | assurance dependency | compromise may invalidate confinement claims |
| Candidate generator or learner, including an LLM | untrusted | optimized to produce accepted candidates |
| Learner memory, checkpoints, and learned abstractions | untrusted artifacts | may be poisoned, stale, evaluator-aware, or authority-seeking |
| Candidate program and dependencies | untrusted | may be buggy, adversarial, or evaluator-aware |
| Candidate explanations and generated tests | untrusted evidence | may help investigation but cannot authorize promotion |
| Production/search telemetry | tainted input | may contain attacks, bias, corruption, or private data |
| External model/provider output | untrusted and potentially non-reproducible | outside local control |

Trust is not a statement of perfection. Trusted components need independent
tests, pinned versions, reproducible builds where feasible, and a documented
upgrade path.

## 5. Threat actors and failure sources

### 5.1 Optimizing candidate

A candidate can exploit any discrepancy between intended behavior and measured
behavior. It need not be consciously malicious; search systematically preserves
exploitable behavior when that behavior raises the score.

### 5.2 Candidate generator

A generator may propose dependency changes, hidden side effects, test-specific
behavior, resource exhaustion, or mutation outside its declared region. A remote
generator may also change behavior between calls.

### 5.3 Telemetry producer

Users, upstream systems, compromised clients, or the current candidate may poison
inputs and outcomes. Natural distribution shift can resemble an attack.

### 5.4 Maintainer or supply chain

An authorized operator may make an erroneous policy change or leak protected
holdout/audit data.
A compiler, dependency, base image, model, or artifact service may be compromised.

### 5.5 Statistical process

Even honest code and infrastructure can promote a regression due to noise,
repeated adaptive comparisons, nonstationarity, biased sampling, missing data, or
an invalid test.

## 6. Trust boundaries

The implementation must document and test these boundaries explicitly:

- process and user identities;
- filesystem mount and write permissions;
- network namespaces and egress policy;
- credential issuance and expiry;
- inter-process message schemas and size limits;
- observation ingestion and privacy filtering;
- candidate build and dependency resolution;
- evaluator data access;
- artifact signing and promotion;
- deployment traffic routing;
- rollback control and out-of-band shutdown.

A container alone is not a complete boundary. Defense in depth may include a
restricted IR, effect checking, process/container/VM or WASM isolation, seccomp or
equivalent syscall policy, cgroup-like resource limits, default-deny network, and
separate host identities.

## 7. Threats and required controls

| Threat | Required controls | Evidence required before autonomy |
| --- | --- | --- |
| Candidate changes its judge | Judge stored outside candidate namespace; signed epoch versions; separate identity | mutation campaign cannot alter contract, evaluator, ledger, or promoter |
| Candidate reads protected cases | separate operational/audit storage and identity; no inherited credentials; query-limited interface | access-control and exfiltration tests |
| Reward or metric hacking | hard constraints; sentinel metrics; explicit populations/denominators; adversarial cases | seeded gaming candidates are rejected |
| Metric suppression | independent collectors; missing/timeout/crash counts as declared failure | candidate cannot improve score by dropping observations |
| Test/evaluator detection | comparable environments; randomized cases; future-data evaluation; limited feedback | test-specific candidates fail prospective gate |
| Adaptive evaluator overfitting | search/operational-holdout/research-audit/future separation; query budgets; epoch-wide risk method | false-promotion simulation meets preregistered bound |
| Candidate escapes mutation scope | semantic and textual diff checks; dependency/build inspection; typed restricted IR | generated out-of-scope mutations are rejected |
| Capability escalation | effect/capability policy; external broker; default deny; runtime containment | adversarial forbidden-effect suite has zero escapes for claimed level |
| Sandbox escape | layered sandbox; patched/pinned runtime; no secrets on worker; disposable workers | documented penetration/fault campaign and residual risk |
| Resource exhaustion or replication | external CPU/memory/process/storage/network/token/cost leases; watchdog | champion remains available under hostile candidates |
| Prompt injection through traces | structured extraction; tainting; escaping; no executable trace interpolation | adversarial trace corpus cannot cross control boundaries |
| Action/parser/canonicalization differential | one versioned decoder and canonical form; differential round-trip tests across learner, checker, hash, and runtime | every adversarial serialization has one accepted meaning or is rejected consistently |
| Semantic feedback leakage | capability-scoped probes; minimum-disclosure schemas; query ledger; no audit access; counterexample budgets | reconstruction and adaptive-overfitting campaign stays within registered risk bound |
| Poisoned learner memory or checkpoint drift | content-addressed checkpoints/memory; source and disclosure lineage; isolated update jobs; rollback; independent re-evaluation | corrupted/stale/undeclared state is rejected and prior learner state is recoverable |
| Malicious learned abstraction | transparent lowering to fixed kernel; type/effect/capability checks; dependency and compatibility evidence | abstraction cannot widen authority or change primitive meaning in adversarial suite |
| Poisoned telemetry | authenticated independent collection; retention-controlled raw payloads; append-only hashes/tombstones; anomaly checks | poisoning experiment reports detection and residual effect |
| Dependency or build attack | allowlist/pin dependencies; hermetic build; SBOM; signatures; no install scripts by default | reproducible build and supply-chain scan |
| Time-of-check/time-of-use swap | content address every artifact; deploy evaluated bytes without rebuild | byte identity is verified at deployment |
| Audit tampering | append-only signed records, preferably copied off worker; corrections append | decision reconstructs after worker compromise simulation |
| Statistical false promotion | paired trials; anytime-valid or registered sequential method; practical effect; epoch-wide error budget | calibration simulation achieves target epoch error rate |
| Tail or minority regression | slice-specific and worst-case constraints; tail metrics | known rare-case suite and per-slice reports pass |
| Delayed/time-bomb failure | randomized/future shadow; canary holds; probation; ongoing revalidation | delayed fault injection is detected within target time |
| Feedback-loop oscillation | hysteresis; cooldowns; promotion-rate limit; original baseline retention | drift simulations bound churn and regret |
| Invalid candidate output | external output shield; reviewed fallback; violation counter independent of candidate | every seeded invalid decision is blocked before effect and candidate is removed |
| State poisoning | no candidate-private state initially; later versioned snapshots, isolation, schema validation, recovery compatibility | corrupt-state and cross-generation tests pass |
| Irreversible external effects | forbid initially; later route through idempotent broker and compensating operations | effect replay and rollback campaign |
| Rollback failure | exact last-known-good artifact/state; independent controller; regular drills | recovery objectives pass under fault injection |
| Signing-key or operator compromise | offline/threshold keys where warranted; rotation; least privilege; break-glass audit | recovery and key-rotation drill |

## 8. Metric integrity requirements

Every metric used for a constraint, objective, or sentinel must declare:

- semantic definition and units;
- eligible population and exclusion rules;
- numerator and denominator;
- aggregation and time window;
- behavior for missing, late, malformed, timed-out, and abstained results;
- trusted collector and calibration process;
- required sample size and uncertainty method;
- slices on which it is separately constrained;
- version and epoch.

For example, “accuracy” without a denominator permits a candidate to avoid hard
inputs. “Mean latency” without failure treatment permits fast crashes. “Cost per
successful request” without an availability sentinel may encourage rejection of
expensive requests.

## 9. System and authority axes

Autonomy is not a coherent scalar. Every experiment and deployment names a
profile `(R, M, G, L, D)`. Representation, generator, and learner update are
scientific treatments; mutation and deployment describe direct authority. Their
separation prevents, for example, calling an LLM more autonomous merely because
it uses a different serialization.

### 9.1 Representation and interaction

| Level | Learner-facing interface |
| --- | --- |
| R0 | unconstrained textual surface/patch generation for the same semantic kernel |
| R1 | grammar/type-constrained textual surface for the same semantic kernel |
| R2 | complete canonical typed AST/IR generation |
| R3 | incremental typed semantic actions with structured construction feedback |
| R4 | R3 plus an explicit typed/effect-checked abstraction layer lowered to a fixed kernel |
| R5 | latent/subsymbolic primitive or interpreter representation |

The first cycle studies R0–R3 and may progress to R4 only after abstraction
lowering and evidence gates pass. R5 is research-only and cannot authorize
deployment under this threat model. Execution-feedback detail is an independent
experimental treatment and evidence-disclosure risk within these levels.
R0–R3 comparisons use the same kernel and capability envelope; general host
source is M4, not an R0 baseline inside the initial confirmatory study.

### 9.2 Mutation surface

| Level | Candidate may change |
| --- | --- |
| M0 | nothing; evaluator validation only |
| M1 | identifier selecting among reviewed strategies |
| M2 | typed bounded parameters |
| M3 | total, typed, capability-limited policy IR/AST |
| M4 | bounded general source region |
| M5 | contract, supervisor, evaluator, compiler, or other TCB component |

The initial research cycle stops at M3. M4 is future work with a weaker
containment claim; M5 is prohibited by the external-judge decision.

### 9.3 Generator class

| Level | Proposal mechanism |
| --- | --- |
| G0 | fixed/manual candidate set |
| G1 | rule-based selector, enumerator, or discrete search |
| G2 | numerical parameter optimizer |
| G3 | symbolic, rewrite, genetic, or enumerative program search |
| G4 | LLM-backed proposal compiled into the current mutation surface |
| G5 | hybrid self-orchestrating generator invoking multiple tools, models, or searchers |

These labels identify generator mechanisms, not a capability ordering. G4 or G5
does not imply broader mutation or deployment authority than G3. G5 is out of
scope for the initial trust model because its tool and data-flow surface requires
separate analysis. Learner self-update is described by `L`; authority changes are
prohibited at L5 rather than hidden in `G`.

### 9.4 Learner update

| Level | State changed by feedback |
| --- | --- |
| L0 | none; proposals are independent of outcomes |
| L1 | run-scoped context, search state, or branch priorities |
| L2 | governed persistent feedback-conditioned retrieval, library, or proposal-policy state derived from prior runs/lineage |
| L3 | versioned model weights/checkpoint |
| L4 | untrusted learner algorithm or model architecture |
| L5 | contract, judge, authority policy, or other trusted implementation |

The initial cycle stops at L2. L3 and L4 require a new review of training-data
provenance, poisoning, reproducibility, containment, and learner rollback. L5 is
prohibited by the external-judge decision.

`L` records the highest update class actually used and does not imply that every
lower mechanism was present. Runs also list concrete mechanisms; for example, L3
weight updates do not imply an L2 learned library. R4 is independently usable at
L0 with a fixed abstraction library. G0/L1+ is invalid for a fixed/manual set and
must be reclassified when a feedback-conditioned proposal mechanism exists.

### 9.5 Deployment authority

| Level | Execution authority |
| --- | --- |
| D0 | offline deterministic simulator only |
| D1 | counterfactual stateful shadow; no served effects |
| D2 | human-authorized, shielded reversible canary |
| D3 | contract-authorized auto-canary and probation |
| D4 | bounded automatic stable promotion within an epoch |
| D5 | unbrokered or irreversible effects |

The first implementation begins around `(R2, M1, G1, L1, D0)`, then studies
R2/R3 with M2/M3, compatible G1–G4 generators, L0/L1, and D0/D1. Persistent
abstraction learning targets `(R4, M3, G3/G4, L2, D1)`, with R4/L0 and R3/L2
controls. D2, D3, and D4 require separate evidence and claims; D5 is prohibited
initially.

Each run records the actual R/M/G/L/D profile and feedback treatment separately
from its maximum authorized M/D ceiling. Authorization is not evidence that the
capability was exercised, and an observed treatment does not silently authorize a
higher one.

## 10. Meaning of “deploy once”

Within this project, deploy-once autonomy means:

> A human deploys a governed supervisor and evolvable target once; the supervisor
> may perform repeated adaptations inside the signed epoch contract until a stop
> condition occurs.

It does not mean maintenance-free operation forever. Security patches, key
rotation, hardware and dependency changes, privacy requests, evaluator defects,
and new objectives require external governance and usually a new epoch.

The long-term deploy-once research target is bounded stable promotion at no more
than `(R4, M3, G4, L3, D4)` under a fixed signed epoch. That profile is an
aspiration, not a current capability or assurance claim. R4, L3, and D2–D4 must
each earn separate evidence and review; R5 remains outside deployable scope under
this threat model. The target’s mechanism list includes persistent abstraction
state and weight updates; the L3 label alone would not assert both.

## 11. Fail-closed and fail-operational behavior

The evolution loop and the serving application have different failure policies:

- Uncertainty, missing evidence, budget exhaustion, evaluator failure, or policy
  disagreement fails closed for **promotion**.
- Failure of the search or evaluation plane must leave the last-known-good
  champion serving when safe to do so.
- A blocked `runtime_enforce` violation attempt or confirmed monitored hard-gate
  failure revokes the candidate, initiates the appropriate recovery action, and
  freezes further evolution until the incident is recorded and the resume policy
  is satisfied.
- Loss of trustworthy runtime monitoring revokes experimental traffic.
- Loss of ledger availability prevents new promotions.

## 12. Mandatory stop conditions

The supervisor must halt candidate generation or promotion when any of the
following occurs:

- a hard constraint or containment boundary is violated;
- evaluated and deployed artifact hashes differ;
- candidate IR, action-schema, canonicalization, learner checkpoint, or learned
  library identities differ from the versions recorded for evaluation;
- operational holdout or research-audit evidence may have leaked beyond its
  declared disclosure policy;
- the evaluator, metric collector, ledger, or signing identity loses integrity;
- rollback fails or last-known-good recovery is uncertain;
- a resource lease or epoch budget is exhausted;
- candidate churn exceeds its rate limit;
- statistical assumptions required by the promotion test are invalidated;
- telemetry schema or ground-truth source changes unexpectedly;
- the contract epoch expires;
- an authorized operator activates the kill switch.

The champion may continue operating only if its independent operational policy
allows it.

## 13. Residual and fundamental limits

- Semantic correctness of arbitrary Turing-complete candidates is undecidable in
  general. Restriction and evidence reduce risk; they do not abolish it.
- A perfectly implemented evaluator can still encode the wrong intention.
- A finite test suite cannot prove absence of all delayed or distribution-specific
  failures.
- Repeated interaction leaks information about an evaluator even without direct
  data access.
- Isolation depends on lower-level hardware and software with their own defects.
- Rollback cannot automatically reverse every external real-world effect.
- Optimization under changing distributions may oscillate or become net
  negative.

Claims must be scoped to a representation, learner-update mode, mutation
language, generator, deployment authority, threat model, workload family,
evidence protocol, and observation horizon.

## 14. Security research agenda

The repository should eventually include an adversarial-candidate corpus with
programs that intentionally:

- return fast incorrect answers;
- skip difficult inputs;
- falsify or suppress metrics;
- detect public tests;
- read hidden data or credentials;
- alter generated tests or build scripts;
- consume excess CPU, memory, disk, processes, network, or model tokens;
- delay failure until after canary holds;
- poison shared state or future observations;
- exploit program/action parser or canonicalization differentials;
- poison persistent learner memory, checkpoints, or retrieved lineage;
- introduce an abstraction whose lowering, effects, or compatibility differ from
  its declared interface;
- exploit parser, archive, compiler, and sandbox edges;
- make rollback-incompatible changes;
- introduce cumulative small regressions relative to the original baseline.

The strong confinement claim is falsified by any forbidden effect that escapes
the declared boundary. Escapes are incident reports and research results, not
cases to remove silently from the benchmark.

## 15. Review triggers

This threat model must be reviewed when:

- a new mutation level is enabled;
- a new representation or learner-update level is enabled;
- network, secrets, persistent state, or external effects enter scope;
- a new language, compiler, sandbox, model provider, or deployment target is used;
- promotion becomes more autonomous;
- a containment or hard-constraint incident occurs;
- the evaluator or evidence policy changes materially;
- six months pass since the previous review.
