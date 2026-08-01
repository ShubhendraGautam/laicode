# Decision 0008: Separate learning curves from language comparisons

- **Status:** accepted for exploratory B0
- **Date:** 2026-08-01
- **Owners:** project owner; implementation delegated to Codex
- **Scope:** current pure `u64 -> u64` E-H0 kernel on one local host

## Context

The project needs comparisons with established programming languages, both to
measure the current engineering gap and to observe whether repeated learning
improves the machine language. A single mixed leaderboard would answer neither
question cleanly. LAIcode currently uses a generated-C switch interpreter,
while direct C is ahead-of-time optimized and Python/JavaScript bring complete
runtime systems and different integer representations.

Timing is also unstable under CPU frequency changes, WSL virtualization,
compiler versions, JIT behavior, thermal state, and scheduling. Early language
generations are expected to lose or behave non-monotonically.

## Decision

Build B0 as two explicitly separate analyses over one correctness protocol:

1. **Evolution learning curve:** compare LAIcode cycle 0, cycle 1, and cycle 2
   with the same generated-C backend, compiler, flags, inputs, and trial rules.
   This is the primary evidence about whether vocabulary learning helps.
2. **Descriptive ecosystem comparison:** compare the current LAIcode backend
   with direct C11/GCC, C11/Clang, Python, and JavaScript/Node. This identifies
   practical gaps; it is not a causal ranking of language quality.

Every adapter must execute identical primitive semantics and input schedules.
A trusted Python-kernel reference freezes a checksum for every pit, and a
measurement is invalid if any adapter differs.

The first three pits are:

- `reuse_holdout`: learned phrases in protected new contexts;
- `audit_transfer`: post-freeze unseen-context transfer; and
- `shift_no_reuse`: a changed workload where learned vocabulary is unused.

Every available adapter uses the same scale, warmups, and odd trial count. B0
archives raw steady-state timings, medians, median absolute deviation, spread,
normalized picoseconds per pipeline invocation, repeated AOT build trials,
cold startup trials, peak RSS, source bytes, runnable artifact bytes, toolchain
identity, and semantic checksums.

Generated sources, the protocol, and trusted reference results form a
content-addressed package that must regenerate byte for byte before host
measurement. Host timing is a separate noisy report and cannot modify the E-H0
selection decision.

## Interpretation rules

- Retain every loss, regression, and non-monotonic learning step.
- Do not call LAIcode faster than another *language* merely because its current
  compiled backend beats that language's adapter on these microkernels.
- Report direct C as the current native ceiling, not an unfair baseline to hide.
- Compare results only within a pit; different pits perform different work.
- Do not combine build, startup, runtime, memory, and size into an arbitrary
  scalar score.
- Do not use a single host run as a confirmatory performance claim.

## Initial evidence

All seven locally available adapters—LAIcode cycles 0/1/2, GCC C11, Clang C11,
Python 3.10, and Node 24 JavaScript—produce the exact reference checksum on all
three pits. The nine-file deterministic comparator package replays exactly.

On the first release protocol, learned cycles substantially improve over cycle
0 on reuse and audit, but cycle ordering is not consistently monotonic and
cycle 2 regresses under shift. Direct optimized C remains decisively faster.
Absolute timing and even the cycle-1/cycle-2 ordering moved between repeated
host runs, confirming that raw distributions and longitudinal replication are
required.

## Consequences

- B0 is a benchmark laboratory, not a benchmark-game score.
- Current Python and JavaScript results include their runtimes but exclude
  runtime installation size; C/LAIcode artifact bytes include emitted binaries.
- JavaScript uses `BigInt` and Python uses explicit masking to preserve exact
  `u64` semantics, which is correct but not necessarily their idiomatic fastest
  representation.
- Energy, hardware counters, runtime installation size, human effort, broad
  application workloads, and independent machines remain outside B0.

## Revisit criteria

Create a new decision before adding a scalar composite winner, training on
benchmark results, selecting or retiring vocabulary from noisy host timing,
claiming cross-language superiority, or changing semantic work between
adapters. Extend B0 incrementally with Rust, Go, JVM, WebAssembly, GPU, RISC-V,
energy counters, and real application kernels when those toolchains and
registered workload contracts are available.
