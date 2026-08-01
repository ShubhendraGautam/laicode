"""Minimal subprocess entry point for isolated cache-artifact evaluation."""

from __future__ import annotations

import sys
from typing import Any

from .cache import decode_trace, simulate_artifact
from .canonical import (
    CanonicalizationError,
    canonical_json_bytes,
    content_id,
    load_json_strict,
)
from .contracts import validate_contract
from .kernel import compile_complete_program


WORKER_REQUEST_SCHEMA_VERSION = "CacheWorkerRequestV0"
WORKER_RESPONSE_SCHEMA_VERSION = "CacheWorkerResponseV0"
MAX_WORKER_INPUT_BYTES = 32 * 1024 * 1024


class WorkerProtocolError(ValueError):
    """Raised for a malformed or identity-inconsistent worker request."""


def _object(value: Any, fields: set[str], path: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise WorkerProtocolError(f"{path}: expected an object")
    missing = fields - value.keys()
    unknown = value.keys() - fields
    if missing:
        raise WorkerProtocolError(
            f"{path}: missing field(s): {', '.join(sorted(missing))}"
        )
    if unknown:
        raise WorkerProtocolError(
            f"{path}: unknown field(s): {', '.join(sorted(unknown))}"
        )
    return value


def evaluate_request(value: Any) -> dict[str, Any]:
    request = _object(
        value,
        {"schema_version", "contract", "artifact", "trace"},
        "$",
    )
    if request["schema_version"] != WORKER_REQUEST_SCHEMA_VERSION:
        raise WorkerProtocolError("$.schema_version: unknown worker protocol")
    contract_document = request["contract"]
    artifact_document = _object(
        request["artifact"],
        {"schema_version", "kernel_version", "contract_id", "program"},
        "$.artifact",
    )
    contract = validate_contract(contract_document)
    artifact = compile_complete_program(contract, artifact_document["program"])
    if artifact.to_document() != artifact_document:
        raise WorkerProtocolError("$.artifact: identity or contract binding mismatch")
    trace = decode_trace(request["trace"])
    result = simulate_artifact(artifact, trace)
    result_document = result.to_document()
    return {
        "schema_version": WORKER_RESPONSE_SCHEMA_VERSION,
        "result_id": content_id(result_document),
        "result": result_document,
    }


def main() -> int:
    try:
        data = sys.stdin.buffer.read(MAX_WORKER_INPUT_BYTES + 1)
        if len(data) > MAX_WORKER_INPUT_BYTES:
            raise WorkerProtocolError("worker request exceeds maximum size")
        value = load_json_strict(data)
        response = evaluate_request(value)
        sys.stdout.buffer.write(canonical_json_bytes(response) + b"\n")
        sys.stdout.buffer.flush()
        return 0
    except (CanonicalizationError, ValueError) as error:
        message = str(error).replace("\n", " ")[:2048]
        sys.stderr.write(f"worker rejected request: {message}\n")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
