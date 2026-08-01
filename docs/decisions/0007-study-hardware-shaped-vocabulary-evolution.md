# Decision 0007: Study hardware-shaped vocabulary evolution

- **Status:** accepted for exploratory E-H0
- **Date:** 2026-08-01
- **Owners:** project owner; implementation delegated to Codex
- **Reviewers:** independent PL/compiler and architecture review required before
  a confirmatory or hardware-general claim
- **Scope:** pure total 64-bit programs at `(R4, M3, G2, L2, D0; F3)`

## Context

The stronger project goal is not merely to let a model emit a nicer
human-designed syntax. It is to test whether repeated execution can shape the
machine-facing language itself: frequently useful operations become vocabulary,
that vocabulary changes later program construction, and the resulting execution
form reflects hardware costs rather than human source-code convenience.

Some semantic foundation remains unavoidable. Hardware already supplies an ISA
and microarchitecture, and any experiment needs fixed meaning and an external
judge. Calling every trusted primitive “emergent” would make correctness and
attribution untestable.

## Decision

Begin with a deliberately small machine language:

- values are unsigned 64-bit words;
- a program is a total, pure pipeline from one word to one word;
- primitive instructions have exact modulo-`2^64` semantics;
- programs and libraries are canonical content-addressed data, not source text;
- a learned superinstruction is a typed sequence of existing primitives;
- the verifier expands every superinstruction to primitives and requires exact
  equivalence;
- the execution engine may dispatch an accepted superinstruction as one fused
  opcode, while its meaning remains its recorded primitive lowering;
- the learner mines execution-weighted recurring sequences, scores their
  dispatch/resource benefit, adds a bounded vocabulary entry, rewrites the
  corpus, and uses the revised vocabulary in the next cycle;
- training, operational holdout, future-shift, and research-audit program
  corpora have distinct identities;
- a deterministic virtual machine cost model drives selection and replay;
- generated C compiled by the installed GCC/Clang toolchain supplies secondary
  host-hardware measurements, never the identity or sole promotion signal.

This is **vocabulary evolution**, not primitive-semantic evolution. The first
form of self-hosting is weak but measurable: the language learned in cycle
`n` changes the representation and proposal operators available in cycle
`n+1`. Rewriting the trusted learner/compiler in its own evolving language is
a later, separately reviewed claim.

## Emergence criteria

The project may say that a hardware-shaped vocabulary emerged only if:

1. vocabulary entries were selected by the registered learner from execution
   evidence rather than inserted as experiment-specific human answers;
2. each entry has a transparent typed lowering and exact identity;
3. the persisted library changes later proposal/encoding behavior;
4. benefit survives on protected held-out programs under matched total budgets;
5. benefit is compared with primitive-only, random-library, and fixed
   human-designed-library baselines;
6. library definition, verification, compilation, and execution costs are
   reported; and
7. host measurements agree in direction often enough to support the narrowly
   declared hardware target, with negative results retained.

Compression or training-corpus reuse alone is insufficient.

## Falsification conditions

The central E-H0 hypothesis fails if held-out total cost does not improve after
library overhead, if random or fixed human macros match the learned library
under matched budgets, if entries do not transfer beyond memorized programs, if
the persistent library does not affect future proposals, or if host-hardware
measurements consistently contradict the deterministic model.

## Consequences

- The experiment directly implements the R4/L2 plane anticipated by Decision
  0002.
- A simple word pipeline is not a general programming language; it isolates
  vocabulary learning, lowering, dispatch, persistence, and hardware feedback.
- The deterministic model can be wrong about a particular CPU. That mismatch is
  evidence requiring model revision, not a result to hide.
- Human-readable names remain optional projections. Canonical instruction and
  library graphs determine identity.
- The learner cannot change primitive meaning, evidence partitions, cost
  collection, verifier, compiler flags, or promotion rules within an epoch.

## Alternatives considered

### Start with arbitrary x86-64 machine code

Rejected for E-H0 because safety, decoding, equivalence, register allocation,
undefined behavior, and measurement noise would confound the language-learning
question.

### Treat neural latent vectors as the language

Deferred. A latent interpreter could be interesting at R5, but without
transparent lowering it cannot yet support the project's attribution,
equivalence, provenance, or authority claims.

### Optimize only source-level description length

Rejected because it would test compression for a learner, not a language shaped
by execution and hardware resource pressure.

## Validation evidence

Required evidence includes primitive semantic vectors, canonical identities,
macro expansion/equivalence tests, adversarial malformed libraries, deterministic
cost replay, persistent cross-cycle vocabulary change, matched baselines,
held-out and drift partitions, full lineage, and reproducible GCC/Clang host
measurement scripts.

## Revisit criteria

Start a new decision before adding memory, branches, effects, concurrency,
unbounded loops, learned primitive semantics, arbitrary native code, model
weight updates, online deployment, or a second hardware architecture.
