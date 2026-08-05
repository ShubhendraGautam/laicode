# Learned-vocabulary synthesis transfer

## What A2-S tests that nothing else does

The A0, A1, and A2 studies all follow the same shape: a human writes task
programs, the learner notices a repeated form across two of them, and an encoder
substitutes it back. That demonstrates the machinery is sound. It does not test
the claim in the [research charter](charter.md) — that a model-native
representation and structured feedback help a machine **construct** programs
more effectively.

Nothing in the repository searched for a program until A2-S. This study does,
and it is the first result here that could have come out the other way.

## The experiment

A synthesizer enumerates candidate loop bodies for a fixed skeleton:

```text
algorithm <task>(nums: array<i64>, target: i64) -> i64 {
    let acc = 0
    for i in 0..len(nums) {
        <BODY>
    }
    return acc
}
```

Two arms differ in exactly one respect — the vocabulary available:

- **primitive**: `add`, `sub`, and comparisons over `acc`, `nums[i]`, `target`,
  and the constants 0, 1, -1;
- **learned**: the same, plus the A2 cycle-2 entries `abs_value` and `max_of`
  as callable operators.

Both arms share one budget, one search procedure, and one enumeration order.
The metric is **candidates evaluated**: deterministic, machine independent, and
reproducible, in keeping with the rule that wall-clock timing never enters a
selection identity. Ratios are carried as integer parts per million because the
canonical JSON profile admits only signed 64-bit integers.

## One-command run

```sh
python3 -m laicode smoke-function-synthesis /tmp/laicode-synthesis
```

The registered budget is 100,000,000 candidates per arm. Reduce it with
`--budget` for a fast pass; tasks that do not resolve report `budget` rather
than being silently truncated.

## Results

The vocabulary trained on **none** of these tasks.

### Treatment: tasks that need absolute value or maximum

| Task | primitive | learned | Reduction |
| --- | ---: | ---: | ---: |
| sum absolute deviation | 77,663,784 | 10,362 | 7,495x |
| max absolute deviation | >36,161,701 | 10,364 | >=3,489x |
| sum positive part | 54,653 | 2,667 | 20.5x |
| max shifted value | 55,183 | 2,691 | 20.5x |

The learned arm's solutions are the ones a person would write:

```text
acc = (acc + op_536ccded<abs_value>((nums[i] - target)))
acc = op_1d947425<max_of>(acc, op_536ccded<abs_value>((nums[i] - target)))
```

### Control: tasks solvable with add and sub alone

| Task | primitive | learned | Cost |
| --- | ---: | ---: | ---: |
| sum all | 44 | 47 | 6.8% more |
| count all | 48 | 54 | 12.5% more |
| sum shifted | 2,379 | 2,689 | 13.0% more |

Both arms return the **identical program** on every control, so the difference
is purely the cost of sifting a larger pool. The control family exists so that a
favourable result stays falsifiable: without it, a clean sweep would be
unfalsifiable rather than convincing. The tax is asserted in the test suite, not
merely observed.

## Why it works, which is not the obvious reason

The gain is not primarily that learned programs are shorter. It is **which pool
the solution lives in**. Enumeration proceeds by size, and conditional
statements are a vastly larger pool than plain assignments. On sum positive part
the primitive arm must reach a conditional:

```text
if acc < (acc + nums[i]) { acc = (acc + nums[i]) }
```

while the learned arm answers with an assignment:

```text
acc = op_1d947425<max_of>(acc, (acc + nums[i]))
```

Vocabulary relocated the answer out of the expensive region of the search space.
Compression is a second-order effect.

## Two results that cut against a clean story

**A decoy.** On max absolute deviation the primitive arm's first hit at
36,161,701 candidates fits all twelve training cases and **fails** the held-out
cases. It did not solve the task. Its true cost is unknown and strictly greater,
so the ratio is reported as a lower bound. The report marks this in data via
`ratio_is_lower_bound`, which is also set whenever an arm stopped at the budget.

Every learned solution generalized. A larger unstructured space is denser in
accidental fits, so this is a solution-quality effect on top of the search-cost
one.

**The tax is real.** Carrying two extra entries costs 6.8% to 13.0% more search
on tasks that cannot use them. Any honest account of learned abstraction has to
report this alongside the wins.

## Trust boundary

Search runs over compiled closures, because enumerating tens of millions of
candidates through the trusted interpreter is not feasible. The fast path is
allowed to **find**; it is never allowed to **certify**. Every reported solution
is materialized as a real `FunctionProgram`, validated by `validate_program`,
and re-executed by the trusted A2 interpreter against independent oracles. A
disagreement between the two paths raises rather than reports, and
`all_reported_solutions_kernel_verified` records the outcome.

Learned entries appear in synthesized programs as genuine `learned_call` nodes
carrying the content-hash identity of the A2 vocabulary entry they invoke, so a
synthesized program is an ordinary kernel program with ordinary provenance.

## What this does not show

The vocabulary was learned from **hand-written** training programs. This study
shows that *given* good abstractions, search cost collapses on unseen tasks. It
does not show that the system discovers good abstractions unaided. Closing that
loop — a synthesizer that produces the training programs its own learner then
abstracts from — is the next experiment, not this one.

Further bounds, all recorded in the run report:

- one fixed accumulator skeleton rather than open-ended program search;
- enumerative search, not a model-driven proposer;
- synthetic deterministic cases, not hidden platform tests;
- a non-generalizing hit makes its arm's cost a lower bound only.

## Output layout

```text
/tmp/laicode-synthesis/
└── bundle/
    ├── experiment-manifest.json
    ├── tasks/<task>/contract.json
    ├── results/<task>/{primitive,learned}.json
    ├── results/<task>/{primitive,learned}.lai
    └── run-report.json
```
