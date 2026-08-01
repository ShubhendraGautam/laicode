# LAIcode

LAIcode is a research project for **model-native programming and bounded,
evidence-driven program evolution**. It explores whether machine learners can
construct and improve typed executable programs through semantic actions and
execution feedback, while an external contract declares what may change, what is
protected, how improvement is measured, and what evidence permits deployment.

The working thesis is:

> An AI learner can improve how it constructs executable programs from semantic
> execution evidence, while the evolving program remains unable to redefine
> success, weaken its constraints, or directly deploy itself.

This repository contains the research and system design plus a working
prototype-v0 D0 control plane: strict evolution-contract validation, canonical
identity, a fixed cache-policy semantic kernel, deterministic partitioned
evaluation, constrained offline selection, an append-only lineage ledger, and
byte-for-byte full-run replay. It makes no claim of safe autonomous deployment.

## Model-native programming vision

LAIcode is not intended to be just an LLM repeatedly rewriting ordinary source
files. Its learner-facing substrate should expose typed program states, holes,
effects, proof obligations, local semantic transformations, reusable
abstractions, traces, counterexamples, and resource outcomes.

An autoregressive model may still predict serialized tokens internally. The
research claim is not that symbol prediction disappears; it is that prediction
becomes one proposal mechanism inside an executable, verifier-grounded learning
loop instead of the entire programming interface. The authoritative object is a
canonical semantic program, while source text is one human-readable projection.

The project therefore studies two coupled questions:

1. Does a model-native program representation and structured execution feedback
   help machine learners construct, repair, transfer, and reuse programs more
   effectively than source-text generation under matched budgets?
2. Can those increasingly capable proposals be evaluated and deployed through a
   candidate-inaccessible governance boundary?

See [Model-native programming design](docs/model-native-language.md).

## What “self-improving” means here

LAIcode does not treat every source-code change as learning. A system counts as
self-improving only when a closed loop:

1. observes executions and outcomes;
2. proposes a new implementation inside an explicitly permitted search space;
3. evaluates it on evidence it cannot alter;
4. rejects it if any hard constraint fails;
5. promotes it through a bounded rollout; and
6. demonstrates improvement on future, previously unseen workloads while fully
   reporting search and evaluation cost.

The candidate program is never the authority that decides whether it improved.

## Research position

Prior work already covers structured code generation, execution-guided program
synthesis, learned abstraction libraries, language-supported hot swapping,
runtime feedback, and synthesized or genetically improved variants. The research
question is therefore much narrower than “a language an AI can learn” or
“self-evolving software.” LAIcode studies whether a model-facing semantic IR and
an **evolution contract** can jointly support this particular combination:

- typed incremental program actions and structured semantic feedback;
- typed/effect-checked learned abstractions with machine-checkable lowering to a
  stable, verifier-grounded kernel;
- first-class objectives, constraints, budgets, and mutable regions;
- candidate-inaccessible, versioned evaluation authority;
- immutable successor identity and complete evidence lineage;
- staged sandbox, counterfactual shadow, canary, promotion, and recovery;
- explicit treatment of evaluator overfitting, workload drift, and total
  optimization cost.

This is a gap hypothesis, not yet a novelty claim. See
[Prior art](docs/prior-art.md).

## Documents

- [Research charter](docs/research-charter.md) — scope, definitions, research
  questions, hypotheses, claims, and non-goals.
- [Model-native programming design](docs/model-native-language.md) — learner-facing
  representation, semantic actions, structured feedback, language growth, and
  comparative experiments.
- [System design](docs/system-design.md) — trust boundaries, language sketch,
  components, candidate lifecycle, and data model.
- [Threat model](docs/threat-model.md) — assets, adversaries, failure modes,
  mitigations, representation/learning/authority axes, and stop conditions.
- [Experiment protocol](docs/experiment-protocol.md) — baselines, dataset
  separation, statistics, cost accounting, and reproducibility requirements.
- [Design checklist](docs/design-checklist.md) — gates that must be satisfied
  before implementation, experimentation, or deployment.
- [Implementation status](docs/implementation-status.md) — the current gate
  review, executable evidence, and remaining blockers.
- [Decision records](docs/decisions/README.md) and
  [Decision 0001](docs/decisions/0001-external-judge.md) — governance format and
  why candidates cannot modify their own judge.
- [Accepted Decision 0002](docs/decisions/0002-model-native-language-planes.md) —
  separation of governance, stable semantics, and learned abstractions.
- [Accepted Decision 0003](docs/decisions/0003-prototype-runtime.md) — scoped
  Python runtime choice and isolation requirements for the first prototype.
- [Working prototype](docs/prototype.md) — exact semantics, run bundle,
  demonstrated result, reproduction, and limitations.
- [Working cache-policy alternative](docs/working-alternative.md) — bounded
  subprocess workers, counterfactual shadow leases, automatic revocation, and
  imported-trace operation.

## Prototype quick start

The current implementation uses only the Python 3.10 standard library. Run and
exactly replay the complete workflow with one command; the output path must not
already exist:

```sh
python3 -m laicode smoke-prototype +  examples/contracts/cache-policy-v0.json /tmp/laicode-prototype
```

The command validates the evaluator before candidate search, enumerates the
reviewed LRU/FIFO/LFU strategies, selects under frozen operational and
historical gates, freezes the D0 decision, consumes prospective and research
audit evidence afterward, archives every input/result/decision, and verifies a
fresh byte-identical replay.

To run the next D1 milestone—offline selection followed by isolated
counterfactual shadow, automatic regression revocation, and exact replay—use:

```sh
python3 -m laicode smoke-alternative \
  examples/contracts/cache-policy-v0.json /tmp/laicode-alternative
```

Component checks remain available:

```sh
python3 -m unittest discover -v
python3 -m laicode validate-contract examples/contracts/cache-policy-v0.json
python3 -m laicode compile-program \
  examples/contracts/cache-policy-v0.json examples/programs/lru-v0.json
python3 -m laicode construct-program \
  examples/contracts/cache-policy-v0.json examples/actions/fill-lru-v0.json
```

The validation command prints the SHA-256 epoch identity. The final two commands
construct the same fixed-kernel artifact through R2 and R3 and print the same
artifact identity. Add `--canonical` to inspect the exact bytes being hashed.

## Experimental scope

The working D0 prototype evolves a pure, deterministic target with an exact
validity oracle and outcome simulator. Later experiments should separate:

1. select among predefined strategies;
2. tune strategy parameters;
3. apply typed or grammar-constrained program rewrites;
4. construct the same restricted IR through incremental typed actions; and
5. use an LLM for those actions without broadening candidate authority.

Each stage must use the same candidate ledger and promotion protocol. This
separates the value of the runtime and evolution contract from the value of any
particular generator. A separate representation experiment compares
unconstrained and constrained textual projections of the same kernel, complete
typed IR, and incremental actions while holding semantic scope and feedback
fixed. A second experiment holds the action interface fixed while varying scalar,
counterexample, trace, and proof/resource feedback.

The first benchmark should contain changing workload distributions, because
optimizing repeatedly on a stationary toy benchmark does not demonstrate
continual improvement. A simulated cache-eviction policy is the current
recommended target: validity invariants are exact, policy quality has delayed
effects, standard baselines exist, and access traces can shift over time. A
deterministic data-transformation engine is the planned second domain for exact
whole-output equivalence and structural rewrite experiments.

## Core safety rule

```text
candidate may change the solution
learner may add checked abstractions that lower to the stable kernel
learner may not redefine primitive semantics within an epoch
candidate may not change the judge
```

“Deploy once” therefore means deploying a stable supervisory control plane and
an evolvable application plane. It never means granting arbitrary self-write or
self-deploy authority to the current application.

## Current status

**Working D0 selector and D1 counterfactual-shadow alternative.** The closed
M1/G1 strategy enumerator completes a deterministic
search–evaluate–select–audit–replay loop. A resource-leased subprocess runner can
then shadow the selected artifact on an imported trace while the immutable
original remains the only served champion. The default recency-shift demo
automatically revokes LFU for regression. Independent review, syscall-level
containment, confirmatory statistics, model-driven generation, network
integration, and D2 canary execution remain open gates.
