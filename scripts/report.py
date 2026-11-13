#!/usr/bin/env python
"""Affiche le rapport pédagogique depuis la base SQLite (§6 — métriques).

Usage :
    python scripts/report.py
    python scripts/report.py --db data/english_tutor.db
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from tutor.config import Config
from tutor.metrics import compute_metrics, print_report
from tutor.storage import Store


def main():
    parser = argparse.ArgumentParser(description="Rapport pédagogique du tuteur")
    parser.add_argument("--db", default=None, help="Chemin vers la base SQLite (défaut : config)")
    args = parser.parse_args()

    cfg = Config()
    db_path = args.db or cfg.db_path
    store = Store(db_path)
    try:
        m = compute_metrics(store)
        print_report(m)
    finally:
        store.close()


if __name__ == "__main__":
    main()

