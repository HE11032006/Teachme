"""Tests pour le ProgressTracker et le modele de maitrise a 5 etats."""

import unittest
from tutor.storage import Store
from tutor.progress import ProgressTracker, MasteryState


class TestProgressTracker(unittest.TestCase):
    def setUp(self):
        self.store = Store(":memory:")
        self.tracker = ProgressTracker(self.store)

    def test_first_spontaneous_success(self):
        """Une reussite sans aide fait passer directement a UTILISE_SPONTANEMENT."""
        state = self.tracker.evaluate_attempt("intro.name", passed=True, used_help=False)
        self.assertEqual(state, MasteryState.UTILISE_SPONTANEMENT.value)

    def test_success_with_help(self):
        """Une reussite avec aide place la competence a UTILISE_AVEC_AIDE."""
        state = self.tracker.evaluate_attempt("intro.city", passed=True, used_help=True)
        self.assertEqual(state, MasteryState.UTILISE_AVEC_AIDE.value)

    def test_retention_after_multiple_successes(self):
        """Deux reussites spontanees consecutives propulsent a MAITRISE_RETENU."""
        self.tracker.evaluate_attempt("intro.age", passed=True, used_help=False)
        state2 = self.tracker.evaluate_attempt("intro.age", passed=True, used_help=False)
        self.assertEqual(state2, MasteryState.MAITRISE_RETENU.value)

    def test_regression_on_repeated_failures(self):
        """Des echecs repetes retrogradent l'etat a UTILISE_AVEC_AIDE."""
        # Monte a maitrise
        self.tracker.evaluate_attempt("intro.hobbies", passed=True, used_help=False)
        self.tracker.evaluate_attempt("intro.hobbies", passed=True, used_help=False)
        # 2 echecs
        self.tracker.evaluate_attempt("intro.hobbies", passed=False, used_help=False)
        state_regressed = self.tracker.evaluate_attempt("intro.hobbies", passed=False, used_help=False)
        self.assertEqual(state_regressed, MasteryState.UTILISE_AVEC_AIDE.value)


if __name__ == "__main__":
    unittest.main()

