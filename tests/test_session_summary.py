"""Tests pour le bilan de fin de session mode libre (§4.6)."""
import unittest
from unittest.mock import MagicMock

from tutor.session import Tutor


def _make_tutor(mode="free"):
    course = MagicMock()
    course.mode = mode
    course.level = "A1"
    course.free_opening = "Hello! Let's chat."
    llm = MagicMock()
    cfg = MagicMock()
    cfg.llm_reactions = False
    cfg.history_turns = 5
    cfg.max_free_tokens = 60
    return Tutor(course, llm, cfg, store=None)


class TestSessionSummary(unittest.TestCase):
    def test_empty_summary_when_no_corrections(self):
        t = _make_tutor()
        self.assertEqual(t.session_summary(), "")

    def test_summary_with_one_correction(self):
        t = _make_tutor()
        t._deferred_corrections.append(("I have 25 years", "I am 25 years old"))
        s = t.session_summary()
        self.assertIn("I have 25 years", s)
        self.assertIn("I am 25 years old", s)
        self.assertIn("summary", s.lower())

    def test_summary_with_two_corrections(self):
        t = _make_tutor()
        t._deferred_corrections.append(("I have 25 years", "I am 25 years old"))
        t._deferred_corrections.append(("She don't like it", "She doesn't like it"))
        s = t.session_summary()
        self.assertIn("I have 25 years", s)
        self.assertIn("She don't like it", s)

    def test_max_three_shown(self):
        """Plus de 3 corrections : on n'affiche que 3 + mention du reste."""
        t = _make_tutor()
        for i in range(5):
            t._deferred_corrections.append((f"wrong {i}", f"right {i}"))
        s = t.session_summary()
        # On doit voir "2 more" (5 - 3 = 2)
        self.assertIn("2 more", s)

    def test_exactly_three_no_extra_message(self):
        t = _make_tutor()
        for i in range(3):
            t._deferred_corrections.append((f"wrong {i}", f"right {i}"))
        s = t.session_summary()
        self.assertNotIn("more", s)

    def test_guided_mode_no_deferred(self):
        """En mode guidé, _deferred_corrections reste vide et summary est vide."""
        t = _make_tutor(mode="guided")
        self.assertEqual(t._deferred_corrections, [])
        self.assertEqual(t.session_summary(), "")

    def test_deferred_corrections_initialized_empty(self):
        t = _make_tutor()
        self.assertIsInstance(t._deferred_corrections, list)
        self.assertEqual(len(t._deferred_corrections), 0)


if __name__ == "__main__":
    unittest.main()

