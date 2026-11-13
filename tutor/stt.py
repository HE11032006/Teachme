"""Reconnaissance vocale : Whisper (faster-whisper) sur CPU."""


class WhisperSTT:
    def __init__(self, model_name="tiny"):
        from faster_whisper import WhisperModel
        self.model = WhisperModel(model_name, device="cpu", compute_type="int8")

    def transcribe(self, audio):
        segments, _ = self.model.transcribe(audio, language="en", beam_size=1)
        return " ".join(s.text for s in segments).strip()
