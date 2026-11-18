"""Spec 042 T052: dispatch_schema.py decisions are unchanged (G15: the unused refusal helper was removed)."""
from __future__ import annotations
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SCRIPTS = REPO / "skills/workerbee/scripts"
sys.path.insert(0, str(SCRIPTS))
import dispatch_schema as ds  # noqa: E402


# Inputs and the exact errors validate_record returned before T052 (decision-unchanged check).
CASES = [
    ({}, []),
    ([], ["record must be a JSON object, got list"]),
    ({"CLASSIFICATION": "secret"}, ["CLASSIFICATION must start with one of public, internal, confidential"]),
    ({"EFFORT": "ultra"}, ["EFFORT must name one of low, medium, high, xhigh, max (ultra is for a codex model only)"]),
    ({"FILES_IN_SCOPE": 5}, ["FILES_IN_SCOPE must be a non-empty array of strings or the string form"]),
    ({"FAN_OUT": "x"}, ["FAN_OUT string must read 'width <n>, total <n>, depth <n>'"]),
    ({"schema_version": 2}, ["schema_version 2 is not supported; this validator reads 1"]),
    ({"CLASSIFICATION": "internal", "EFFORT": "medium", "FILES_IN_SCOPE": "a.py"}, []),
]


class DecisionsUnchanged(unittest.TestCase):
    def test_validate_record_same_errors(self):
        for obj, want in CASES:
            with self.subTest(obj=obj):
                self.assertEqual(ds.validate_record(obj), want)


if __name__ == "__main__":
    unittest.main()
