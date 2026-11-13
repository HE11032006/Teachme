"""
Test de petits LLM (via Ollama) pour le role de tuteur d'anglais.

Pour chaque modele : temps de lecture du prompt, vitesse de generation
(tokens/seconde) et longueur des reponses (un prof oral doit rester court).

Prerequis : Ollama installe et lance, modeles telecharges (ollama pull <modele>).
Lancement :
    python test_llm.py modele1 modele2 ...
"""

import json
import sys
import urllib.error
import urllib.request

URL = "http://localhost:11434/api/chat"

SYSTEM = (
    "You are a friendly English tutor for a beginner (level A2). "
    "Speak in short, simple sentences. Answer in at most 25 words. "
    "Gently correct one mistake if there is one. "
    "Always end with a short question to keep the conversation going. "
    "Never use lists, markdown or emojis: your words will be read aloud."
)

TURNS = [
    "Hello, my name is Euloge. I am student.",
    "Yesterday I go to the market and I buy fish.",
    "I like computers because it is interesting.",
    "I want to practice my English speaking.",
    "What is the difference between make and do?",
]


def chat(model, user_text):
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": user_text},
        ],
        "stream": False,
        "options": {"temperature": 0.7, "num_predict": 80},
    }
    if "qwen3" in model:
        payload["think"] = False  # desactive le mode reflexion de Qwen3
    body = json.dumps(payload).encode()
    req = urllib.request.Request(URL, body, {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=600) as resp:
        return json.load(resp)


def main():
    models = sys.argv[1:]
    if not models:
        print("Usage : python test_llm.py modele1 [modele2 ...]")
        return

    summary = []
    for model in models:
        print(f"\n=== Modele : {model} ===")
        try:
            chat(model, "Hi")  # chauffe : charge le modele en memoire
            prompt_times, speeds, lengths = [], [], []
            for turn in TURNS:
                r = chat(model, turn)
                text = r["message"]["content"].strip()
                if "</think>" in text:
                    text = text.split("</think>")[-1].strip()
                prompt_s = r.get("prompt_eval_duration", 0) / 1e9
                eval_s = r.get("eval_duration", 0) / 1e9
                tps = r.get("eval_count", 0) / eval_s if eval_s else 0.0
                n_words = len(text.split())
                prompt_times.append(prompt_s)
                speeds.append(tps)
                lengths.append(n_words)
                print(f"  Eleve : {turn}\n  Prof  : {text}")
                print(f"  -> {n_words} mots | prompt {prompt_s:.2f} s | {tps:.1f} tokens/s\n")
            summary.append((
                model,
                sum(prompt_times) / len(prompt_times),
                sum(speeds) / len(speeds),
                sum(lengths) / len(lengths),
                max(lengths),
            ))
        except urllib.error.HTTPError as e:
            print(f"Erreur Ollama pour {model} : {e}. Le modele est-il telecharge ?")
        except urllib.error.URLError:
            print("Impossible de joindre Ollama. Est-il lance ? (ollama serve)")
            return

    print("\n=== Resume (a copier dans NOTES.md) ===")
    print("| Modele | Prompt moy. (s) | Tokens/s | Mots moy. | Mots max |")
    print("|---|---|---|---|---|")
    for name, p, s, avg_w, max_w in summary:
        print(f"| {name} | {p:.2f} | {s:.1f} | {avg_w:.0f} | {max_w} |")


if __name__ == "__main__":
    main()
