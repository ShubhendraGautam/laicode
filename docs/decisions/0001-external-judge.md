# Decision 0001: Keep the judge outside candidate control

- **Status:** accepted for Phase 0
- **Date:** 2026-07-31
- **Scope:** all evolution epochs

## Context

The project aims to let a deployed program use execution evidence to generate
and promote improved successor versions. If a candidate can modify its objective,
constraints, evaluator, evidence, promotion rule, or audit trail, the cheapest
path to a higher score may be to redefine or forge success.

At the same time, evaluators and policies will need legitimate maintenance. They
cannot be immutable for the lifetime of the project.

## Decision

Candidate programs and candidate generators cannot write, replace, configure, or
authorize:

- the active evolution contract;
- the candidate semantic kernel, canonicalization, primitive meanings, required
  lowering rules, or model-action validator;
- required evaluators and trusted metric collectors;
- evidence partitioning and protected operational/audit data;
- the promotion and rollback controller;
- capability and resource policy;
- candidate lineage and decision records.

These components form a candidate-immutable root of trust. Authorized human
governance may update them through a separately authenticated process. A material
update starts a new evolution epoch and records a new version. Baselines are
rerun when needed for comparison.

Candidates may propose evaluator improvements as untrusted artifacts, but those
proposals have no authority and follow the external governance path.

Candidates may define authorized transparent abstractions that lower into the
unchanged semantic kernel. This grows the solution vocabulary without granting
authority to redefine execution, verification, or success.

## Consequences

### Positive

- Improvement has a stable operational meaning within an epoch.
- Candidates cannot pass by weakening tests or falsifying their own score.
- Promotion decisions can be audited and replayed.
- Candidate generation can be treated as adversarial without trusting a
  particular model or search algorithm.
- Evaluators remain maintainable through explicit versioned governance.

### Costs

- The supervisor and evaluator become part of the assurance burden.
- A flawed judge can still select harmful behavior.
- Changes across epochs require baseline reruns and careful comparability claims.
- The design is not fully recursively self-improving.
- Some useful meta-optimization requires a slower human-governed path.

## Alternatives rejected

### Let candidates modify tests and evaluator code

Rejected because generated tests are useful evidence but cannot be allowed to
erase independent requirements or authorize their own producer.

### Permit evaluator changes if aggregate score rises

Rejected because scores before and after a changed measurement process are not
necessarily comparable.

### Freeze the entire system permanently

Rejected because security fixes, evaluator corrections, and objective changes
are legitimate. Candidate-immutable is the needed property, not eternal
immutability.

### Allow recursive meta-evolution immediately

Rejected for the initial research program because it removes the independent
authority needed to interpret empirical improvement. It may be studied later as
a separate threat model and research question.

## Revisit criteria

Revisit only after LAIcode:

- demonstrates bounded evolution at mutation level M3 and a reviewed deployment
  authority level;
- demonstrates useful typed/effect-checked abstraction transfer with
  machine-checkable lowering at R4/L2, if the proposed change concerns
  learner-driven language growth;
- has a mechanized or otherwise precise meta-policy for evaluator changes; and
- can state a falsifiable assurance claim for the new trust model.
