# Replicated hardware-feedback lifecycle

## What this adds

H1 turns real-host measurements into a conservative, executable vocabulary
profile. It runs the complete cross-language benchmark repeatedly, compares
LAIcode learning cycles within matched sessions, and freezes which already
verified vocabulary should be active for each registered benchmark pit on one
pinned hardware target.

This is the first closed connection from measured hardware behavior back into
the language lifecycle:

```text
replayable E-H0 language + deterministic comparator package
                              │
                              ▼
                 repeated matched host sessions
                              │ raw timing + checksums
                              ▼
                    paired stability gates
                              │
                              ▼
        target/pit profile + lifecycle decision + exact replay
```

Hardware feedback may activate or retire existing transparent operations in an
offline profile. It cannot change primitive meaning, invent instructions from
nanoseconds, infer a live workload, or deploy anything.

## One-command study

Use a path that does not exist:

```sh
python3 -m laicode smoke-hardware-feedback /tmp/laicode-feedback
```

The default study creates a fresh E-H0 machine bundle and comparator package,
runs five complete benchmark sessions, derives the target profile, and exactly
replays the decision from the archive without rerunning timing.

For an existing machine bundle and comparator package:

```sh
python3 -m laicode run-hardware-feedback \
  /tmp/machine /tmp/comparator-package /tmp/feedback-study

python3 -m laicode replay-hardware-feedback \
  /tmp/machine /tmp/comparator-package /tmp/feedback-study
```

Development runs can lower benchmark scale and trial counts, but the session
count must remain odd and at least three:

```sh
python3 -m laicode smoke-hardware-feedback /tmp/feedback-dev \
  --sessions 3 --scale 2 --trials 3 --warmups 1 --startup-trials 3
```

## Frozen selection policy

The study pins the CPU model, operating system and release, machine
architecture, generated-C backend, compiler path/version, and compiler flags.
Every session must pass the exact semantic checksums.

Cycle 0 is the primitive fallback. A learned cycle is eligible only when all
three default gates pass:

- deterministic weighted dispatch tokens decrease from cycle 0;
- the candidate wins at least 80% of paired sessions; and
- the median paired improvement is at least 5%.

Among eligible cycles, the lowest median of session medians wins, with cycle
number as the deterministic tie-breaker. If neither learned cycle qualifies,
the profile selects cycle 0. A measured speedup alone is intentionally
insufficient when the workload does not reuse learned vocabulary.

## Output and use

```text
/tmp/laicode-feedback/
├── machine/                    replayable E-H0 language experiment
├── comparator-package/         deterministic sources and reference outputs
└── feedback-study/
    ├── study-manifest.json      target, sessions, gates, and authority
    ├── sessions/                raw results and compiled artifacts per run
    ├── aggregate.json           paired evidence and eligibility by pit/cycle
    ├── target-profile.json      active and retired operation IDs by pit
    ├── lifecycle-decision.json  frozen offline lifecycle outcome
    └── run-report.json          claims, identities, and limitations
```

An integration supplies a registered pit identity to
`resolve_target_vocabulary`. The resolver checks that the selected vocabulary,
active entries, retired entries, and primitive-fallback flag all agree. Unknown
workloads are rejected; H1 does not guess their class. Retirement means profile
exclusion, not deletion: exact lowering, lineage, and negative evidence remain
available.

## Release evidence

The first default five-session H1 run selected cycle 2 for `reuse_holdout` and
`audit_transfer`, and cycle 0 for `shift_no_reuse`. The learned cycle passed all
gates on the first two pits. The shift pit had no deterministic token reduction
and failed the paired stability gates, so the apparently faster measurements
in some sessions could not promote it.

| Pit | Selected cycle | Cycle-2 median paired gain | Cycle-2 paired wins |
| --- | ---: | ---: | ---: |
| `reuse_holdout` | 2 | 61.643% | 5 / 5 |
| `audit_transfer` | 2 | 57.641% | 5 / 5 |
| `shift_no_reuse` | 0 | -5.760% | 2 / 5 |

The release run report is
`sha256:35d778ab6f0887ba1c4abfc4f60648da1730a7cfdc4f4d80303e620cf7c1888c`;
its target profile is
`sha256:8c99dfead7d611c2c5e30b8af90ef7cc946215d1ef9539a68462fcb91c13ad8b`.
These are code-current evidence identities, not portable performance promises.

## Claims boundary

H1 provides exploratory evidence from sequential sessions on one CPU/OS/compiler
target. Host timing itself is not byte-replayable; the archived evidence and
derived decision are. The study does not establish cross-machine stability,
energy efficiency, a mature-language performance win, automatic workload
routing, online learning, or deployment safety. Those require a separately
reviewed H2 design with independent machines, randomized ordering, calibrated
uncertainty, hardware counters, and external review.
