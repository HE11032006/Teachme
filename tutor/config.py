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

    # Reconnaissance vocale
    whisper_model: str = "tiny"

    # Micro (detection simple de fin de phrase par energie sonore)
    sample_rate: int = 16000
    energy_threshold: float = 0.01
    silence_seconds: float = 1.0
    max_record_seconds: float = 15.0

    # Voix
    speech_rate: int = 140

    # Fichiers
    courses_dir: Path = ROOT / "courses"
    db_path: Path = ROOT / "data" / "tutor.db"
