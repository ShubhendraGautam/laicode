from __future__ import annotations

import unittest

from laicode.canonical import (
    CanonicalizationError,
    canonical_json_bytes,
    load_json_strict,
)


class CanonicalJsonTests(unittest.TestCase):
    def test_object_order_and_whitespace_do_not_change_bytes(self) -> None:
        first = load_json_strict('{"z": 1, "a": [true, null, "value"]}')
        second = load_json_strict('{\n  "a": [true,null,"value"], "z":1\n}')

        self.assertEqual(canonical_json_bytes(first), canonical_json_bytes(second))
        self.assertEqual(
            canonical_json_bytes(first), b'{"a":[true,null,"value"],"z":1}'
        )

    def test_duplicate_fields_are_rejected(self) -> None:
        with self.assertRaisesRegex(CanonicalizationError, "duplicate object field"):
            load_json_strict('{"epoch":"one","epoch":"two"}')

    def test_floating_point_numbers_are_rejected(self) -> None:
        with self.assertRaisesRegex(CanonicalizationError, "floating-point"):
            load_json_strict('{"threshold":0.1}')

    def test_non_nfc_strings_are_rejected(self) -> None:
        with self.assertRaisesRegex(CanonicalizationError, "not Unicode NFC"):
            canonical_json_bytes({"name": "e\u0301"})

    def test_unpaired_surrogates_are_rejected(self) -> None:
        with self.assertRaisesRegex(CanonicalizationError, "unpaired surrogate"):
            load_json_strict('{"name":"\\ud800"}')

    def test_out_of_range_integer_is_rejected(self) -> None:
        with self.assertRaisesRegex(CanonicalizationError, "signed 64-bit"):
            canonical_json_bytes({"value": 2**63})


if __name__ == "__main__":
    unittest.main()
