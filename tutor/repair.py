"""Detection et nettoyage des reprises vocales (speech repairs / false starts).

Permet d'isoler l'intention reelle de l'eleve lorsqu'il hesite ou se corrige
en plein milieu de phrase (ex: "I go... no, I went to Paris").
"""

import re
from dataclasses import dataclass


# Marqueurs explicites d'auto-correction ou d'hesitation orale
REPAIR_MARKERS = [
    r"\bno\b",
    r"\bsorry\b",
    r"\bi mean\b",
    r"\bwait\b",
    r"\boh\b",
    r"\bactually\b",
]

# Pronoms sujets typiques pour detecter les redemarrages
SUBJECT_PRONOUNS = {"i", "you", "he", "she", "it", "we", "they"}


@dataclass
class RepairedSpeech:
    raw: str              # Texte original transcrit par Whisper
    cleaned: str          # Texte repare et nettoye
    was_repaired: bool    # True si une auto-correction a ete detectee
    repair_marker: str    # Marqueur trouve (ex: "no", "sorry", "restart")
    discarded: str        # La partie abandonnee par l'eleve (ex: "I go")


def clean_spaces(text: str) -> str:
    """Nettoie les espaces et ponctuations parasites."""
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"\s*([,!?])", r"\1", text)
    return text.strip(" ,")


def repair_utterance(text: str) -> RepairedSpeech:
    """Analyse une phrase et extrait la version nettoyee apres auto-correction."""
    raw = text.strip()
    if not raw:
        return RepairedSpeech(raw=raw, cleaned="", was_repaired=False, repair_marker="", discarded="")

    # Normalisation legere pour analyse
    lower = raw.lower()

    # 1. Detection via marqueurs explicites ("no", "sorry", "I mean", "wait")
    for marker in REPAIR_MARKERS:
        pattern = re.compile(rf"(.*?)\b({marker[2:-2]})\b(.*)", re.IGNORECASE)
        match = pattern.search(raw)
        if match:
            before = match.group(1).strip()
            marker_found = match.group(2).strip()
            after = match.group(3).strip()

            # S'il y a du contenu avant et apres le marqueur (ex: "I go no I went")
            if before and after:
                cleaned = clean_spaces(after)
                # Remettre une majuscule au debut de la phrase nettoyee
                if cleaned:
                    cleaned = cleaned[0].upper() + cleaned[1:]
                return RepairedSpeech(
                    raw=raw,
                    cleaned=cleaned,
                    was_repaired=True,
                    repair_marker=marker_found.lower(),
                    discarded=clean_spaces(before),
                )

    # 2. Detection de redemarrage avec répétition de pronom sujet (ex: "She have she has two cats")
    words = re.findall(r"[A-Za-z']+|[.,!?]", raw)
    # Chercher si un pronom sujet se repete apres quelques mots
    for i, w in enumerate(words):
        w_lower = w.lower()
        if w_lower in SUBJECT_PRONOUNS and i > 0:
            # Regarder si le meme pronom ou un autre pronom etait apparu plus tot
            prev_pronoun_idx = [idx for idx in range(i) if words[idx].lower() == w_lower]
            if prev_pronoun_idx:
                p_idx = prev_pronoun_idx[-1]
                # S'il y a un verbe ou 1-3 mots entre les deux, c'est un faux depart
                span = i - p_idx
                if 1 <= span <= 4:
                    discarded_words = words[:i]
                    cleaned_words = words[i:]
                    discarded = " ".join(discarded_words)
                    cleaned = clean_spaces(" ".join(cleaned_words))
                    if cleaned:
                        cleaned = cleaned[0].upper() + cleaned[1:]
                    return RepairedSpeech(
                        raw=raw,
                        cleaned=cleaned,
                        was_repaired=True,
                        repair_marker="restart",
                        discarded=discarded,
                    )

    # Aucun faux depart detecte : la phrase est retournee telle quelle
    cleaned = clean_spaces(raw)
    return RepairedSpeech(
        raw=raw,
        cleaned=cleaned,
        was_repaired=False,
        repair_marker="",
        discarded="",
    )

