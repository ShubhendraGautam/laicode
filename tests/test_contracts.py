from __future__ import annotations

import copy
import json
import subprocess
import sys
import unittest
from pathlib import Path

from laicode.contracts import ContractValidationError, load_contract, validate_contract


ROOT = Path(__file__).resolve().parents[1]
VALID_CONTRACT = ROOT / "examples" / "contracts" / "cache-policy-v0.json"


def contract_document() -> dict[str, object]:
    value = json.loads(VALID_CONTRACT.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


class ContractValidationTests(unittest.TestCase):
    def test_cache_contract_is_valid_and_content_addressed(self) -> None:
        contract = load_contract(VALID_CONTRACT)

        self.assertEqual(
            contract.epoch_id,
            "sha256:326b1534c27c6b94c2875e0835db94257498fbbe246ef00e434d53b1479cac25",
        )
        self.assertEqual(contract.to_dict()["name"], "cache-policy")

    def test_key_order_does_not_change_epoch_identity(self) -> None:
        document = contract_document()
        reversed_document = dict(reversed(list(document.items())))

        self.assertEqual(
            validate_contract(document).epoch_id,
            validate_contract(reversed_document).epoch_id,
        )

    def test_unknown_root_field_is_rejected(self) -> None:
        document = contract_document()
        document["candidate_may_deploy"] = True

        with self.assertRaisesRegex(ContractValidationError, "unknown field"):
            validate_contract(document)

    def test_direct_validation_rejects_noncanonical_values(self) -> None:
        document = contract_document()
        document["unsafe_threshold"] = 0.1

        with self.assertRaisesRegex(ContractValidationError, "floating-point"):
            validate_contract(document)  # type: ignore[arg-type]

    def test_unknown_nested_field_is_rejected(self) -> None:
        document = contract_document()
        capabilities = document["capabilities"]
        assert isinstance(capabilities, dict)
        capabilities["magic"] = "brokered_call"

        with self.assertRaisesRegex(ContractValidationError, "capabilities.*unknown field"):
            validate_contract(document)

    def test_mutation_cannot_exceed_reviewed_profile(self) -> None:
        document = contract_document()
        profiles = document["profiles"]
        mutation = document["mutation"]
        assert isinstance(profiles, dict) and isinstance(mutation, dict)
        maximum = profiles["maximum_reviewed"]
        assert isinstance(maximum, dict)
        maximum["m"] = "M0"

        with self.assertRaisesRegex(ContractValidationError, "exceeds profiles"):
            validate_contract(document)

    def test_constraint_failure_action_must_match_enforcement_class(self) -> None:
        document = contract_document()
        constraints = document["constraints"]
        assert isinstance(constraints, list)
        first = constraints[0]
        assert isinstance(first, dict)
        first["failure_action"] = "fallback"

        with self.assertRaisesRegex(ContractValidationError, "expected one of"):
            validate_contract(document)

    def test_protected_evidence_cannot_enter_generation(self) -> None:
        document = contract_document()
        evidence = document["evidence"]
        assert isinstance(evidence, dict)
        audit = evidence["research_audit"]
        assert isinstance(audit, dict)
        audit["candidate_access"] = True

        with self.assertRaisesRegex(ContractValidationError, "only search evidence"):
            validate_contract(document)

    def test_denied_network_requires_zero_network_budget(self) -> None:
        document = contract_document()
        budgets = document["budgets"]
        assert isinstance(budgets, dict)
        per_candidate = budgets["per_candidate"]
        assert isinstance(per_candidate, dict)
        per_candidate["network_bytes"] = 1

        with self.assertRaisesRegex(ContractValidationError, "network_bytes must be zero"):
            validate_contract(document)

    def test_each_static_invalid_example_is_rejected(self) -> None:
        invalid_dir = VALID_CONTRACT.parent / "invalid"
        for path in invalid_dir.glob("*.json"):
            with self.subTest(path=path.name):
                with self.assertRaises(ContractValidationError):
                    load_contract(path)

    def test_cli_reports_identity(self) -> None:
        result = subprocess.run(
            [sys.executable, "-m", "laicode", "validate-contract", str(VALID_CONTRACT)],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertRegex(result.stdout, r"^valid sha256:[0-9a-f]{64}\n$")

    def test_validation_does_not_retain_mutable_input(self) -> None:
        document = contract_document()
        contract = validate_contract(document)
        original = copy.deepcopy(contract.to_dict())
        document["name"] = "mutated-after-validation"

        self.assertEqual(contract.to_dict(), original)


if __name__ == "__main__":
    unittest.main()
