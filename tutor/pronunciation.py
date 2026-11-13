"""Évaluation légère de la prononciation par logprobs Whisper (§4.9 — Phase 5).

Approche : faster-whisper retourne un score de probabilité (0.0 → 1.0) par mot.
Un score faible signifie que Whisper a eu du mal à reconnaître le mot → probable
difficulté de prononciation.

Ce module NE confond PAS ASR (transcription) et phonétique. Il utilise le signal
de confiance comme proxy léger, sans aucun modèle supplémentaire.

Limitations connues :
- Un mot inconnu de Whisper peut avoir un score faible même si bien prononcé.
- Les mots grammaticaux courts ('a', 'the', 'I') ont souvent des scores faibles
  naturellement → liste d'exclusion.
- Option ultérieure : wav2vec2 / speechbrain pour une analyse phonétique réelle.

Utilisation :
    from tutor.pronunciation import PronunciationFeedback, assess_pronunciation
    fb = assess_pronunciation(word_confidences, threshold=0.6)
    if fb.has_issues:
        print(fb.message)   # phrase courte prête à être lue à voix haute
"""

from dataclasses import dataclass
from typing import List, Tuple

# Mots grammaticaux très courts que Whisper transcrit souvent avec peu de confiance
# même quand ils sont bien prononcés → on les ignore pour le feedback
_SKIP_WORDS = {
    "a", "an", "the", "i", "to", "in", "on", "at", "is", "am", "are",
    "was", "were", "be", "do", "did", "my", "your", "his", "her", "it",
    "of", "and", "or", "but", "so", "if", "as", "up", "by",
}

# Seuil de probabilité en dessous duquel on signale le mot
# (0.6 = Whisper moins de 60 % sûr → possible difficulté de prononciation)
DEFAULT_THRESHOLD = 0.6

# Nombre maximal de mots signalés par feedback (pour rester court à l'oral)
MAX_WORDS_TO_FLAG = 2


@dataclass
class PronunciationFeedback:
    has_issues: bool
    weak_words: List[str]      # mots identifiés comme difficiles
    message: str               # phrase courte prête pour le TTS


def assess_pronunciation(
    word_confidences: List[Tuple[str, float]],
    threshold: float = DEFAULT_THRESHOLD,
) -> PronunciationFeedback:
    """Analyse les logprobs par mot et génère un feedback de prononciation.

    Args:
        word_confidences: liste de (mot, probabilité) issue de Whisper.
        threshold: seuil de probabilité (0.0–1.0) sous lequel un mot est signalé.

    Returns:
        PronunciationFeedback avec has_issues, weak_words, et message TTS.
    """
    if not word_confidences:
        return PronunciationFeedback(False, [], "")

    weak = [
        word
        for word, prob in word_confidences
        if prob < threshold and word.lower().strip(".,!?'\"") not in _SKIP_WORDS
        and len(word.strip()) > 1
    ]

    # Dédupliquer en conservant l'ordre d'apparition
    seen = set()
    deduped = []
    for w in weak:
        key = w.lower().strip(".,!?'\"")
        if key not in seen:
            seen.add(key)
            deduped.append(w.strip(".,!?'\""))

    flagged = deduped[:MAX_WORDS_TO_FLAG]

    if not flagged:
        return PronunciationFeedback(False, [], "")

    if len(flagged) == 1:
        msg = f"I had trouble catching '{flagged[0]}'. Try saying it clearly."
    else:
        joined = "' and '".join(flagged)
        msg = f"I had trouble with '{joined}'. Try saying them clearly."

    return PronunciationFeedback(True, flagged, msg)

