"""Parcours pedagogiques : chargement JSON, verification des reponses, erreurs frequentes."""

import json
import re
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Step:
    id: str
    opening: str                      # ce que le prof dit pour lancer l'etape
    target: str = ""                  # phrase modele, ex. "My name is ..."
    pass_any: list = field(default_factory=list)  # motifs regex : un seul suffit
    hint_fr: str = ""                 # aide affichee en francais (echec 1)
    hint_en: str = ""                 # amorce anglaise, ex. "My name..." (echec 2 — §4.2)
    max_attempts: int = 2
    example: str = ""                 # bonne reponse complete, dite si l'eleve bloque
    vocab: list = field(default_factory=list)


@dataclass
class Course:
    id: str
    title: str
    level: str
    mode: str = "guided"              # "guided" (etapes) ou "free" (conversation libre)
    steps: list = field(default_factory=list)
    closing: str = "Great job today. See you next time!"
    free_opening: str = "Hello! What would you like to talk about?"


def load_course(path):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    steps = [Step(**s) for s in data.pop("steps", [])]
    course = Course(steps=steps, **data)
    if course.mode == "guided" and not course.steps:
        raise ValueError(f"Le parcours guide '{course.id}' n'a aucune etape.")
    return course


# --- Erreurs frequentes des francophones --------------------------------------

def _article(word):
    return "an" if word[0].lower() in "aeiou" else "a"


MISTAKE_RULES = [
    # "I am student" -> article manquant
    (re.compile(r"\bi(?:'m| am) (student|teacher|developer|engineer|programmer|doctor|nurse)\b", re.I),
     lambda m: f"I am {_article(m.group(1))} {m.group(1).lower()}"),
    # "I have 24 years" -> calque du francais "J'ai 24 ans"
    (re.compile(r"\bi have (\d+) years?\b(?! of)", re.I),
     lambda m: f"I am {m.group(1)} years old"),
    # "I am 24" -> "years old" manquant
    (re.compile(r"\bi(?:'m| am) (\d+)\b(?!\s*years)", re.I),
     lambda m: f"I am {m.group(1)} years old"),
    # "I am agree" -> calque de "Je suis d'accord"
    (re.compile(r"\bi(?:'m| am) agree\b", re.I),
     lambda m: "I agree"),
]


@dataclass
class Evaluation:
    passed: bool
    corrections: list
    incomplete: bool = False   # la phrase s'est arretee apres le debut (ex. "I am.")


def normalize(text):
    return text.replace("\u2019", "'").strip()


def find_corrections(text):
    text = normalize(text)
    found = []
    for rule, fix in MISTAKE_RULES:
        m = rule.search(text)
        if m:
            correction = fix(m)
            if correction not in found:
                found.append(correction)
    return found


def _words(text):
    return re.findall(r"[a-z']+", text.lower())


def is_fragment(step, text):
    """La personne s'est arretee apres le debut de la phrase modele (ex. 'I am.')."""
    prefix = _words(step.target.split("...")[0])
    return bool(prefix) and _words(text) == prefix


def check_step(step, text):
    """La reponse contient-elle une tournure attendue ? Quelles erreurs frequentes ?"""
    text = normalize(text)
    if step.pass_any:
        passed = any(re.search(p, text, re.I) for p in step.pass_any)
    else:
        passed = bool(text)
    return Evaluation(passed, find_corrections(text), is_fragment(step, text))
