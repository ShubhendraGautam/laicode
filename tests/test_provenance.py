from __future__ import annotations

import json
import tempfile
import threading
import unittest
from pathlib import Path

from laicode.canonical import canonical_json_bytes
from laicode.contracts import load_contract
from laicode.evaluation import EvidenceCatalog
from laicode.kernel import compile_complete_program
from laicode.provenance import (
    AppendOnlyLedger,
    ProvenanceError,
    baseline_manifest,
    decode_candidate_record,
    enumerated_manifest,
)

from .test_kernel import CONTRACT_PATH


def artifact(strategy_id: str):
    return compile_complete_program(
        load_contract(CONTRACT_PATH),
        {
            "schema_version": "CacheStrategySelectionV0",
            "op": "select_strategy",
            "strategy_id": strategy_id,
        },
    )


class CandidateManifestTests(unittest.TestCase):
    def test_candidate_identity_covers_provenance_not_only_artifact(self) -> None:
        catalog_id = EvidenceCatalog().prefreeze_catalog_id
        lru_artifact = artifact("lru")
        baseline = baseline_manifest(lru_artifact, evidence_catalog_id=catalog_id)
        alternate = enumerated_manifest(
            lru_artifact,
            parent_id=baseline.candidate_id,
            evidence_catalog_id=catalog_id,
        )

        self.assertEqual(baseline.artifact_id, alternate.artifact_id)
        self.assertNotEqual(baseline.candidate_id, alternate.candidate_id)
        self.assertEqual(
            decode_candidate_record(baseline.to_record()),
            baseline,
        )

    def test_candidate_record_tampering_is_detected(self) -> None:
        manifest = baseline_manifest(
            artifact("lru"),
            evidence_catalog_id=EvidenceCatalog().prefreeze_catalog_id,
        )
        record = manifest.to_record()
        manifest_document = record["manifest"]
        assert isinstance(manifest_document, dict)
        mutation = manifest_document["mutation_report"]
        assert isinstance(mutation, dict)
        mutation["to_strategy"] = "lfu"

        with self.assertRaisesRegex(ProvenanceError, "does not match"):
            decode_candidate_record(record)

    def test_candidate_record_rejects_capability_widening(self) -> None:
        manifest = baseline_manifest(
            artifact("lru"),
            evidence_catalog_id=EvidenceCatalog().prefreeze_catalog_id,
        )
        record = manifest.to_record()
        manifest_document = record["manifest"]
        assert isinstance(manifest_document, dict)
        capability = manifest_document["capability_request"]
        assert isinstance(capability, dict)
        capability["effects"] = ["network"]

        with self.assertRaisesRegex(ProvenanceError, "candidates are pure"):
            decode_candidate_record(record)


class AppendOnlyLedgerTests(unittest.TestCase):
    def test_append_and_chain_replay(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            ledger = AppendOnlyLedger(Path(directory) / "ledger.jsonl")
            first = ledger.append("run_started", payload={"run": "smoke"})
            second = ledger.append(
                "manifest_frozen",
                payload={"manifest_id": "sha256:" + "a" * 64},
            )

            events = ledger.read_all()
            self.assertEqual(events, (first, second))
            self.assertEqual(events[0].sequence, 0)
            self.assertIsNone(events[0].previous_event_id)
            self.assertEqual(events[1].previous_event_id, events[0].event_id)
            self.assertTrue(ledger.path.read_bytes().endswith(b"\n"))

    def test_middle_event_mutation_is_detected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ledger.jsonl"
            ledger = AppendOnlyLedger(path)
            ledger.append("run_started", payload={"run": "smoke"})
            ledger.append("manifest_frozen", payload={"stage": "frozen"})
            lines = path.read_bytes().splitlines()
            first = json.loads(lines[0])
            first["event"]["payload"]["run"] = "altered"
            lines[0] = canonical_json_bytes(first)
            path.write_bytes(b"\n".join(lines) + b"\n")

            with self.assertRaisesRegex(ProvenanceError, "event_id"):
                ledger.read_all()

    def test_reordering_is_detected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ledger.jsonl"
            ledger = AppendOnlyLedger(path)
            ledger.append("run_started")
            ledger.append("manifest_frozen")
            lines = path.read_bytes().splitlines()
            path.write_bytes(lines[1] + b"\n" + lines[0] + b"\n")

            with self.assertRaisesRegex(ProvenanceError, "sequence"):
                ledger.read_all()

    def test_partial_line_is_detected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ledger.jsonl"
            ledger = AppendOnlyLedger(path)
            ledger.append("run_started")
            data = path.read_bytes()
            path.write_bytes(data[:-4])

            with self.assertRaisesRegex(ProvenanceError, "truncated"):
                ledger.read_all()

    def test_complete_tail_truncation_is_detected_against_expected_event(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ledger.jsonl"
            ledger = AppendOnlyLedger(path)
            ledger.append("run_started")
            final = ledger.append("run_completed")
            lines = path.read_bytes().splitlines()
            path.write_bytes(lines[0] + b"\n")

            self.assertEqual(len(ledger.read_all()), 1)
            with self.assertRaisesRegex(ProvenanceError, "final event mismatch"):
                ledger.verify_expected_final_event(final.event_id)

    def test_noncanonical_record_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ledger.jsonl"
            ledger = AppendOnlyLedger(path)
            event = ledger.append("run_started")
            record = event.to_record()
            path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")

            with self.assertRaisesRegex(ProvenanceError, "ledger line"):
                ledger.read_all()

    def test_concurrent_appends_are_serialized(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            ledger = AppendOnlyLedger(Path(directory) / "ledger.jsonl")
            errors: list[Exception] = []

            def append(index: int) -> None:
                try:
                    ledger.append("incident", payload={"index": index})
                except Exception as error:  # captured so the test can report it
                    errors.append(error)

            threads = [threading.Thread(target=append, args=(index,)) for index in range(16)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()

            self.assertEqual(errors, [])
            events = ledger.read_all()
            self.assertEqual(len(events), 16)
            self.assertEqual([event.sequence for event in events], list(range(16)))
            self.assertEqual(
                {event.payload["index"] for event in events},
                set(range(16)),
            )


if __name__ == "__main__":
    unittest.main()
