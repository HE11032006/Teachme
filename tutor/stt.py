"""Reconnaissance vocale : Whisper (faster-whisper) sur CPU, avec indice de confiance."""

from dataclasses import dataclass


@dataclass
class Transcript:
    text: str
    logprob: float = -9.0      # confiance moyenne de Whisper (plus proche de 0 = plus sur)
    no_speech: float = 1.0     # probabilite que ce ne soit pas de la parole

    def confident(self, min_logprob=-1.2, max_no_speech=0.6):
        return (bool(self.text)
                and self.logprob >= min_logprob
                and self.no_speech <= max_no_speech)


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
        # vad_filter avec paramètres ajustés pour ne pas couper les pauses courtes
        segments, _ = self.model.transcribe(
            audio,
            language="en",
            beam_size=1,
            vad_filter=True,
            vad_parameters=dict(min_silence_duration_ms=400),
        )
        segs = list(segments)
        if not segs:
            return Transcript("")
        text = " ".join(s.text.strip() for s in segs).strip()
        logprob = sum(s.avg_logprob for s in segs) / len(segs)
        no_speech = max(s.no_speech_prob for s in segs)
        return Transcript(text, logprob, no_speech)
