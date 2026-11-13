"""Tests de la logique du coeur (sans micro, sans Ollama : on utilise un faux LLM).

Lancer depuis la racine du projet :
    python -m unittest discover -s tests -v
"""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tutor.config import Config
from tutor.course import check_step, find_corrections, load_course
from tutor.llm import LLMError
from tutor.session import Tutor, clean_text, drop_questions, shorten
from tutor.storage import Store

COURSES = ROOT / "courses"


class FakeLLM:
    def __init__(self, answer="Nice!"):
        self.answer = answer
        self.calls = []

    def complete(self, messages, max_tokens=60):
        self.calls.append(messages)
        return self.answer


class BrokenLLM:
    def complete(self, messages, max_tokens=60):
        raise LLMError("down")


class CorrectionsTest(unittest.TestCase):
    def test_frequent_mistakes(self):
        self.assertEqual(find_corrections("I am student"), ["I am a student"])
        self.assertEqual(find_corrections("I am engineer"), ["I am an engineer"])
        self.assertEqual(find_corrections("I have 24 years"), ["I am 24 years old"])
        self.assertEqual(find_corrections("I am 24"), ["I am 24 years old"])
        self.assertEqual(find_corrections("I am agree"), ["I agree"])

    def test_no_false_positive(self):
        self.assertEqual(find_corrections("I am 24 years old"), [])
        self.assertEqual(find_corrections("I am a student"), [])
        self.assertEqual(find_corrections("I have 2 years of experience"), [])

    def test_typographic_apostrophe(self):
        self.assertEqual(find_corrections("I\u2019m student"), ["I am a student"])


class StepCheckTest(unittest.TestCase):
    def setUp(self):
        self.course = load_course(COURSES / "se_presenter.json")

    def test_name_step(self):
        step = self.course.steps[0]
        self.assertTrue(check_step(step, "My name is Euloge").passed)
        self.assertFalse(check_step(step, "Euloge").passed)

    def test_age_step(self):
        step = self.course.steps[2]
        self.assertFalse(check_step(step, "I have 24 years").passed)
        self.assertTrue(check_step(step, "I am 24 years old").passed)
        self.assertTrue(check_step(step, "I'm 24").passed)


class HelpersTest(unittest.TestCase):
    def test_shorten(self):
        self.assertEqual(shorten("one two", 5), "one two")
        self.assertEqual(shorten("Good job. You did it well today", 4), "Good job.")

    def test_drop_questions(self):
        self.assertEqual(drop_questions("Nice! Do you like it?"), "Nice!")
        self.assertEqual(drop_questions("Do you like it?"), "")


class GuidedCourseTest(unittest.TestCase):
    def setUp(self):
        self.course = load_course(COURSES / "se_presenter.json")

    def test_full_course(self):
        store = Store(":memory:")
        llm = FakeLLM("Very good.")
        tutor = Tutor(self.course, llm, Config(llm_reactions=True), store)
        reply = tutor.start()
        self.assertEqual(reply.step_id, "name")
        self.assertIn("name", reply.text.lower())

        answers = ["My name is Euloge", "I live in Paris", "I am 24 years old",
                   "I like football", "I can build apps", "I am a student"]
        for i, answer in enumerate(answers):
            reply = tutor.reply(answer)
            if i < len(answers) - 1:
                self.assertFalse(reply.finished)
        self.assertTrue(reply.finished)
        self.assertIn("introduce yourself", reply.text)
        self.assertEqual(len(llm.calls), 6)
        self.assertGreater(len(store.turns(tutor.session_id)), 12)

    def test_retry_then_move_on(self):
        tutor = Tutor(self.course, FakeLLM(), Config())
        tutor.start()
        first = tutor.reply("Euloge")
        self.assertEqual(first.step_id, "name")
        self.assertIn("Try again", first.text)
        self.assertIn("My name is", first.hint_fr)
        self.assertFalse(first.finished)
        second = tutor.reply("hmm")
        self.assertEqual(second.step_id, "city")
        self.assertIn("No problem", second.text)

    def test_correction_shown_on_retry(self):
        tutor = Tutor(self.course, FakeLLM(), Config())
        tutor.start()
        tutor.reply("My name is Euloge")
        tutor.reply("I live in Paris")
        reply = tutor.reply("I have 24 years")
        self.assertEqual(reply.step_id, "age")
        self.assertIn("Try again", reply.text)
        self.assertIn("I am ... years old", reply.hint_fr)

    def test_llm_down_uses_fallback(self):
        tutor = Tutor(self.course, BrokenLLM(), Config(llm_reactions=True))
        tutor.start()
        reply = tutor.reply("My name is Euloge")
        self.assertTrue(reply.text.startswith("Good!"))
        self.assertIn("Where do you live", reply.text)

    def test_questions_in_reaction_are_dropped(self):
        tutor = Tutor(self.course, FakeLLM("Nice! Do you like it?"), Config(llm_reactions=True))
        tutor.start()
        reply = tutor.reply("My name is Euloge")
        self.assertNotIn("Do you like it", reply.text)
        self.assertIn("Where do you live", reply.text)


class DefaultBehaviourTest(unittest.TestCase):
    def setUp(self):
        self.course = load_course(COURSES / "se_presenter.json")

    def test_canned_reaction_makes_no_llm_call(self):
        llm = FakeLLM("should not be used")
        tutor = Tutor(self.course, llm, Config())
        tutor.start()
        reply = tutor.reply("My name is Euloge")
        self.assertEqual(llm.calls, [])
        self.assertTrue(reply.text.startswith("Good!"))
        self.assertIn("Where do you live", reply.text)

    def test_canned_reaction_includes_correction(self):
        tutor = Tutor(self.course, FakeLLM(), Config())
        tutor.start()
        reply = tutor.reply("I am student")
        self.assertIn("Better: I am a student", reply.text)

    def test_inappropriate_sentence_in_guided_course(self):
        tutor = Tutor(self.course, FakeLLM(), Config())
        tutor.start()
        tutor.reply("My name is Euloge")
        tutor.reply("I live in Paris")
        tutor.reply("I am 20 years old")
        blocked = tutor.reply("I like fuck girls")
        self.assertEqual(blocked.step_id, "hobby")
        self.assertIn("friendly", blocked.text)
        ok = tutor.reply("I like football")
        self.assertEqual(ok.step_id, "skill")

    def test_inappropriate_sentence_in_free_mode(self):
        llm = FakeLLM("unused")
        tutor = Tutor(load_course(COURSES / "libre.json"), llm, Config())
        tutor.start()
        reply = tutor.reply("fuck")
        self.assertIn("something else", reply.text)
        self.assertEqual(llm.calls, [])

    def test_clean_text_removes_dangling_quotes(self):
        self.assertEqual(
            clean_text('Great, you\'re saying "I live in Kutun.'),
            "Great, you're saying I live in Kutun.",
        )


class VoiceLogicTest(unittest.TestCase):
    def setUp(self):
        self.course = load_course(COURSES / "se_presenter.json")

    def test_fragment_detection(self):
        name, age = self.course.steps[0], self.course.steps[2]
        self.assertTrue(check_step(age, "I am.").incomplete)
        self.assertTrue(check_step(name, "My name is").incomplete)
        self.assertFalse(check_step(age, "I am 20 years old").incomplete)
        self.assertFalse(check_step(name, "My name is Paul").incomplete)

    def test_fragment_is_encouraged_without_penalty(self):
        tutor = Tutor(self.course, FakeLLM(), Config())
        tutor.start()
        tutor.reply("My name is Paul")
        tutor.reply("I live in Paris")
        keep = tutor.reply("I am.")
        self.assertEqual(keep.step_id, "age")
        self.assertIn("Keep going", keep.text)
        self.assertEqual(tutor.attempts, 0)
        done = tutor.reply("I am 20 years old")
        self.assertEqual(done.step_id, "hobby")
        self.assertTrue(done.text.startswith("Much better!"))

    def test_repeated_fragment_eventually_counts_as_failure(self):
        tutor = Tutor(self.course, FakeLLM(), Config())
        tutor.start()
        tutor.reply("My name is Paul")
        tutor.reply("I live in Paris")
        for _ in range(2):
            self.assertIn("Keep going", tutor.reply("I am.").text)
        third = tutor.reply("I am.")
        self.assertIn("Try again", third.text)
        self.assertIn("years old", third.hint_fr)
        self.assertEqual(third.step_id, "age")
        self.assertEqual(tutor.attempts, 1)

    def test_second_try_gets_much_better(self):
        tutor = Tutor(self.course, FakeLLM(), Config())
        tutor.start()
        tutor.reply("Paul")
        reply = tutor.reply("My name is Paul")
        self.assertTrue(reply.text.startswith("Much better!"))

    def test_self_correction_gets_praise(self):
        tutor = Tutor(self.course, FakeLLM(), Config())
        tutor.start()
        # L'eleve hesite et se reprend au premier essai : "I call me no My name is Paul"
        reply = tutor.reply("I call me no My name is Paul")
        self.assertTrue(reply.text.startswith("Great self-correction!"))

    def test_not_understood_does_not_count_as_failure(self):
        tutor = Tutor(self.course, FakeLLM(), Config())
        tutor.start()
        first = tutor.not_understood()
        self.assertIn("didn't catch", first.text)
        self.assertNotIn("slowly", first.text)
        self.assertEqual(first.step_id, "name")
        second = tutor.not_understood()
        self.assertIn("slowly", second.text)
        self.assertIn("My name is", second.text)
        self.assertEqual(tutor.attempts, 0)
        tutor.reply("My name is Paul")
        third = tutor.not_understood()
        self.assertNotIn("slowly", third.text)

    def test_example_is_given_when_moving_on(self):
        tutor = Tutor(self.course, FakeLLM(), Config())
        tutor.start()
        tutor.reply("hmm")
        reply = tutor.reply("hmm")
        self.assertIn(self.course.steps[0].example, reply.text)


class FreeModeTest(unittest.TestCase):
    def test_free_conversation(self):
        course = load_course(COURSES / "libre.json")
        llm = FakeLLM("That sounds fun.")
        cfg = Config()
        tutor = Tutor(course, llm, cfg)
        self.assertEqual(tutor.start().step_id, "free")
        reply = tutor.reply("I am student")
        self.assertEqual(reply.text, "That sounds fun.")
        self.assertIn("I am a student", llm.calls[-1][-1]["content"])
        for _ in range(20):
            tutor.reply("I like music")
        self.assertLessEqual(len(tutor.history), cfg.history_turns * 2)


if __name__ == "__main__":
    unittest.main()
