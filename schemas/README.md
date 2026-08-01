# Prototype schema and canonicalization profile

The JSON Schema files document transport shape. The trusted Python decoders also
enforce cross-field authorization and transition rules that JSON Schema alone
does not capture.

The directory covers the prototype contract; complete and partial candidate
programs; construction actions/results; cache traces, snapshots, simulations,
and partition evaluations; evidence, promotion, and audit records; immutable
candidate and append-only ledger records; experiment and implementation
manifests; the offline decision; evaluator meta-tests; and the final run report.
Every object schema rejects unknown top-level and nested fields unless a field
is explicitly documented as an open payload map.

Prototype v1 adds strict isolated-worker request/response schemas and D1
counterfactual-shadow lease, checkpoint, and report schemas.

E-H0 adds schemas for pure 64-bit word pipelines, transparent learned
superinstruction vocabularies, identity-separated weighted corpora, persistent
learning cycles, full-cost partition evaluations, deterministic run reports,
and supplemental generated-C host measurements.

B0 adds strict cross-language comparator manifests, trusted checksum reference
results, deterministic generated-source package records, and noisy host reports
covering LAIcode learning cycles, C11/GCC, C11/Clang, Python, and JavaScript.

H1 adds a pinned CPU/OS/compiler target, replicated hardware-feedback study,
paired aggregate evidence, pit-specific vocabulary activation/retirement
profiles, offline lifecycle decisions, and replayable run reports. Raw timing is
archived but remains outside canonical program semantics and deployment.

A0 adds a typed structured algorithm language over signed integers and arrays;
transparent cross-task expression intrinsics; task contracts and deterministic
oracle cases; interpreter validity reports; generated-C validation; and exact
growth-bundle replay. Platform-style tasks remain local compatibility evidence,
not official judge submissions.

A1 adds a distinct bounded owned-vector and typed-record kernel; transparent
statement intrinsics; collection task, case, trace, validity, experiment, run,
and native-report records; plus strict core and encoded program transports. Its
fixed 256-element storage and one-vector-field record limit are epoch semantics,
not general heap-allocation claims.

A2 adds a distinct bounded-function call-graph kernel; transparent learned
function abstractions carrying their exact archived definitions; function task,
case, trace, validity, experiment, run, and native-report records; plus strict
core and encoded program transports. Its eight-function, four-parameter, and
depth-four limits and its forward-only call resolution are epoch semantics.
The run record constrains dispatch change to zero, because an A2 abstraction
must remove duplicated definitions without altering executed work.

Prototype-v0 identity is SHA-256 over UTF-8 JSON with:

- object fields sorted by Unicode scalar value;
- no insignificant whitespace;
- JSON strings emitted without optional ASCII escaping;
- only NFC strings without surrogate code points;
- only signed 64-bit integer numbers; and
- duplicate input fields rejected before decoding.

This is a deliberately restricted project profile, not a claim of full RFC 8785
JSON Canonicalization Scheme compatibility. Any future canonicalization change
requires a new schema/kernel version and evolution epoch.
