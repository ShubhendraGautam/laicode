from __future__ import annotations

import copy
import json
import subprocess
import sys
import unittest
from pathlib import Path

from laicode.canonical import canonical_json_bytes
from laicode.contracts import load_contract, validate_contract
from laicode.kernel import (
    ACTION_SCHEMA_VERSION,
    CommitError,
    ConstructionSession,
    KernelError,
    compile_complete_program,
    graph_program,
    render_program,
)


ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "examples" / "contracts" / "cache-policy-v0.json"
PROGRAM_PATH = ROOT / "examples" / "programs" / "lru-v0.json"
ACTION_PATH = ROOT / "examples" / "actions" / "fill-lru-v0.json"


def contract():
    return load_contract(CONTRACT_PATH)


def fill_action(strategy_id: str = "lru") -> dict[str, object]:
    return {
        "schema_version": ACTION_SCHEMA_VERSION,
        "action": "fill_hole",
        "payload": {
            "hole_id": "root",
            "constructor": {
                "op": "select_strategy",
                "strategy_id": strategy_id,
            },
        },
    }


class KernelTransitionTests(unittest.TestCase):
    def test_open_exposes_typed_effect_free_root_hole(self) -> None:
        session = ConstructionSession.open(contract())
        state = session.state

        self.assertEqual(state.status, "open")
        self.assertEqual(len(state.open_holes), 1)
        hole = state.open_holes[0]
        self.assertEqual(hole.hole_id, "root")
        self.assertEqual(hole.expected_type, "CacheKeyV0")
        self.assertEqual(hole.allowed_effects, ())
        self.assertEqual(hole.scope, ("snapshot",))
        self.assertEqual(
            hole.obligations,
            ("result_is_evictable", "result_is_not_pinned"),
        )

    def test_fill_hole_produces_complete_pure_program(self) -> None:
        session = ConstructionSession.open(contract())
        result = session.step(fill_action())

        self.assertTrue(result.accepted)
        self.assertEqual(result.state.status, "complete")
        self.assertEqual(result.state.open_holes, ())
        self.assertEqual(
            result.type_and_effect_delta,
            {
                "filled_hole": "root",
                "produced_type": "CacheKeyV0",
                "added_effects": [],
            },
        )
        canonical_json_bytes(result.to_document())

    def test_rejected_action_does_not_change_state(self) -> None:
        session = ConstructionSession.open(contract())
        before = session.state.state_id
        action = fill_action()
        payload = action["payload"]
        assert isinstance(payload, dict)
        constructor = payload["constructor"]
        assert isinstance(constructor, dict)
        constructor["effects"] = ["network"]

        result = session.step(action)

        self.assertFalse(result.accepted)
        self.assertEqual(result.state.state_id, before)
        self.assertEqual(session.state.state_id, before)
        self.assertIn("unknown field", str(result.diagnostics[0]["message"]))

    def test_unauthorized_strategy_is_rejected_without_mutation(self) -> None:
        session = ConstructionSession.open(contract())
        before = session.state.state_id

        result = session.step(fill_action("candidate_defined_strategy"))

        self.assertFalse(result.accepted)
        self.assertEqual(result.state.state_id, before)
        self.assertIn("not contract-authorized", str(result.diagnostics[0]["message"]))

    def test_abstraction_cannot_be_smuggled_in_as_a_primitive(self) -> None:
        session = ConstructionSession.open(contract())
        before = session.state.state_id
        action = fill_action()
        payload = action["payload"]
        assert isinstance(payload, dict)
        payload["constructor"] = {
            "op": "learned_abstraction",
            "strategy_id": "invented",
        }

        result = session.step(action)

        self.assertFalse(result.accepted)
        self.assertEqual(result.state.state_id, before)
        self.assertIn("unknown constructor", str(result.diagnostics[0]["message"]))

    def test_malformed_and_duplicate_field_actions_are_structured_rejections(self) -> None:
        session = ConstructionSession.open(contract())
        before = session.state.state_id

        malformed = session.step(b'{"schema_version":')
        duplicate = session.step(
            b'{"schema_version":"CachePolicyActionV0",'
            b'"action":"fill_hole","action":"abandon_branch","payload":{}}'
        )

        for result in (malformed, duplicate):
            self.assertFalse(result.accepted)
            self.assertIsNone(result.action_id)
            self.assertEqual(result.state.state_id, before)
            self.assertEqual(
                result.diagnostics[0]["code"],
                "invalid_action_transport",
            )

    def test_second_fill_is_rejected_without_changing_complete_state(self) -> None:
        session = ConstructionSession.open(contract())
        self.assertTrue(session.step(fill_action("fifo")).accepted)
        complete = session.state.state_id

        result = session.step(fill_action("lru"))

        self.assertFalse(result.accepted)
        self.assertEqual(session.state.state_id, complete)

    def test_commit_requires_complete_non_abandoned_program(self) -> None:
        incomplete = ConstructionSession.open(contract())
        with self.assertRaisesRegex(CommitError, "open holes"):
            incomplete.commit()

        abandoned = ConstructionSession.open(contract())
        result = abandoned.step(
            {
                "schema_version": ACTION_SCHEMA_VERSION,
                "action": "abandon_branch",
                "payload": {"reason": "dominated branch"},
            }
        )
        self.assertTrue(result.accepted)
        self.assertEqual(abandoned.state.status, "abandoned")
        with self.assertRaisesRegex(CommitError, "abandoned"):
            abandoned.commit()

    def test_only_contract_disclosed_evidence_can_open_a_session(self) -> None:
        allowed = ConstructionSession.open(contract(), permitted_evidence=("search",))
        self.assertEqual(allowed.permitted_evidence, ("search",))

        with self.assertRaisesRegex(KernelError, "not candidate-accessible"):
            ConstructionSession.open(
                contract(),
                permitted_evidence=("research_audit",),
            )

    def test_action_schema_version_is_exact(self) -> None:
        with self.assertRaisesRegex(KernelError, "expected 'CachePolicyActionV0'"):
            ConstructionSession.open(contract(), action_schema="future-action-schema")

    def test_r2_and_r3_lower_to_identical_artifact(self) -> None:
        r2_artifact = compile_complete_program(contract(), PROGRAM_PATH.read_bytes())
        session = ConstructionSession.open(contract())
        result = session.step(ACTION_PATH.read_bytes())
        self.assertTrue(result.accepted)
        r3_artifact = session.commit()

        self.assertEqual(r2_artifact.canonical_bytes, r3_artifact.canonical_bytes)
        self.assertEqual(r2_artifact.artifact_id, r3_artifact.artifact_id)
        self.assertEqual(
            r2_artifact.artifact_id,
            "sha256:063ae3688075ea2e460abdc2435e377b510b9c6babe6696c11640c6a398fbca4",
        )

    def test_program_state_identity_is_bound_to_the_contract(self) -> None:
        first_contract = contract()
        document = first_contract.to_dict()
        document["epoch"] = "prototype-1"
        second_contract = validate_contract(document)

        first_state = ConstructionSession.open(first_contract).state
        second_state = ConstructionSession.open(second_contract).state

        self.assertNotEqual(first_state.state_id, second_state.state_id)

    def test_contract_cannot_register_new_primitive_semantics(self) -> None:
        document = contract().to_dict()
        mutation = document["mutation"]
        assert isinstance(mutation, dict)
        allowed = mutation["allowed_strategy_ids"]
        assert isinstance(allowed, list)
        allowed.append("candidate_defined")
        changed_contract = validate_contract(document)

        with self.assertRaisesRegex(KernelError, "kernel has no semantics"):
            ConstructionSession.open(changed_contract)

    def test_contract_must_declare_kernel_obligations(self) -> None:
        document = contract().to_dict()
        constraints = document["constraints"]
        assert isinstance(constraints, list)
        document["constraints"] = [
            item
            for item in constraints
            if isinstance(item, dict) and item["id"] != "result_is_not_pinned"
        ]
        changed_contract = validate_contract(document)

        with self.assertRaisesRegex(KernelError, "requires obligation"):
            ConstructionSession.open(changed_contract)

    def test_contract_cannot_weaken_kernel_obligation_semantics(self) -> None:
        document = contract().to_dict()
        constraints = document["constraints"]
        assert isinstance(constraints, list)
        for item in constraints:
            if isinstance(item, dict) and item["id"] == "result_is_not_pinned":
                item["enforcement"] = "test"
                item["failure_action"] = "reject_candidate"
        changed_contract = validate_contract(document)

        with self.assertRaisesRegex(KernelError, "enforcement semantics"):
            ConstructionSession.open(changed_contract)

    def test_complete_program_rejects_unknown_fields_and_strategies(self) -> None:
        document = json.loads(PROGRAM_PATH.read_text(encoding="utf-8"))
        document["effects"] = ["network"]
        with self.assertRaisesRegex(KernelError, "unknown field"):
            compile_complete_program(contract(), document)

        document = json.loads(PROGRAM_PATH.read_text(encoding="utf-8"))
        document["strategy_id"] = "not_reviewed"
        with self.assertRaisesRegex(KernelError, "not contract-authorized"):
            compile_complete_program(contract(), document)

    def test_r3_requires_reviewed_representation_level(self) -> None:
        document = contract().to_dict()
        profiles = document["profiles"]
        assert isinstance(profiles, dict)
        maximum = profiles["maximum_reviewed"]
        assert isinstance(maximum, dict)
        maximum["r"] = "R2"
        r2_only_contract = validate_contract(document)

        compile_complete_program(r2_only_contract, PROGRAM_PATH.read_bytes())
        with self.assertRaisesRegex(KernelError, "R3 actions are not reviewed"):
            ConstructionSession.open(r2_only_contract)

    def test_views_are_derived_from_the_authoritative_program(self) -> None:
        artifact = compile_complete_program(contract(), PROGRAM_PATH.read_bytes())

        self.assertEqual(
            render_program(artifact.program),
            "select_victim(snapshot: CacheSnapshotV0) -> CacheKeyV0 = "
            "reviewed::lru(snapshot)",
        )
        graph = graph_program(artifact.program)
        self.assertEqual(graph["nodes"][0]["strategy_id"], "lru")
        self.assertEqual(graph["nodes"][0]["effects"], [])

    def test_validated_artifact_does_not_retain_mutable_program_input(self) -> None:
        document = json.loads(PROGRAM_PATH.read_text(encoding="utf-8"))
        artifact = compile_complete_program(contract(), document)
        before = copy.deepcopy(artifact.to_document())
        document["strategy_id"] = "fifo"

        self.assertEqual(artifact.to_document(), before)

    def test_compile_and_construct_cli_paths_match(self) -> None:
        compile_result = subprocess.run(
            [
                sys.executable,
                "-m",
                "laicode",
                "compile-program",
                str(CONTRACT_PATH),
                str(PROGRAM_PATH),
            ],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        construct_result = subprocess.run(
            [
                sys.executable,
                "-m",
                "laicode",
                "construct-program",
                str(CONTRACT_PATH),
                str(ACTION_PATH),
            ],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertEqual(compile_result.returncode, 0, compile_result.stderr)
        self.assertEqual(construct_result.returncode, 0, construct_result.stderr)
        self.assertEqual(compile_result.stdout, construct_result.stdout)


if __name__ == "__main__":
    unittest.main()
