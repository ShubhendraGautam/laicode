# Decision 0013: Measure vocabulary transfer by matched-budget synthesis

- **Status:** accepted for exploratory A2-S
- **Date:** 2026-08-02
- **Owners:** project owner; implementation delegated to Codex
- **Reviewers:** independent synthesis/statistics review open
- **Scope:** `(R4, M3, G2, L2, D0; F3)` synthesis transfer study

## Context

A0, A1, and A2 all measure learned vocabulary the same way: a human writes the
task programs, the learner extracts a repeated form, and an encoder substitutes
it back. Every reported "transfer" is therefore a statement about an encoder,
not about problem solving. The programs were already written.

The [research charter](../research-charter.md) asks whether a model-native
representation helps a machine **construct** programs. No study in this
repository answered that, because no study searched for a program.

## Decision

A2-S adds a synthesis study over the existing A2 kernel. It does not add kernel
semantics, does not change any epoch, and does not grant new authority.

- A fixed accumulator-fold skeleton bounds the search to one loop body.
- Two arms share one search procedure, one enumeration order, and one candidate
  budget, differing only in the vocabulary available.
- The metric is candidates evaluated: deterministic, machine independent, and
  free of wall-clock timing.
- Ratios are carried as integer parts per million, because the canonical JSON
  profile admits only signed 64-bit integers.

## Control requirement

The registered task set **must** contain a control family solvable with `add`
and `sub` alone, where the learned vocabulary cannot shorten any solution.

Without controls, a favourable result is unfalsifiable: every task would be one
the vocabulary happens to help, and a clean sweep would be indistinguishable
from a rigged benchmark. The measured control cost of 6.8% to 13.0% additional
search is a required output, not an incidental observation, and is asserted by
the test suite.

## Verification boundary

Enumerating tens of millions of candidates through the trusted interpreter is
not feasible, so search runs over compiled closures. That fast path is allowed
to **find** and is never allowed to **certify**:

- every reported solution is materialized as a real `FunctionProgram`;
- it is validated by `validate_program` under the arm's vocabulary;
- it is re-executed by the trusted interpreter against independent oracles; and
- disagreement between the two paths raises rather than reports.

Learned entries appear as genuine `learned_call` nodes carrying the content-hash
identity of the vocabulary entry they invoke.

## Honest-reporting requirement

A reported candidate count is a **lower bound** whenever the arm did not
actually solve its task — because it stopped at the budget, or because its
program failed held-out cases. Both conditions set `ratio_is_lower_bound` in the
run record. This is a data field rather than prose so that a truncated or decoy
run cannot be read as a solved one by any downstream consumer.

## Consequences

- The project gains its first result that could have come out the other way.
- The measured effect is attributable to vocabulary alone, because the arms
  differ in nothing else.
- The study measures the value of *having* abstractions, not of discovering
  them; the vocabulary still comes from hand-written training programs.
- A fixed skeleton is far narrower than open-ended program search, so no general
  synthesis claim is authorized.
- Enumerative search is not a model-driven proposer, so no claim about LLM
  proposal quality is authorized.

## Validation evidence

Required evidence includes independent oracles per task, held-out
generalization checks, control-family tax measurement, identical control
programs across arms, kernel verification of every reported solution, real
vocabulary identities inside synthesized programs, budget reporting rather than
silent truncation, lower-bound marking, schema validation, tamper rejection, and
byte-identical replay.

## Revisit criteria

Start another decision before claiming autonomous abstraction discovery,
removing the control family, reporting a ratio without its lower-bound flag,
certifying a solution on the fast path alone, searching without a matched
budget, generalizing beyond the fixed skeleton, or attaching any deployment
authority to a synthesized program.
