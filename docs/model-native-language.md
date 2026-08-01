# Model-native programming design

**Status:** design hypothesis; R2/R3 kernel slice implemented, with no representation-effect claim
**Last updated:** 2026-08-01
**Owner:** to assign

## 1. Mission

LAIcode investigates a programming substrate in which an LLM, program
synthesizer, reinforcement-learning agent, or other machine learner can construct,
execute, revise, reuse, and extend programs through semantic actions rather than
being limited to unconstrained continuation of human-oriented source text.

The intended loop is:

```text
typed program state + obligations + permitted evidence
                         │
                         ▼
                  machine learner
                         │ typed semantic action
                         ▼
                parser / type / effect / proof checks
                         │ structured result
                         ▼
              isolated execution / counterexample / cost
                         │
                         └──────────► next proposal policy or memory
```

Natural language and token generation may still propose actions. Accepted
programs, however, are identified by formal structure and judged by declared
semantics and execution evidence—not by token likelihood.

## 2. Precision about “beyond token prediction”

A programming language cannot make an autoregressive model stop predicting
tokens internally. Trees, logic terms, opcodes, and edit actions are symbols too.
The research claim is therefore about the **external programming interface and
learning signal**, not an unsupported claim about a model’s internal cognition.

LAIcode compares:

- unconstrained source-token or text-patch generation;
- syntax-, grammar-, or type-constrained textual generation;
- complete canonical AST/IR construction;
- incremental typed semantic actions over partial programs;
- the same actions with structured execution, counterexample, proof, and cost
  feedback; and
- a stable semantic kernel augmented with learned, transparent,
  machine-checkably lowered abstractions.

Success would mean that the semantic interfaces improve verified task success,
cost-to-solve, repair efficiency, or transfer under matched budgets. Merely
producing more syntactically valid programs is not sufficient.

## 3. Operational vocabulary

### 3.1 Model-native

**Model-native** means that the authoritative program representation and editing
protocol are designed for machine construction:

- canonical structure independent of formatting;
- typed, validity-checkable construction actions;
- explicit effects, capabilities, resources, and obligations;
- machine-readable execution and verification feedback;
- stable identities for subterms, abstractions, and evidence; and
- a human-readable projection that is a view, not the program identity.

Model-native does not mean model-exclusive. Humans must be able to inspect,
debug, specify, and override the system.

### 3.2 Machine learner

A **machine learner** is a candidate generator whose future proposal distribution
can change from permitted feedback. The update may live in run-scoped search
state, persistent retrieval/proposal state derived from lineage, a learned
abstraction library, a policy, or model weights. These update modes must be
reported separately.

A frozen model sampled repeatedly without feedback is a generator, but it has not
thereby learned from execution.

The documents use **machine learner** to include LLMs, program synthesizers,
reinforcement-learning agents, and future advanced learners. “Super learner” is
not used as a technical category unless a study defines its algorithm and update
semantics precisely.

### 3.3 Semantic action

A **semantic action** is a typed transition over a program state, such as filling
a typed hole, applying a rewrite, introducing a binding, composing terms,
defining a transparent abstraction, or discharging an obligation. Its validity is
defined over the language state, not inferred from whether a text patch happens
to parse.

### 3.4 Execution-conditioned learning

**Execution-conditioned learning** occurs only when execution-derived evidence
changes the distribution of future proposals and the effect can be measured on
held-out tasks or workloads. Best-of-N selection, lineage-guided search, library
learning, policy learning, and weight learning are different treatments—not
interchangeable uses of the word “learning.”

### 3.5 Expressive, logical, and free

These terms are hypotheses with measurable meanings:

- **expressive:** the representation covers a declared task family with bounded
  description length and without frequent host-language escape hatches;
- **logical:** types, effects, constraints, refinements, equations, and proof
  obligations have explicit semantics; this does not imply that a model reasons
  logically merely because it uses the language;
- **free:** a learner can compose and invent solutions within an explicit effect
  and capability envelope; it does not mean unrestricted filesystem, network,
  judge, or deployment authority.

Expressivity, searchability, and verifiability form a tradeoff. A language may
represent more programs while becoming harder to search or assure.

## 4. Three language planes

LAIcode separates responsibilities that ordinary source languages often mix.

| Plane | Primary author | Purpose | May learner change it within an epoch? |
| --- | --- | --- | --- |
| evolution contract | human governance | mutation scope, evidence, objectives, budgets, acceptance, rollout | no |
| candidate semantic kernel and IR | trusted language implementation | executable program meaning, types, effects, actions, lowering | no |
| learned abstraction layer | learner or human | reusable transparent functions, combinators, rewrites, and search vocabulary | yes, when authorized and independently checked |

The contract governs authority. The candidate IR expresses solutions. The
abstraction layer lets the effective language grow without silently changing
primitive semantics.

Changing the kernel, compiler semantics, verifier, or primitive meaning changes
the trusted computing base and starts a new human-governed epoch. Learning a
derived abstraction that lowers into the unchanged kernel is an ordinary
candidate change with versioned evidence.

## 5. Candidate semantic kernel

The initial kernel should test the following design hypotheses:

1. **Canonical program graphs.** Formatting, declaration order where irrelevant,
   generated names, and equivalent serialization do not create new identities.
2. **Typed holes.** Incomplete programs are explicit objects with expected type,
   effect allowance, scope, and outstanding obligations.
3. **Validity-preserving local construction.** The protocol exposes only actions
   meaningful for the current state, or rejects invalid actions without mutating
   it.
4. **Explicit effects and costs.** State, I/O, time, randomness, allocation, model
   calls, and external services are visible in types/effects or capability terms.
5. **Compositional semantics.** A learner can form larger programs from checked
   subprograms without regenerating unrelated text.
6. **Structured failure.** Type errors, failed obligations, counterexamples,
   resource violations, and unknown verifier results have versioned schemas.
7. **Content-derived identity.** Programs, subterms, abstractions, action traces,
   and evidence are hash-addressable under canonical serialization.
8. **Multiple projections.** A compact machine representation, readable source
   view, graph view, and diagnostic view denote the same authoritative object.

The first kernel should be total or externally step-bounded and pure except for
explicit brokered effects. General recursion, unrestricted reflection, dynamic
loading, and ambient authority are deferred until their research value outweighs
the loss of tractability.

## 6. Model action and observation protocol

A one-shot `prompt -> source file` API cannot test this thesis. The learner-facing
interface is episodic:

```text
open(parent_artifact, contract, action_schema, permitted_evidence)
  -> ProgramState

step(session, TypedProgramAction)
  -> ActionResult {
       state_id,
       accepted,
       type_and_effect_delta,
       open_holes,
       proof_obligations,
       structured_diagnostics,
       action_cost
     }

probe(session, ProbeRequest, search_evidence_capability)
  -> ProbeResult {
       outputs,
       trace_summary,
       counterexamples,
       resource_vector,
       uncertainty,
       evidence_provenance
     }

commit(session)
  -> immutable_candidate_manifest + artifact
```

Candidate actions may include:

- `fill_hole(hole, constructor, operands)`;
- `introduce_binding(scope, typed_expression)`;
- `replace_subterm(node, typed_expression)`;
- `apply_rewrite(node, registered_rule)`;
- `compose(operator, operands)`;
- `define_abstraction(body, interface)`;
- `instantiate_abstraction(id, arguments)`;
- `request_check(obligation)`; and
- `abandon_branch(reason)`.

Exact constructors belong to the versioned IR schema. Free-form names and
explanations are metadata and never determine semantics or authorization.

Feedback is minimum-disclosure and capability-controlled. Search cases may yield
structured counterexamples; operational holdout yields only the registered
summary; the post-freeze research audit never enters the construction session.

## 7. Language growth and self-improvement

The project distinguishes three increasingly strong claims:

1. **Program evolution:** find better terms in a fixed kernel and library.
2. **Vocabulary evolution:** discover reusable transparent abstractions that
   lower into the fixed kernel and improve future search or compression.
3. **Semantic evolution:** change primitive meaning, compiler, verifier, or
   effect semantics.

The initial system studies program evolution. Vocabulary evolution is a primary
later research target because it most closely captures a learner improving its
own way of programming while preserving independent meaning. Semantic evolution
is outside candidate authority and requires a new epoch and trust analysis.

A learned abstraction is promoted only if its canonical definition, type/effect
signature, lowering, dependencies, provenance, compatibility range, and
verification/evaluation evidence are recorded. Popularity or compression alone
does not establish correctness.

## 8. Experimental axes

Representation and learner update must be reported independently from mutation,
generator, and deployment authority.

### 8.1 Representation/interface `R`

| Level | Learner-facing programming interface |
| --- | --- |
| R0 | unconstrained textual surface/patch generation for the same semantic kernel |
| R1 | grammar/type-constrained textual surface for the same semantic kernel |
| R2 | complete canonical typed AST/IR generation |
| R3 | incremental typed semantic actions with structured construction feedback |
| R4 | R3 plus an explicit typed/effect-checked abstraction layer lowered to a fixed kernel |
| R5 | latent/subsymbolic primitive or interpreter representation; research-only initially |

R0 is not arbitrary Python, Rust, or repository source. It is an unconstrained
textual projection of the same kernel and capability envelope used by R1–R3, so
representation can vary without silently moving from M3 to M4. General host
source is an ecological M4 baseline requiring a separate review and claim.

### 8.2 Execution-feedback treatment `F`

| Class | Execution-derived information returned to the learner |
| --- | --- |
| F0 | none; construction validity only |
| F1 | scalar pass/fail, reward, or objective summary |
| F2 | structured outputs and bounded counterexamples |
| F3 | detailed execution traces plus verifier/proof and resource diagnostics |

`F` is an experimental treatment and evidence-disclosure class, not an autonomy
level. Higher detail may help repair while increasing leakage and evaluator-query
risk. Every study registers cases, precision, query budget, and provenance in
addition to the class.

### 8.3 Learner update `L`

| Level | What changes from execution feedback |
| --- | --- |
| L0 | nothing; proposals are independent of outcomes |
| L1 | run-scoped context, search state, or branch priorities |
| L2 | governed persistent feedback-conditioned retrieval, library, or proposal-policy state derived from prior runs/lineage |
| L3 | versioned model weights/checkpoint updated from permitted evidence |
| L4 | untrusted learner algorithm or model architecture is itself evolved |
| L5 | learner changes the contract, judge, or trusted implementation |

L records the highest update class used, not an assumption that all lower classes
also occurred. A run also records an explicit mechanism set, such as
`[run_search, persistent_library, weight_update]`; L3 alone does not imply L2.
L5 is prohibited by the external-judge decision. L3 and L4 require separate data,
poisoning, reproducibility, containment, and rollback analyses.

R and L are independent. R4 may use a fixed human library at L0, run-only
abstraction proposals at L1, or a persistent learned library at L2. Conversely,
R3/L2 can retain feedback-conditioned search or retrieval memory without changing
the vocabulary. The first experiments target R2/R3, F0–F3, and L0/L1 before
persistent abstraction learning at R4/L2.

Every result reports an `(R, M, G, L, D)` profile, `F` treatment, explicit learner
mechanisms, and separately the maximum authorized M/D ceiling. No scalar
“autonomy level” may substitute for these distinct dimensions.

## 9. Research questions and falsifiers

### Representation

Under matched model, visible information, candidate, evaluator-query, compute,
and monetary budgets, does R3 improve verified task success or cost-to-solve over
R0, R1, R2, and a strong existing typed DSL?

The claim fails if gains are only parse/type validity, disappear after equalizing
budget, or are matched by an ordinary canonical AST plus the same scaffold.

### Semantic feedback

Do structured values, traces, counterexamples, effect deltas, and proof failures
improve repair and held-out semantic success over compiler prose, scalar reward,
or no execution feedback?

The claim fails if feedback only increases evaluator leakage or calls without
improving protected outcomes.

### Learning versus repeated search

Does persistent execution-conditioned state improve future-task sample efficiency
over independent best-of-N and lineage-only selection?

The claim fails if the proposal distribution or future-task result does not
change beyond what candidate selection alone explains.

### Abstraction transfer

Do learned, machine-checkably lowered abstractions reduce description length,
actions, evaluator calls, or cost on withheld compositions and shifted task
families?

The claim fails if the library merely memorizes training tasks, grows without
reuse, or worsens the registered cost/assurance frontier.

### Expressivity frontier

How does expanding the kernel or abstraction vocabulary change representable
solutions, search success, invalid or unsafe proposals, and assurance cost?

There may be no single best representation; mapping this frontier is a valid
negative or mixed result.

## 10. Required comparative experiments

The confirmatory design separates three interventions.

### 10.1 Representation study

Hold the semantic kernel, M/G/L/D profile, execution-feedback treatment, task
information, and budgets constant:

| Treatment | Representation |
| --- | --- |
| R-T0 | unconstrained textual surface/patch for the same kernel |
| R-T1 | grammar/type-constrained textual surface for the same kernel |
| R-T2 | complete canonical typed AST/IR |
| R-T3 | incremental typed semantic actions |

An ordinary general-purpose host language is reported separately as an ecological
M4 comparison; it cannot identify the R0–R3 representation effect.

### 10.2 Feedback study

Hold R3 and the M/G/L/D profile constant while varying F0, F1, F2, and F3.
Feedback information is intentionally the intervention, so case/query/risk and
compute budgets are matched while information content is described rather than
falsely claimed to be identical.

### 10.3 Learner-state and abstraction study

Compare at least R4/L0 with a fixed library, R4/L1 with run-only abstraction
proposals, R3/L2 with persistent non-vocabulary memory, and R4/L2 with a
persistent learned library. This distinguishes interface support for abstraction
from actual cross-run vocabulary learning.

Measure at least:

- parse, type, effect, and verifier acceptance rates;
- semantic success on protected cases and held-out task compositions;
- tokens/actions, evaluator calls, CPU/GPU, time, and money to threshold;
- repair steps after a counterexample;
- semantic rather than textual candidate diversity;
- program and learned-library size;
- abstraction reuse and transfer efficiency;
- performance under task or workload drift; and
- specification, primitive-engineering, and human-review effort.

The cache-policy study can test the governance loop and early R2/R3 construction,
but one cache objective cannot support a broad expressivity or abstraction-
learning claim. A compositional deterministic transformation curriculum with
withheld operator combinations is required before claiming that the language
helps models learn how to program.

## 11. Non-goals and cautions

- Claiming that structured syntax causes logical reasoning.
- Claiming that execution success establishes general correctness.
- Claiming invention of structured code generation, neural program synthesis,
  learned DSLs, execution-guided search, or neuro-symbolic programming.
- Hiding extra execution, feedback, prompt, tool, or human effort in a favorable
  comparison.
- Allowing learned abstractions to bypass types, effects, capabilities, budgets,
  or evidence policy.
- Training a foundation model during the first research cycle.
- Treating a proprietary model improvement as a language contribution without a
  reproducible non-proprietary generator baseline.

The language thesis remains a hypothesis until controlled studies show a semantic
or learning advantage beyond validity filtering.
