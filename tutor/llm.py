"""Client minimal pour Ollama (API locale)."""

import json
import urllib.error
import urllib.request


class LLMError(RuntimeError):
    """Le modele n'a pas pu repondre."""


class OllamaLLM:
    def __init__(self, model, url="http://localhost:11434/api/chat", temperature=0.7):
        self.model = model
        self.url = url
        self.temperature = temperature

    def available(self):
        """Ollama repond-il ? (verification rapide au demarrage)"""
        base = self.url.split("/api/")[0]
        try:
            with urllib.request.urlopen(base + "/api/tags", timeout=3):
                return True
        except Exception:
            return False

    def warm_up(self):
        """Charge le modele en memoire (evite ~10 s d'attente au premier tour)."""
        try:
            self.complete([{"role": "user", "content": "Hi"}], max_tokens=1)
        except LLMError:
            pass

    def complete(self, messages, max_tokens=60):
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {"temperature": self.temperature, "num_predict": max_tokens},
            "keep_alive": "30m",
        }
        if "qwen3" in self.model:
            payload["think"] = False  # desactive le mode reflexion de Qwen3
        req = urllib.request.Request(
            self.url, json.dumps(payload).encode(), {"Content-Type": "application/json"}
        )
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                data = json.load(resp)
        except urllib.error.HTTPError as e:
            raise LLMError(
                f"Ollama a repondu {e.code} pour {self.model} (modele telecharge ?)"
            ) from e
        except urllib.error.URLError as e:
            raise LLMError("Impossible de joindre Ollama (est-il lance ?)") from e
        except OSError as e:
            raise LLMError(f"Erreur reseau avec Ollama : {e}") from e

        text = data.get("message", {}).get("content", "").strip()
        if "</think>" in text:
            text = text.split("</think>")[-1].strip()
        return text
