"""Moteur de validation pedagogique hybride (Regles A1 + Fallback LLM structure).

Garantit :
1. Une reponse instantanee (0 ms) pour les reponses standard A1.
2. Une protection absolue contre les hallucinations du LLM (incoherences JSON).
3. Le recadrage separe du hors-sujet sans fausse correction grammaticale.
"""

import json
import re
from dataclasses import dataclass
from typing import Optional


@dataclass
class EvaluationResult:
    passed: bool
    grammar_correct: bool
    meaning_clear: bool
    on_topic: bool
    complete: bool
    error_type: str        # "none", "grammar", "vocabulary", "off_topic", "incomplete"
    corrected: Optional[str]
    explanation_fr: Optional[str]
    confidence: float
    source: str            # "rules", "llm", "fallback"


# Regles deterministes strictes A1 (Passe 1)
RULES_A1 = {
    "name": {
        "valid_pattern": r"^(my name is|i am|i'm)\s+[a-z]{2,15}$",
        "error_patterns": [
            (r"^i call me", "On dit 'My name is ...' ou 'I am ...'."),
        ]
    },
    "location": {
        "valid_pattern": r"^(i live in|i am from|i'm from)\s+[a-z\s]{2,20}$",
        "invalid_tokens": {"beneath", "under", "table", "chair", "bed", "car", "here", "there"},
    },
    "age": {
        "valid_pattern": r"^(i am|i'm)\s+\d{1,2}(\s+years old)?$",
        "error_patterns": [
            (r"^(i have|i've)\s+\d{1,2}", "En anglais on utilise 'to be' pour l'age : 'I am 20 years old'."),
        ]
    },
    "free_time": {
        # Si la question demande une activite ("What do you like to do?") et que l'eleve dit "I like her", c'est hors-sujet
        "off_topic_patterns": [
            (r"^i like (her|him|them|it|you)$", "La question te demande ce que tu aimes FAIRE (une activite)."),
        ]
    },
    "studies": {
        # Detection des confusions de vocabulaire ("computer sets" au lieu de "computer science")
        "vocabulary_errors": [
            (r"computer sets", "On dit 'computer science' (informatique), pas 'computer sets'."),
        ]
    }
}


def rule_based_check(step_id: str, text: str) -> Optional[EvaluationResult]:
    """Passe 1 : Regles deterministes ultra-rapides sans appel LLM."""
    clean = text.lower().strip(" .!?")

    if step_id == "name":
        if re.match(RULES_A1["name"]["valid_pattern"], clean):
            return EvaluationResult(True, True, True, True, True, "none", None, None, 1.0, "rules")
        for bad_pat, expl in RULES_A1["name"]["error_patterns"]:
            if re.match(bad_pat, clean):
                return EvaluationResult(False, False, True, True, True, "grammar", "My name is ...", expl, 1.0, "rules")

    elif step_id == "location":
        clean_norm = re.sub(r"\.{2,}", " ", clean)  # remplace '...' par un espace
        m = re.match(r"^(i live in|i'm from|i am from)\s+([a-z\s\.]+)$", clean_norm)
        if m:
            city_or_country = m.group(2).strip(" .")
            tokens = set(city_or_country.split())
            if tokens & RULES_A1["location"]["invalid_tokens"]:
                return EvaluationResult(
                    False, False, False, True, False, "vocabulary",
                    None, f"'{city_or_country}' n'est pas une ville ou un pays valide.", 1.0, "rules"
                )
            if len(city_or_country) >= 2:
                return EvaluationResult(True, True, True, True, True, "none", None, None, 1.0, "rules")

    elif step_id == "age":
        if re.match(RULES_A1["age"]["valid_pattern"], clean):
            return EvaluationResult(True, True, True, True, True, "none", None, None, 1.0, "rules")
        m_have = re.search(r"^(?:i have|i've)\s+(\d{1,2})", clean)
        if m_have:
            num = m_have.group(1)
            return EvaluationResult(False, False, True, True, True, "grammar", f"I am {num} years old", "En anglais on utilise 'to be' pour l'age : 'I am 20 years old'.", 1.0, "rules")
        for bad_pat, expl in RULES_A1["age"]["error_patterns"]:
            if re.search(bad_pat, clean):
                return EvaluationResult(False, False, True, True, True, "grammar", "I am ... years old", expl, 1.0, "rules")

    elif step_id in ("hobby", "free_time", "free"):
        for bad_pat, expl in RULES_A1["free_time"]["off_topic_patterns"]:
            if re.match(bad_pat, clean):
                return EvaluationResult(False, True, True, False, True, "off_topic", None, expl, 1.0, "rules")

    elif step_id in ("studies", "study"):
        for bad_pat, expl in RULES_A1["studies"]["vocabulary_errors"]:
            if re.search(bad_pat, clean):
                return EvaluationResult(
                    False, False, False, True, True, "vocabulary",
                    clean.replace("computer sets", "computer science"), expl, 1.0, "rules"
                )

    return None  # Cas ambigu : necessite l'analyse du LLM


def validate_llm_output(raw_json: str, user_text: str) -> EvaluationResult:
    """Passe 3 : Garde-fou anti-hallucination strict sur la sortie JSON du LLM."""
    try:
        clean_json = re.sub(r"^```(?:json)?|```$", "", raw_json.strip(), flags=re.MULTILINE).strip()
        data = json.loads(clean_json)

        grammar = bool(data.get("grammar_correct", False))
        meaning = bool(data.get("meaning_clear", False))
        on_topic = bool(data.get("on_topic", False))
        complete = bool(data.get("complete", False))
        error_type = data.get("error_type", "none")
        corrected = data.get("corrected")
        explanation = data.get("explanation_fr")
        confidence = float(data.get("confidence", 0.5))

        # --- Incoherences a corriger automatiquement ---

        # 1. Hors-sujet : interdiction formelle de corriger la grammaire
        if not on_topic:
            error_type = "off_topic"
            corrected = None

        # 2. Incoherence grammar_correct=true mais proposition de correction
        if grammar and corrected and corrected.strip().lower() != user_text.strip().lower():
            grammar = False
            if error_type == "none":
                error_type = "grammar"

        # 3. Decision finale de validation
        passed = grammar and meaning and on_topic and complete and (error_type == "none")

        return EvaluationResult(
            passed=passed,
            grammar_correct=grammar,
            meaning_clear=meaning,
            on_topic=on_topic,
            complete=complete,
            error_type=error_type,
            corrected=corrected,
            explanation_fr=explanation,
            confidence=confidence,
            source="llm"
        )

    except Exception:
        return EvaluationResult(
            passed=False,
            grammar_correct=False,
            meaning_clear=False,
            on_topic=True,
            complete=False,
            error_type="incomplete",
            corrected=None,
            explanation_fr="Je n'ai pas bien compris ta reponse. Peux-tu reformuler ?",
            confidence=0.0,
            source="fallback"
        )
