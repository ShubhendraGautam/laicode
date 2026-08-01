# Visible algorithm language and validity laboratory

## What A0 demonstrates

A0 moves LAIcode beyond unary word pipelines into small, recognizable
algorithms. The fixed semantic kernel now supports:

- signed 64-bit scalars, booleans, read-only signed-integer arrays, and pairs;
- checked array access and checked arithmetic;
- typed declarations and assignments;
- bounded `for` and `while` loops;
- conditionals and one typed return; and
- transparent learned expression intrinsics with exact core lowering.

The result is a language you can inspect at every stage: core program, learned
program, vocabulary lineage, execution trace, generated C11, oracle evidence,
native artifact, and replay report.

## One-command showcase

Use a path that does not exist:

```sh
python3 -m laicode smoke-algorithm-language /tmp/laicode-algorithms
```

The command grows the vocabulary through two learning cycles, validates every
task through the trusted interpreter, regenerates the complete 138-file bundle
byte for byte, compiles representative C translations with strict warnings,
and executes the same archived cases natively.

Individual stages are available as well:

```sh
python3 -m laicode run-algorithm-experiment /tmp/algorithm-bundle
python3 -m laicode replay-algorithm-experiment /tmp/algorithm-bundle
python3 -m laicode validate-algorithm-native \
  /tmp/algorithm-bundle /tmp/algorithm-native
```

## What the language looks like

The cycle-2 maximum-subarray program renders as:

```text
algorithm maximum_subarray(nums: array<i64>, target: i64) -> i64 {
    let current = nums[0]
    let best = nums[0]
    for i in 1..len(nums) {
        current = max(nums[i], op_9f0f6b8c(current, nums, i))
        best = max(best, current)
    }
    return best
}
```

`op_9f0f6b8c` was not registered as a human primitive. The learner found the
same expression shape in two training tasks and persisted it as a vocabulary
entry. Its authoritative lowering is:

```text
op_9f0f6b8c(acc, array, index) = acc + array[index]
```

Cycle 1 independently learns:

```text
op_fa95198e(array, index, value) = array[index] == value
```

That operation subsequently appears in protected binary search and in the
post-freeze two-sum audit, even though neither task was available to its
learner.

## How growth works

The learner walks typed expression trees in pre-freeze training programs,
replaces variable leaves with typed holes, and counts structural patterns across
distinct tasks. A candidate must occur in at least two task identities and
contain at least two primitive operators. Selection is deterministic by saved
dispatch, pattern size, and canonical identity.

| Cycle | Training tasks added | New vocabulary | Total dispatches, all tasks |
| --- | --- | --- | ---: |
| 0 | none | primitives only | 11,820 |
| 1 | count target, linear search | fused element comparison | 10,659 |
| 2 | array sum, positive sum | fused element accumulation | 10,112 |

Each learned operation stores its typed holes, exact lowering tree, parent
vocabulary, evidence-catalog identity, training-task identities, occurrence
count, learner version, and estimated dispatch saving. Encoding never changes
the trusted core program or deletes the lowering.

## Compilation

The compiler verifies the encoded program against the selected vocabulary and
then lowers every learned operation back through its transparent core meaning.
It emits a self-checking C11 translation unit with:

- a fixed `nums: array<i64>, target: i64` ABI;
- checked addition, subtraction, division, and indexing helpers;
- explicit loop budgets;
- the learned entry identities and lowerings in source comments;
- all archived cases compiled into a native harness; and
- a deterministic result checksum.

The current C compiler can optimize primitive and learned forms to the same
native binary. That is a useful result: the learned vocabulary reduces the
machine-facing interpreter representation while exact lowering lets a mature
backend recover equivalent native code. A0 makes no native speedup claim.

## Platform-style validity

The registered study has four training tasks and three protected tasks:

| Task | Partition | Contract |
| --- | --- | --- |
| count target | learning cycle 1 | local training task |
| first linear-search index | learning cycle 1 | local training task |
| array sum | learning cycle 2 | local training task |
| sum positive values | learning cycle 2 | local training task |
| binary search | protected holdout | LeetCode 704-style contract |
| maximum subarray | protected holdout | LeetCode 53-style contract |
| two-sum indices | post-freeze audit | LeetCode 1-style contract |

Every task has 32 deterministic cases and an independent trusted Python oracle.
All 224 cases pass in all three interpreter cycles. The final release also
compiles and runs all seven cycle-2 tasks plus every cycle of the three
platform-style tasks: 13 translations and 416 native case executions pass.

Vocabulary transfer reduces dispatch without changing outputs:

| Protected task | Cycle 0 | Cycle 2 | Reduction |
| --- | ---: | ---: | ---: |
| binary search | 1,773 | 1,674 | 99 |
| maximum subarray | 1,512 | 1,328 | 184 |
| two-sum indices | 4,434 | 3,834 | 600 |

This is local contract-equivalence evidence. LAIcode does not scrape LeetCode,
call its judge, submit code under a user account, or claim an official Accepted
result. Hidden platform tests, exact submission wrappers, platform resource
limits, and legal/API integration remain separate work.

## Output layout

```text
/tmp/laicode-algorithms/
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
`sha256:63564c5c0f26d6653322dc4c6a6882b11e22b99c5c148a66d14dc8159bcfb19a`;
the final vocabulary is
`sha256:b31b4746cb959623b65e8e01ce222bb14e2222e10f5f1922e21304558819082d`.

## Current boundary and next growth

A0 is intentionally not a general-purpose language. It has no allocation,
strings, maps, graphs, recursion, user-defined functions, mutation of input, or
I/O. The next algorithm epoch should add one capability family at a time—first
owned vectors and structured records, then functions/recursion, then strings or
graph storage—while keeping independent oracles, complexity limits, transparent
lowering, and protected transfer tasks.
