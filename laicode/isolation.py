"""Bounded subprocess execution with external deterministic result validation."""

from __future__ import annotations

import math
import resource
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from .cache import CacheTrace, SimulationResult, simulate_artifact
from .canonical import (
    CanonicalizationError,
    JsonValue,
    canonical_json_bytes,
    content_id,
    load_json_strict,
)
from .contracts import ValidatedContract
from .kernel import CandidateArtifact
from .worker import WORKER_REQUEST_SCHEMA_VERSION, WORKER_RESPONSE_SCHEMA_VERSION


class IsolationError(RuntimeError):
    """Raised when an evaluation worker violates its resource or data contract."""


@dataclass(frozen=True)
class WorkerLimits:
    cpu_milliseconds: int
    wall_milliseconds: int
    memory_bytes: int
    output_bytes: int
    open_files: int = 32
    processes: int = 1

    @classmethod
    def from_contract(cls, contract: ValidatedContract) -> "WorkerLimits":
        document = contract.to_dict()
        budgets = document["budgets"]
        assert isinstance(budgets, dict)
        per_candidate = budgets["per_candidate"]
        assert isinstance(per_candidate, dict)
        return cls(
            cpu_milliseconds=int(per_candidate["cpu_milliseconds"]),
            wall_milliseconds=int(per_candidate["wall_milliseconds"]),
            memory_bytes=int(per_candidate["memory_bytes"]),
            output_bytes=int(per_candidate["storage_bytes"]),
            processes=int(per_candidate["processes"]),
        )

    def to_document(self) -> dict[str, JsonValue]:
        return {
            "cpu_milliseconds": self.cpu_milliseconds,
            "wall_milliseconds": self.wall_milliseconds,
            "memory_bytes": self.memory_bytes,
            "output_bytes": self.output_bytes,
            "open_files": self.open_files,
            "processes": self.processes,
        }


def _limit_worker(limits: WorkerLimits) -> None:
    cpu_seconds = max(1, math.ceil(limits.cpu_milliseconds / 1000))
    resource.setrlimit(resource.RLIMIT_CPU, (cpu_seconds, cpu_seconds))
    resource.setrlimit(
        resource.RLIMIT_AS,
        (limits.memory_bytes, limits.memory_bytes),
    )
    resource.setrlimit(
        resource.RLIMIT_FSIZE,
        (limits.output_bytes, limits.output_bytes),
    )
    resource.setrlimit(resource.RLIMIT_NOFILE, (limits.open_files, limits.open_files))
    if hasattr(resource, "RLIMIT_NPROC"):
        resource.setrlimit(
            resource.RLIMIT_NPROC,
            (limits.processes, limits.processes),
        )


def evaluate_artifact_isolated(
    contract: ValidatedContract,
    artifact: CandidateArtifact,
    trace: CacheTrace,
    *,
    limits: WorkerLimits | None = None,
) -> SimulationResult:
    active_limits = limits or WorkerLimits.from_contract(contract)
    request = {
        "schema_version": WORKER_REQUEST_SCHEMA_VERSION,
        "contract": contract.to_dict(),
        "artifact": artifact.to_document(),
        "trace": trace.to_document(),
    }
    root = Path(__file__).resolve().parents[1]
    environment = {
        "PYTHONHASHSEED": "0",
        "PYTHONIOENCODING": "utf-8",
    }
    try:
        completed = subprocess.run(
            [sys.executable, "-m", "laicode.worker"],
            input=canonical_json_bytes(request),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=root,
            env=environment,
            timeout=active_limits.wall_milliseconds / 1000,
            check=False,
            start_new_session=True,
            preexec_fn=lambda: _limit_worker(active_limits),
        )
    except subprocess.TimeoutExpired as error:
        raise IsolationError("evaluation worker exceeded its wall-time lease") from error
    except OSError as error:
        raise IsolationError(f"evaluation worker could not start: {error}") from error

    if completed.returncode != 0:
        diagnostic = completed.stderr.decode("utf-8", errors="replace")[:2048].strip()
        raise IsolationError(
            f"evaluation worker failed with status {completed.returncode}: {diagnostic}"
        )
    if len(completed.stdout) > active_limits.output_bytes:
        raise IsolationError("evaluation worker exceeded its output-byte lease")
    try:
        response = load_json_strict(completed.stdout)
    except CanonicalizationError as error:
        raise IsolationError(f"worker returned invalid JSON: {error}") from error
    if not isinstance(response, dict) or set(response) != {
        "schema_version",
        "result_id",
        "result",
    }:
        raise IsolationError("worker returned an invalid response envelope")
    if response["schema_version"] != WORKER_RESPONSE_SCHEMA_VERSION:
        raise IsolationError("worker returned an unknown response schema")
    result_document = response["result"]
    result_id = response["result_id"]
    if not isinstance(result_id, str) or content_id(result_document) != result_id:
        raise IsolationError("worker result identity mismatch")

    expected = simulate_artifact(artifact, trace)
    if canonical_json_bytes(result_document) != canonical_json_bytes(
        expected.to_document()
    ):
        raise IsolationError("worker result failed external reference validation")
    return expected
