# Decision 0010: Add a typed algorithm language and local validity laboratory

- **Status:** accepted for exploratory A0
- **Date:** 2026-08-01
- **Owners:** project owner; implementation delegated to Codex
- **Reviewers:** independent language/compiler review open
- **Scope:** `(R4, M3, G2, L2, D0; F3)` algorithm-language extension

## Context

E-H0 demonstrates vocabulary growth over pure `u64 -> u64` pipelines, but a
user cannot yet inspect familiar algorithms or ask whether the language can
express common programming-challenge contracts. Directly claiming LeetCode
validity would be unsound without an official submission, hidden tests, exact
wrapper ABI, and platform-controlled resource measurements.

The project needs a broader executable kernel and a locally reproducible
validity claim before any platform integration.

## Decision

A0 adds a fixed structured kernel with signed i64 scalars, booleans, read-only
i64 arrays, pairs, typed locals, assignment, bounded loops, conditionals, and a
single return. Arithmetic and indexing fail closed when their registered
semantics are undefined.

A cross-task learner may add transparent expression intrinsics when one typed
operator pattern:

- occurs in at least two distinct pre-freeze task identities;
- contains at least two primitive operators;
- records typed holes and exact lowering;
- is selected deterministically under the frozen learner rule; and
- preserves every core and oracle output.

The study separates learning tasks, protected holdout tasks, and one post-freeze
audit. Each cycle is validated by an external interpreter oracle. Generated C11
is supplemental validity evidence and must execute the same archived cases.

## Platform claim

Binary search, maximum subarray, and two-sum use locally frozen contracts
equivalent to representative LeetCode-style semantics. A0 may report local
contract equivalence. It may not report an official Accepted result, scrape
platform content, automate an account, or infer hidden-test validity.

## Authority boundary

A0 remains D0. The learner cannot change primitive semantics, types, oracles,
partitions, case evidence, compiler checks, runtime limits, deployment state, or
platform state. Learned entries lower transparently and cannot introduce I/O,
allocation, ambient authority, or effects.

## Consequences

- The language becomes inspectable on recognizable algorithms.
- Learned vocabulary demonstrably transfers across task identities.
- Generated C is useful validity evidence without conflating representation
  savings with native speed.
- The fixed ABI excludes strings, graphs, maps, recursion, and general platform
  submission wrappers.
- Every new capability family requires a new kernel/schema epoch and adversarial
  validity cases.

## Validation evidence

Required evidence includes static type failures, bounds failures, exact learned
lowering, protected-task transfer, all-cycle oracle agreement, generated-C
compilation under strict warnings, native case agreement, trace/source
inspectability, schema validation, tamper detection, and byte-identical replay.

## Revisit criteria

Start a new decision before adding allocation, recursion, effectful operations,
opaque learned entries, official platform submission, hidden-test claims,
performance ranking, online adaptation, or deployment authority.
