"""Reconnaissance vocale : Whisper (faster-whisper) sur CPU, avec indice de confiance.

§4.9 — Évaluation légère de la prononciation par logprobs par mot.
faster-whisper expose les logprobs au niveau du mot via word_timestamps=True.
Un logprob par mot proche de 0.0 = bien prononcé.
Un logprob < WORD_LOGPROB_THRESHOLD = probablement mal prononcé.
"""

from dataclasses import dataclass, field
from typing import List, Tuple

# Seuil en dessous duquel un mot est considéré difficile à comprendre
WORD_LOGPROB_THRESHOLD = -0.8


@dataclass
class Transcript:
    text: str
    logprob: float = -9.0      # confiance moyenne de Whisper (plus proche de 0 = plus sur)
    no_speech: float = 1.0     # probabilite que ce ne soit pas de la parole
    # §4.9 : logprob par mot — liste de (mot, logprob) ; vide si word_timestamps désactivé
    word_confidences: List[Tuple[str, float]] = field(default_factory=list)

    def confident(self, min_logprob=-1.2, max_no_speech=0.6):
        return (bool(self.text)
                and self.logprob >= min_logprob
                and self.no_speech <= max_no_speech)

    def weak_words(self, threshold=WORD_LOGPROB_THRESHOLD):
        """Retourne les mots prononcés avec une faible confiance (candidats à la correction)."""
        return [w for w, lp in self.word_confidences if lp < threshold]


class WhisperSTT:
    def __init__(self, model_name="tiny.en", cpu_threads=4):
        from faster_whisper import WhisperModel
        self.model = WhisperModel(
            model_name,
            device="cpu",
            compute_type="int8",
            cpu_threads=cpu_threads,
        )

    def transcribe(self, audio):
        # beam_size=1 pour vitesse maximale (greedy decoding)
        # word_timestamps=True pour récupérer les logprobs par mot (§4.9)
        # vad_filter avec paramètres ajustés pour ne pas couper les pauses courtes
        segments, _ = self.model.transcribe(
            audio,
            language="en",
            beam_size=1,
            word_timestamps=True,
            vad_filter=True,
            vad_parameters=dict(min_silence_duration_ms=400),
        )
        segs = list(segments)
        if not segs:
            return Transcript("")
        text = " ".join(s.text.strip() for s in segs).strip()
        logprob = sum(s.avg_logprob for s in segs) / len(segs)
        no_speech = max(s.no_speech_prob for s in segs)

        # §4.9 : extraction des logprobs par mot
        word_confidences: List[Tuple[str, float]] = []
        for seg in segs:
            if seg.words:
                for w in seg.words:
                    word_confidences.append((w.word.strip(), w.probability))

        return Transcript(text, logprob, no_speech, word_confidences)
