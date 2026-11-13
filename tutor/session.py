"""Session de tutorat : le CODE pilote le parcours, le LLM ne fait que reagir.

Parcours guide : a chaque tour, on verifie la reponse avec des regles, le LLM
produit une courte reaction (felicitation ou correction), puis le code ajoute
la question de l'etape suivante. Reponses courtes, donc rapides et previsibles.
Parcours libre : le LLM converse avec un historique limite.
"""

import re
from dataclasses import dataclass

from .course import check_step, find_corrections, normalize
from .llm import LLMError

REACTION_SYSTEM = (
    "You are a kind English tutor for a {level} learner. "
    "Reply with ONE short reaction (maximum 12 words). Praise the student. "
    "If a better sentence is given, say it clearly. "
    "Never ask a question. No lists, no markdown, no emojis: your words are read aloud."
)

FREE_SYSTEM = (
    "You are a friendly English tutor for a {level} learner. "
    "Speak in short, simple sentences. Answer in at most 25 words. "
    "If a tutor note gives a better sentence, say it gently. "
    "Always end with a short question to keep the conversation going. "
    "Never use lists, markdown or emojis: your words are read aloud."
)


@dataclass
class TutorReply:
    text: str
    hint_fr: str = ""
    finished: bool = False
    step_id: str = ""


def shorten(text, max_words):
    """Coupe a max_words mots, de preference a la fin d'une phrase."""
    words = " ".join(text.split()).split()
    if len(words) <= max_words:
        return " ".join(words)
    cut = " ".join(words[:max_words])
    end = max(cut.rfind("."), cut.rfind("!"), cut.rfind("?"))
    return cut[: end + 1] if end > 0 else cut + "."


def drop_questions(text):
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return " ".join(p for p in parts if p and not p.endswith("?"))


class Tutor:
    def __init__(self, course, llm, cfg, store=None):
        self.course = course
        self.llm = llm
        self.cfg = cfg
        self.store = store
        self.index = 0          # etape courante (parcours guide)
        self.attempts = 0       # essais rates sur l'etape courante
        self.history = []       # historique (parcours libre)
        self.session_id = store.new_session(course.id) if store else None

    # --- API publique ---------------------------------------------------------

    def start(self):
        if self.course.mode == "free":
            self.history.append({"role": "assistant", "content": self.course.free_opening})
            return self._emit(self.course.free_opening, "", False, "free")
        step = self.course.steps[0]
        return self._emit(step.opening, step.hint_fr, False, step.id)

    def reply(self, user_text):
        user_text = normalize(user_text)
        if self.course.mode == "free":
            return self._reply_free(user_text)
        return self._reply_guided(user_text)

    def close(self):
        if self.store and self.session_id:
            self.store.close_session(self.session_id)

    # --- Parcours guide -------------------------------------------------------

    def _reply_guided(self, user_text):
        step = self.course.steps[self.index]
        ev = check_step(step, user_text)
        self._log("student", user_text, step.id, ev.passed)

        if not ev.passed:
            self.attempts += 1
            if self.attempts < step.max_attempts:
                if ev.corrections:
                    text = f"Almost! You can say: {ev.corrections[0]}."
                else:
                    text = f"Let's try again. You can say: {step.target}"
                return self._emit(text, step.hint_fr, False, step.id)
            lead = f"No problem. A good answer is: {step.target}" if step.target else "No problem."
        else:
            lead = self._reaction(user_text, ev.corrections)

        self.index += 1
        self.attempts = 0
        if self.index >= len(self.course.steps):
            self.close()
            return self._emit(f"{lead} {self.course.closing}", "", True, step.id)
        nxt = self.course.steps[self.index]
        return self._emit(f"{lead} {nxt.opening}", nxt.hint_fr, False, nxt.id)

    def _reaction(self, user_text, corrections):
        content = f'Student said: "{user_text}"'
        if corrections:
            content += f'\nBetter way to say it: "{corrections[0]}"'
        messages = [
            {"role": "system", "content": REACTION_SYSTEM.format(level=self.course.level)},
            {"role": "user", "content": content},
        ]
        try:
            raw = self.llm.complete(messages, self.cfg.max_reaction_tokens)
        except LLMError:
            raw = ""
        text = shorten(drop_questions(raw), 15)
        if not text:
            text = f"Good! Better: {corrections[0]}." if corrections else "Good!"
        return text

    # --- Parcours libre -------------------------------------------------------

    def _reply_free(self, user_text):
        self._log("student", user_text, "free")
        self.history.append({"role": "user", "content": user_text})

        recent = self.history[-self.cfg.history_turns * 2:]
        messages = [{"role": "system", "content": FREE_SYSTEM.format(level=self.course.level)}]
        messages += recent[:-1]
        last = user_text
        corrections = find_corrections(user_text)
        if corrections:
            last += f'\n[Tutor note: the better sentence is "{corrections[0]}"]'
        messages.append({"role": "user", "content": last})

        try:
            raw = self.llm.complete(messages, self.cfg.max_free_tokens)
        except LLMError:
            raw = ""
        text = shorten(raw, 30) or "Sorry, can you say that again?"

        self.history.append({"role": "assistant", "content": text})
        self.history = self.history[-self.cfg.history_turns * 2:]
        return self._emit(text, "", False, "free")

    # --- Utilitaires ----------------------------------------------------------

    def _emit(self, text, hint_fr, finished, step_id):
        self._log("tutor", text, step_id)
        return TutorReply(text, hint_fr, finished, step_id)

    def _log(self, role, text, step_id, passed=None):
        if self.store:
            self.store.log_turn(self.session_id, step_id, role, text, passed)
