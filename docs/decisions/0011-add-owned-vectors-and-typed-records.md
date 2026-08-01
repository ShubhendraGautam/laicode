# Decision 0011: Add bounded owned vectors and typed records

- **Status:** accepted for exploratory A1
- **Date:** 2026-08-01
- **Owners:** project owner; implementation delegated to Codex
- **Reviewers:** independent language/compiler review open
- **Scope:** `(R4, M3, G2, L2, D0; F3)` collection-language epoch

## Context

A0 can inspect input arrays and return a scalar or pair, but cannot construct an
array result. That excludes a large class of recognizable algorithms and makes
records such as “retained values plus logical length” impossible. Adding
unbounded heap allocation would expand the safety and compiler problem too far
for the next exploratory epoch.

## Decision

A1 is a new `OwnedVectorRecordKernelV1` epoch. It adds:

- locally owned mutable `vector<i64>` values with an explicit capacity;
- immutable input arrays and no aliasing of owned storage;
- a hard limit of 256 elements per input or owned vector;
- vector length, checked indexing, and checked append;
- vector returns and named record returns with statically ordered typed fields;
- exactly one owned-vector field per record in this epoch; and
- strict generated C11 using fixed local storage with the same bounds.

The A1 learner may add only transparent statement intrinsics. A form must occur
in at least two distinct pre-freeze task identities, retain an exact primitive
lowering, and preserve every core and oracle result. The registered study first
learns indexed append, then conditional indexed append.

## Evidence separation

Copy and reverse tasks train cycle 1. Positive filtering and target filtering
train cycle 2. Remove Element and Running Sum are protected holdouts. Move
Zeroes is disclosed only as a post-freeze audit. All tasks use independently
implemented Python oracles and 32 deterministic archived cases.

## Authority boundary

A1 remains D0. Owned mutation is local to one execution and cannot mutate the
input, filesystem, network, evaluator, vocabulary, or deployment state. Learned
entries cannot introduce allocation, hidden effects, new primitive semantics,
or opaque native implementations.

## Consequences

- Programs can construct inspectable collection outputs and typed result
  records.
- The fixed 256-element bound is intentionally unlike a general-purpose vector.
- Fixed C storage supplies strong native validity evidence but is not a heap or
  performance claim.
- A0 artifacts remain on their original kernel and replay unchanged.
- General records with multiple collections, borrowing, heap allocation,
  functions, recursion, strings, maps, and graphs remain outside A1.

## Validation evidence

Required evidence includes type and capacity failures, immutable-input checks,
cross-task learning provenance, protected/audit transfer, all-cycle oracle
agreement, strict C compilation, native case agreement, record/source/trace
inspection, schema validation, tamper rejection, and byte-identical replay.

## Revisit criteria

Start another kernel decision before adding heap allocation, reference
lifetimes, mutation through aliases, more than one collection field per record,
unbounded output, opaque intrinsics, online learning, official platform
submission, or deployment authority.
