"""Jeu de test annote pour la validation pedagogique (Phase 1).

Couvre specifiquement :
1. Les 3 faux positifs constates dans les logs de session reelle :
   - 'I live in... beneath' -> DOIT ETRE REJETE (vocabulary / incomplete)
   - 'I like her' -> DOIT ETRE REJETE (off_topic, sans correction grammaticale)
   - 'I have a degree in computer sets' -> DOIT ETRE REJETE (vocabulary)
2. Les reponses A1 valides directes.
3. Les fautes de grammaire classiques A1 ('I have 20 years old').
"""

import unittest
from tutor.validator import rule_based_check, validate_llm_output


class TestPedagogicalEvaluation(unittest.TestCase):

    def test_log_error_1_location_beneath(self):
        """Cas 1 du log reel : 'I live in... beneath' doit echouer."""
        res = rule_based_check("location", "I live in... beneath")
        self.assertIsNotNone(res)
        self.assertFalse(res.passed)
        self.assertEqual(res.error_type, "vocabulary")

    def test_log_error_2_off_topic_like_her(self):
        """Cas 2 du log reel : 'I like her' a la question d'activite doit etre hors-sujet et sans correction grammaticale."""
        res = rule_based_check("free_time", "I like her")
        self.assertIsNotNone(res)
        self.assertFalse(res.passed)
        self.assertFalse(res.on_topic)
        self.assertEqual(res.error_type, "off_topic")
        self.assertIsNone(res.corrected)  # Jamais de correction grammaticale sur du hors-sujet

    def test_log_error_3_computer_sets(self):
        """Cas 3 du log reel : 'I have a degree in computer sets' doit etre corrige en 'computer science'."""
        res = rule_based_check("studies", "I have a degree in computer sets")
        self.assertIsNotNone(res)
        self.assertFalse(res.passed)
        self.assertEqual(res.error_type, "vocabulary")
        self.assertIn("computer science", res.corrected)

    def test_valid_name_passes(self):
        """Une reponse correcte valide passe immediatement."""
        res = rule_based_check("name", "My name is John")
        self.assertIsNotNone(res)
        self.assertTrue(res.passed)
        self.assertEqual(res.error_type, "none")

    def test_grammar_error_age_have(self):
        """'I have 20 years old' doit echouer avec explication en francais."""
        res = rule_based_check("age", "I have 20 years old")
        self.assertIsNotNone(res)
        self.assertFalse(res.passed)
        self.assertEqual(res.error_type, "grammar")
        self.assertIn("'to be'", res.explanation_fr)

    def test_anti_hallucination_llm_inconsistency(self):
        """Si le LLM renvoie grammar_correct=true mais fournit une correction, le validateur force l'erreur."""
        fake_llm_json = """
        {
          "grammar_correct": true,
          "meaning_clear": true,
          "on_topic": true,
          "complete": true,
          "error_type": "none",
          "corrected": "I live in London.",
          "confidence": 0.95
        }
        """
        res = validate_llm_output(fake_llm_json, "I living in London")
        self.assertFalse(res.passed)
        self.assertEqual(res.error_type, "grammar")

    def test_anti_hallucination_off_topic_strips_correction(self):
        """Si le LLM detecte un hors-sujet, aucune correction grammaticale ne doit fuiter."""
        fake_llm_json = """
        {
          "grammar_correct": false,
          "meaning_clear": true,
          "on_topic": false,
          "complete": true,
          "error_type": "off_topic",
          "corrected": "I like reading.",
          "explanation_fr": "Hors sujet",
          "confidence": 0.90
        }
        """
        res = validate_llm_output(fake_llm_json, "I like apples")
        self.assertFalse(res.passed)
        self.assertFalse(res.on_topic)
        self.assertIsNone(res.corrected)  # Nettoye par le garde-fou


if __name__ == "__main__":
    unittest.main()

