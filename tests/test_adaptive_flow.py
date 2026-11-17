"""Tests pour le flux adaptatif corrigé :
1. Saut d'étape avant de poser la question (y compris à start(), sans jeter de réponse).
2. Remédiation avec issue de secours après échecs répétés (pas de blocage infini).
"""
import unittest
from unittest.mock import MagicMock

from tutor.config import Config
from tutor.course import Course, Step
from tutor.session import Tutor
from tutor.storage import Store


class FakeLLM:
    def complete(self, messages, max_tokens=60):
        return ""


def _build_course():
    return Course(
        id="test_course",
        title="Test Course",
        level="A1",
        mode="guided",
        closing="Well done!",
        steps=[
            Step(id="step0", opening="Q0: What is your name?", target="My name is ...", pass_any=[r"\bmy name is\b"], example="My name is John."),
            Step(id="step1", opening="Q1: Where do you live?", target="I live in ...", pass_any=[r"\bi live in\b"], example="I live in Paris."),
            Step(id="step2", opening="Q2: How old are you?", target="I am ... years old", pass_any=[r"\byears old\b"], example="I am 25 years old."),
        ]
    )


class TestAdaptiveFlow(unittest.TestCase):

    def setUp(self):
        self.store = Store(":memory:")
        self.course = _build_course()
        self.cfg = Config()

    def tearDown(self):
        self.store.close()

    def test_start_skips_mastered_first_step(self):
        """Si l'étape 0 est déjà maîtrisée (3 succès), start() démarre directement à l'étape 1."""
        self.store.save_competency("test_course.step0", "UTILISE_SPONTANEMENT", 3, 0, 0)
        tutor = Tutor(self.course, FakeLLM(), self.cfg, self.store)
        reply = tutor.start()

        # Ne doit PAS poser la question 0 ! Doit poser directement la question 1
        self.assertEqual(reply.step_id, "step1")
        self.assertIn("Q1: Where do you live?", reply.text)
        self.assertEqual(tutor.index, 1)

    def test_start_skips_multiple_chained_steps(self):
        """Si étapes 0 et 1 sont maîtrisées, start() saute directement à l'étape 2."""
        self.store.save_competency("test_course.step0", "UTILISE_SPONTANEMENT", 3, 0, 0)
        self.store.save_competency("test_course.step1", "UTILISE_SPONTANEMENT", 3, 0, 0)
        tutor = Tutor(self.course, FakeLLM(), self.cfg, self.store)
        reply = tutor.start()

        self.assertEqual(reply.step_id, "step2")
        self.assertIn("Q2: How old are you?", reply.text)
        self.assertEqual(tutor.index, 2)

    def test_next_step_skipped_without_asking_question(self):
        """Quand étape 0 est réussie, si étape 1 est maîtrisée, on passe direct à l'étape 2."""
        self.store.save_competency("test_course.step1", "UTILISE_SPONTANEMENT", 3, 0, 0)
        tutor = Tutor(self.course, FakeLLM(), self.cfg, self.store)
        r0 = tutor.start()
        self.assertEqual(r0.step_id, "step0")

        # L'élève répond à l'étape 0
        r1 = tutor.reply("My name is Alice")
        # Étape 1 est sautée en amont, on reçoit directement la question de l'étape 2 !
        self.assertEqual(r1.step_id, "step2")
        self.assertIn("Q2: How old are you?", r1.text)
        self.assertEqual(tutor.index, 2)

    def test_remediation_does_not_loop_infinitely(self):
        """Après remédiation et échecs répétés, l'élève avance et n'est pas bloqué indéfiniment."""
        # On force 3 échecs préalables sur step0
        self.store.save_competency("test_course.step0", "UTILISE_AVEC_AIDE", 0, 3, 3)
        tutor = Tutor(self.course, FakeLLM(), self.cfg, self.store)
        tutor.start()

        # 1er échec en session -> déclenche la remédiation
        r1 = tutor.reply("wrong answer 1")
        self.assertIn("slow down", r1.text.lower())
        self.assertTrue(tutor.in_remediation)
        self.assertEqual(tutor.index, 0)

        # 2e échec (1er essai post-remédiation)
        r2 = tutor.reply("wrong answer 2")
        self.assertTrue(tutor.in_remediation)
        self.assertEqual(tutor.index, 0)

        # 3e échec (2e essai post-remédiation) -> issue de secours !
        r3 = tutor.reply("wrong answer 3")
        # L'élève a été débloqué et avance à l'étape suivante !
        self.assertIn("review this later", r3.text.lower())
        self.assertEqual(r3.step_id, "step1")
        self.assertEqual(tutor.index, 1)
        self.assertFalse(tutor.in_remediation)


if __name__ == "__main__":
    unittest.main()

