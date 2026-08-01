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
