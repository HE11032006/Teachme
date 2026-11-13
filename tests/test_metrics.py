"""Tests unitaires pour tutor/metrics.py (§6 — métriques pédagogiques)."""
import unittest

from tutor.metrics import compute_metrics, PedagogicalMetrics
from tutor.storage import Store


def _store():
    return Store(":memory:")


class TestMetricsEmpty(unittest.TestCase):
    def test_empty_db_no_crash(self):
        s = _store()
        m = compute_metrics(s)
        self.assertIsInstance(m, PedagogicalMetrics)
        self.assertEqual(m.first_attempt_total, 0)
        self.assertEqual(m.first_attempt_accuracy, 0.0)
        s.close()

    def test_summary_always_present(self):
        s = _store()
        m = compute_metrics(s)
        self.assertIn("Premier essai", m.summary)
        s.close()


class TestFirstAttemptAccuracy(unittest.TestCase):
    def setUp(self):
        self.s = _store()
        # Session 1 : étape 'name' réussie spontanément
        sid = self.s.new_session("test")
        self.s.log_turn(sid, "name", "student", "My name is Alice",
                        passed=True, was_repaired=False)
        # Session 2 : étape 'name' échouée
        sid2 = self.s.new_session("test")
        self.s.log_turn(sid2, "name", "student", "I Alice",
                        passed=False, was_repaired=False)

    def tearDown(self):
        self.s.close()

    def test_accuracy_50_percent(self):
        m = compute_metrics(self.s)
        self.assertEqual(m.first_attempt_total, 2)
        self.assertEqual(m.first_attempt_success, 1)
        self.assertAlmostEqual(m.first_attempt_accuracy, 0.5)

    def test_repaired_not_counted_as_spontaneous(self):
        """Une réponse réparée (was_repaired=1) réussie ne compte pas comme spontanée."""
        sid3 = self.s.new_session("test")
        self.s.log_turn(sid3, "age", "student", "no I mean I am 25",
                        passed=True, was_repaired=True)
        m = compute_metrics(self.s)
        # 3 premiers essais au total, 1 seul spontané (Alice)
        self.assertEqual(m.first_attempt_total, 3)
        self.assertEqual(m.first_attempt_success, 1)


class TestErrorRecurrence(unittest.TestCase):
    def setUp(self):
        self.s = _store()
        # 'location' échouée dans 2 sessions → récurrente
        for _ in range(2):
            sid = self.s.new_session("test")
            self.s.log_turn(sid, "location", "student", "I live beneath",
                            passed=False)
        # 'name' échouée dans 1 session seulement → pas récurrente
        sid3 = self.s.new_session("test")
        self.s.log_turn(sid3, "name", "student", "wrong", passed=False)

    def tearDown(self):
        self.s.close()

    def test_location_is_recurring(self):
        m = compute_metrics(self.s)
        self.assertIn("location", m.recurring_error_steps)

    def test_name_not_recurring(self):
        m = compute_metrics(self.s)
        self.assertNotIn("name", m.recurring_error_steps)

    def test_recurrence_rate_positive(self):
        m = compute_metrics(self.s)
        self.assertGreater(m.error_recurrence_rate, 0.0)


class TestSpeakingFluency(unittest.TestCase):
    def setUp(self):
        self.s = _store()
        sid = self.s.new_session("test")
        self.s.log_turn(sid, "name", "student", "My name is Bob",
                        passed=True, was_repaired=False)
        self.s.log_turn(sid, "age", "student", "no I mean I am 25",
                        passed=True, was_repaired=True)

    def tearDown(self):
        self.s.close()

    def test_fluency_50_percent(self):
        m = compute_metrics(self.s)
        self.assertEqual(m.total_student_turns, 2)
        self.assertEqual(m.fluent_turns, 1)
        self.assertAlmostEqual(m.speaking_fluency, 0.5)


class TestTransferAccuracy(unittest.TestCase):
    def setUp(self):
        self.s = _store()
        # Session 1 : 'name' échouée (première vue)
        sid = self.s.new_session("test")
        self.s.log_turn(sid, "name", "student", "wrong", passed=False)
        # Session 2 : 'name' réussie (transfert)
        sid2 = self.s.new_session("test")
        self.s.log_turn(sid2, "name", "student", "My name is Bob", passed=True)

    def tearDown(self):
        self.s.close()

    def test_transfer_success(self):
        m = compute_metrics(self.s)
        self.assertEqual(m.transfer_total, 1)
        self.assertEqual(m.transfer_success, 1)
        self.assertAlmostEqual(m.transfer_accuracy, 1.0)


if __name__ == "__main__":
    unittest.main()

