# Working cache-policy alternative

## What is usable now

Prototype v1 is a local, dependency-free alternative for evaluating cache
replacement policies against an application's access trace without allowing a
challenger to affect the served cache.

It combines two stages:

1. D0 selects among reviewed LRU, FIFO, and LFU artifacts under frozen search,
   operational-holdout, and historical gates.
2. D1 gives the selected artifact a bounded counterfactual-shadow lease. The
   original LRU cache remains the served champion while an independent twin
   receives the same requests and evolves under challenger decisions.

Both artifacts execute in resource-limited subprocesses. The supervisor
independently recomputes and byte-validates their results. At fixed checkpoints,
it revokes the challenger for a hard failure or excessive miss-ratio regression.
A passing lease expires without promotion because D1 has no served-effect
authority.

## One-command demonstration

Use a path that does not exist:

```sh
python3 -m laicode smoke-alternative \
  examples/contracts/cache-policy-v0.json /tmp/laicode-alternative
```

The default demonstration first selects LFU offline and then subjects it to a
256-event recency-shift trace. LFU eventually crosses the 50,000 ppm regression
limit, so its lease is revoked. The output reports
`disposition=revoked_regression`, pins the original LRU artifact as the only
served artifact, and exactly replays the complete D0+D1 bundle.

This is a useful result rather than a failed demo: the original offline winner
does not generalize to the new workload, and the external lifecycle prevents it
from affecting served state.

## Use an imported trace

Input traces use
[CacheTraceV0](../schemas/cache-trace.v0.schema.json). A deterministic example
can be generated and then replaced with a trace exported by an integration:

```sh
python3 -m laicode generate-trace recency_shift \
  --seed 901 --events 512 > /tmp/cache-trace.json

python3 -m laicode run-prototype \
  examples/contracts/cache-policy-v0.json /tmp/laicode-source

python3 -m laicode run-shadow \
  /tmp/laicode-source /tmp/cache-trace.json /tmp/laicode-shadow

python3 -m laicode replay-shadow /tmp/laicode-shadow
```

Trace keys are bounded stable identifiers, event order is logical time, and
optional per-event pin declarations are enforced by the external output shield.
The v1 runner limits a D1 trace to 4,096 events so archived evidence remains
bounded. Imported traces must already be stripped of secrets and personal data;
v1 intentionally has no retention or deletion service for sensitive workloads.

## Isolation and failure behavior

Each worker receives only a canonical contract, immutable artifact, and trace.
The supervisor supplies a minimal environment and enforces contract-derived CPU,
wall, address-space, output, open-file, and process limits. Worker output must
match both its claimed content identity and the independent reference result.

A worker timeout, crash, invalid response, or reference mismatch revokes the
lease and prevents a complete D1 report. The champion is never routed through
the worker's challenger result. The lifecycle ledger retains the incident and
revocation.

This is process separation for a closed, reviewed IR. It is not a syscall
sandbox for arbitrary hostile Python or native code, and it does not claim
network isolation.

## What remains before a drop-in service

The current interface consumes access traces; it does not expose a network cache
API or canary a challenger on live traffic. The next product-facing slice is a
local key/value cache adapter that records the canonical trace while the stable
champion serves values. D2 would then require human-authorized canary traffic,
trusted wall-clock leases, independent online monitoring, and served-state
rollback. Those are deliberately separate from this D1 milestone.
