# Design and research checklist

**Status:** active from Phase 0
**Last updated:** 2026-08-01

## How to use this checklist

This is a set of stage gates, not a backlog. A box is complete only when the
repository links to reviewable evidence: a decision record, test, schema,
measurement, or artifact. “We intend to do this” does not satisfy a gate.

For each active item, track:

```text
owner:
evidence:
reviewer:
reviewed_at:
next_review:
```

Items marked **BLOCKER** prevent entry into the next stage. If an item is not
applicable, record why and which assumption makes it unnecessary.

## Gate 0 — Research identity

- [ ] **BLOCKER:** Define `self`, `execution observation`, `learning`,
  `candidate`, `improvement`, `generation`, `epoch`, and `deployment`.
- [ ] **BLOCKER:** Define `model-native`, `semantic action`, learner learning,
  application adaptation, vocabulary evolution, and semantic evolution without
  implying that a token model stops predicting symbols internally.
- [ ] **BLOCKER:** State the narrow central thesis and its falsification
  conditions.
- [ ] **BLOCKER:** Choose the initial and maximum reviewed representation (`R`),
  mutation (`M`), generator (`G`), learner-update (`L`), and deployment (`D`)
  profiles, plus the execution-feedback (`F`) treatments and disclosure limits.
- [ ] Define non-goals and prohibited deployment domains.
- [ ] Separate research claims from product aspirations.
- [ ] Define the claims ladder from offline search through bounded auto-promotion.
- [ ] Record the first benchmark population and why it represents the research
  question.
- [ ] Identify who owns scientific, safety, security, privacy, and operational
  decisions; one person may initially hold several roles, but the roles stay
  conceptually separate.
- [ ] Establish a decision-record format and record irreversible choices.
- [ ] Schedule periodic charter and threat-model review.

**Exit evidence:** accepted research charter, threat-model scope, first experiment
title, and owners.

## Gate 1 — Novelty and prior art

- [ ] **BLOCKER:** Do not claim invention of self-improving software or the
  generate–execute–select loop.
- [ ] Complete registered literature-search strings and inclusion criteria.
- [ ] Search programming languages, synthesis, genetic improvement, automated
  repair, superoptimization, emergent/self-designing software, dynamic software
  updating, autonomic systems, runtime assurance, adaptive data analysis, safe
  learning, and deployment provenance.
- [ ] Include neural program synthesis, structured/typed code generation,
  execution-guided repair, learned DSL/library/grammar work, neuro-symbolic and
  differentiable languages, typed-hole editors, and tactic/program learning.
- [ ] Include peer-reviewed work and clearly label preprints/product reports.
- [ ] Perform backward and forward citation snowballing from closest work.
- [ ] Build a feature matrix covering mutation unit, judge, trust, deployment,
  drift, statistics, provenance, and rollback.
- [ ] Maintain a claim-to-source table.
- [ ] Ask researchers from self-adaptive systems, programming languages/systems
  security, and neural program synthesis/program learning to challenge the gap
  hypothesis.
- [ ] Revise or abandon a proposed contribution when prior art already covers it.

**Exit evidence:** dated literature corpus, extraction table, and a provisional
novelty statement with explicit uncertainty.

## Gate 2 — Evolution-contract semantics

### Subject and versioning

- [ ] **BLOCKER:** Identify the exact evolvable subject and public interface.
- [ ] Define an operational or denotational semantics for the minimal candidate
  IR and supervisor transition core.
- [ ] Define canonical contract serialization and content hashing.
- [ ] Define material contract change and epoch-transition semantics.
- [ ] Define how baselines bridge two epochs.
- [ ] Reject unknown or ambiguous contract fields rather than ignoring them.

### Model-native representation and interaction

- [ ] **BLOCKER:** Separate the human-governed evolution contract, trusted
  candidate semantic kernel, and learner-mutable transparent abstraction layer.
- [ ] **BLOCKER:** Specify operational semantics for partial program states and
  every accepted/rejected model action.
- [ ] Define canonical program identity independently of formatting, names, and
  transport serialization.
- [ ] Define typed holes, scopes, constructors, effects, capabilities, resources,
  and proof obligations visible at each action.
- [ ] Define an episodic `open`/`step`/`probe`/`commit` protocol with structured,
  versioned action and observation schemas.
- [ ] Prove or test that an accepted action cannot silently widen type, effect,
  capability, evidence, mutation, or deployment authority.
- [ ] Define learned-abstraction lowering, compatibility, provenance, evidence,
  retirement, and library-growth limits.
- [ ] Ensure human-readable source, machine representation, graph, and diagnostic
  views round-trip to one authoritative object.
- [ ] State the expressivity/searchability/verifiability frontier and define the
  benchmark coverage and escape-hatch measures.

### Mutation authority

- [ ] **BLOCKER:** Declare allowed parameter, strategy, AST/IR, source, build,
  dependency, and state changes separately.
- [ ] Declare frozen regions and prove or check enforcement within the claimed
  scope.
- [ ] Account for generated files, macros, build scripts, plugins, dynamic loads,
  and transitive dependencies.
- [ ] Define a complexity or artifact-growth policy.
- [ ] Define the parent/merge semantics for candidate lineage.
- [ ] State the confinement, promotion-authorization, artifact-identity, and
  lineage-integrity properties with all trust assumptions.

### Capabilities and effects

- [ ] **BLOCKER:** Default all effects to denied.
- [ ] Declare filesystem, network, process, clock, randomness, environment,
  credential, model, and external-service capabilities.
- [ ] Keep effect enforcement outside candidate authority.
- [ ] Define behavior for an undeclared or unclassifiable effect.
- [ ] Define capability deltas as part of candidate comparison and risk.

### Correctness and constraints

- [ ] **BLOCKER:** Identify an independent source of truth for each correctness
  claim.
- [ ] Separate deterministic invariants, probabilistic constraints, objectives,
  sentinel metrics, and budgets.
- [ ] Classify each requirement as `prove`, `runtime_enforce`, finite `test`, or
  `statistically_monitor`; only the first two may support `always` wording within
  their declared model.
- [ ] Never permit objective improvement to compensate for a hard failure.
- [ ] Label proofs, exhaustive checks, translation validation, differential
  tests, properties, examples, and learned judgments as different evidence
  classes.
- [ ] Define temporal/state invariants or prohibit the relevant state.

### Objectives and acceptance

- [ ] Define objective direction, unit, population, denominator, window, and
  missing-data behavior.
- [ ] Choose Pareto, constrained, or lexicographic comparison explicitly.
- [ ] If scalar weights are used, record normalization and sensitivity analysis.
- [ ] Define non-inferiority dimensions.
- [ ] Define minimum practical effects and uncertainty requirements.
- [ ] Define tie-breaking toward lower risk or simpler candidates.

### Budgets and halt policy

- [ ] Declare per-candidate, per-epoch, and per-time-window resource limits.
- [ ] Include CPU/GPU, memory, storage, processes, wall time, network, tokens,
  evaluator queries, and money where applicable.
- [ ] Define candidate-churn and promotion-rate limits.
- [ ] Define every automatic halt, freeze, resume, and epoch-expiry condition.

**Exit evidence:** a minimal contract schema, static examples and counterexamples,
and executable validation tests.

## Gate 3 — Root of trust and containment

- [ ] **BLOCKER:** Enumerate the complete trusted computing base.
- [ ] Include independent metric collectors/reference monitors, evidence
  storage, artifact registry/deployer, router, signing/key service, trusted time,
  lease enforcement, and the candidate semantic kernel/action validator in the
  TCB or assurance-dependency inventory.
- [ ] **BLOCKER:** Prove by access-control test that candidates cannot write the
  contract, required evaluators, evidence manager, ledger, promoter, or rollback
  controller.
- [ ] Draw process, user/identity, filesystem, network, credential, and signing
  boundaries.
- [ ] Ensure no untrusted generator/candidate shares a control-plane process,
  identity, credentials, or address space.
- [ ] Ensure workers contain no unnecessary secrets.
- [ ] Issue short-lived, least-privilege capabilities.
- [ ] Use layered isolation appropriate to the candidate language and threat.
- [ ] Pin and patch the compiler/runtime relied on for safety claims.
- [ ] Produce dependency inventory/SBOM and verify signatures where supported.
- [ ] Make candidate build workers disposable.
- [ ] Treat compiler diagnostics, traces, prompts, model output, archives, and
  candidate manifests as hostile inputs.
- [ ] Bound message size, recursion, decompression, log volume, and artifact size.
- [ ] Keep the champion operational when the search plane fails, when safe.
- [ ] Provide an out-of-band kill switch and recovery identity.
- [ ] Define signing-key rotation and compromise recovery.
- [ ] Run an adversarial forbidden-effect suite.
- [ ] Before M3, mechanize or otherwise independently validate the claimed IR
  termination, typing, and effect-confinement properties.

**Exit evidence:** threat-boundary diagram, access tests, resource-exhaustion
tests, containment report, and documented residual risk.

## Gate 4 — Evidence and evaluator integrity

### Metric definitions

- [ ] **BLOCKER:** Specify every promotion metric completely, including failure,
  timeout, abstention, and missing-data behavior.
- [ ] Collect promotion and rollback signals independently of the candidate.
- [ ] Calibrate collectors and version their schemas.
- [ ] Add sentinel metrics for likely negative externalities.
- [ ] Define relevant tails and population slices.

### Partitioning

- [ ] **BLOCKER:** Separate search, operational holdout, post-freeze research
  audit, prospective future, and historical regression evidence.
- [ ] Enforce separate identities/storage for operational-holdout and
  research-audit evidence.
- [ ] Record every score disclosure and its precision.
- [ ] Set evaluator-query and feedback-detail budgets.
- [ ] Treat traces, counterexamples, proof failures, and structured diagnostics as
  evidence disclosures with provenance and leakage budgets.
- [ ] Never use the current study’s research audit for promotion; retire it after
  it influences any later search, design, or operational decision.
- [ ] Prefer temporal splits for workload adaptation.
- [ ] Check entity, duplicate, feature, and preprocessing leakage.

### Judge validation

- [ ] Build known equivalent, better, worse, invalid, and metric-gaming
  candidates.
- [ ] Estimate false-promotion and false-rejection behavior.
- [ ] Test test-aware and delayed-failure candidates.
- [ ] Test minority/tail regressions and cumulative parent-relative degradation.
- [ ] Validate metric direction, units, denominator, and aggregation.
- [ ] Calibrate an epoch-wide false-promotion/error budget across adaptive
  comparisons.
- [ ] Register maximum comparisons, an anytime-valid/sequential or otherwise
  justified method, and a power/sample-size rule.
- [ ] Confirm evaluator failure blocks promotion without taking down the champion.

**Exit evidence:** versioned metric dictionary, partition manifest, disclosure
ledger, and evaluator meta-test report.

## Gate 5 — Candidate lifecycle and provenance

- [ ] **BLOCKER:** Implement an externally enforced candidate state machine.
- [ ] Give every artifact and policy a content-derived identity.
- [ ] Record parents, generator, inputs, configuration, seed, and mutation report.
- [ ] Record representation/kernel/action-schema versions, accepted and rejected
  construction actions, probes, learner-update level, checkpoint, retrieval or
  search memory, and learned-library identity.
- [ ] Use hermetic and reproducible builds where feasible.
- [ ] Record all candidates, including malformed, rejected, crashed, dominated,
  and timed-out candidates.
- [ ] Separate candidate-supplied explanations from trusted evidence.
- [ ] Deploy byte-identical evaluated artifacts; never rebuild after evaluation.
- [ ] Record each transition guard and the exact rule that fired.
- [ ] Preserve the immutable original baseline, current champion, and
  last-known-good recovery artifact.
- [ ] Do not allow a rolled-back candidate to re-enter without a new identity and
  recorded justification.
- [ ] Make every promotion decision replayable from archived evidence.
- [ ] Copy critical lineage and decisions outside candidate workers.

**Exit evidence:** state-transition tests, sample evidence bundles, hash-identity
test, and full decision replay.

## Gate 6 — Experimental design

- [ ] **BLOCKER:** Freeze an experiment manifest before confirmatory search.
- [ ] State whether each run is exploratory or confirmatory.
- [ ] Register primary/secondary outcomes, exclusions, effect thresholds,
  analysis, budgets, and stop rules.
- [ ] Name the result that would falsify each hypothesis.
- [ ] Choose the correct experimental unit.
- [ ] Include no-op repetitions to quantify measurement noise.
- [ ] Include original fixed, current champion, random-search, domain-adaptive,
  and strongest practical baselines.
- [ ] Match compute, candidates, time, evaluator queries, and/or monetary budget.
- [ ] Use paired measurements and repeated trials when feasible.
- [ ] Run multiple independent search seeds.
- [ ] Address adaptive comparisons with the registered epoch-wide risk/error
  budget and disclosure accounting.
- [ ] Report effect sizes, intervals, raw distributions, and tails.
- [ ] Compare every champion to its parent and the original baseline.
- [ ] Include drift, recovery, and retained-performance evaluation.
- [ ] Include generator and assurance ablations.
- [ ] Compare R0–R3 using textual projections of the same kernel, capability
  envelope, and feedback treatment; treat general host source as a separate M4
  ecological comparison.
- [ ] At fixed R3, compare F0–F3 while matching case/query/risk and compute
  budgets; feedback information content is the intervention and must be reported.
- [ ] Cross abstraction support and learner persistence with R4/L0, R4/L1,
  R3/L2, and R4/L2 controls where feasible.
- [ ] Separate syntax/type validity from protected semantic success, repair
  efficiency, and held-out compositional transfer.
- [ ] Distinguish independent best-of-N search, lineage adaptation, run-scoped
  learner state, persistent memory/library learning, and weight learning.
- [ ] Record actual R/M/G/L/D mechanisms and `F` treatment separately from the
  maximum authorized mutation/deployment ceiling.
- [ ] Record deviations before inspecting their affected result where possible.

**Exit evidence:** registered manifest, analysis plan, power/budget rationale,
baseline implementations, and dry-run report.

## Gate 7 — Cost and sustainability

- [ ] Count unsuccessful generation and failed evaluation cost.
- [ ] Record compute, elapsed time, memory, storage, network, tokens, and money.
- [ ] Record model actions, rejected actions, probes/evaluator calls, repair steps,
  abstraction growth, and human primitive/specification engineering effort.
- [ ] Report supervisor, monitoring, shadow, and canary overhead.
- [ ] Report gross objectives, full costs, and their Pareto/cost-efficiency curve.
- [ ] Report net value and break-even only when a preregistered common utility or
  conversion model and sensitivity analysis justify them.
- [ ] Track artifact, dependency, build-time, and evaluator-cost growth.
- [ ] Define a complexity-debt or cleanup policy between epochs.
- [ ] Bound the evolution plane so it cannot starve the champion.
- [ ] State the environmental/energy measurement limitations if energy is not
  measured directly.

**Exit evidence:** per-candidate cost records, full-run cost report, and
cost-efficiency analysis; conditional net/break-even analysis where justified.

## Gate 8 — Shadow, canary, promotion, and rollback

- [ ] **BLOCKER:** Complete E0–E2 at D0/D1 before any M3 candidate can enter a
  canary.
- [ ] Run candidate/champion comparisons concurrently or control temporal
  confounding.
- [ ] Define shadow as a counterfactual twin whose internal state evolves under
  candidate decisions while served external effects remain suppressed.
- [ ] Put an independent output shield and reviewed fallback in front of every
  canary decision with an exactly checkable validity property.
- [ ] Define traffic stages, sample requirements, hold periods, and cooldowns.
- [ ] Use expiring deployment leases that candidates cannot extend.
- [ ] Monitor health and constraints outside candidate processes.
- [ ] Define probation after apparent promotion.
- [ ] Distinguish blocked enforcement attempts, monitored violations, normal
  lease expiry, regression rollback, security quarantine, retirement, and
  recovery.
- [ ] Exercise crashes, hangs, bad outputs, latency regressions, metric loss, and
  controller partitions.
- [ ] Freeze evolution after a hard incident until resume conditions are met.
- [ ] Test restoration of the exact last-known-good artifact and state.
- [ ] Forbid irreversible effects and schema migrations initially.
- [ ] For future stateful targets, specify atomic snapshots, backward
  compatibility, migration rollback, and compensating actions.
- [ ] Measure detection, revocation, and recovery latency.

**Exit evidence:** fault-injection report, rollback drill, independent monitoring
test, and signed deployment-policy example.

## Gate 9 — Data, ethics, and governance

- [ ] Identify data owners and legal/licensing basis for every trace or dataset.
- [ ] Minimize telemetry fields and define retention/deletion.
- [ ] Remove or protect secrets and personal data before generator access.
- [ ] Document sampling bias and affected populations.
- [ ] Define human review and appeal for subjective or user-impacting outcomes.
- [ ] Do not use live users as unreviewed exploration subjects.
- [ ] Document who bears the consequence of a failed candidate.
- [ ] Establish vulnerability and incident reporting processes.
- [ ] Review dual-use implications before releasing autonomous deployment
  machinery.

**Exit evidence:** dataset cards/provenance, privacy review, license inventory,
and incident contact.

## Gate 10 — Reproducibility and publication

- [ ] Archive exact repository, contract, evaluator, generator, environment,
  dataset, seed, and candidate versions.
- [ ] Archive raw model outputs when exact model reruns are unavailable.
- [ ] Archive canonical action traces, action/observation schemas, learner
  checkpoints/state, training disclosures, and learned abstraction libraries.
- [ ] Keep raw per-case and per-trial results only under their privacy/retention
  policy; retain append-only hashes, aggregates, decisions, and tombstones.
- [ ] Provide one command or documented workflow for a smoke reproduction.
- [ ] Generate every reported table and figure from archived raw data.
- [ ] Reproduce the main result in a clean environment.
- [ ] Have another person follow the artifact instructions without oral help.
- [ ] Publish negative/null results and all research incidents relevant to the
  claim.
- [ ] Distinguish peer-reviewed references, preprints, and product reports.
- [ ] Recheck the prior-art map immediately before publication.
- [ ] Scope the title, abstract, and conclusion to the demonstrated domain,
  `(R, M, G, L, D)` profile, and horizon.
- [ ] Target the exact ACM categories where relevant: Artifacts Available;
  Artifacts Evaluated—Functional/Reusable; and Results
  Validated—Reproduced/Replicated.

**Exit evidence:** archived artifact, clean-room reproduction log, claim-to-result
matrix, and limitations section.

## Automatic no-go conditions

Do not promote or broaden a research claim when any of the following is true:

- the candidate can change or impersonate its required judge;
- no independent correctness oracle or property exists;
- the only evidence is the data used to generate the candidate;
- a hard failure can be offset by a performance score;
- protected evidence has leaked or influenced decisions while still described as
  an untouched research audit;
- failed candidates or search costs were discarded;
- the deployed artifact differs from the evaluated artifact;
- rollback has not been exercised;
- a stronger conventional baseline was omitted without justification;
- results depend on one search seed or one noisy timing run;
- “self-improvement” refers only to an operational-holdout win;
- “model-native” evidence is only improved parse/type validity without protected
  semantic, cost, or transfer results;
- the system’s authority exceeds the reviewed threat model;
- an incident affecting validity or safety remains unresolved or undisclosed.

## Phase-0 definition of done

- [x] Initial research charter exists.
- [x] Initial system and trust-boundary design exists.
- [x] Initial threat model and independent system/authority axes exist.
- [x] Initial model-native language thesis and comparative design exist.
- [x] Seed prior-art map and provisional gap hypothesis exist.
- [x] Experiment protocol and first-study recommendation exist.
- [x] External-judge decision is recorded.
- [ ] Project owners review and amend the terminology and central thesis.
- [x] Cache-policy benchmark and reference simulator are specified precisely.
- [x] Minimal evolution-contract schema is frozen for prototype v0.
- [x] Minimal candidate kernel and model action/observation schema are frozen for
  prototype v0.
- [ ] Representation and feedback experiments are factored so neither changes
  mutation surface, task information, or learner persistence unintentionally.
- [x] First experiment manifest and evaluator meta-test corpus are written.
- [ ] Implementation language and isolation mechanism are chosen through a
  recorded decision.

The checked boxes establish scoped prototype evidence, not full experimental or
deployment readiness. The working run reaches
`(R2, M1, G1, L0, D0; F0)`; broader mutation, learner updates, and deployment
remain gated.
