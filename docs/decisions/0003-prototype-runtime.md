# Decision 0003: Start the control-plane prototype in Python

- **Status:** accepted for D0 prototype
- **Date:** 2026-08-01
- **Owners:** project owner; implementation delegated to Codex on 2026-08-01
- **Reviewers:** project-owner review deferred; independent systems/security
  review required before D1 or any containment claim
- **Scope:** Phase-0 contract tooling and the E0 deterministic simulator at D0

## Context

The repository needs executable evidence for strict contract decoding, canonical
identity, and deterministic record/replay. The currently available workspace has
Python 3.10 and Node.js, but no Rust or Go toolchain. Pulling in a new language
toolchain before the contract boundary is testable would add bootstrap and
supply-chain work to the first slice.

Python does not provide the host-language static guarantees preferred by the
system design. It can, however, provide a dependency-free and inspectable
control-plane prototype while the candidate language remains a closed, typed
data representation validated at runtime.

## Decision

Use Python 3.10 and its standard library for prototype-v0 contract tooling and
the E0 deterministic cache simulator. Apply these limits:

- candidate programs are data interpreted by a closed semantic kernel, not
  imported Python modules;
- all trust-boundary inputs pass strict schema validation that rejects unknown
  fields, duplicate fields, floats, non-NFC strings, and oversized documents;
- canonical artifacts contain only UTF-8 NFC strings, booleans, null, signed
  64-bit integers, arrays, and sorted-key objects;
- closed M1 candidate data may be interpreted in-process by the reviewed
  semantic kernel at D0; candidate-supplied code, M2/M3 mutation, or D1
  execution requires a separate resource-limited worker first;
- ambient filesystem, network, process-spawn, clock, randomness, environment,
  credential, model, and external-service access defaults to denied;
- no production isolation or safety claim rests on Python object-level
  boundaries.

The process sandbox and kernel implementation require their own tests. This
record does not accept a particular container as a complete security boundary.

## Consequences

- The first schema, canonicalization, and replay tests run without downloaded
  dependencies.
- The contract and candidate IR can be reviewed before committing to a compiler
  toolchain.
- Runtime validation carries more of the assurance burden than it would in a
  strongly typed implementation.
- Porting the trusted kernel remains possible because canonical inputs and
  identities are language-neutral byte contracts.

## Alternatives considered

### Bootstrap Rust immediately

Rust is a strong candidate for the long-lived trusted kernel, but it is not
installed in the current workspace. Defer the toolchain and dependency decision
until the v0 semantics are reviewable.

### Use TypeScript on Node.js

TypeScript would still require adding a compiler/toolchain dependency, and its
runtime trust-boundary validation needs the same explicit schema work.

### Implement candidates as ordinary Python plugins

Rejected because importing candidate code into the control-plane process would
conflate candidate and trusted authority.

## Validation evidence

- [Contract validator tests](../../tests/test_contracts.py)
- [Canonicalization tests](../../tests/test_canonical.py)
- [Kernel authorization tests](../../tests/test_kernel.py)
- [Deterministic simulator and shield tests](../../tests/test_cache.py)
- [Exact full-run replay tests](../../tests/test_prototype.py)

CPU/wall/memory isolation, forbidden-effect tests for candidate-supplied code,
and a process boundary remain required before M2/M3 or D1.

The project owner delegated D0 prototype decisions on 2026-08-01. This accepts
the scoped runtime choice for offline execution only; it does not accept Python
process boundaries as a security sandbox.

## Revisit criteria

Revisit before M2/M3, before D1, if profiling shows interpreter distortion of
the representation experiments, or when a supported strongly typed toolchain is
available. Independent review remains mandatory before D1, M2/M3 candidate
execution, or any containment claim.

## 2026-08-01 scoped D1 implementation amendment

[Decision 0006](0006-use-counterfactual-shadow-before-serving.md) permits local
D1 implementation evidence for the same closed, reviewed M1 data IR. That path
now uses a resource-limited subprocess and independent reference validation.
This amendment does not authorize candidate-supplied code, operational traffic,
sensitive traces, D2, or a hostile-code containment claim. Those retain the
independent-review requirement above.
