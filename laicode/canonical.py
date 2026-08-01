"""Strict JSON decoding and the prototype-v0 canonical JSON profile.

The profile intentionally accepts less than general JSON. In particular, it
rejects duplicate object names, floating-point numbers, non-NFC strings, and
integers outside the signed 64-bit range. That keeps identity deterministic
across the first prototype implementations.
"""

from __future__ import annotations

import hashlib
import json
import unicodedata
from typing import Any, NoReturn


JsonValue = None | bool | int | str | list["JsonValue"] | dict[str, "JsonValue"]


class CanonicalizationError(ValueError):
    """Raised when input is outside the canonical JSON profile."""


def _reject_float(raw: str) -> NoReturn:
    raise CanonicalizationError(
        f"floating-point JSON number {raw!r} is not allowed; use an integer unit"
    )


def _reject_constant(raw: str) -> NoReturn:
    raise CanonicalizationError(f"non-finite JSON number {raw!r} is not allowed")


def _object_from_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise CanonicalizationError(f"duplicate object field {key!r}")
        result[key] = value
    return result


def load_json_strict(data: bytes | str) -> JsonValue:
    """Decode JSON while rejecting ambiguous or non-canonical value classes."""

    if isinstance(data, bytes):
        try:
            text = data.decode("utf-8", errors="strict")
        except UnicodeDecodeError as error:
            raise CanonicalizationError("input is not valid UTF-8") from error
    else:
        text = data

    try:
        value = json.loads(
            text,
            object_pairs_hook=_object_from_pairs,
            parse_float=_reject_float,
            parse_constant=_reject_constant,
        )
    except json.JSONDecodeError as error:
        raise CanonicalizationError(
            f"invalid JSON at line {error.lineno}, column {error.colno}: {error.msg}"
        ) from error

    _validate_canonical_value(value, path="$")
    return value


def _validate_canonical_value(value: Any, path: str) -> None:
    if value is None or isinstance(value, bool):
        return

    if isinstance(value, int):
        if not -(2**63) <= value <= 2**63 - 1:
            raise CanonicalizationError(f"{path}: integer is outside signed 64-bit range")
        return

    if isinstance(value, float):
        raise CanonicalizationError(
            f"{path}: floating-point values are not allowed; use an integer unit"
        )

    if isinstance(value, str):
        if any(0xD800 <= ord(character) <= 0xDFFF for character in value):
            raise CanonicalizationError(f"{path}: string contains an unpaired surrogate")
        if unicodedata.normalize("NFC", value) != value:
            raise CanonicalizationError(f"{path}: string is not Unicode NFC")
        return

    if isinstance(value, list):
        for index, item in enumerate(value):
            _validate_canonical_value(item, f"{path}[{index}]")
        return

    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise CanonicalizationError(f"{path}: object field name is not a string")
            _validate_canonical_value(key, f"{path}.<field>")
            _validate_canonical_value(item, f"{path}.{key}")
        return

    raise CanonicalizationError(f"{path}: unsupported value type {type(value).__name__}")


def canonical_json_bytes(value: JsonValue) -> bytes:
    """Return the one prototype-v0 byte representation of a JSON value."""

    _validate_canonical_value(value, path="$")
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def content_id(value: JsonValue) -> str:
    """Return a domain-readable SHA-256 identity for a canonical JSON value."""

    digest = hashlib.sha256(canonical_json_bytes(value)).hexdigest()
    return f"sha256:{digest}"
