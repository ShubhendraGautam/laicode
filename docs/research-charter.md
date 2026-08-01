# Research charter

**Status:** draft for project review
**Last updated:** 2026-07-31
**Owner:** to assign

## 1. Purpose

LAIcode investigates whether a model-native programming representation can help
machine learners construct and improve executable programs from structured
semantic feedback, and whether an external language/runtime can govern the
continual, bounded evolution of those programs using evidence gathered from
their executions.

The project is research-grade from its first implementation in the following
sense:

- claims are operationalized before experiments are run;
- baselines and disconfirming results are designed in;
- correctness and safety constraints are separate from optimization objectives;
- adaptive search is evaluated on data that search did not observe;
- all artifacts and decisions are reconstructible, and measurements/results are
  reproducible within preregistered tolerances and dependency limitations;
- negative results remain first-class results.

“Research-grade” does **not** mean “safe for unsupervised production use.” That
claim requires evidence the project does not yet have.

## 2. Object of study

The object of study is an **evolutionary programming system**, consisting of:

1. an evolution-contract language;
2. a model-facing typed candidate IR and semantic action/observation protocol;
3. a trusted supervisor that interprets and enforces the contract;
4. one or more candidate generators or machine learners;
5. versioned search, lineage, and learned-abstraction state;
6. isolated build and execution environments;
7. evaluators and verifiers;
8. a version and evidence ledger; and
9. bounded deployment and rollback machinery.

The initial artifact may use embedded DSLs and a runtime hosted by an existing
language. The evolution contract and candidate program IR are different language
planes: the former expresses human-governed authority, while the latter is the
machine-constructed solution space. A standalone surface syntax or compiler is
justified only if experiments show value beyond a library, protocol, or
configuration format.

## 3. Operational definitions

### 3.1 Self

For the initial research cycle, “self” is the declared target application across
its candidate lineage: the current champion, its permitted mutable implementation
or policy state, and immutable candidate/lineage identity and history. It does
not include proposal/search state, retrieval memory, learned libraries,
checkpoints, the contract, supervisor, required evaluator, compiler/runtime
trusted for confinement, or the underlying generator model.

The initial claim is therefore application self-evolution, not recursive
self-improvement of the entire evolutionary system. Initial model-native studies
use fixed or run-scoped learners outside `self`. Later governed studies may make
versioned learner memory, libraries, or checkpoints evolvable untrusted
artifacts and define a separate **learner self**, but that expansion requires an
explicit reviewed decision and never includes the contract or judge in candidate
authority.

### 3.2 Execution observation

An execution observation is a versioned, schema-checked record of an input,
relevant environment state, observable outcome, resource measurements, and any
delayed ground-truth signal. Telemetry without an outcome is performance data,
not correctness evidence.

### 3.3 Learning

The evolutionary **system adapts** when observations change which implementation
or policy is retained. A **machine learner learns from execution** only when
permitted execution evidence changes its future proposal distribution through
context/search state, feedback-conditioned retrieval/proposal state derived from
lineage, a learned abstraction library, a policy, or model weights. These are
separate outcomes and must be reported at their declared learner-update level.

Merely logging executions is observation. Best-of-N selection can adapt the
application without changing the generator. Repeated rebuilding without retained
information is search without learner memory. Learner learning need not mean
updating neural-network weights, but weight learning must not be implied when only
lineage or run-scoped state changed.

### 3.4 Candidate

A candidate is an immutable content-addressed program artifact. Its append-only
ledger record additionally contains:

- its parent or parents;
- generator and generator configuration;
- declared mutation scope;
- build environment;
- evaluation inputs and results;
- resource consumption;
- provenance and timestamps.

### 3.5 Improvement

Given baseline version `b`, candidate `c`, workload distribution `W`, hard
constraints `K`, objective vector `O`, practical effect threshold `delta`, and
confidence rule `C`, `c` is an improvement only if:

1. `c` satisfies every constraint in `K`;
2. `c` is non-inferior on protected objective dimensions;
3. `c` improves at least one declared objective by `delta` under `C`;
4. the result holds on evaluation data unavailable to the candidate generator;
5. the result survives the declared rollout horizon; and
6. every search, evaluation, deployment, and recovery cost is reported.

The term **net improvement** is permitted only when objective benefit and cost
share a registered conversion or utility model with sensitivity analysis. When
they do not, results must report an objective/cost Pareto frontier or
cost-efficiency curve rather than inventing a scalar net value or break-even
point.

A promotion is a decision under uncertainty. It is not itself proof of
improvement.

### 3.6 Self-improvement

A system demonstrates self-improvement over horizon `H` only when improvements
are produced by the deployed observe–propose–evaluate–promote loop, rather than
manual source edits, and validated on future observations within `H`.

We will report at least four distinct outcomes:

- **search success:** the loop found a candidate that passes its selection gate;
- **offline generalization:** the candidate improves on a post-freeze research
  audit set that did not influence current-study decisions;
- **prospective shadow performance:** a stateful counterfactual twin improves on
  future inputs without affecting the served system;
- **online canary effect:** the candidate improves when its decisions affect a
  bounded share of real or deployment-like execution;
- **sustained improvement:** benefits persist across the preregistered horizon
  while satisfying every registered proof, enforcement, test, and monitoring
  decision rule at its stated evidence strength.

These labels must never be collapsed into a single “self-improved” result.

### 3.7 Evolution epoch

An epoch is an interval during which the objective definitions, hard constraints,
evaluator implementations, and promotion policy are immutable. Changing the
judge starts a new epoch and breaks direct comparability unless a bridging
evaluation is run.

### 3.8 Generation

Generation is the untrusted act of proposing one or more immutable candidate
artifacts from declared parents, visible evidence, and a bounded budget. A
generation does not imply acceptance, lineage advancement, or deployment. When
discussing graph position, use **lineage depth** rather than assuming that every
branch shares a single generation number.

### 3.9 Deployment

A deployment is a signed supervisor decision granting an exact artifact an
expiring execution lease in a declared shadow, canary, probation, or stable
context. Building, replaying, or scoring a candidate offline is evaluation, not
deployment. Deployment authority is reported separately using the `D` axis in
the threat model.

### 3.10 Model-native programming

Model-native programming uses a canonical typed program representation and a
structured semantic action/observation protocol designed for machine
construction. A model may still emit a token serialization; the authoritative
actions denote program-state transitions, and feedback carries types, effects,
obligations, execution results, counterexamples, resources, uncertainty, and
provenance rather than only source text and compiler prose.

The complete operational design and representation (`R`) and learner-update
(`L`) axes are defined in the model-native programming document. Source syntax is
a projection and transport, not candidate identity.

## 4. Central thesis and contribution boundary

### Model-native representation thesis

Under matched model, information, evaluator-query, and compute budgets, a typed
compositional program-action space with structured semantic feedback can improve
verified task success, cost-to-solve, repair efficiency, and held-out transfer
relative to unconstrained source completion or text-patch generation.

### Evolution-governance thesis

A declarative evolution contract, enforced by a supervisor outside the mutable
program, can make continual program search more auditable and safer while
retaining measurable optimization benefit under workload drift.

### Contribution under test

Prior work already integrates substantial subsets of structured code generation,
execution-guided synthesis, learned DSL libraries, language-supported runtime
adaptation, online learning, synthesized variants, formal feedback loops, and
runtime assurance. The contribution below is a gap hypothesis, not an established
novelty claim.

The intended contribution is the combination of:

- a model-facing typed semantic IR with incremental construction and structured
  execution/proof feedback;
- a stable verifier-grounded kernel plus a versioned, transparent
  learned-abstraction layer;
- language semantics that separate mutable implementation from immutable
  constraints and externally owned evidence;
- a candidate lifecycle whose promotion decisions are replayable;
- first-class multi-objective and resource-budget semantics;
- continual evaluation under temporal drift and repeated adaptive search;
- evidence about which assurance mechanisms reduce false promotions and at what
  cost.

### Program-level falsification conditions

The representation thesis is not supported if structured actions improve only
syntactic validity, fail to improve protected semantic outcomes or cost, are
matched by an ordinary canonical AST with the same scaffold, or prevent compact
solutions to the target family. The governance thesis is not supported if,
across registered study domains and matched budgets, the contract/runtime cannot
enforce its claimed authority boundary, decisions cannot be reconstructed, or
assurance does not reduce false promotion or recovery risk relative to strong
conventional pipelines. Optimization results also fail if apparent gains do not
persist on post-freeze or prospective evidence. The novelty hypothesis fails
independently if a completed literature review finds the same combination
already demonstrated.

### Explicitly insufficient contributions

None of the following is sufficient on its own:

- prompting an LLM to rewrite a file repeatedly;
- serializing an ordinary AST as JSON and calling it model-native;
- increasing parse/type validity without improving semantic success or cost;
- selecting the fastest candidate on visible tests;
- tuning configuration parameters with an optimizer;
- demonstrating one improvement on one benchmark;
- placing ordinary CI around generated code;
- calling a program “self-improving” because it retrains a model.

## 5. Research questions

### RQ1 — Contract expressiveness

Can an evolution-contract language express realistic objectives, hard
constraints, mutation scopes, evidence requirements, and rollout policies
without embedding application-specific supervisor code?

**Measures:** contract size and complexity, number of host-language escape
hatches, specification defects, and coverage across benchmark domains.

### RQ2 — Assurance

Does enforcing the evolution contract reduce false promotions, constraint
violations, and time to recovery compared with convention-based optimization
pipelines?

**Measures:** false-promotion rate, escaped violations, detection latency,
rollback latency, and assurance overhead.

### RQ3 — Optimization efficacy

Can the closed loop produce improvements on future unseen workloads compared
with static optimization and established adaptive-search baselines, at what full
adaptation cost?

**Measures:** objective and cost vectors, cost-efficiency frontiers, search cost,
time-to-improvement, and percentage of future windows in which the promoted
version remains on the Pareto frontier. Net utility is reported only when a
common utility model was preregistered as required by Section 3.5.

### RQ4 — Repeated adaptation

How quickly does adaptive overfitting accumulate across generations, and which
evidence-separation policies best preserve future generalization?

**Measures:** selection-to-test gap by generation, test reuse count,
false-discovery rate, lineage depth, and post-promotion regret.

### RQ5 — Distribution shift

Under which forms and rates of workload drift does continual evolution outperform
a fixed program, periodic offline retuning, or strategy selection alone?

**Measures:** recovery time after a change point, dynamic regret, constraint
violations during recovery, and total adaptation cost.

### RQ6 — Generator dependence

Which results come from the language/runtime rather than the candidate generator?

**Measures:** outcomes across predefined selection, parameter search,
grammar-based mutation, genetic improvement, and LLM-based generation while
holding the evaluator and promotion protocol fixed.

### RQ7 — System boundary

Which combinations of representation `R`, mutation surface `M`, generator class
`G`, learner-update mode `L`, and deployment authority `D` can operate while
meeting preregistered semantic-success, false-promotion, containment,
auditability, and recovery targets under a registered execution-feedback
treatment `F`?

**Measures:** intervention frequency, unsafe proposal rate, containment failures,
unexplained decisions, recovery success, and the tested `(R, M, G, L, D)`
profile.

### RQ8 — Model-facing representation

Under matched model, information, evaluator-query, compute, and monetary budgets,
does an incremental typed semantic action space improve verified held-out task
success or cost-to-solve relative to source text, constrained text, complete AST
generation, and an established typed DSL?

**Measures:** semantic success at budget, parse/type/effect validity, verifier
rejection, actions/tokens/evaluator calls to threshold, semantic diversity,
description length, and human primitive-engineering effort.

### RQ9 — Semantic feedback and learner change

Which feedback changes future program construction: compiler prose, scalar
execution reward, structured values/traces, counterexamples, proof obligations,
or resource/effect deltas? Does persistent learner state outperform independent
search on later tasks?

**Measures:** repair steps, future-proposal distribution change, protected task
success, leakage, evaluation calls, transfer efficiency, and results by `L`
level.

### RQ10 — Learned abstraction transfer

Can a learner discover transparent abstractions over a stable kernel that reduce
future description length and search cost on withheld compositions without
expanding effects or weakening verification?

**Measures:** abstraction reuse, compression, held-out compositional success,
cost-to-solve, library growth, equivalence/check evidence, and regression rate.

## 6. Initial hypotheses

The hypotheses below are directional starting points, not facts.

- **H1:** Explicit mutation scopes and external hard constraints reduce escaped
  behavioral regressions relative to repository-level unconstrained generation.
- **H2:** A three-way split—search, operational holdout, and post-freeze research
  audit—reduces the generation-dependent generalization gap relative to
  repeatedly selecting on one benchmark.
- **H3:** Strategy selection or parameter tuning captures most early improvement;
  unrestricted code generation adds search cost and failure rate before it adds
  consistent benefit relative to its cost frontier.
- **H4:** Under temporal workload drift, bounded continual adaptation yields
  lower dynamic regret than a fixed implementation, but only above a measurable
  drift/benefit threshold due to search cost.
- **H5:** Shadow and canary evidence reduce false promotions compared with offline
  replay alone, especially for stateful and concurrent targets.
- **H6:** Evidence and lineage requirements add overhead, but the overhead is
  bounded and smaller than the expected cost of escaped regressions in the
  selected study domains.
- **H7:** Incremental typed semantic actions improve
  cost-normalized held-out semantic success over an unconstrained textual surface
  for the same kernel after holding the model, task information, `F` treatment,
  mutation surface, and evaluator/compute budget fixed.
- **H8:** Structured counterexamples and execution traces reduce repair steps and
  evaluator calls relative to compiler prose or scalar reward under matched
  case/query/risk and compute budgets, without consuming protected audit
  evidence. Feedback information content is the intervention, not a controlled
  constant.
- **H9:** Typed/effect-checked learned abstractions with machine-checkable
  lowering reduce search cost on withheld compositional tasks relative to a fixed
  library; memorized abstractions that do not transfer do not satisfy this
  hypothesis.

Every experiment must identify which result would falsify its hypothesis.

## 7. Formalization agenda

The first prototype should have a small enough core to state and test—or
mechanize where feasible—the following properties:

- **IR confinement:** a well-typed candidate in the initial policy IR terminates
  within a statically or externally bounded step budget, reads only its declared
  input/state, invokes no forbidden effect, and returns either a value of the
  declared type or a controlled failure.
- **Action preservation:** every accepted model action transforms a schema-valid
  program state into another schema-valid state and cannot silently widen its
  type, effect, capability, evidence, or mutation authority.
- **Transparent abstraction lowering:** every accepted learned abstraction has a
  deterministic lowering into the fixed kernel with the declared type/effect
  behavior, or is rejected rather than becoming a new primitive meaning.
- **Mutation confinement:** accepting an artifact implies that every semantic
  component changed by the artifact lies within its contract-authorized mutation
  scope, under an explicitly stated model of builds and dependencies.
- **Promotion authorization:** every supervisor transition to `eligible`,
  `canary`, or `promoted` corresponds to a complete evidence record satisfying
  the normalized epoch policy.
- **Artifact identity:** the artifact receiving a deployment lease has the same
  content identity as the artifact evaluated for that decision.
- **Lineage integrity:** every non-root candidate names existing immutable parents
  and ledger events cannot rewrite prior history.
- **Judge non-authority:** no capability available to candidate code can mutate
  or authorize the contract, required evaluator, evidence partitions, ledger,
  promoter, or rollback controller.

These are conditional system properties: they depend on the formal semantics and
trusted implementation. They do not prove that an empirical metric captures
human intent, that finite tests imply general correctness, or that a candidate
will improve on every future distribution.

## 8. Non-goals for the first research cycle

- General artificial intelligence or open-ended recursive self-improvement.
- Claiming that an LLM ceases token prediction internally or that structured
  syntax by itself causes symbolic/logical reasoning.
- Allowing a candidate to rewrite the supervisor, evaluator, policy, audit log,
  or containment layer.
- Optimizing subjective human outcomes without an independent feedback design.
- Safety-critical, medical, financial, weapons, or physical-control deployment.
- Claiming semantic equivalence for arbitrary programs.
- Training a foundation model from scratch.
- Building a new general-purpose parser, compiler backend, package manager, and
  operating system before the evolution semantics are validated.
- Using live users as an unreviewed exploration environment.

## 9. First benchmark program

The recommended first target is a cache-eviction policy executed in a simulator:

- the candidate is a pure `select_victim(snapshot) -> key` function over the
  contract domain where `snapshot.evictable_keys` is nonempty;
- exact properties require the result to exist, be evictable, and not be pinned;
- the simulator contains external effects and makes runs replayable;
- recency/frequency and all other policy state is simulator-owned and included in
  the immutable input snapshot; initial candidates have no private persistent
  state;
- miss ratio provides a delayed quality outcome;
- decision latency, memory, and total evolution cost are measurable;
- access traces can shift in locality, working-set size, skew, scans, and bursts;
- reviewed policies provide fixed and adaptive baselines;
- the mutation surface can grow from strategy selection to a typed policy IR.

This domain is intentionally less glamorous than autonomous repository editing.
It provides controlled drift and exact decision-validity properties while still requiring
the system to learn from consequences over a trace. A deterministic
data-transformation engine is the planned second domain for exact whole-output
equivalence and structural rewrite experiments.

The cache study primarily validates governance, delayed execution outcomes, and
early R2/R3 construction. It cannot by itself support a broad claim about
language expressivity, learned abstractions, or cross-task transfer. Those claims
require a compositional multi-task transformation curriculum with withheld
operator combinations and matched representation treatments.

### Experimental stages

| Stage | Mutable surface | Generator | Main question |
| --- | --- | --- | --- |
| E0 | none | fixed baseline | Can evaluation be replayed exactly? |
| E1 | strategy identifier | bandit/search | Does the loop adapt under drift? |
| E2 | typed parameters | Bayesian/evolutionary search | Is tuning cost-efficient? |
| E3 | typed cache-policy IR | rewrite/genetic/enumerative search | Can structural changes stay valid? |
| E4 | typed cache-policy IR | LLM generator | Does generative search add value without broader authority? |

General source-region mutation belongs to the future M4 mutation level and is not
part of the initial research cycle.

A later stage may not begin until the previous stage’s evidence and containment
gates pass.

## 10. Claims ladder

Project communications must use the narrowest supported claim:

| Level | Allowed claim | Required evidence |
| --- | --- | --- |
| C0 | “The design supports candidate evolution.” | executable design and tests |
| C1 | “The system finds offline improvements.” | post-freeze research-audit results over repeated seeds |
| C2 | “The system adapts under simulated drift.” | temporal benchmark and adaptive baselines |
| C3 | “The system improves in counterfactual shadow operation.” | prospective twin-state shadow results and cost accounting |
| C4 | “The system produces a bounded online canary effect while meeting declared assurance targets.” | canary, shield, recovery, adversarial campaign, and sustained horizon |
| C5 | “The approach generalizes across domains.” | preregistered multi-domain replication |

No result at one level implies a result at the next.

Model-native programming claims use a separate ladder:

| Level | Allowed claim | Required evidence |
| --- | --- | --- |
| P0 | “The system exposes a typed semantic action interface.” | executable semantics and transition tests |
| P1 | “The interface prevents specified invalid constructions.” | adversarial syntax/type/effect action corpus |
| P2 | “The interface improves model programming under matched budget.” | paired R0–R3 study with protected semantic outcomes |
| P3 | “Execution-conditioned learner state improves future tasks.” | L0/L1/L2 ablation and held-out task transfer |
| P4 | “The language grows useful abstractions.” | R4 library reuse, lowering evidence, transfer, and cost frontier |

P1 is a validity result, not evidence for P2. P2 does not imply that a model has
learned unless future proposal behavior changes under a registered `L` treatment.

## 11. Evidence policy

Research artifacts must include:

- the exact contract and supervisor version;
- candidate and parent content hashes;
- generator/model/provider versions and prompts when legally publishable;
- dependency and execution-environment lock data;
- seeds and nondeterminism notes;
- raw per-trial results, including rejected and failed candidates;
- evaluator and dataset hashes;
- total CPU/GPU time, elapsed time, tokens, and estimated monetary cost;
- analysis scripts that regenerate every reported table and figure;
- negative and null results;
- a documented path for an independent operator to reproduce the result.

## 12. Ethical and release posture

The default release target is a contained research system. Features that permit
unbounded filesystem, network, credential, deployment, or supervisor mutation
are out of scope.

Before any public autonomous deployment, the project must document:

- who bears the risk of a bad candidate;
- who can stop the loop and how quickly;
- which data subjects supplied telemetry;
- how data is minimized and retained;
- how vulnerabilities are reported;
- which claims are supported and which remain speculative.

## 13. Phase-0 exit criteria

Phase 0 is complete only when:

- key terminology and the improvement predicate are agreed;
- the representation, feedback, mutation, generator, learner-update, and
  deployment treatments/axes are accepted;
- Decision 0002 is accepted or replaced before freezing the candidate
  kernel and action schema;
- the first benchmark, fixed baselines, and drift scenarios are specified;
- every initial hypothesis has a falsification condition;
- the evolution-contract minimal schema is frozen for the first prototype;
- the candidate IR and model action/observation schema are frozen for the first
  representation experiment;
- the threat model has an owner and review date;
- the experiment manifest can describe the first full study;
- no implementation decision silently expands the mutable surface.
