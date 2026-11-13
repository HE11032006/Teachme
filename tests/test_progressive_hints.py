"""Test de l'impact des indices progressifs §4.2.

Ce test démontre concrètement la différence de comportement :
  AVANT : la phrase cible est montrée dès le 1er échec
  APRÈS : 3 niveaux — intention FR / amorce EN / phrase complète
"""
import unittest
from unittest.mock import MagicMock

from tutor.course import Course, Step
from tutor.session import Tutor


def _make_tutor_with_step(hint_fr="Dis : My name is...", hint_en="My name is…", max_attempts=3):
    step = Step(
        id="name",
        opening="What is your name?",
        target="My name is ...",
        example="My name is Paul.",
        pass_any=[r"\bmy name is\b"],
        hint_fr=hint_fr,
        hint_en=hint_en,
        max_attempts=max_attempts,
    )
    course = MagicMock()
    course.id = "test"
    course.mode = "guided"
    course.level = "A1"
    course.closing = "Bye!"
    course.steps = [step]
    llm = MagicMock()
    llm.complete.return_value = ""
    cfg = MagicMock()
    cfg.llm_reactions = False
    cfg.max_reaction_tokens = 30
    return Tutor(course, llm, cfg, store=None)


class TestProgressiveHints(unittest.TestCase):

    def test_echec_1_montre_hint_fr_seulement(self):
        """Premier échec → encouragement + hint_fr. PAS de phrase cible."""
        t = _make_tutor_with_step()
        reply = t.reply("I is Paul")  # réponse fausse
        # Le message ne doit pas contenir la phrase cible complète
        self.assertNotIn("My name is Paul", reply.text)
        self.assertNotIn("A good answer", reply.text)
        # Le hint_fr doit être présent dans hint_fr du TutorReply
        self.assertIn("My name is", reply.hint_fr)
        # Le message est encourageant
        self.assertIn("Try again", reply.text)

    def test_echec_2_montre_amorce_anglaise(self):
        """Deuxième échec → amorce anglaise (hint_en). Toujours pas la phrase complète."""
        t = _make_tutor_with_step()
        t.reply("I is Paul")    # échec 1
        reply = t.reply("Paul") # échec 2
        # L'amorce anglaise doit apparaître dans le message
        self.assertIn("My name is…", reply.text)
        # Toujours pas la phrase complète "Paul"
        self.assertNotIn("My name is Paul", reply.text)

    def test_echec_3_montre_phrase_complete(self):
        """Troisième échec (max_attempts atteint) → phrase complète."""
        t = _make_tutor_with_step(max_attempts=3)
        t.reply("I is Paul")    # échec 1
        t.reply("Paul")         # échec 2
        reply = t.reply("Bob")  # échec 3 → max_attempts
        self.assertIn("My name is Paul", reply.text)

    def test_sans_hint_en_fallback_correction(self):
        """Sans hint_en, le fallback est la correction ciblée (comportement actuel préservé)."""
        t = _make_tutor_with_step(hint_en="")  # pas de hint_en
        t.reply("I is Paul")  # échec 1
        reply = t.reply("I is Bob")  # échec 2 → fallback
        # Sans hint_en, on utilise la correction ou le target
        self.assertTrue(reply.text)  # au moins quelque chose est dit

    def test_reussite_directe_pas_dindice(self):
        """Réponse correcte dès le premier essai → aucun indice montré."""
        t = _make_tutor_with_step()
        reply = t.reply("My name is Alice")
        # Doit avancer (ou finir le cours) sans montrer d'indice
        self.assertNotIn("Try again", reply.text)
        self.assertNotIn("My name is…", reply.text)
        self.assertEqual(reply.hint_fr, "")


class TestImpactComparaison(unittest.TestCase):
    """Comparaison explicite avant/après pour évaluer l'impact pédagogique."""

    def _sequence_echecs(self, hint_en="My name is…"):
        t = _make_tutor_with_step(hint_en=hint_en, max_attempts=3)
        r1 = t.reply("I is Paul")   # échec 1
        r2 = t.reply("Paul")        # échec 2
        r3 = t.reply("Bob")         # échec 3
        return r1.text, r2.text, r3.text

    def test_sequence_complete_avec_hint_en(self):
        r1, r2, r3 = self._sequence_echecs(hint_en="My name is…")
        print("\n--- Avec hint_en ---")
        print(f"Échec 1 : {r1}")
        print(f"Échec 2 : {r2}")
        print(f"Échec 3 : {r3}")
        # Niveau 1 : pas de phrase
        self.assertNotIn("Paul", r1)
        # Niveau 2 : amorce
        self.assertIn("My name is…", r2)
        # Niveau 3 : phrase complète
        self.assertIn("Paul", r3)

    def test_sequence_complete_sans_hint_en(self):
        r1, r2, r3 = self._sequence_echecs(hint_en="")
        print("\n--- Sans hint_en (fallback) ---")
        print(f"Échec 1 : {r1}")
        print(f"Échec 2 : {r2}")
        print(f"Échec 3 : {r3}")
        # Juste vérifier que ça ne plante pas
        self.assertTrue(r1)
        self.assertTrue(r2)
        self.assertTrue(r3)


if __name__ == "__main__":
    unittest.main(verbosity=2)

