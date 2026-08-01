# Owned-vector and typed-record language

## What A1 adds

A1 makes the algorithm language constructive. An A0 program can inspect a
read-only array and return a scalar or pair; an A1 program can additionally own
bounded mutable storage and return a newly constructed collection or a typed
record.

The `OwnedVectorRecordKernelV1` epoch provides:

- immutable `array<i64>` input and locally owned `vector<i64>` storage;
- explicit vector capacity, checked append, length, and indexing;
- a hard 256-element limit for input and every owned vector;
- vector outputs and named records with statically checked ordered fields;
- signed i64 scalars, booleans, locals, assignment, loops, and branches; and
- transparent learned statement intrinsics with exact primitive lowerings.

A1 is separate from A0. Existing A0 programs, identities, and replay bundles
remain on `StructuredI64ArrayKernelV0`.

## One-command showcase

Use a path that does not exist:

```sh
python3 -m laicode smoke-collection-language /tmp/laicode-collections
```

The command grows two vocabulary entries across three cycles, validates seven
tasks in the trusted interpreter, regenerates the 138-file bundle byte for byte,
compiles 13 representative C11 translations with strict warnings, and executes
416 archived cases natively.

Individual stages are also available:

```sh
python3 -m laicode run-collection-experiment /tmp/collection-bundle
python3 -m laicode replay-collection-experiment /tmp/collection-bundle
python3 -m laicode validate-collection-native \
  /tmp/collection-bundle /tmp/collection-native
```

## What the language looks like

The final-cycle Remove Element program renders as:

```text
record collection_result { values: vector<i64>, length: i64 }

algorithm remove_element(nums: array<i64>, target: i64) -> collection_result {
    own out: vector<i64> capacity len(nums)
    for i in 0..len(nums) {
        op_24143553<append_indexed_if>(out, (nums[i] != target), nums, i)
    }
    return collection_result { values: out, length: len(out) }
}
```

The return is not a display-only wrapper. The verifier checks the record name,
field order, field names, and each field type. The interpreter returns the owned
values plus their logical length, while generated C copies the vector into a
bounded result structure and validates the same record fields.

## How the language grows

The A1 learner walks statements in pre-freeze training programs and counts
typed structural forms by distinct task identity. A candidate must appear in at
least two tasks and contain multiple primitive operations.

Cycle 1 observes copy and reverse programs and learns:

```text
push_indexed(vector, array, index)
    = vector.push(array[index])
```

Cycle 2 adds two stable-filter programs and learns:

```text
append_indexed_if(vector, condition, array, index)
    = if condition { vector.push(array[index]) }
```

| Cycle | New training tasks | Entries | All-task dispatches |
| --- | --- | ---: | ---: |
| 0 | none | 0 | 20,473 |
| 1 | copy array, reverse array | 1 | 18,859 |
| 2 | filter positive, filter not-target | 2 | 17,854 |

Each entry archives its exact statement lowering, typed operands, parent
vocabulary, learner identity, evidence-catalog identity, training-task
identities, occurrence count, and estimated dispatch saving. Encoding changes
the machine-facing program but never the trusted core program.

## Task validity

The study registers four learning tasks and three platform-style tasks:

| Task | Partition | Output and contract |
| --- | --- | --- |
| copy array | learning cycle 1 | owned vector |
| reverse array | learning cycle 1 | owned vector |
| filter positive | learning cycle 2 | stable filtered vector |
| filter not-target | learning cycle 2 | stable filtered vector |
| remove element | protected holdout | LeetCode 27-style values-and-length record |
| running sum | protected holdout | LeetCode 1480-style vector |
| move zeroes | post-freeze audit | LeetCode 283-style functional vector |

Every task has 32 deterministic cases and an independent Python oracle. All 224
cases pass in every interpreter cycle. The learned forms transfer without
access to protected or audit evidence:

| Task | Cycle 0 | Cycle 2 | Dispatch reduction |
| --- | ---: | ---: | ---: |
| remove element | 3,224 | 2,682 | 542 |
| move zeroes | 3,754 | 3,136 | 618 |

Running Sum is deliberately retained even though it does not reuse the current
vocabulary: it proves A1 can construct computed values rather than only copy or
filter input elements.

These are locally frozen equivalent contracts, not official platform results.
LAIcode does not submit to LeetCode, invoke an account, claim hidden-test
acceptance, or use platform-controlled resource measurements.

## Compilation and behavior

The C backend lowers both learned forms through their archived primitive
meaning. Each translation unit contains:

- a fixed `nums, target` input ABI;
- fixed local storage for at most 256 signed i64 vector elements;
- checked input/vector indexing, append capacity, and arithmetic;
- an explicit loop budget;
- comments identifying every learned entry and lowering;
- all 32 archived cases in a self-checking native harness; and
- a deterministic result checksum over vector elements and record fields.

This backend demonstrates semantic preservation, not native acceleration. A
mature C compiler may optimize primitive and learned lowerings to identical
machine code.

Execution traces make allocation, append, learned-intrinsic use, assignment,
and return events inspectable. The trace is bounded to 256 events and records
when it was truncated.

## Output layout

```text
/tmp/laicode-collections/
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
`sha256:db9d15245fcd0fa270646178234af5e80585d4dcc20a0df9e237dd64f4feb5e4`;
the final vocabulary is
`sha256:134f05ea8347fe7d776fd94ecd2c2c8e7a94044a7b27dae15e94c50ca4a91fd4`;
and the code-current native report is
`sha256:57d133dc1b70114a7c52a90e27342f0f69388b9c7bcbd21188b2c42c2bd864e5`.

## Current boundary and next growth

A1 vectors are bounded values backed by fixed local storage, not a general heap.
Records contain exactly one vector field in this epoch. There are no borrowed
references, aliasing, general allocation, strings, maps, graphs, user-defined
functions, recursion, or I/O.

The next language epoch should add bounded user-defined functions and a
statically limited call graph. Recursion should follow only with an explicit
depth budget and separate native/interpreter validity evidence. Strings or
graph storage remain later capability families.
