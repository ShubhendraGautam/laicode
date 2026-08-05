# Research charter

**Narrowed:** 2026-08-05. Supersedes the research charter, design checklist,
experiment protocol, system design, threat model, model-native language design,
and implementation status that preceded it. Those documents, and the code they
governed, are preserved at the `archive/pre-narrowing` tag.

## The question

> Does the system discover abstractions nobody gave it, and do those
> abstractions measurably reduce the cost of constructing programs it has never
> seen?

That is the whole charter. One question, two halves — **discovery** and
**transfer** — and a result requires both.

## What is no longer asked

The project previously asked a second question: whether proposals could be
evaluated and deployed through a candidate-inaccessible governance boundary.
That question licensed a cache-policy control plane, counterfactual shadow
leases, a hash-chained ledger, resource-bounded workers, cross-language
benchmarks, hardware target profiles, and two superseded language epochs —
roughly 11,000 lines answering a question that cannot become interesting until
something is worth governing.

Governance is deferred, not abandoned. It returns from the archive tag when
there is a capability that needs it, and not before.

Recover any of it with:

```sh
git checkout archive/pre-narrowing -- <path>
```

## Acceptance rules

A change ships only if it passes all eight. These are rejection rules. They are
written to be applied against work this project wants to do, which is the only
situation in which a rule matters.

**R1 — No oracle in the learner.** No table of known-good answers may influence
what the learner proposes or accepts. A learner that recognizes answers someone
already wrote measures an encoder, not discovery.

**R2 — Tasks frozen before vocabulary.** The held-out task set and its content
hash are committed in an *earlier commit* than the discovery run that produces
the vocabulary. Task selection made after seeing what was discovered
manufactures its own result.

**R3 — Pre-registered falsifier.** Every study names, in its manifest, the
observation that would make it fail. A study with no such observation is not an
experiment and is not run.

**R4 — One kernel.** New expressiveness extends the existing kernel. A second
`execute_program` is a rejection, whatever it enables.

**R5 — No new epoch until discovery lands.** Recursion, strings, graphs, and
collection-returning functions are frozen. Expressiveness has never been this
project's bottleneck, and adding it has never once been the reason a study
failed.

**R6 — Performance is last.** No timing, no native lowering claim, no
cross-language comparison, no hardware profile until a discovery result exists.
Measuring the speed of a system that has not yet demonstrated its capability
reports on the wrong variable.

**R7 — Governance follows capability.** No new schema, decision record, gate, or
ledger format for something that does not run.

**R8 — Dead code is not progress.** A module with no caller and no test is a
draft, not committed work, and does not count toward any claim.

R1, R7, and R8 are partly mechanized: `tests/test_schemas.py` fails on any
schema with no runtime constant behind it. The remaining rules are enforced at
review.

## Current state

Honest summary: **no discovery result exists.**

| Component | State |
| --- | --- |
| [`canonical.py`](../laicode/canonical.py) | Canonical JSON, content identity, strict decoding. Sound. |
| [`function_language.py`](../laicode/function_language.py) | A2 kernel: named functions, forward-only resolution, depth-bounded call graph. Sound. Its `learn_function_abstraction` is a **known R1 violation** — see below. |
| [`function_benchmark.py`](../laicode/function_benchmark.py) | A2 task registry, cycle study, C11 lowering. Supplies the task set and vocabularies the synthesizer consumes. |
| [`function_synthesis.py`](../laicode/function_synthesis.py) | Matched-budget enumerative search, primitive and learned arms, control family. The first component here that constructs programs. |
| [`function_discovery.py`](../laicode/function_discovery.py) | Anti-unification over synthesized programs, consulting no table. Tested, including that emptying `_DEFINITIONS` changes nothing about what it proposes. **Still wired to no experiment**, so it supports no claim yet. |

### The known R1 violation

[`learn_function_abstraction`](../laicode/function_language.py) accepts a
candidate abstraction only when it byte-matches an entry in a hardcoded
`_DEFINITIONS` map. Every "learned" result in the A2 and A2-S studies traces
back to a definition a person wrote. Those studies therefore measure the value
of good abstractions, not their discovery, and the
[synthesis transfer study](synthesis-transfer.md) says so in its own report
record.

This path is retained only so the A2-S study remains reproducible against its
frozen manifest. It is scheduled for removal once discovery is wired, and no
result depending on it may be described as discovery.

## The open experiment

1. ~~Test `function_discovery.py` in isolation.~~ **Done.** 32 tests in
   [`tests/test_function_discovery.py`](../tests/test_function_discovery.py).
   They found one real defect: `_anti_unify` compared `op`, arity, `name`, and
   `entry_id` but not `value`, so two differing constants took the structural
   branch and were rebuilt as the left constant. The result was a
   "generalization" that did not cover its own right-hand input. Because
   `covers` is recomputed per task, this suppressed candidates rather than
   admitting wrong ones — a recall defect, not a soundness one. Fixed, with the
   defining property now asserted directly.
2. Freeze the held-out task set and commit it. This precedes everything else
   (R2).
3. Build a corpus by synthesizing solutions to training tasks under the
   **primitive** vocabulary only. A corpus of hand-written programs reproduces
   the R1 violation with extra steps.
4. Run discovery over that corpus. Archive every proposal, including rejects —
   what the learner declined is evidence about the learner.
5. Re-synthesize the held-out tasks under primitive and discovered vocabularies
   at matched budget, retaining the control family.

### Pre-registered falsifiers (R3)

- **F1** — No valid entry is discovered. Discovery fails on this corpus; report
  it as a negative result.
- **F2** — Entries are discovered but held-out search cost does not beat the
  control tax. The abstractions are real and useless.
- **F3** — Discovery recovers only `abs`/`max` *and* the held-out set is the set
  needing `abs`/`max`. This is the original circularity rebuilt behind a better
  learner. The study is void; the task families must be redesigned before it is
  rerun.

### Known risk, recorded before the run

[`body_template`](../laicode/function_discovery.py) returns `None` unless a loop
body is exactly one statement, so the discoverable space is single-statement
accumulator bodies. Over that space, anti-unification will most plausibly
surface `abs`- and `max`-shaped templates and little else — which lands
directly on F3.

A second narrowing, confirmed while testing rather than assumed:
**discovery can only ever propose guarded abstractions.**
`check_discovered_definition` requires at least two statements, and an
unconditional template lowers to a single `return`, so it is always rejected. No
purely arithmetic abstraction is reachable today, whatever the corpus contains.
Both surviving hand-written definitions happen to be guarded, which is exactly
why this went unnoticed — and exactly why it compounds F3.

Either widen the template space before running the study, or accept in advance
that a thin result is the expected outcome. Discovering this after the fact and
reinterpreting it as success is the specific failure this section exists to
prevent.

## Decision rule

The experiment has three outcomes and no fourth:

- **Discovery works and transfers** — a genuine result. Governance earns its way
  back from the archive tag at that point, not before.
- **Discovery works but does not transfer** — a publishable negative result.
  Scope was wrong. Stop.
- **Discovery produces nothing valid** — the representation is too narrow. Fix
  the representation or stop.

"Add another epoch and try again" is R5, and is already rejected.

## Claims

No novelty claim is authorized. The [prior-art map](prior-art.md) is a seed, not
a dated systematic corpus, and library-learning systems already perform
abstraction discovery with stronger learners. Any differentiator this project
has would rest on the governance boundary, which is precisely what has been
deferred until there is something to govern.
