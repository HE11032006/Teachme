"""Tests unitaires pour scripts/export_dataset.py (§4.8)."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.export_dataset import build_sample, export
from tutor.storage import Store


def _row(target=None, self_corrected=0, was_repaired=0, raw="My name is Alice"):
    return (1, "name", raw, raw, was_repaired, self_corrected, "rules", target, -0.3)


class TestBuildSample(unittest.TestCase):
    def test_correct_response(self):
        s = build_sample(_row())
        self.assertIn("correct", s["instruction"].lower())
        self.assertEqual(s["output"], "Good job!")
        self.assertEqual(s["input"], "My name is Alice")

    def test_wrong_response(self):
        s = build_sample(_row(target="My name is Alice."))
        self.assertIn("error", s["instruction"].lower())
        self.assertEqual(s["output"], "My name is Alice.")

    def test_self_corrected(self):
        s = build_sample(_row(self_corrected=1))
        self.assertIn("self-corrected", s["instruction"].lower())
        self.assertIn("self-correction", s["output"])

    def test_metadata_present(self):
        s = build_sample(_row())
        self.assertIn("step_id", s["metadata"])
        self.assertIn("stt_confidence", s["metadata"])
        self.assertEqual(s["metadata"]["step_id"], "name")

    def test_raw_text_used_as_input(self):
        s = build_sample(_row(raw="I name Alice"))
        self.assertEqual(s["input"], "I name Alice")


class TestExport(unittest.TestCase):
    def setUp(self):
        self.s = Store(":memory:")
        sid = self.s.new_session("test")
        # Tour avec erreur
        self.s.log_training_sample(sid, "name", "I Alice", "I Alice",
                                   False, False, "rules", "My name is Alice.", -0.4)
        # Tour correct
        self.s.log_training_sample(sid, "age", "I am 25", "I am 25",
                                   False, False, "rules", None, -0.2)

    def tearDown(self):
        self.s.close()

    def test_export_all(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "out.jsonl"
            count = export(self.s, out)
            self.assertEqual(count, 2)
            lines = out.read_text(encoding="utf-8").strip().split("\n")
            self.assertEqual(len(lines), 2)
            obj = json.loads(lines[0])
            self.assertIn("instruction", obj)
            self.assertIn("output", obj)

    def test_export_only_errors(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "errors.jsonl"
            count = export(self.s, out, only_errors=True)
            self.assertEqual(count, 1)  # seulement le tour avec target_correction
            obj = json.loads(out.read_text(encoding="utf-8").strip())
            self.assertEqual(obj["output"], "My name is Alice.")

    def test_output_is_valid_jsonl(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "out.jsonl"
            export(self.s, out)
            for line in out.read_text(encoding="utf-8").strip().split("\n"):
                obj = json.loads(line)
                self.assertIn("instruction", obj)
                self.assertIn("input", obj)
                self.assertIn("output", obj)
                self.assertIn("metadata", obj)


if __name__ == "__main__":
    unittest.main()

