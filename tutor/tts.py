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
    # Selon la version de Piper, l'option de sortie s'ecrit differemment.
    OUTPUT_FLAGS = ["--output_file", "--output-file", "-f"]

    def __init__(self, voice="en_US-lessac-medium", voices_dir="voices"):
        self.voice = voice
        self.voices_dir = Path(voices_dir).resolve()
        self.voices_dir.mkdir(parents=True, exist_ok=True)
        self.cache_dir = self.voices_dir / "cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # Telechargement automatique du modele ONNX et du JSON de la voix si absent
        onnx_file = self.voices_dir / f"{self.voice}.onnx"
        if not onnx_file.exists():
            print(f"Telechargement de la voix Piper ONNX ({self.voice})...")
            from piper.download_voices import download_voice
            download_voice(self.voice, self.voices_dir)

        exe = shutil.which("piper")
        self.base_cmd = [exe] if exe else [sys.executable, "-m", "piper"]
        self.model_path = str(onnx_file) if onnx_file.exists() else self.voice
        self.flag = None
        self._synthesize("Hello.", self.cache_dir / "_check.wav")

    def _synthesize(self, text, wav_path):
        flags = [self.flag] if self.flag else self.OUTPUT_FLAGS
        last_error = ""
        for flag in flags:
            cmd = self.base_cmd + ["--model", self.model_path, flag, str(wav_path)]
            try:
                result = subprocess.run(
                    cmd, input=text.encode("utf-8"), capture_output=True,
                    cwd=str(self.voices_dir), timeout=300,
                )
            except (OSError, subprocess.TimeoutExpired) as e:
                raise RuntimeError(f"Piper n'a pas pu etre lance : {e}") from e
            if result.returncode == 0 and Path(wav_path).exists():
                self.flag = flag
                return
            last_error = result.stderr.decode("utf-8", errors="replace")[-300:]
        raise RuntimeError(f"Piper a echoue : {last_error.strip() or 'erreur inconnue'}")

    def speak(self, text):
        import sounddevice as sd
        import soundfile as sf

        key = hashlib.sha1(f"{self.voice}|{text}".encode("utf-8")).hexdigest()
        wav = self.cache_dir / f"{key}.wav"   # cache : une phrase deja dite repart instantanement
        if not wav.exists():
            tmp = Path(tempfile.gettempdir()) / f"piper_{os.getpid()}_{key}.wav"
            try:
                self._synthesize(text, tmp)
                shutil.move(str(tmp), str(wav))
            finally:
                if tmp.exists():
                    tmp.unlink()
        data, rate = sf.read(str(wav), dtype="float32")
        sd.play(data, rate)
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
