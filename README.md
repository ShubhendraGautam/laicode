# LAIcode

[![CI](https://github.com/ShubhendraGautam/laicode/actions/workflows/ci.yml/badge.svg)](https://github.com/ShubhendraGautam/laicode/actions/workflows/ci.yml)

LAIcode is a research project studying one question:

> Does the system discover abstractions nobody gave it, and do those
> abstractions measurably reduce the cost of constructing programs it has never
> seen?

A result requires both halves — **discovery** and **transfer**. Neither alone
counts.

## Status

**No discovery result exists yet.**

What runs today is a typed bounded-function kernel, a matched-budget enumerative
synthesizer, and a frozen study comparing search cost with and without a learned
vocabulary. That study's vocabulary comes from programs a person wrote, so it
measures the value of good abstractions rather than their discovery — a
limitation recorded in the study's own report record, not just in prose.

The component that would close that gap,
[`function_discovery.py`](laicode/function_discovery.py), performs
anti-unification over synthesized programs and consults no table of known
abstractions. It is written, untested, and wired to nothing. Under the project's
own rules that makes it a draft, not a result.

See the [research charter](docs/charter.md) for the acceptance rules, the open
experiment, and the falsifiers registered before it runs.

## Scope

This repository was narrowed on 2026-08-05. It previously also asked whether
proposals could be evaluated and deployed through a candidate-inaccessible
governance boundary, which licensed a cache-policy control plane, counterfactual
shadow leases, an append-only ledger, cross-language benchmarks, hardware target
profiles, and two superseded language epochs.

That work is preserved at the `archive/pre-narrowing` tag and is not maintained
on `main`. Governance returns when there is a capability that needs governing.

```sh
git checkout archive/pre-narrowing -- <path>
```

## Quick start

Python 3.10 standard library only; no third-party dependencies.

Grow the A2 bounded-function language, replay it exactly, compile the generated
C11, and validate every archived case (the output path must not exist):

```sh
python3 -m laicode smoke-function-language /tmp/laicode-functions
```

Calls resolve only against earlier declarations, so recursion is
unrepresentable rather than rejected. Learned abstractions remove duplicated
definitions while interpreter dispatch stays exactly unchanged; that equality is
asserted per case rather than reported as a speedup.

Run the matched-budget synthesis transfer study:

```sh
python3 -m laicode smoke-function-synthesis /tmp/laicode-synthesis
```

Under one enumeration order and one budget, learned vocabulary cuts search on
treatment tasks and costs 7–13% more on control tasks that cannot use it. Both
figures are reported. The mechanism is relocation, not compression: vocabulary
moves a solution out of the conditional-statement pool into the far smaller
assignment pool. Neither figure is a deployment claim, and neither is evidence
of discovery.

Component checks:

```sh
python3 -m unittest discover -v
python3 -m laicode --help
```

GitHub Actions runs the suite on Python 3.10 and 3.14 for every pull request and
push to `main`. A nightly job runs the language and synthesis studies and retains
their evidence for 30 days.

## Documents

- [Research charter](docs/charter.md) — the question, the eight acceptance
  rules, current state, the open experiment, and its falsifiers.
- [Bounded-function and call-graph language](docs/function-language.md) — the A2
  kernel: named functions, forward-only resolution, static call graph.
- [Learned-vocabulary synthesis transfer](docs/synthesis-transfer.md) — the
  matched-budget study, its control family, and its recorded limitations.
- [Prior art](docs/prior-art.md) — a seed map, not a dated systematic corpus.
- [Decision records](docs/decisions/README.md) — the two decisions governing
  code that still exists.

## Claims

No novelty claim is authorized. Library-learning systems already perform
abstraction discovery with stronger learners. Any differentiator here would rest
on the governance boundary, which is exactly what has been deferred until there
is something to govern.

## Multi-agent development

When more than one coding agent works this repository at the same time,
coordinate through [gator-tools](https://github.com/ShubhendraGautam/gator-tools),
vendored here as a submodule:

```sh
node gator-tools/skills/multi-agent-coordination/scripts/coord.mjs
```

Run `git submodule update --init` if that directory is empty. Coordination state
lives in this repository's `.git/`, never in the submodule, and nothing the
project needs at runtime depends on it — a clone without submodules still works.
