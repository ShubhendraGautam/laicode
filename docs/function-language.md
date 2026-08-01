# Bounded-function and call-graph language

## What A2 adds

A0 learned expression shapes and A1 learned statement shapes. Both grow the
language by substituting fixed operator trees inline, so a program can never
give a computation a name, a signature, or a reuse boundary. A2 makes the unit
of abstraction a **function**.

The `CallGraphFunctionKernelV2` epoch provides:

- up to eight declared functions per program, at most four parameters each;
- parameters typed `i64`, `bool`, or immutable `array<i64>`;
- `i64` or `bool` returns, with early returns inside branches;
- calls resolved only against earlier declarations;
- a statically computed call depth of at most four; and
- transparent learned function abstractions with exact archived definitions.

A2 is separate from A0 and A1. Existing programs, identities, and replay bundles
remain on `StructuredI64ArrayKernelV0` and `OwnedVectorRecordKernelV1`.

## One-command showcase

Use a path that does not exist:

```sh
python3 -m laicode smoke-function-language /tmp/laicode-functions
```

The command grows two vocabulary entries across three cycles, validates seven
tasks in the trusted interpreter, regenerates the 138-file bundle byte for byte,
compiles 13 representative C11 translations with strict warnings, and executes
416 archived cases natively.

Individual stages are also available:

```sh
python3 -m laicode run-function-experiment /tmp/function-bundle
python3 -m laicode replay-function-experiment /tmp/function-bundle
python3 -m laicode validate-function-native \
  /tmp/function-bundle /tmp/function-native
```

## What the language looks like

The cycle-0 Highest Altitude program declares its own helper:

```text
fn max_of(a: i64, b: i64) -> i64 {
    if (a < b) {
        return b
    }
    return a
}

algorithm highest_altitude(nums: array<i64>, target: i64) -> i64 {
    let best = 0
    let altitude = 0
    for i in 0..len(nums) {
        altitude = (altitude + nums[i])
        best = max_of(best, altitude)
    }
    return best
}
```

By cycle 2 the same task carries no definition at all. The `use fn` block is the
archived vocabulary definition rendered for inspection, not part of the program:

```text
use fn op_1d947425<max_of>(a: i64, b: i64) -> i64 {
    if (a < b) {
        return b
    }
    return a
}

algorithm highest_altitude(nums: array<i64>, target: i64) -> i64 {
    let best = 0
    let altitude = 0
    for i in 0..len(nums) {
        altitude = (altitude + nums[i])
        best = op_1d947425<max_of>(best, altitude)
    }
    return best
}
```

## Why recursion is unrepresentable

A call resolves only against functions declared **earlier** in the same program,
and the entry point is declared last. A recursive or mutually recursive call
therefore names a function that does not yet exist, and is rejected during type
checking rather than by a separate cycle detector. The kernel additionally
computes a static call depth over both local and learned calls, rejects anything
deeper than four, and rejects any function that the entry point cannot reach.
The interpreter enforces the same depth budget at run time.

This is a strong structural guarantee and a real restriction: algorithms that
want mutual recursion cannot be written in A2 at all.

## How the language grows

The A2 learner reads the helper definitions of pre-freeze training programs and
groups them by name. A candidate must appear in at least two distinct task
identities with a **byte-identical definition** and contain at least two
statements. If two tasks declare the same name with different bodies, the
candidate is discarded rather than reconciled.

Cycle 1 observes the two absolute-magnitude programs and learns:

```text
abs_value(x: i64) -> i64
    = if x < 0 { return 0 - x }
      return x
```

Cycle 2 adds the two maximum-tracking programs and learns:

```text
max_of(a: i64, b: i64) -> i64
    = if a < b { return b }
      return a
```

The kernel deliberately has no `max` primitive, so `max_of` is something the
learner discovers rather than something the kernel supplies.

| Cycle | New training tasks | Entries | Definition statements | All-task dispatches |
| --- | --- | ---: | ---: | ---: |
| 0 | none | 0 | 28 | 44,920 |
| 1 | sum absolute, count large absolute | 1 | 16 | 44,920 |
| 2 | max absolute, max prefix sum | 2 | 4 | 44,920 |

Each entry archives its exact definition tree, typed signature, parent
vocabulary, learner identity, evidence-catalog identity, training-task
identities, occurrence count, and estimated definition saving.

## What the cost column means

**Dispatch does not move.** This is the central A2 result and it is deliberate.
A learned abstraction removes a duplicated definition; the executed work is
unchanged, because calling a shared function costs exactly what calling a local
copy cost. The study asserts this equality per case: if an encoded program ever
consumed a different dispatch count than its core program, the run fails as an
encoding defect.

So A2 improves on a different axis from A0 and A1. Its improvement is
representational — 28 definition statements fall to 4 across the seven tasks —
and its evidence of correctness is that execution cost stayed *identical* rather
than improved. Claiming a speedup here would be claiming something the
measurement does not show.

## Task validity

The study registers four learning tasks and three platform-style tasks:

| Task | Partition | Contract |
| --- | --- | --- |
| sum absolute | learning cycle 1 | total absolute magnitude |
| count large absolute | learning cycle 1 | count magnitudes above the target |
| max absolute | learning cycle 2 | largest absolute value, zero when empty |
| max prefix sum | learning cycle 2 | largest inclusive prefix sum |
| highest altitude | protected holdout | LeetCode 1732-style contract |
| sum absolute deviation | protected holdout | LeetCode 462-style total-distance contract with a supplied target |
| max increasing difference | post-freeze audit | LeetCode 2016-style contract |

Every task has 32 deterministic cases and an independent Python oracle. All 224
cases pass in every interpreter cycle. The learned functions transfer without
access to protected or audit evidence:

| Task | Cycle 0 definitions | Cycle 2 definitions | Reduction | Dispatch change |
| --- | ---: | ---: | ---: | ---: |
| highest altitude | 3 | 0 | 3 | 0 |
| sum absolute deviation | 3 | 0 | 3 | 0 |
| max increasing difference | 6 | 3 | 3 | 0 |

Two local functions are deliberately **not** learned. `max_absolute_pair` occurs
in a single training task, so it fails the cross-task requirement and stays
local — while still calling two learned entries, which is what pushes that
program's static call depth to three. `min_of` occurs only in protected and
audit tasks, which the learner never sees, so the post-freeze program keeps
three definition statements it cannot abstract away. Both are evidence that the
eligibility rule binds.

These are locally frozen equivalent contracts, not official platform results.
LAIcode does not submit to LeetCode, invoke an account, claim hidden-test
acceptance, or use platform-controlled resource measurements.

## Compilation and behavior

Each declared function lowers to one `static` C function; learned entries lower
through their archived definitions under `lai_learned_<id>` names. Each
translation unit contains:

- a fixed `nums, target` input ABI and an `int64_t` result;
- array parameters passed as a `const` pointer and length pair;
- checked input indexing and checked addition and subtraction;
- an explicit loop budget shared across the whole call tree;
- comments carrying the static call depth, the resolved call graph, and every
  learned entry with its exact definition;
- all 32 archived cases in a self-checking native harness; and
- a deterministic result checksum.

Native validation additionally requires each task's checksum to be **identical
across all three cycles**, so learned abstraction provably did not change
compiled behaviour. This backend demonstrates semantic preservation, not native
acceleration.

Execution traces make call, return, assignment, and learned-call events
inspectable with their depth. The trace is bounded to 256 events and records
when it was truncated.

## Output layout

```text
/tmp/laicode-functions/
├── bundle/
│   ├── experiment-manifest.json
│   ├── tasks/<task>/
│   │   ├── contract.json
│   │   ├── cases.json
│   │   ├── program.json
│   │   └── program.lai
│   ├── vocabularies/cycle-{0,1,2}.json
│   ├── cycles/cycle-<n>/<task>/
│   │   ├── encoded-program.json
│   │   ├── program.lai
│   │   ├── program.c
│   │   ├── trace.json
│   │   └── validity.json
│   └── run-report.json
└── native/
    ├── artifacts/
    └── native-report.json
```

The code-current run report is
`sha256:114bee4984c9a4cd78135d0397b57dd6b1d6584f213df802507e58679f62bbaf`;
the final vocabulary is
`sha256:0b4198828d1bf344d486c526fffe19e696fb21baccf20708c0e2c302d505632b`;
and the code-current native report is
`sha256:70477eb8bad7da08e134c94bcf40bf0c903e2963b76a411671568a7aef2d0b7e`.

## Current boundary and next growth

A2 functions are pure, first-order, and scalar-returning. There are no recursive
or mutually recursive calls, indirect or dynamic calls, function values,
closures, generic signatures, default arguments, or helpers that return a
collection or record. A helper cannot construct an A1 owned vector, because the
two epochs are separate kernels.

The next language epoch should add depth-bounded recursion with an explicit
budget and separate interpreter and native evidence that the budget holds.
Collection-returning functions — the join between the A1 and A2 kernels — should
follow as its own epoch. Strings and graph storage remain later capability
families.
