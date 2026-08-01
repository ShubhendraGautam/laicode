# Experiment protocol

**Status:** draft protocol; experiment-specific methods remain to be registered
**Last updated:** 2026-07-31
**Owner:** to assign

## 1. Purpose

This protocol defines the minimum evidence for claims about LAIcode. It separates
finding a candidate from demonstrating that the candidate generalizes, survives
deployment-like conditions, and remains worthwhile when its full cost is shown.

An experiment that produces an impressive candidate but cannot reconstruct its
search, rejected siblings, evaluator disclosures, and total cost is a demo, not a
research result.

## 2. Study lifecycle

Every confirmatory study follows this sequence:

1. state the research question and falsifiable hypothesis;
2. freeze an experiment manifest;
3. validate the evaluator using candidates with known behavior;
4. run fixed and adaptive baselines;
5. run the candidate search without direct access to operational-holdout cases or
   any research-audit evidence;
6. select candidates using only the declared operational holdout and freeze the
   candidate and deployment-like study plan;
7. run prospective counterfactual-shadow/canary simulation exactly as frozen;
8. freeze current-study search, operational decisions, and analysis code;
9. evaluate once on the research audit set under the registered analysis;
10. report all trials, exclusions, incidents, and costs;
11. package artifacts so another operator can rerun the study.

Exploratory work is welcome but must be labeled exploratory. A hypothesis written
after results are observed cannot be reported as preregistered.

## 3. Experiment manifest

Each experiment begins with a versioned machine-readable manifest. The eventual
schema should encode at least:

```text
experiment_id
title
research_question
hypothesis
falsification_condition
exploratory_or_confirmatory

repository_revision
contract_hash
supervisor_hash
evaluator_hashes
generator_versions
environment_hashes
representation_id_and_R_level
kernel_ir_and_action_schema_versions
feedback_treatment_and_schema
learner_update_L_level
learner_update_mechanisms
learner_checkpoint_memory_and_library_ids
system_profile_R_M_G_L_D
maximum_authorized_M_D_ceiling

target_population
workload_sources
partition_method
exclusion_rules
sample_size_or_budget_rule

primary_outcomes
secondary_outcomes
hard_constraints
sentinel_metrics
minimum_practical_effects
uncertainty_method
adaptive_comparison_method
epoch_error_or_risk_budget
maximum_comparisons
power_or_sample_size_rule
utility_or_cost_efficiency_model

baselines
ablations
random_seeds
search_budget
stopping_rules
incident_policy

artifact_plan
analysis_command
registered_at
```

Any post-registration change appends an amendment with its reason and timing.
Original fields remain available.

## 4. Evidence partitioning

Continual optimization creates adaptive data-analysis risk. A single train/test
split is insufficient when thousands of descendants receive feedback.

### 4.1 Required partitions

| Partition | Visible to generator? | Used to promote? | Purpose |
| --- | --- | --- | --- |
| search/development | yes | no, by itself | propose and debug candidates |
| operational holdout | summary feedback only as declared | yes, offline eligibility | compare candidates without touching the research audit |
| research audit | no; ideally single post-freeze access | never for the current study | estimate generalization after operational decisions are frozen |
| prospective future | only after events occur | yes for shadow/canary | test temporal generalization and deployment behavior |
| historical regression | pass/fail or bounded feedback | yes | prevent loss of previously protected behavior |

The ledger records which candidate or generator learned which result. “Hidden”
is a disclosure history, not just a directory permission.

### 4.2 Temporal splitting

For workload-driven evolution, prefer time-ordered partitions over random rows:

```text
past search window → operational holdout → actual prospective window
                                               ↓ freeze all decisions
                                      research audit window/data
```

Random splitting can leak repeated entities and erase the distribution shift the
project intends to study.

### 4.3 Reuse policy

- A research-audit result that changes generator, design, or operational decisions
  retires that audit set for future confirmatory studies.
- Evaluator query count, returned precision, and per-case detail are recorded.
- Repeated studies use rotated or newly collected audit cohorts where possible.
- Historical cases may become regression tests after disclosure, but they cannot
  remain an unbiased audit set.

## 5. Evaluator validation before candidate search

The project must test the judge, not assume it.

Create a labeled meta-suite containing:

- behaviorally identical candidates;
- known correct speedups and slowdowns;
- candidates with deterministic correctness faults;
- rare-slice and tail regressions;
- fast crashes, timeouts, abstentions, and missing telemetry;
- candidates that recognize public cases;
- metric-denominator and sampling attacks;
- resource-exhausting candidates;
- cumulative small regressions against the original baseline.

Use this suite to estimate false-promotion and false-rejection behavior, confirm
metric direction and units, test stop conditions, and calibrate measurement
noise. A failed meta-test blocks confirmatory optimization experiments.

## 6. Baselines

Every study should compare against the strongest feasible alternatives, not only
the initial implementation.

### 6.1 Required baseline categories

- original fixed implementation;
- current champion and best fixed strategy selected with hindsight for analysis;
- no-op candidates, to measure evaluator noise;
- random search under the same candidate and compute budget;
- standard parameter optimizer where parameters exist;
- established domain-specific adaptive method;
- generator ablations, such as LLM without lineage feedback or search without
  operational-holdout/prospective gates;
- representation baselines: unconstrained textual surface for the same kernel,
  grammar/type-constrained surface, complete canonical AST/IR, incremental typed
  actions, and an established typed DSL where applicable; general host source is
  a separate M4 ecological baseline;
- feedback baselines: compiler prose, scalar execution result, structured
  trace/counterexample/proof feedback, and no execution feedback;
- learner-memory baselines: independent samples, run-scoped search state,
  persistent feedback-conditioned retrieval/library/proposal state derived from
  prior runs/lineage, and weight updates where in scope;
- manual or compiler-optimized implementation where a fair reference exists.

### 6.2 Budget fairness

Compare methods at matched candidate, wall-clock, compute, evaluator-query, and/or
monetary budgets as appropriate. Report when perfect matching is impossible.
Giving one method more evaluator disclosures is a treatment difference, not an
implementation detail.

## 7. Outcomes and cost accounting

### 7.1 Outcome hierarchy

Report separately:

1. hard-constraint pass rate;
2. candidate search success;
3. operational-holdout effect;
4. prospective counterfactual-shadow performance;
5. online or simulated canary effect;
6. research-audit effect;
7. sustained post-promotion effect;
8. recovery behavior;
9. total search and assurance cost.

For model-native claims also report:

- parse/type/effect/verifier acceptance separately from semantic task success;
- actions, rejected actions, repair steps, probes, and evaluator calls;
- held-out compositional and cross-task transfer;
- semantic rather than merely textual candidate diversity;
- learned-abstraction reuse, compression, and library growth; and
- measured change in future proposals at each learner-update level.

### 7.2 Benefit and cost

At minimum, cost includes:

- all generated candidates, including invalid and failed builds;
- evaluator executions and benchmark repetitions;
- CPU/GPU, memory, storage, network, and elapsed time;
- model input/output tokens and monetary charge;
- accepted/rejected semantic actions, probes, counterexamples, and repair steps;
- shadow/canary duplicate execution;
- human review and incident handling when measured;
- rollback and lost-service cost in deployment studies.

Always report:

- gross operational improvement;
- one-time search and evaluation cost;
- ongoing supervisor/evidence overhead;
- objective-versus-cost and cost-efficiency curves over the registered horizon.

Report break-even workload/time and net cumulative value only if the manifest
registers a defensible conversion model—for example, monetary cost per avoided
cache miss—with sensitivity analysis. Without a common model, miss ratio,
latency, CPU-hours, money, and human effort remain a Pareto vector and must not be
collapsed after seeing the result.

### 7.3 Complexity and maintainability sentinels

Even when not optimized, record artifact size, dependency count, build time,
static complexity indicators, and evaluator runtime. This detects an evolution
loop that buys small speed gains through unbounded program or assurance growth.

These indicators are proxies, not claims of human maintainability unless a human
study supports that interpretation.

## 8. Statistical analysis principles

The exact method is study-specific and must be registered, but every study must:

- define the observational or randomization unit correctly;
- use paired candidate/champion workloads where feasible;
- include warm-up and repeated measurements for performance results;
- report effect sizes and uncertainty intervals, not only significance tests;
- define a minimum practically important effect before search;
- register an epoch-wide false-promotion/error budget and an appropriate
  sequential, anytime-valid, or other adaptive-comparison method;
- cap the number and information content of comparisons;
- provide a power or sample-size rule for the minimum practical effect;
- state assumptions and test their plausibility;
- report raw distributions and tail behavior when relevant;
- distinguish technical repetitions from independent search runs;
- run enough independent seeds to characterize generator variance;
- hold the base model, task semantics, visible evidence, and budgets fixed when
  attributing a gain to representation or feedback;
- disclose censored, timed-out, crashed, and excluded trials.

For hard risks, use conservative bounds appropriate to the claim. Observing zero
failures does not prove the true failure probability is zero.

The current champion must be compared both with its parent and with the immutable
original baseline. Parent-only comparison can hide gradual cumulative regression.

## 9. Distribution-shift protocol

At least one benchmark must include registered changes in:

- input feature distribution;
- workload/operator mixture;
- volume or concurrency;
- resource availability or hardware class;
- outcome delay or noise where applicable.

Report:

- performance before, during, and after each change;
- change-detection and adaptation delay;
- dynamic regret or another registered temporal measure;
- constraint violations during exploration and recovery;
- candidate churn and rollback count;
- comparison with a fixed baseline, periodic retuning, and an established online
  adaptive method.

Do not describe adaptation to a stationary repeatedly reused benchmark as
evidence of handling drift.

## 10. Reproducibility requirements

### 10.1 Archive

Archive for every reported run:

- repository and contract revision;
- normalized candidate artifacts and complete lineage;
- generated prompts/inputs and raw model outputs where publishable;
- candidate-kernel, IR, canonicalization, and action/observation schema versions;
- accepted/rejected action traces, probe disclosures, learner checkpoints,
  run/persistent memory, and learned abstraction libraries;
- generator, model, API, and provider identifiers;
- toolchain, dependency, container/image, and hardware information;
- dataset identifiers, schemas, collection windows, partition and sampling code;
- seeds and nondeterminism sources;
- raw per-case and per-trial measurements;
- evaluator disclosures and transition decisions;
- resource and monetary costs;
- analysis scripts and final derived tables/figures;
- failures, incidents, deviations, and negative results.

### 10.2 Reproduction target

An independent operator should be able to:

1. rebuild the fixed components and candidates, bit-for-bit where feasible;
2. verify artifact and evidence hashes;
3. rerun a small smoke version of every stage;
4. reproduce the main conclusions within registered tolerance;
5. regenerate every table and figure from archived raw data.

When a proprietary or changing model prevents exact reruns, preserve its outputs
and include at least one reproducible generator baseline. State clearly which
claim depends on the unavailable system.

## 11. Research incidents

The following are recorded as results, not silently cleaned up:

- containment or forbidden-effect escape;
- hidden-evidence disclosure;
- metric or evaluator defect discovered after search;
- irreproducible build or measurement;
- evaluated/deployed hash mismatch;
- unplanned human intervention;
- false promotion or failed rollback;
- privacy, licensing, credential, or cost-budget violation;
- analysis change after research-audit results are viewed.

An incident may invalidate a run. Both the invalidation and raw history remain in
the artifact, subject to responsible security and privacy handling.

## 12. First study: bounded cache-policy evolution

### 12.1 Why this target

A cache-eviction policy is small enough to contain but rich enough to test
continual adaptation:

- `select_victim(snapshot) -> key` can be a pure candidate function on the
  contract domain where `snapshot.evictable_keys` is nonempty;
- validity invariants are exact and cheap to check;
- a simulator prevents durable external side effects;
- all recency/frequency features and policy state are simulator-owned and supplied
  in an immutable input snapshot;
- miss ratio supplies a delayed quality outcome;
- decision latency and evolution cost supply time and cost outcomes;
- changing access traces create controlled temporal drift;
- standard strategies provide credible baselines;
- the mutation surface can grow from selection to typed program synthesis.

This becomes the recommended first experiment. A deterministic data-transformation
engine remains a valuable second domain for exact whole-output equivalence and
structural rewrite research.

### 12.2 Candidate contract sketch

```text
subject select_victim(CacheSnapshot) -> Key
precondition snapshot.evictable_keys is_not_empty

require prove:
  candidate effects subset_of [read_snapshot]

require runtime_enforce with reviewed LRU fallback:
  result in snapshot.evictable_keys
  result not in snapshot.pinned_keys

require test/monitor:
  candidate_violation_rate == 0 on operational holdout

optimize constrained:
  minimize miss_ratio
  then minimize p99_decision_cost_semantic_steps
  report total_evolution_cost

sentinel:
  throughput
  peak_memory
  invalid_decision_rate
  policy_ir_size
```

Only proved or runtime-enforced properties receive `always` wording. Finite tests
and statistical monitoring remain scoped evidence.

Prototype D0 uses deterministic semantic steps rather than wall-clock latency
for its protected promotion outcome, as frozen in
[Decision 0004](decisions/0004-freeze-cache-d0-semantics.md). Measured latency
remains a future reported cost until isolation and calibration are in place.

### 12.3 Experimental stages

| Stage | Generator treatment | Mutable surface |
| --- | --- | --- |
| E0 | no evolution | evaluator and simulator validation |
| E1 | strategy selector | choose reviewed LRU/LFU/ARC-like and simple policies |
| E2 | parameter optimizer | thresholds, window lengths, aging factors |
| E3 | restricted synthesizer | total typed policy IR with bounded loops and no private state/effects |
| E4 | LLM-backed generator | proposals compiled into the same restricted IR |

Within E3/E4, representation is a crossed treatment rather than an authority
increase: batch canonical IR (R2) is compared with incremental typed actions and
structured construction feedback (R3) using compatible generators while the
execution-feedback `F` treatment is held fixed. E4 does not receive a broader
runtime capability set than E3. This isolates representation, generator
intelligence, and candidate authority.

### 12.4 Initial baselines

- LRU;
- LFU with registered aging variants;
- a reviewed adaptive or ARC-like strategy where implementation/licensing is
  suitable;
- offline optimal replacement (Belady/MIN) as a trace-specific lower bound, not a
  deployable competitor;
- random strategy/parameter search under matched budgets;
- periodic offline retuning;
- typed evolutionary or enumerative search;
- no-op champion reevaluation to quantify noise.

### 12.5 Workloads

Begin with seeded synthetic traces whose phases vary locality, working-set size,
frequency skew, scans, bursts, and change points. Keep generator definitions and
seeds for operational-holdout and research-audit partitions protected according
to their different disclosure policies.

Counterfactual shadow uses a twin cache whose candidate decisions evolve the
twin’s own contents while leaving the served cache unchanged. Later add
appropriately licensed public traces and prospective twin traces. Do not use live
user traffic until privacy, retention, and operational approvals are documented.

### 12.6 Model-native representation sub-study

The cache study may make narrow construction comparisons, but it is not
sufficient evidence that the representation supports general program learning.
It separates two interventions:

1. **Representation:** hold the semantic kernel, M/G/L/D profile, task
   information, budgets, and one registered `F` treatment fixed while comparing
   an unconstrained textual surface for that kernel (R0), constrained text (R1),
   complete typed IR (R2), and incremental typed actions (R3). General host
   source is M4 and cannot identify this effect.
2. **Execution feedback:** hold R3 and M/G/L/D fixed while comparing no execution
   feedback (F0), scalar outcome (F1), bounded outputs/counterexamples (F2), and
   detailed trace/verifier/proof/resource diagnostics (F3). Match case/query/risk
   and compute budgets; information content is intentionally different and must
   be reported.

Primary language outcomes are protected semantic success at matched budget and
cost-to-solve. Parse/type validity is secondary. Report rejected actions, repair
steps, probes, evaluator calls, tokens, wall/compute cost, semantic diversity,
and any extra scaffolding or primitive-engineering effort.

A later deterministic multi-task transformation curriculum with withheld
operator compositions includes R4/L0 fixed-library, R4/L1 run-only abstraction,
R3/L2 persistent non-vocabulary memory, and R4/L2 persistent learned-library
controls. That later study—not one cache objective—is the minimum evidence for an
abstraction-learning or “learns how to program” claim.

### 12.7 Primary first claim

The first confirmatory claim should be intentionally narrow:

> Under registered synthetic temporal workload families and a fixed total search
> budget, the external supervisor can select or synthesize cache policies that
> reduce future miss ratio relative to fixed and periodic-retuning baselines,
> while an external shield prevents every tested invalid eviction proposal from
> taking effect, and while reporting the full objective/cost frontier.

The claim is falsified if any invalid proposal passes the shield, the registered
future effect does not exceed the minimum practical threshold, or adaptive
baselines match or beat it under equal budget. A net-value subclaim is falsified
if a preregistered common utility model does not break even in its registered
horizon; without that model, no net-value subclaim is made.

It is not a claim of production safety, universal semantic correctness, or
general self-improving software.

## 13. Publication readiness gate

Before submission, verify that:

- the closest-work and novelty statements remain accurate;
- hypotheses and primary outcomes predate research-audit evaluation;
- baselines are competitive and budget-matched;
- all independent seeds and failed candidates are reported;
- effect sizes, uncertainty, practical thresholds, and cost are included;
- an adversarial evaluator campaign is included, not only performance search;
- ablations separate the contract/runtime from the generator;
- at least one clean environment reproduces the artifact;
- the paper’s claim is no broader than the experiment population and tested
  `(R, M, G, L, D)` system profile;
- limitations and incidents are visible in the main report.
