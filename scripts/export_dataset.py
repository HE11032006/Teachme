#!/usr/bin/env python
"""Exporte la table training_samples vers le format Alpaca JSONL pour fine-tuning (§4.8).

Format de sortie (un objet JSON par ligne) :
{
  "instruction": "...",
  "input": "<texte brut de l'élève>",
  "output": "<correction cible ou réaction si correct>",
  "metadata": {
    "step_id": "name",
    "was_repaired": false,
    "self_corrected": false,
    "stt_confidence": -0.3
  }
}

Usage :
    python scripts/export_dataset.py
    python scripts/export_dataset.py --out data/finetune_export.jsonl
    python scripts/export_dataset.py --only-errors
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from tutor.config import Config
from tutor.storage import Store

_INSTR_CORRECT = (
    "You are a kind English tutor for an A1 learner. "
    "The student's response was correct. "
    "Write a short encouraging reaction (max 12 words, no questions, no markdown)."
)
_INSTR_WRONG = (
    "You are a kind English tutor for an A1 learner. "
    "The student made an error. "
    "Write a short targeted correction with the corrected sentence (max 20 words, no markdown)."
)
_INSTR_SELF = (
    "You are a kind English tutor for an A1 learner. "
    "The student hesitated but self-corrected. "
    "Write a short encouraging reaction that acknowledges the self-correction (max 12 words, no markdown)."
)


def build_sample(row: tuple) -> dict:
    """Transforme une ligne de training_samples en objet Alpaca."""
    (sid, step_id, raw_text, cleaned_text,
     was_repaired, self_corrected, llm_response,
     target_correction, stt_confidence) = row

    if self_corrected:
        instruction = _INSTR_SELF
        output = "Great self-correction! Keep going."
    elif target_correction:
        instruction = _INSTR_WRONG
        output = target_correction
    else:
        instruction = _INSTR_CORRECT
        output = "Good job!"

    return {
        "instruction": instruction,
        "input": raw_text or cleaned_text,
        "output": output,
        "metadata": {
            "step_id": step_id,
            "was_repaired": bool(was_repaired),
            "self_corrected": bool(self_corrected),
            "stt_confidence": stt_confidence,
        },
    }


def export(store, out_path: Path, only_errors: bool = False) -> int:
    """Exporte vers un fichier JSONL Alpaca. Retourne le nombre d'échantillons."""
    base_query = """
        SELECT session_id, step_id, raw_text, cleaned_text,
               was_repaired, self_corrected, llm_response,
               target_correction, stt_confidence
        FROM training_samples
        {where}
        ORDER BY session_id, id
    """
    where = "WHERE target_correction IS NOT NULL" if only_errors else ""
    cur = store.db.execute(base_query.format(where=where))
    rows = cur.fetchall()

    out_path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with open(out_path, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(build_sample(row), ensure_ascii=False) + "\n")
            count += 1
    return count


def main():
    parser = argparse.ArgumentParser(
        description="Export training_samples → Alpaca JSONL"
    )
    parser.add_argument("--out", default=None,
                        help="Fichier de sortie (défaut : data/finetune_export.jsonl)")
    parser.add_argument("--only-errors", action="store_true",
                        help="N'exporter que les tours avec une correction cible")
    parser.add_argument("--db", default=None,
                        help="Base SQLite (défaut : config)")
    args = parser.parse_args()

    cfg = Config()
    db_path = args.db or cfg.db_path
    out_path = Path(args.out) if args.out else Path("data/finetune_export.jsonl")

    store = Store(db_path)
    try:
        count = export(store, out_path, only_errors=args.only_errors)
        print(f"✓ {count} échantillons exportés → {out_path}")
        if count == 0:
            print("  (Aucune donnée : lance d'abord quelques sessions avec python main.py)")
    finally:
        store.close()


if __name__ == "__main__":
    main()

