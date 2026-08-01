# Decision 0002: Separate governance, semantic kernel, and learned abstractions

- **Status:** accepted for prototype v0
- **Date:** 2026-07-31
- **Owners:** project owner
- **Reviewers:** project-owner approval recorded 2026-08-01; independent
  programming-languages/ML review required before a confirmatory experiment
- **Scope:** model-native representation and every R2+ experiment

## Context

The project intends to give LLMs and other program learners a more semantic way
to construct and learn programs than unconstrained editing of human-oriented
source text. The existing evolution-contract design governs what may change, but
it does not itself define the program representation a learner manipulates.

Letting a learner change primitive meanings, its verifier, or the contract would
make execution feedback incomparable and violate the external-judge boundary.
Freezing every abstraction, however, would exclude the important hypothesis that
a learner can improve its reusable programming vocabulary.

## Decision

Separate three planes:

1. a human-governed evolution contract defining authority and evidence;
2. a stable trusted semantic kernel defining canonical typed programs, effects,
   construction actions, execution, and lowering; and
3. a transparent abstraction layer whose fixed, run-scoped, or persistently
   learner-updated contents must lower into the unchanged kernel with versioned
   evidence.

Models interact through an episodic typed action/observation protocol. Text may
transport proposed actions, but canonical semantic objects determine identity and
meaning.

Changing the contract, kernel, compiler semantics, primitive meaning, or required
verifier starts a new human-governed epoch. Adding an authorized transparent
abstraction is a candidate change within the current epoch.

The project owner approved this decision for implementation on 2026-08-01. The
approval authorizes the prototype separation and tests; it does not by itself
freeze the kernel/action schema or satisfy the independent-review gate for a
confirmatory experiment.

## Consequences

- The project has two explicit research contributions under test: model-facing
  program construction and externally governed continual evolution.
- Vocabulary learning can be studied without granting authority to redefine
  execution or success.
- The kernel and action validator join the trusted computing base.
- Expressivity is intentionally bounded by what lowers to the kernel; broader
  host-language interoperation requires a later, weaker assurance claim.
- Structured action protocols, learned DSLs, and execution-guided synthesis are
  prior art, so value must be established through matched comparative studies.

## Alternatives considered

### Use ordinary source files as the only model interface

Retained as the R0 baseline, but rejected as the sole design because it cannot
isolate whether canonical typed actions and structured feedback help learning.

### Let the learner invent primitive semantics or its interpreter

Deferred to R5 research-only experiments because it changes the meaning of
evidence and expands the trusted computing base.

### Freeze the complete language and library

Rejected as the long-term design because it prevents testing reusable abstraction
learning. It remains the initial R2/R3 baseline.

## Validation evidence

Current prototype evidence:

- [fixed semantic kernel and action protocol](../../laicode/kernel.py);
- [program, action, state, result, and artifact schemas](../../schemas/README.md);
- [operational transition and R2/R3 identity tests](../../tests/test_kernel.py); and
- [canonicalization tests](../../tests/test_canonical.py).

Continuing validation requires:

- proof or independent checking of abstraction lowering within the stated model;
- R0–R3 matched-budget representation experiments; and
- an R4/L2 transfer study before claiming useful language growth.

## Revisit criteria

Revisit if an ordinary source/AST interface matches the proposed protocol, the
kernel blocks target-task expressivity, learned abstractions fail to transfer, or
new prior art subsumes the proposed distinction.
