"""Session de tutorat : le CODE pilote le parcours, le LLM ne fait que reagir.

Parcours guide : a chaque tour, on verifie la reponse avec des regles, puis le
code produit une courte reaction (felicitation ou correction) et pose la question
de l'etape suivante. Le LLM n'est utilise dans ce mode que si on l'active.
Parcours libre : le LLM converse avec un historique limite.
"""

import re
from dataclasses import dataclass

from .course import check_step, find_corrections, normalize
from .llm import LLMError
from .repair import repair_utterance
from .validator import rule_based_check, validate_llm_output, EvaluationResult
from .analyzer_prompt import build_analysis_prompt
from .progress import ProgressTracker

REACTION_SYSTEM = (
    "You are a kind English tutor for a {level} learner. "
    "Reply with ONE short reaction (maximum 12 words). Praise the student. "
    "If a better sentence is given, say it clearly. "
    "Never ask a question. No lists, no markdown, no emojis: your words are read aloud."
)

FREE_SYSTEM = (
    "You are a real, friendly human English tutor having a casual oral conversation with a {level} learner. "
    "Rules you MUST follow:\n"
    "1. Directly react to what the student actually said (their hobbies, thoughts, plans).\n"
    "2. If they make a grammar mistake, gently recast it naturally in your reply.\n"
    "3. Never recite generic templates or say 'I am just reciting that sentence'.\n"
    "4. Always ask ONE engaging question strictly related to what the student just talked about.\n"
    "5. Keep your answer under 18 words so it sounds natural when spoken aloud. No markdown, no emojis."
)

BLOCKED_WORDS = {
    "fuck", "fucking", "shit", "bitch", "dick", "pussy",
    "cunt", "slut", "whore", "nigger", "nigga",
}
PRAISE = ["Good!", "Well done!", "Nice!", "Very good!", "Great!"]


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


def clean_text(text):
    """Retire les caracteres qui se lisent mal a voix haute (guillemets, markdown)."""
    return re.sub(r'["*`_#]', "", text).strip()


def is_inappropriate(text):
    words = set(re.findall(r"[a-z']+", text.lower()))
    return bool(words & BLOCKED_WORDS)


class Tutor:
    def __init__(self, course, llm, cfg, store=None):
        self.course = course
        self.llm = llm
        self.cfg = cfg
        self.store = store
        self.index = 0             # etape courante (parcours guide)
        self.attempts = 0          # essais rates sur l'etape courante
        self.incomplete_count = 0  # phrases interrompues sur l'etape courante
        self.unclear = 0           # "pas compris" de suite (reconnaissance vocale)
        self.history = []          # historique (parcours libre)
        self.session_id = store.new_session(course.id) if store else None
        self.tracker = ProgressTracker(store) if store else None

    # --- API publique ---------------------------------------------------------

    def start(self):
        if self.course.mode == "free":
            self.history.append({"role": "assistant", "content": self.course.free_opening})
            return self._emit(self.course.free_opening, "", False, "free")
        step = self.course.steps[0]
        # Interdiction §4.1 : Ne JAMAIS afficher la phrase cible avant l'essai de l'élève
        return self._emit(step.opening, "", False, step.id)

    def reply(self, user_text):
        self.unclear = 0
        raw_text = user_text
        # Reparation automatique des hesitations et fausses reprises
        repaired = repair_utterance(user_text)
        cleaned_text = normalize(repaired.cleaned or user_text)

        if self.course.mode == "free":
            return self._reply_free(cleaned_text, raw_text, repaired.was_repaired)
        return self._reply_guided(cleaned_text, raw_text, repaired.was_repaired)

    def not_understood(self):
        """Whisper n'est pas sur de ce qu'il a entendu : on redemande, sans compter d'echec."""
        self.unclear += 1
        if self.course.mode == "free":
            return self._emit("Sorry, I didn't catch that. Can you say it again?", "", False, "free")
        step = self.course.steps[self.index]
        if self.unclear >= 2 and step.target:
            text = f"Sorry, I didn't catch that. Say it slowly: {step.target}"
        else:
            text = "Sorry, I didn't catch that. Can you say it again?"
        return self._emit(text, step.hint_fr, False, step.id)

    def close(self):
        if self.store and self.session_id:
            self.store.close_session(self.session_id)

    # --- Parcours guide -------------------------------------------------------

    def _reply_guided(self, user_text, raw_text="", was_repaired=False):
        step = self.course.steps[self.index]
        if is_inappropriate(user_text):
            self._log("student", user_text, step.id, raw_text=raw_text, was_repaired=was_repaired, passed=False)
            text = f"Let's keep it friendly. Try again: {step.opening}"
            return self._emit(text, "", False, step.id)

        # Gestion des fragments et phrases coupees (ex: "I am.") avant verification lourde
        ev_old = check_step(step, user_text)
        if ev_old.incomplete and self.incomplete_count < 2:
            self.incomplete_count += 1
            self._log("student", user_text, step.id, raw_text=raw_text, was_repaired=was_repaired, passed=False)
            text = f"Keep going! You can say: {step.target}"
            return self._emit(text, step.hint_fr, False, step.id)

        # 1. Évaluation hybride (Règles strictes A1 d'abord, puis check_step / LLM)
        eval_res = rule_based_check(step.id, user_text)
        if eval_res is None:
            # Si le step_id est "city" au lieu de "location"
            if step.id == "city":
                eval_res = rule_based_check("location", user_text)

        if eval_res is None:
            if ev_old.passed:
                eval_res = EvaluationResult(True, True, True, True, True, "none", None, None, 1.0, "rules")
            elif ev_old.corrections:
                eval_res = EvaluationResult(False, False, True, True, True, "grammar", ev_old.corrections[0], None, 1.0, "rules")
            else:
                prompt_msgs = build_analysis_prompt(step.opening, step.target, user_text)
                try:
                    raw_eval = self.llm.complete(prompt_msgs, max_tokens=120)
                except LLMError:
                    raw_eval = ""
                eval_res = validate_llm_output(raw_eval, user_text)

        passed = eval_res.passed
        self._log("student", user_text, step.id, raw_text=raw_text, was_repaired=was_repaired, passed=passed)

        # Mise a jour du modele de maitrise a 5 etats (§4.3)
        if self.tracker:
            used_help = (self.attempts > 0 or self.incomplete_count > 0)
            comp_id = f"{self.course.id}.{step.id}"
            self.tracker.evaluate_attempt(comp_id, passed, used_help, was_repaired)

        # 2. Gestion de l'échec selon le type d'erreur
        if not passed:
            self.attempts += 1
            hint_fr = ""

            if eval_res.error_type == "off_topic":
                lead = "You didn't answer the question."
                hint_fr = eval_res.explanation_fr or "Réponds à la question posée."
                text = f"{lead} {step.opening}"
                return self._emit(text, hint_fr, False, step.id)

            if self.attempts < step.max_attempts:
                correction = eval_res.corrected or (ev_old.corrections[0] if ev_old.corrections else None)
                if correction:
                    text = f"Almost! You can say: {correction}."
                else:
                    text = f"Let's try again. You can say: {step.target}"
                return self._emit(text, step.hint_fr, False, step.id)

            model = step.example or step.target
            lead = f"No problem. A good answer is: {model}" if model else "No problem."
        else:
            corrections = [eval_res.corrected] if (eval_res.corrected and eval_res.error_type != "none") else ev_old.corrections
            lead = self._reaction(user_text, corrections, was_repaired)

        self.index += 1
        self.attempts = 0
        self.incomplete_count = 0
        if self.index >= len(self.course.steps):
            self.close()
            return self._emit(f"{lead} {self.course.closing}", "", True, step.id)
        nxt = self.course.steps[self.index]
        return self._emit(f"{lead} {nxt.opening}", "", False, nxt.id)

    def _canned_reaction(self, corrections, was_repaired=False):
        if was_repaired:
            praise = "Great self-correction!"
        elif self.attempts or self.incomplete_count:
            praise = "Much better!"      # il a repris sa phrase et l'a reussie
        else:
            praise = PRAISE[self.index % len(PRAISE)]
        if corrections:
            return f"{praise} Better: {corrections[0]}."
        return praise

    def _reaction(self, user_text, corrections, was_repaired=False):
        if not self.cfg.llm_reactions:
            return self._canned_reaction(corrections, was_repaired)
        content = f'Student said: "{user_text}"'
        if was_repaired:
            content += "\n(Note: the student successfully self-corrected their speech)"
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
        text = shorten(drop_questions(clean_text(raw)), 15)
        if not text:
            if was_repaired:
                text = "Great self-correction!"
            else:
                text = f"Good! Better: {corrections[0]}." if corrections else "Good!"
        return text

    # --- Parcours libre -------------------------------------------------------

    def _reply_free(self, user_text, raw_text="", was_repaired=False):
        self._log("student", user_text, "free", raw_text=raw_text, was_repaired=was_repaired)
        if is_inappropriate(user_text):
            text = "Let's talk about something else. What is your favorite food?"
            return self._emit(text, "", False, "free")
        self.history.append({"role": "user", "content": user_text})

        recent = self.history[-self.cfg.history_turns * 2:]
        messages = [{"role": "system", "content": FREE_SYSTEM.format(level=self.course.level)}]
        messages += recent[:-1]
        last = user_text
        if was_repaired:
            last += "\n[Tutor note: the student hesitated or self-corrected nicely, encourage them]"
        corrections = find_corrections(user_text)
        if corrections:
            last += f'\n[Tutor note: the better sentence is "{corrections[0]}"]'
        messages.append({"role": "user", "content": last})

        try:
            raw = self.llm.complete(messages, self.cfg.max_free_tokens)
        except LLMError:
            raw = ""
        text = shorten(clean_text(raw), 30) or "Sorry, can you say that again?"

        self.history.append({"role": "assistant", "content": text})
        self.history = self.history[-self.cfg.history_turns * 2:]
        return self._emit(text, "", False, "free")

    # --- Utilitaires ----------------------------------------------------------

    def _emit(self, text, hint_fr, finished, step_id):
        self._log("tutor", text, step_id)
        return TutorReply(text, hint_fr, finished, step_id)

    def _log(self, role, text, step_id, raw_text=None, was_repaired=False, passed=None):
        if self.store:
            self.store.log_turn(self.session_id, step_id, role, text, raw_text, was_repaired, passed)
