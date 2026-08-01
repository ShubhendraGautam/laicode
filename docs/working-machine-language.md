# Working hardware-shaped language prototype

## What this is

E-H0 is an executable, deliberately small programming-language experiment. It
is not a new human syntax and it is not an unconstrained code-generating model.
Its authoritative programs are typed canonical data: pure `u64 -> u64`
pipelines over a fixed seven-operation kernel.

The part that evolves is the language vocabulary. Execution-weighted recurring
instruction graphs become anonymous superinstructions. Each learned operation
has a content identity and an exact primitive lowering, so it can be inspected,
replayed, verified, retired, or compiled without trusting a human-readable
name.

The implementation uses three languages at different boundaries:

- Python 3.10+ implements the learner, verifier, deterministic virtual machine,
  experiment controller, provenance, and CLI;
- canonical JSON is the durable machine-facing program, vocabulary, evidence,
  and decision interface; and
- generated C11 is the first real-hardware backend, compiled with the local
  `cc` toolchain for secondary timing evidence.

## Run the working prototype

Use a path that does not exist:

```sh
python3 -m laicode smoke-machine-language /tmp/laicode-machine
```

The command performs the entire bounded workflow:

1. freezes the corpora, learner, baselines, budgets, and cost equation;
2. learns one operation in cycle 1;
3. persists it as an atomic token that changes the cycle-2 proposal space;
4. learns a second, compositional operation;
5. verifies exact lowering and boundary outputs;
6. compares learned, primitive-only, fixed-human, and seeded-random forms;
7. freezes the offline decision without research-audit evidence;
8. consumes the audit and retains a workload-shift negative result;
9. regenerates all deterministic evidence and compares every byte; and
10. emits C, compiles it, checks semantic checksums, and measures both
    interpreters on the host CPU.

The output has two roots:

```text
/tmp/laicode-machine/
├── deterministic/
│   ├── corpora/          frozen workloads
│   ├── cycles/           parent/child learning records and counterfactual
│   ├── vocabularies/     primitive and three matched alternatives
│   ├── evaluations/      semantic digests and full cost vectors
│   ├── offline-decision.json
│   ├── audit-report.json
│   └── run-report.json
└── hardware/
    ├── measurement.c     generated backend/interpreter
    ├── measurement-runner
    ├── raw-stdout.txt
    └── measurement.json  compiler, host, checksums, raw trials, medians
```

The individual stages are also CLI commands:

```sh
python3 -m laicode run-machine-experiment /tmp/machine-run
python3 -m laicode replay-machine-experiment /tmp/machine-run
python3 -m laicode measure-machine-hardware \
  /tmp/machine-run /tmp/machine-hardware
```

For the cycle-by-cycle comparison with direct C/GCC, C/Clang, Python, and
JavaScript, including build, startup, memory, size, correctness, and timing
variability, see the [cross-language benchmark laboratory](language-benchmarks.md).

## Current measured result

On the registered protected holdout, the deterministic full-cost totals are:

| Vocabulary | Total units | Result |
| --- | ---: | --- |
| learned | 26,698 | selected |
| fixed human | 35,349 | rejected |
| primitive only | 46,715 | rejected |
| seeded random | 46,881 | rejected |

The learned vocabulary also wins the post-freeze research audit. Under an
unrelated future workload it costs 12,665 units versus 12,499 for the primitive
form, because the unused library still has definition, verification,
compilation, and storage cost. That negative transfer is archived explicitly.

Host timing is intentionally not a frozen claim: it varies by CPU, compiler,
thermal state, virtualization, and scheduling. The measurement report records
all raw trials and whether its median direction agrees with the deterministic
model; it never changes the content-addressed selection.

## Intended use and eventual interface

The practical target is repeated low-level kernels where interpreter dispatch,
code size, memory traffic, latency, energy, or target-specific instruction
patterns matter: packet transforms, codecs, query operators, tensor kernels,
embedded control, cryptographic building blocks, and accelerator command
streams. A user would provide behavior/property tests, representative
workloads, hardware/resource objectives, and an authority contract—not write
anonymous opcodes by hand.

The present user interface is the CLI plus inspectable JSON evidence. A later
product interface can put a task/workload form in front of it and visualize:

- the primitive graph and learned vocabulary;
- why each operation was proposed;
- exact lowering and verifier state;
- lineage across learning cycles;
- cost and real-hardware trial comparisons; and
- transfer failures, retirement, freeze, and rollback controls.

Readable labels and diagrams are projections only. Content-addressed typed
graphs remain authoritative.

## Claims boundary

This prototype demonstrates transparent vocabulary evolution over fixed
semantics and a generated-C hardware adapter. It does not yet demonstrate a
general-purpose emergent language, new primitive semantics, compiler
self-hosting, architecture-independent benefit, production containment, or
autonomous deployment. Those require separate epochs and evidence.
