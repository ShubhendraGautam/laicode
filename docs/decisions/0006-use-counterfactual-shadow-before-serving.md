# Decision 0006: Require counterfactual shadow before served effects

- **Status:** accepted for prototype v1
- **Date:** 2026-08-01
- **Owners:** project owner; implementation delegated to Codex
- **Reviewers:** project-owner review deferred; independent systems/security
  review required before D2
- **Scope:** closed cache-policy artifacts at D1 only

## Context

The D0 prototype makes an offline decision but does not show that an evaluated
artifact can participate in a long-running lifecycle without controlling served
state. The first offline winner, LFU, also regresses on the registered
recency-shift future workload. Sending that candidate directly to a canary would
ignore the strongest evidence produced by the prototype.

## Decision

Advance only to D1 counterfactual shadow:

- the immutable original LRU artifact remains the sole served champion;
- the offline-selected artifact receives an external, content-addressed
  event-count lease;
- champion and challenger receive the same ordered trace but maintain
  independent cache states;
- challenger choices never affect the champion, external state, or a response;
- each candidate evaluation runs in a subprocess with external CPU, wall,
  address-space, output, file-descriptor, and process limits;
- subprocess output is content-addressed and byte-compared with the supervisor's
  independent reference execution;
- the supervisor checks hard constraints and miss-ratio regression at frozen
  event checkpoints;
- a hard failure, worker failure, or regression beyond tolerance revokes the
  shadow lease; otherwise it expires without promotion;
- revocation verifies that the exact original artifact remained the
  last-known-good served artifact;
- the complete source D0 bundle, lease, trace, checkpoint evidence, worker
  results, ledger, and D1 decision are archived and exactly replayed.

The D1 lease uses logical event count rather than wall-clock expiry so the
prototype remains byte-replayable. This does not authorize D2 canary traffic.

## Consequences

- A workload can be imported through the canonical trace schema and evaluated
  through a realistic champion/challenger lifecycle.
- Search-plane or challenger failure leaves the champion unchanged.
- The system can demonstrate automatic revocation, but not rollback of served
  candidate state because D1 never gives the challenger served effects.
- Resource limits reduce accidental and bounded-worker risk. They are not a
  network syscall sandbox or a claim that Python process isolation contains
  arbitrary hostile native code.
- Any D2 transition needs trusted wall time, stronger isolation, independent
  monitoring, a human authorization path, and an exercised served-state
  rollback.

## Alternatives considered

### Promote the D0 winner directly

Rejected. Operational selection does not outweigh negative prospective evidence
and D0 contains no served-state recovery evidence.

### Simulate both policies in the supervisor process

Rejected for v1 because it would not establish an execution boundary or external
resource lease, even though the current artifact language is closed data.

### Add a network service immediately

Deferred. Network exposure adds authentication, protocol abuse, privacy,
availability, and operational rollback concerns unrelated to validating the D1
control loop.

## Validation evidence

- [Worker protocol, resource-limit, and external reference-validation tests](../../tests/test_isolation.py)
- [Twin-state, regression-revocation, lease-expiry, failure, lineage, tamper,
  and byte-exact replay tests](../../tests/test_shadow.py)
- [Worker, lease, checkpoint, ledger, and report schemas](../../schemas/README.md)

## Revisit criteria

Revisit before D2, wall-clock leases, arbitrary candidate code, private
candidate state, network ingestion, multiple challengers, or an isolation claim
against hostile code.
