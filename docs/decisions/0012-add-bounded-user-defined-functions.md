# Decision 0012: Add bounded user-defined functions and a static call graph

- **Status:** accepted for exploratory A2
- **Date:** 2026-08-01
- **Owners:** project owner; implementation delegated to Codex
- **Reviewers:** independent language/compiler review open
- **Scope:** `(R4, M3, G2, L2, D0; F3)` function-language epoch

## Context

A0 learned expression intrinsics and A1 learned statement intrinsics. Both grow
the language by adding fixed operator shapes that the encoder substitutes inline.
Neither can name a computation, give it a signature, or reuse it as a unit. That
excludes the most ordinary abstraction mechanism in programming and forces every
task program to restate shared logic.

Adding functions raises two separate risks. Unbounded call graphs admit
recursion and non-termination, and function-valued abstractions would make the
learned vocabulary opaque. Both must be excluded before the capability is safe
to study.

## Decision

A2 is a new `CallGraphFunctionKernelV2` epoch. It adds:

- up to eight declared functions per program, each with at most four parameters;
- parameters typed `i64`, `bool`, or immutable `array<i64>`;
- `i64` or `bool` returns, with early returns permitted inside branches;
- calls resolved only against earlier declarations, making recursion and mutual
  recursion unrepresentable rather than merely rejected;
- a statically computed call depth of at most four, counting learned calls;
- mandatory reachability of every declared function from the entry point; and
- strict generated C11 with one static C function per declared function.

The kernel deliberately omits a `max` primitive so that `max_of` remains
something the learner can discover rather than something the kernel supplies.

The A2 learner may add only transparent function abstractions. A candidate must
appear under the same name with a byte-identical definition in at least two
distinct pre-freeze task identities, contain at least two statements, retain its
exact archived definition, and preserve every core and oracle result. The
registered study first learns `abs_value`, then `max_of`.

## Evidence separation

Total-absolute and count-large-absolute tasks train cycle 1. Max-absolute and
max-prefix-sum tasks train cycle 2. Highest Altitude and total absolute
deviation are protected holdouts. Maximum increasing difference is disclosed
only as a post-freeze audit. All tasks use independently implemented Python
oracles and 32 deterministic archived cases.

## Cost semantics

A learned A2 abstraction removes duplicated definitions; it does not remove
executed work. The epoch therefore measures definition statements as the
improvement axis and requires interpreter dispatch to be **exactly unchanged**
between a core program and its encoded form. A dispatch change is treated as an
encoding defect and fails the run, not as a performance result.

## Authority boundary

A2 remains D0. Functions are pure: they cannot mutate the input, allocate, or
touch the filesystem, network, evaluator, vocabulary, or deployment state.
Learned entries cannot introduce recursion, indirect calls, function values,
hidden effects, new primitive semantics, or opaque native implementations.

## Consequences

- Programs can name, sign, and reuse a computation as a unit.
- Forward-only resolution is a strong structural guarantee but forbids the
  mutually recursive programs that some algorithms want.
- Scalar-only returns keep this epoch separate from A1 owned vectors; a program
  cannot yet return a constructed collection from a helper.
- A0 and A1 artifacts remain on their original kernels and replay unchanged.
- Recursion, indirect calls, collection-returning functions, generics, and
  closures remain outside A2.

## Validation evidence

Required evidence includes recursion and mutual-recursion rejection, call-depth
overflow rejection, unreachable-function rejection, call-argument type failures,
missing-return rejection, return-from-loop rejection, conflicting-definition
learning refusal, single-task learning refusal, cross-task learning provenance,
protected/audit transfer, all-cycle oracle agreement, exact dispatch equality
between core and encoded programs, strict C compilation, native case agreement
with cycle-stable checksums, source/trace/call-graph inspection, schema
validation, tamper rejection, and byte-identical replay.

## Revisit criteria

Start another kernel decision before adding recursion of any depth, indirect or
dynamic calls, function values or closures, mutual reference, collection or
record returns from helpers, generic or polymorphic signatures, opaque
intrinsics, online learning, official platform submission, or deployment
authority.
