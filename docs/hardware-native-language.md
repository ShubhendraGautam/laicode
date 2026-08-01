# Hardware-native evolving language research

## Thesis

The proposed end state is a language for machines whose useful vocabulary is
not fixed entirely by what humans find readable. Execution repeatedly supplies
correctness, instruction, dispatch, memory, and hardware measurements; a learner
uses that evidence to change the language available for constructing the next
generation of programs.

The analogy with an LLM learning human language is useful but incomplete. Human
language is the environment an LLM observes. Here, the environment is a
combination of:

- fixed program meaning;
- task and workload distributions;
- the target machine and its costs;
- verifier and resource constraints; and
- the history of successful and failed programs.

The learner is not expected to invent meaning from nothing. It discovers a
machine-useful vocabulary over a stable semantic ground, much as repeated
phrases can become words, compiler idioms can become instructions, or common
instruction sequences can become micro-operations.

## First executable form

E-H0 uses pure `u64 -> u64` pipelines. The initial trusted vocabulary contains
small total word operations. Programs have no source names, variables,
allocation, I/O, clock, randomness, or ambient authority.

A learned vocabulary entry records:

```text
content identity
u64 -> u64 type
ordered primitive lowering
training evidence IDs
learner and cycle identity
estimated dispatch/resource saving
verification evidence
held-out evaluation evidence
retirement status
```

If execution repeatedly encounters:

```text
xor_shift_right(30)
multiply(0xbf58476d1ce4e5b9)
xor_shift_right(27)
```

the learner may introduce one anonymous fused opcode whose authoritative
meaning is exactly that sequence. Future programs can use the fused opcode as
one construction choice and one interpreter dispatch. Humans may render it as
`op_7f3a…`, but its name has no semantics.

The executable E-H0 implementation and reproduction commands are documented in
[Working hardware-shaped language prototype](working-machine-language.md).
The first bounded real-hardware feedback loop is documented in
[Replicated hardware-feedback lifecycle](hardware-feedback.md).

## Evolution cycle

```text
primitive kernel + current learned library
                    │
                    ▼
encode and execute training programs
                    │ traces and resource vectors
                    ▼
mine recurring typed subgraphs / sequences
                    │
                    ▼
propose bounded superinstructions
                    │ exact expansion + equivalence check
                    ▼
rewrite programs with proposed vocabulary
                    │
                    ▼
external held-out cost comparison
          ┌─────────┴─────────┐
        reject             persist library
                              │
                              └──► next cycle's language
```

This is the first concrete sense in which the language tweaks itself. A
persistent learned library changes the action space and encoding used by the
next cycle. The trusted kernel and judge do not change.

## Hardware relationship

Selection begins with a deterministic virtual hardware model so every decision
can be replayed. It accounts separately for primitive ALU work, opcode dispatch,
program bytes, library bytes, verification, and compilation.

The same primitive and fused programs are emitted as generated C interpreters
and compiled with pinned flags on the local x86-64 GCC/Clang toolchain.
Repeated host measurements test whether modeled savings survive on real
hardware. Timing is noisy and cannot establish exact identity; raw distributions,
environment details, and disagreements are archived.

Later epochs may target a metered WebAssembly runtime, eBPF, RISC-V, GPU kernels,
or FPGA/HLS, but each target needs its own cost model, backend validation, and
claim. A vocabulary optimized for one machine is not presumed optimal for
another.

## Intended eventual interface

Most users would not write this language directly. They would supply tasks,
examples/properties, resource objectives, and authority through an evolution
contract. The system would expose:

- a machine API for typed construction and vocabulary operations;
- a graph/trace view showing how learned operations lower;
- a CLI for running, replaying, comparing, freezing, and retiring libraries;
- a dashboard showing vocabulary lineage, reuse, hardware benefit, verification
  state, and negative transfer; and
- optional readable projections for inspection, never as authoritative identity.

## Claims boundary

E-H0 can potentially demonstrate a learned transparent opcode vocabulary that
improves a bounded interpreter workload. It cannot demonstrate that an entire
general-purpose language emerged, that hardware design is unnecessary, that an
LLM changed its internal representational language, or that the result
generalizes across architectures.
