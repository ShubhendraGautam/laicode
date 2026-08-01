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

- [0001 — Keep the judge outside candidate control](0001-external-judge.md)
- [0002 — Separate governance, semantic kernel, and learned abstractions](0002-model-native-language-planes.md)
- [0003 — Start the control-plane prototype in Python](0003-prototype-runtime.md)
- [0004 — Freeze deterministic cache semantics for prototype D0](0004-freeze-cache-d0-semantics.md)
- [0005 — Use a hash-chained append-only ledger at D0](0005-use-hash-chained-ledger-at-d0.md)
- [0006 — Require counterfactual shadow before served effects](0006-use-counterfactual-shadow-before-serving.md)
- [0007 — Study hardware-shaped vocabulary evolution](0007-study-hardware-shaped-vocabulary-evolution.md)
- [0008 — Separate learning curves from language comparisons](0008-separate-learning-curves-from-language-comparisons.md)
