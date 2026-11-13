"""Script d'exploration et d'exemple de telechargement des datasets Hugging Face.

Ce script illustre comment charger des echantillons de donnees :
1. De reparations de la parole / faux departs (ex: Switchboard / Disfluency)
2. De corrections grammaticales pour apprenants (GEC, ex: agentlans/grammar-correction)
"""

import json
from pathlib import Path


def explore_samples():
    print("--- 1. Exemples types de Speech Disfluency (Switchboard / Repairs) ---")
    disfluency_samples = [
        {
            "raw": "I go no I went to Paris last summer",
            "clean": "I went to Paris last summer",
            "type": "restart_with_marker",
        },
        {
            "raw": "She have she has two little cats",
            "clean": "She has two little cats",
            "type": "repetition_restart",
        },
        {
            "raw": "He live I mean he lives in Canada",
            "clean": "He lives in Canada",
            "type": "self_correction_marker",
        },
    ]
    for s in disfluency_samples:
        print(f"  [BRUT]    {s['raw']}")
        print(f"  [NETTOYE] {s['clean']} ({s['type']})\n")

    print("--- 2. Exemples types de Grammatical Error Correction (GEC Apprenants) ---")
    gec_samples = [
        {
            "input": "I am student in high school",
            "target": "I am a student in high school",
            "tutor_recast": "Nice! I am a student too. What grade are you in?",
        },
        {
            "input": "I have 22 years old",
            "target": "I am 22 years old",
            "tutor_recast": "Great! So you are 22 years old. When is your birthday?",
        },
        {
            "input": "Yesterday I go to the cinema",
            "target": "Yesterday I went to the cinema",
            "tutor_recast": "Oh, you went to the cinema? What movie did you see?",
        },
    ]
    for g in gec_samples:
        print(f"  [ELEVE]   {g['input']}")
        print(f"  [CIBLE]   {g['target']}")
        print(f"  [TUTEUR]  {g['tutor_recast']}\n")

    output_file = Path("data") / "sample_training_format.jsonl"
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, "w", encoding="utf-8") as f:
        for item in gec_samples:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")

    print(f"Format type enregistre dans {output_file}")


if __name__ == "__main__":
    explore_samples()

