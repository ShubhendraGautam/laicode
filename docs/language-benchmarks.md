# Cross-language benchmark laboratory

## Purpose

B0 answers two different questions without conflating them:

1. Does the same LAIcode runtime improve as its vocabulary grows from cycle 0
   to cycle 1 to cycle 2?
2. How far is the current prototype from mature direct implementations in C,
   Python, and JavaScript?

The first is the evidence about language evolution. The second is an
engineering-gap report. It is not a claim that a language is intrinsically
better or worse.

## One-command benchmark

Use a path that does not exist:

```sh
python3 -m laicode smoke-language-comparators /tmp/laicode-comparators
```

This command creates and replays a complete E-H0 machine experiment, generates
a deterministic comparator package, verifies all nine package files byte for
byte, detects available local toolchains, builds applicable adapters, checks
every semantic checksum, and archives noisy host measurements.

The default protocol uses scale 50, three warmups, seven steady-state trials,
five repeated AOT build trials, and five cold-start trials. Smaller values are
available for development only:

```sh
python3 -m laicode smoke-language-comparators /tmp/comparator-dev \
  --scale 2 --trials 3 --warmups 1 --startup-trials 3
```

Individual stages are also exposed:

```sh
python3 -m laicode prepare-language-benchmark \
  /tmp/machine-run /tmp/comparator-package

python3 -m laicode replay-language-benchmark \
  /tmp/machine-run /tmp/comparator-package

python3 -m laicode run-language-benchmark \
  /tmp/machine-run /tmp/comparator-package /tmp/comparator-host
```

## Adapters and benchmark pits

The current local suite includes:

- LAIcode cycle 0: primitive generated-C switch interpreter;
- LAIcode cycle 1: the same backend with one learned operation;
- LAIcode cycle 2: the same backend with two learned operations;
- direct C11 compiled with GCC `-O2`;
- direct C11 compiled with Clang `-O2`;
- direct Python 3 with explicit `u64` masking; and
- direct JavaScript on Node using `BigInt` for exact `u64` behavior.

Optional adapters are marked as skipped when their toolchain is absent. The
three pits are:

| Pit | Question |
| --- | --- |
| `reuse_holdout` | Do learned phrases help in protected new contexts? |
| `audit_transfer` | Do they survive post-freeze unseen-context transfer? |
| `shift_no_reuse` | What happens when the workload contains no learned phrase? |

All adapters execute the same programs, weighted invocation counts, inputs,
and checksum fold. A mismatch invalidates the run.

## Metrics

The report keeps each cost dimension separate:

- raw and median steady-state nanoseconds;
- picoseconds per pipeline invocation;
- median absolute deviation and full trial spread in parts per million;
- raw repeated AOT build times and median;
- raw cold-start trials and median;
- peak resident memory from GNU `time` when available;
- source and runnable artifact bytes;
- source/artifact/toolchain identities; and
- semantic checksum for every adapter and pit.

Runtime installation size, energy, hardware performance counters, and human
engineering effort are not yet measured. Interpreted-source artifact size does
not include the Python or Node installation, so it must not be directly read as
a deployment-size win.

## Initial noisy snapshot

One code-current release run on the development WSL2 x86-64 host produced these
steady-state medians. Its deterministic package is
`sha256:399b64791c1d58164827f8847665ee9fb46539867955b18b17f14cc32598165b`
and its generated noisy host report is
`sha256:174a73f6dd7ab1b4e48f1e739c66fed417ea3a2ab8752d7eff28dd019bbb432c`.
These values are an example of the report format, not a stable release
promise:

| Adapter | Reuse | Audit transfer | No-reuse shift |
| --- | ---: | ---: | ---: |
| LAIcode cycle 0 | 1.307 ms | 0.721 ms | 0.405 ms |
| LAIcode cycle 1 | 0.589 ms | 0.345 ms | 0.306 ms |
| LAIcode cycle 2 | 0.532 ms | 0.295 ms | 0.411 ms |
| direct C11 / GCC | 0.103 ms | 0.054 ms | 0.036 ms |
| direct C11 / Clang | 0.094 ms | 0.051 ms | 0.026 ms |
| Python 3 direct | 50.581 ms | 29.253 ms | 21.248 ms |
| JavaScript / Node direct | 13.577 ms | 11.370 ms | 7.725 ms |

The useful reading is:

- cycles 1 and 2 both beat cycle 0 on reuse and audit;
- cycle 2 is best on reuse and audit in this run;
- cycle 2 regresses on the no-reuse shift, where deterministic token counts do
  not improve;
- optimized direct C is still the native-performance target by a wide margin;
- the narrow LAIcode backend beats these Python/JavaScript adapters because it
  is compiled C operating on a tiny kernel—not because B0 proves LAIcode is a
  superior general language.

A preceding run on the same host produced materially different absolute values
and a different cycle-1/cycle-2 ordering on reuse. That instability is retained
as evidence that repeated independent sessions and confidence intervals are
needed before performance promotion uses host data.

## Output

```text
/tmp/laicode-comparators/
├── machine/                 replayable source E-H0 experiment
├── benchmark-package/
│   ├── benchmark-manifest.json
│   ├── reference-results.json
│   ├── package-record.json
│   └── sources/             three LAIcode, C, Python, and JS runners
└── host-results/
    ├── artifacts/           compiled runners
    ├── raw/                 per-adapter/per-pit timing protocol output
    └── benchmark-report.json
```

The content-addressed package is deterministic. The host report is intentionally
not exactly replayable because it contains real timing, memory, build, runtime,
compiler, and operating-system observations.

## Growth path

Future benchmark epochs should add real task families rather than merely more
micro-operations: branching state machines, memory scans, codecs, parsers,
query kernels, tensor transforms, and accelerator command streams. Each family
needs a frozen semantic contract and equivalent implementations.

Rust, Go, JVM, WebAssembly, RISC-V, GPU, FPGA/HLS, energy counters, and hardware
performance counters are planned comparators when their toolchains and target
authority are available. The exploratory H1
[hardware-feedback lifecycle](hardware-feedback.md) now aggregates repeated
sessions on one pinned host into an offline profile. Independent-machine runs
and external review remain mandatory before a confirmatory or deployed policy.
