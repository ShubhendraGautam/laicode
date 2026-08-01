from __future__ import annotations

import subprocess
import unittest
from dataclasses import replace
from unittest.mock import patch

from laicode.cache import generate_trace, simulate_artifact
from laicode.canonical import canonical_json_bytes, content_id
from laicode.isolation import (
    IsolationError,
    WorkerLimits,
    evaluate_artifact_isolated,
)
from laicode.kernel import PROGRAM_SCHEMA_VERSION, compile_complete_program
from laicode.worker import (
    WORKER_REQUEST_SCHEMA_VERSION,
    WORKER_RESPONSE_SCHEMA_VERSION,
    WorkerProtocolError,
    evaluate_request,
)

from .test_kernel import contract


class IsolatedWorkerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = contract()
        self.artifact = compile_complete_program(
            self.contract,
            {
                "schema_version": PROGRAM_SCHEMA_VERSION,
                "op": "select_strategy",
                "strategy_id": "lfu",
            },
        )
        self.trace = generate_trace("mixed_bursts", 701, event_count=96)

    def request(self) -> dict[str, object]:
        return {
            "schema_version": WORKER_REQUEST_SCHEMA_VERSION,
            "contract": self.contract.to_dict(),
            "artifact": self.artifact.to_document(),
            "trace": self.trace.to_document(),
        }

    def test_isolated_result_matches_external_reference(self) -> None:
        isolated = evaluate_artifact_isolated(
            self.contract,
            self.artifact,
            self.trace,
        )

        self.assertEqual(isolated, simulate_artifact(self.artifact, self.trace))

    def test_worker_recompiles_and_rejects_artifact_tampering(self) -> None:
        request = self.request()
        artifact = request["artifact"]
        assert isinstance(artifact, dict)
        artifact["contract_id"] = "sha256:" + "0" * 64

        with self.assertRaisesRegex(WorkerProtocolError, "binding mismatch"):
            evaluate_request(request)

    def test_unknown_worker_field_is_rejected(self) -> None:
        request = self.request()
        request["ambient_credentials"] = True

        with self.assertRaisesRegex(WorkerProtocolError, "unknown field"):
            evaluate_request(request)

    def test_output_lease_is_enforced_by_supervisor(self) -> None:
        limits = replace(WorkerLimits.from_contract(self.contract), output_bytes=16)

        with self.assertRaisesRegex(IsolationError, "output-byte lease"):
            evaluate_artifact_isolated(
                self.contract,
                self.artifact,
                self.trace,
                limits=limits,
            )

    def test_content_valid_but_false_worker_result_fails_reference_check(self) -> None:
        expected = simulate_artifact(self.artifact, self.trace).to_document()
        metrics = expected["metrics"]
        assert isinstance(metrics, dict)
        metrics["misses"] = int(metrics["misses"]) + 1
        response = {
            "schema_version": WORKER_RESPONSE_SCHEMA_VERSION,
            "result_id": content_id(expected),
            "result": expected,
        }
        completed = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout=canonical_json_bytes(response),
            stderr=b"",
        )

        with patch("laicode.isolation.subprocess.run", return_value=completed):
            with self.assertRaisesRegex(IsolationError, "reference validation"):
                evaluate_artifact_isolated(
                    self.contract,
                    self.artifact,
                    self.trace,
                )


if __name__ == "__main__":
    unittest.main()
