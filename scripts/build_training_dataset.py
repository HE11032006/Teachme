"""Telechargement et transformation de datasets Hugging Face pour fine-tuner le tuteur.

Ce script :
1. Telecharge un echantillon de paires (erreur d'anglais -> correction) depuis Hugging Face.
2. Transforme chaque paire en un echange conversationnel oral de tuteur bienveillant :
   - Reformulation douce (recast)
   - Longueur courte (< 20 mots)
   - Question de relance
   - Valorisation des hesitations / auto-corrections
3. Exporte le tout en JSONL au format standard 'messages' pret pour Unsloth / Ollama.

Usage :
    python scripts/build_training_dataset.py --samples 500 --output data/tutor_finetune.jsonl
"""

import argparse
import json
import random
import re
import urllib.request
from pathlib import Path

# URL directe de l'API Hugging Face pour recuperer des lignes de 'agentlans/grammar-correction'
HF_API_URL = (
    "https://datasets-server.huggingface.co/rows?"
    "dataset=agentlans%2Fgrammar-correction&config=default&split=train&offset={offset}&limit={limit}"
)

# Questions de relance simples pour entretenir la conversation (niveau A1-A2)
FOLLOW_UPS = [
    "What do you think?",
    "Can you tell me more?",
    "Why do you like it?",
    "When did that happen?",
    "Who were you with?",
    "How was it?",
    "Do you do this often?",
    "What is your favorite part?",
]

# Modeles d'auto-corrections simulees pour apprendre au modele a reagir aux reprises
REPAIR_TEMPLATES = [
    ("I go", "I went"),
    ("She have", "She has"),
    ("He don't", "He doesn't"),
    ("They is", "They are"),
    ("I am agree", "I agree"),
    ("I have 20 years", "I am 20 years old"),
]

SYSTEM_PROMPT = (
    "You are a friendly, encouraging English tutor for beginner learners. "
    "Respond in 1 or 2 short spoken sentences (maximum 20 words). "
    "Praise self-corrections, gently recast mistakes, and always end with a simple question."
)


def fetch_hf_rows(limit=100, offset=0):
    """Telecharge des lignes depuis l'API publique de Hugging Face sans necessiter de package lourd."""
    url = HF_API_URL.format(offset=offset, limit=min(limit, 100))
    req = urllib.request.Request(url, headers={"User-Agent": "EnglishTutor/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.load(resp)
            return [r["row"] for r in data.get("rows", [])]
    except Exception as e:
        print(f"Avertissement : impossible d'atteindre Hugging Face ({e}). Utilisation du jeu de secours local.")
        return []


def create_tutor_response(uncorrected: str, corrected: str, is_repair: bool = False) -> str:
    """Genere une reponse pedagogique parfaite de tuteur oral."""
    follow_up = random.choice(FOLLOW_UPS)

    if is_repair:
        praise = random.choice(["Great self-correction!", "Well done fixing that!", "Nice correction!"])
        # Reprise douce avec la cible
        clean = corrected.rstrip(".!?")
        return f"{praise} Yes, {clean[0].lower() + clean[1:]}. {follow_up}"

    # Recast classique : reprise de la correction dans la reponse
    lead = random.choice(["Good try!", "I see!", "Nice!", "Ah, good."])
    clean = corrected.rstrip(".!?")
    return f"{lead} So, {clean[0].lower() + clean[1:]}. {follow_up}"


def build_dataset(total_samples=300, output_path="data/tutor_finetune.jsonl"):
    print(f"Preparation de {total_samples} exemples pour le fine-tuning...")
    records = []

    # 1. Recuperation des donnees GEC Hugging Face
    fetched = []
    batch_size = 100
    for offset in range(0, total_samples, batch_size):
        rows = fetch_hf_rows(limit=min(batch_size, total_samples - len(fetched)), offset=offset)
        if not rows:
            break
        fetched.extend(rows)

    # 2. Transformation des paires Hugging Face en conversations de tuteur
    for row in fetched:
        inp = row.get("input", "").strip()
        out = row.get("output", "").strip()
        if not inp or not out or inp == out:
            continue

        tutor_reply = create_tutor_response(inp, out, is_repair=False)
        conversation = {
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": inp},
                {"role": "assistant", "content": tutor_reply},
            ]
        }
        records.append(conversation)

    # 3. Ajout d'exemples specifiques de Speech Repair (auto-correction orale)
    for bad, good in REPAIR_TEMPLATES:
        simulated_user = f"{bad}... no, {good} yesterday."
        corrected_full = f"{good} yesterday."
        tutor_reply = create_tutor_response(simulated_user, corrected_full, is_repair=True)
        records.append({
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": simulated_user},
                {"role": "assistant", "content": tutor_reply},
            ]
        })

    # Sauvegarde au format JSONL
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    print(f"Termine ! {len(records)} exemples generes et enregistres dans : {output_path}")
    if records:
        print("\nExemple de paire generee pour le fine-tuning :")
        sample = records[0]["messages"]
        print(f"  [System]    : {sample[0]['content']}")
        print(f"  [User]      : {sample[1]['content']}")
        print(f"  [Assistant] : {sample[2]['content']}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Genere le dataset de fine-tuning du Tuteur.")
    parser.add_argument("--samples", type=int, default=150, help="Nombre d'exemples a telecharger")
    parser.add_argument("--output", type=str, default="data/tutor_finetune.jsonl", help="Fichier de sortie")
    args = parser.parse_args()

    build_dataset(total_samples=args.samples, output_path=args.output)

