# Schema and canonicalization profile

The JSON Schema files document transport shape. The trusted Python decoders also
enforce cross-field authorization and transition rules that JSON Schema alone
does not capture. Every object schema rejects unknown top-level and nested
fields unless a field is explicitly documented as an open payload map.

The directory covers exactly two live studies. Schemas for the cache control
plane, the hardware and comparator tracks, and the A0/A1 epochs were removed
when the project narrowed on 2026-08-05 and are preserved at the
`archive/pre-narrowing` tag. `tests/test_schemas.py` fails if a schema is
present with no runtime constant behind it, so an orphan cannot reaccumulate
here unnoticed.

A2 covers the bounded-function call-graph kernel: transparent learned function
abstractions carrying their exact archived definitions; function task, case,
trace, validity, experiment, run, and native-report records; plus strict core
and encoded program transports. Its eight-function, four-parameter, and
depth-four limits and its forward-only call resolution are epoch semantics. The
run record constrains dispatch change to zero, because an A2 abstraction must
remove duplicated definitions without altering executed work.

A2-S covers the matched-budget synthesis experiment: an experiment manifest,
task contracts separating treatment from control, and a run record whose ratios
are integer parts per million. The record marks a ratio as a lower bound
whenever the compared arm stopped at its budget or returned a program that
failed held-out cases, so a truncated or decoy run cannot be read as a solved
one.

`function-language-defs.v2.schema.json` is a shared `$defs` bundle referenced by
the others and carries no `schema_version` of its own.

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
