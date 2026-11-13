"""Tests pour le ReviewScheduler (Phase 3 & Phase 4)."""

import time
import unittest
from tutor.storage import Store
from tutor.scheduler import ReviewScheduler


class TestReviewScheduler(unittest.TestCase):
    def setUp(self):
        self.store = Store(":memory:")
        self.scheduler = ReviewScheduler(self.store)

    def test_due_reviews_detection(self):
        """Une competence planifiee dans le passe doit ressortir en revision due."""
        past_time = time.time() - 3600  # Il y a 1 heure
        self.store.save_competency("intro.name", "COMPRIS", 1, 0, 0, next_review_at=past_time)

        future_time = time.time() + 86400  # Demain
        self.store.save_competency("intro.age", "UTILISE_SPONTANEMENT", 2, 0, 0, next_review_at=future_time)

        due = self.scheduler.get_due_reviews()
        self.assertIn("intro.name", due)
        self.assertNotIn("intro.age", due)

    def test_skip_step_after_3_consecutive_successes(self):
        """3 reussites spontanees consecutives declenchent le saut d'etape."""
        self.store.save_competency("intro.city", "UTILISE_SPONTANEMENT", 3, 0, 0)
        self.assertTrue(self.scheduler.should_skip_step("intro.city"))

    def test_no_skip_if_less_than_3_successes(self):
        """Moins de 3 reussites spontanees ne saute pas l'etape."""
        self.store.save_competency("intro.city", "UTILISE_SPONTANEMENT", 2, 0, 0)
        self.assertFalse(self.scheduler.should_skip_step("intro.city"))

    def test_remediation_triggered_after_3_failures(self):
        """3 echecs consecutifs declenchent la remediation ciblee."""
        self.store.save_competency("intro.age", "UTILISE_AVEC_AIDE", 0, 3, 3)
        self.assertTrue(self.scheduler.needs_remediation("intro.age"))


if __name__ == "__main__":
    unittest.main()

