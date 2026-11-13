"""Tests pour le module de reparation de la parole et fausses reprises."""

import unittest
from tutor.repair import repair_utterance


class TestRepair(unittest.TestCase):
    def test_clean_speech_without_repair(self):
        """Une phrase normale sans hésitation doit rester intacte."""
        rep = repair_utterance("I went to London last summer.")
        self.assertFalse(rep.was_repaired)
        self.assertEqual(rep.cleaned, "I went to London last summer.")
        self.assertEqual(rep.discarded, "")

    def test_explicit_marker_no(self):
        """Reprise avec le mot 'no' : 'I go no I went to Paris'."""
        rep = repair_utterance("I go no I went to Paris")
        self.assertTrue(rep.was_repaired)
        self.assertEqual(rep.repair_marker, "no")
        self.assertEqual(rep.cleaned, "I went to Paris")
        self.assertEqual(rep.discarded, "I go")

    def test_explicit_marker_sorry(self):
        """Reprise avec 'sorry' : 'She are sorry she is happy'."""
        rep = repair_utterance("She are sorry she is happy")
        self.assertTrue(rep.was_repaired)
        self.assertEqual(rep.repair_marker, "sorry")
        self.assertEqual(rep.cleaned, "She is happy")
        self.assertEqual(rep.discarded, "She are")

    def test_explicit_marker_i_mean(self):
        """Reprise avec 'I mean'."""
        rep = repair_utterance("He live I mean he lives in Madrid")
        self.assertTrue(rep.was_repaired)
        self.assertEqual(rep.repair_marker, "i mean")
        self.assertEqual(rep.cleaned, "He lives in Madrid")
        self.assertEqual(rep.discarded, "He live")

    def test_explicit_marker_wait(self):
        """Reprise avec 'wait'."""
        rep = repair_utterance("Yesterday I go wait yesterday I went to school")
        self.assertTrue(rep.was_repaired)
        self.assertEqual(rep.repair_marker, "wait")
        self.assertEqual(rep.cleaned, "Yesterday I went to school")
        self.assertEqual(rep.discarded, "Yesterday I go")

    def test_subject_repetition_restart(self):
        """Redémarrage spontané sans marqueur : 'She have she has two cats'."""
        rep = repair_utterance("She have she has two cats")
        self.assertTrue(rep.was_repaired)
        self.assertEqual(rep.repair_marker, "restart")
        self.assertEqual(rep.cleaned, "She has two cats")
        self.assertEqual(rep.discarded, "She have")

    def test_pronoun_i_restart(self):
        """Redémarrage avec 'I' : 'I don't I cannot come'."""
        rep = repair_utterance("I don't I cannot come")
        self.assertTrue(rep.was_repaired)
        self.assertEqual(rep.repair_marker, "restart")
        self.assertEqual(rep.cleaned, "I cannot come")

    def test_empty_string(self):
        """Texte vide."""
        rep = repair_utterance("   ")
        self.assertFalse(rep.was_repaired)
        self.assertEqual(rep.cleaned, "")


if __name__ == "__main__":
    unittest.main()

