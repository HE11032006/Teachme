"""Configuration du tuteur (valeurs par defaut, modifiables)."""

from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


@dataclass
class Config:
    # LLM (Ollama)
    llm_model: str = "qwen3:1.7b"
    ollama_url: str = "http://localhost:11434/api/chat"
    temperature: float = 0.7
    max_reaction_tokens: int = 40
    max_free_tokens: int = 70
    history_turns: int = 6
    llm_reactions: bool = False   # True : le LLM commente chaque reponse du parcours guide (plus lent)

    # Reconnaissance vocale
    whisper_model: str = "tiny.en"  # Modèle dédié anglais : plus rapide et plus précis que "tiny"
    whisper_threads: int = 4        # Utilise les 4 cœurs physiques sans saturer le système
    min_logprob: float = -1.2       # en dessous : Whisper n'est pas sur de ce qu'il a entendu
    max_no_speech: float = 0.6      # au dessus : probablement pas de la parole

    # Micro (detection adaptative de parole et de fin de phrase)
    sample_rate: int = 16000
    energy_threshold: float = 0.01
    silence_seconds: float = 0.8  # Seuil de coupure réactif (800ms au lieu de 1.6s)
    hesitation_silence_seconds: float = 1.4  # Tolérance allongée si la phrase vient juste de démarrer
    max_record_seconds: float = 15.0

    # Voix : "auto" essaie Piper puis la voix Windows ; "piper" ou "pyttsx3" pour forcer
    tts_engine: str = "auto"
    piper_voice: str = "en_US-lessac-medium"
    voices_dir: Path = ROOT / "voices"
    speech_rate: int = 140         # voix Windows seulement

    # Fichiers
    courses_dir: Path = ROOT / "courses"
    db_path: Path = ROOT / "data" / "tutor.db"
