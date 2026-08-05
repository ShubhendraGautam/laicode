# Architecture and research decisions

Use a decision record for choices that change the project’s claims, trust model,
experimental validity, interoperability, or cost of reversal. Examples include
the mutation language, evaluator policy, evidence partitions, statistical
method, sandbox, host language, artifact identity, and deployment authority.

Decision records are append-only project history. Amend a record with a dated
note or supersede it with a new record; do not silently rewrite an accepted
decision after experiments depend on it.

## Status values

- `proposed` — open for review;
- `accepted` — governs current work;
- `rejected` — considered but not adopted;
- `superseded by NNNN` — replaced by a linked decision;
- `retired` — no longer applicable and not replaced.

## Template

```markdown
# Decision NNNN: Short imperative title

- **Status:** proposed
- **Date:** YYYY-MM-DD
- **Owners:** names or roles
- **Reviewers:** names or roles
- **Scope:** affected epochs, components, studies, or system/authority profiles

## Context

State the decision pressure, evidence, assumptions, and constraints.

## Decision

State the chosen rule precisely enough to test.

## Consequences

List expected benefits, costs, risks, and migrations.

## Alternatives considered

Record credible alternatives and why they were not selected.

## Validation evidence

Link tests, experiments, reviews, or analyses required to keep this accepted.

## Revisit criteria

List events or evidence that require reconsideration.
```

Number records monotonically. Acceptance requires an owner, at least one
reviewer independent of the implementation where practical, and links to any
gate evidence the decision claims to satisfy.

## Records

Records 0001-0011 governed the cache-policy control plane, the hardware and
comparator tracks, and the A0/A1 language epochs. All of that code was removed
when the project narrowed on 2026-08-05; those records are preserved at the
`archive/pre-narrowing` tag rather than kept here, because a decision governing
nothing is the kind of artifact rule R7 exists to prevent.

Numbering stays monotonic so surviving cross-references keep their meaning.

- [0012 — Add bounded user-defined functions and a static call graph](0012-add-bounded-user-defined-functions.md)
- [0013 — Measure vocabulary transfer by matched-budget synthesis](0013-measure-vocabulary-transfer-by-synthesis.md)

New records are subject to the acceptance rules in the
[research charter](../charter.md); in particular R7, which forbids a decision
record for a capability that does not run.
