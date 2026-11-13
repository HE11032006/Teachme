"""Synthese vocale.

Deux moteurs, avec repli automatique :
- Piper (recommande) : voix neuronale hors-ligne, bien plus naturelle. Installation :
      pip install piper-tts
  La voix se telecharge au premier lancement (quelques dizaines de Mo).
- pyttsx3 : voix Windows integrees (qualite moyenne), sans installation.

Chaque moteur expose la meme methode speak(text).
"""

import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


class ConsoleTTS:
    """Mode sans voix : le texte est deja affiche, on ne fait rien de plus."""

    def speak(self, text):
        pass


class Pyttsx3TTS:
    def __init__(self, rate=140):
        self.rate = rate
        engine = self._new_engine()  # verifie que le moteur s'initialise
        del engine

    def _new_engine(self):
        import pyttsx3
        engine = pyttsx3.init()
        engine.setProperty("rate", self.rate)
        for voice in engine.getProperty("voices"):
            if "english" in voice.name.lower():
                engine.setProperty("voice", voice.id)
                break
        return engine

    def speak(self, text):
        # Un moteur neuf a chaque phrase : reutiliser le meme rend la voix muette
        # apres la premiere phrase sur certaines installations Windows.
        engine = self._new_engine()
        engine.say(text)
        engine.runAndWait()
        engine.stop()
        del engine


class PiperTTS:
    def __init__(self, voice="en_US-lessac-medium", voices_dir="voices"):
        self.voice = voice
        self.voices_dir = Path(voices_dir).resolve()
        self.voices_dir.mkdir(parents=True, exist_ok=True)
        self.cache_dir = self.voices_dir / "cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        onnx_file = self.voices_dir / f"{self.voice}.onnx"
        if not onnx_file.exists():
            print(f"Telechargement de la voix Piper ONNX ({self.voice})...")
            from piper.download_voices import download_voice
            download_voice(self.voice, self.voices_dir)

        # Chargement direct du modele en memoire (latence < 200 ms au lieu de 1.5s en sous-processus)
        from piper import PiperVoice
        self.piper_voice = PiperVoice.load(str(onnx_file))

    def speak(self, text):
        import numpy as np
        import sounddevice as sd

        # Synthese directe en memoire vive (< 200 ms)
        audio_chunks = list(self.piper_voice.synthesize(text))
        if not audio_chunks:
            return
        
        sample_rate = audio_chunks[0].sample_rate
        audio_arrays = [chunk.audio_float_array for chunk in audio_chunks if chunk.audio_float_array is not None]
        if not audio_arrays:
            return
        full_audio = np.concatenate(audio_arrays)

        sd.play(full_audio, sample_rate)
        sd.wait()


def make_tts(cfg):
    """Choisit le meilleur moteur disponible, en expliquant ce qui se passe."""
    if cfg.tts_engine in ("auto", "piper"):
        try:
            tts = PiperTTS(cfg.piper_voice, cfg.voices_dir)
            print("Voix : Piper")
            return tts
        except Exception as e:
            print(f"(Piper indisponible : {e})")
            if cfg.tts_engine == "piper":
                return ConsoleTTS()
    try:
        tts = Pyttsx3TTS(cfg.speech_rate)
        print("Voix : Windows (pyttsx3)")
        return tts
    except Exception as e:
        print(f"(Voix indisponible : {e}. Le prof repondra par ecrit seulement.)")
        return ConsoleTTS()
