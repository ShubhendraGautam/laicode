"""This project's half of the shared canonical-json contract.

`canonical_json_bytes` and `content_id` are not private to LAIcode: ai-cohort
implements the same encoding in JavaScript, and the two agree byte for byte.
`gator-tools/contracts/canonical-json` freezes that agreement so it cannot decay
into a coincidence — one project fixes an edge case, the other does not, and two
content ids that used to match quietly stop.

Skipped rather than failed when the submodule is absent, so a clone without
`--recurse-submodules` still runs the suite. CI checks out submodules.
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from laicode.canonical import (
    CanonicalizationError,
    canonical_json_bytes,
    content_id,
)

VECTOR = Path(__file__).resolve().parents[1] / "gator-tools" / "contracts" / "canonical-json" / "vector.json"


@unittest.skipUnless(
    VECTOR.is_file(),
    "gator-tools submodule not checked out: git submodule update --init",
)
class CanonicalJsonContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.vector = json.loads(VECTOR.read_text(encoding="utf-8"))

    def test_the_vector_is_the_contract_this_project_implements(self) -> None:
        self.assertEqual(self.vector["contract"], "canonical-json")
        self.assertGreaterEqual(len(self.vector["cases"]), 13, "the vector should not have shrunk")

    def test_every_frozen_case_is_reproduced_exactly(self) -> None:
        for case in self.vector["cases"]:
            with self.subTest(case=case["name"]):
                produced = canonical_json_bytes(case["value"]).decode("utf-8")
                self.assertEqual(produced, case["canonical"])
                self.assertEqual(content_id(case["value"]), case["content_id"])


class CanonicalJsonRefusalTests(unittest.TestCase):
    """Rule 6, which a vector cannot express: every case in one must encode."""

    def test_non_finite_numbers_have_no_canonical_form(self) -> None:
        for value in (float("nan"), float("inf"), float("-inf")):
            with self.subTest(value=value):
                with self.assertRaises(CanonicalizationError):
                    canonical_json_bytes({"n": value})

    def test_floats_remain_refused_and_that_is_outside_the_contract(self) -> None:
        # ai-cohort accepts finite floats; this project does not. The contract
        # covers only what both agree on, so no vector case contains a float and
        # this stricter behaviour stays conformant. See CONTRACT.md.
        with self.assertRaises(CanonicalizationError):
            canonical_json_bytes({"n": 0.5})


if __name__ == "__main__":
    unittest.main()
