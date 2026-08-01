# Decision 0005: Use a hash-chained append-only ledger at D0

- **Status:** accepted for prototype v0
- **Date:** 2026-08-01
- **Owners:** project owner; implementation delegated to Codex
- **Reviewers:** project-owner review deferred; storage/security review required
  before multi-user or D1 operation
- **Scope:** local single-writer D0 candidate, evidence, and decision provenance

## Context

The prototype must retain rejected candidates and make its decision replayable.
It does not yet need a distributed database, signing service, or concurrent
control plane. A normal mutable JSON result file would not expose deletion,
reordering, or prior-event edits.

## Decision

Use two related content-addressed structures:

1. Candidate manifests are canonical immutable JSON values. Their candidate ID
   is SHA-256 over the complete manifest, excluding no mutable timestamp because
   prototype manifests contain no timestamp.
2. Lifecycle and run events are canonical JSON Lines records. Every event covers
   its sequence number, previous event ID, type, candidate/artifact references,
   and payload. Its event ID is SHA-256 over that event. Appends take an exclusive
   file lock, validate the complete existing chain, append one canonical line,
   flush, and `fsync` before returning.

The D0 lifecycle records proposed, built, verified, search evaluated,
operationally evaluated, eligible/rejected, offline champion selected, decision
frozen, prospective evaluated, research audit consumed, and run completed. An
offline champion selection is not a deployment or stable-production promotion.

A run bundle stores canonical contract, experiment manifest, artifacts,
candidate manifests, trace payloads, full trusted evaluations, decision, audit
report, and ledger. Replay verifies every content hash and chain link, reruns the
simulator, and reconstructs the decision.

## Consequences

- Edits, deletion from the middle, reordering, and truncation are detectable when
  the expected final ledger ID is available from the run report.
- A local maintainer with write access can replace both the ledger and its
  expected ID. D0 therefore claims integrity checking, not authenticated
  non-repudiation.
- Canonical JSONL is inspectable and dependency-free but less query-efficient
  than SQLite or an event database.
- Raw trace/evaluation payloads may be much larger than aggregate records; the
  smoke bundle remains intentionally small and synthetic.

## Alternatives considered

### Mutable JSON summary

Rejected because failed candidates and earlier decisions could disappear
without detection.

### SQLite immediately

Deferred. SQLite is likely useful for analysis and indexes, but database triggers
alone do not supply authenticated append-only history. The canonical event model
can later be stored in SQLite without changing event identity.

### Signed transparency log

Deferred until signing identity, key storage, trusted time, rotation, and
compromise recovery are designed. Pretending a local development key solves
those questions would create false assurance.

## Validation evidence

- [Candidate identity, chain replay, concurrent append, mutation, reorder, and
  truncation tests](../../tests/test_provenance.py)
- [Complete run, final-event pinning, bundle tamper, and exact decision replay
  tests](../../tests/test_prototype.py)
- [Candidate and ledger record schemas](../../schemas/README.md)

## Revisit criteria

Revisit before multiple writers, remote workers, credentials, D1, retention of
non-synthetic data, or any authenticated audit claim.
