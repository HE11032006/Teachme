# Feuille de route technique — Tuteur d'anglais oral hors-ligne

> **Objectif global** : Tuteur 100 % local (CPU i7-8665U, sans GPU), latence < 2 s, correction pédagogique réelle (pas de validation aveugle).

---

## Phase 1 — Analyse JSON + Correction ciblée ✅ TERMINÉE

| Tâche | État |
|---|---|
| Prompt d'analyse JSON optimisé 1.5B (`analyzer_prompt.py`) | ✅ |
| Validateur hybride Python + fallback règles A1 (`validator.py`) | ✅ |
| Anti-hallucination LLM (cascade règles → LLM → garde-fous) | ✅ |
| Intégration dans `_reply_guided` : blocage sur échec, recadrage off_topic | ✅ |
| Exploitation signaux STT : logprob < -0.8, no_speech > 0.3 (`main.py`) | ✅ |
| Module réparation vocale auto-correction / fausses reprises (`repair.py`) | ✅ |
| 48 tests unitaires (repair, core, evaluation, progress, scheduler) | ✅ |

---

## Phase 2 — Modèle de maîtrise + storage enrichi ✅ TERMINÉE

| Tâche | État |
|---|---|
| Modèle 5 états : DECOUVERTE → COMPRIS → UTILISE_AVEC_AIDE → UTILISE_SPONTANEMENT → MAITRISE_RETENU | ✅ |
| `ProgressTracker` : calcul d'état à partir de l'historique | ✅ |
| Table `competencies` dans SQLite (état + date + compteurs) | ✅ |
| Table `training_samples` (§4.8 — succès ET échecs) | ✅ |
| Auto-migration schéma sans casser les sessions existantes | ✅ |

---

## Phase 3 — Répétition espacée ✅ TERMINÉE

| Tâche | État |
|---|---|
| `ReviewScheduler` : intervalles J+1, J+2, J+4, J+7, J+14 | ✅ |
| `get_competencies_due_for_review()` dans `storage.py` | ✅ |
| Annonce des révisions dues au démarrage (`main.py` — mode texte et voix) | ✅ |
| `Tutor.get_due_reviews()` — API publique session → main | ✅ |

---

## Phase 4 — Parcours adaptatif ✅ TERMINÉE

| Tâche | État |
|---|---|
| `should_skip_step()` : saut automatique si 3 réussites spontanées | ✅ |
| `needs_remediation()` : remédiation ciblée si 3 échecs consécutifs | ✅ |
| Intégration dans `_reply_guided` (avant évaluation) | ✅ |
| `log_training_sample()` branché à chaque tour (succès + échecs) | ✅ |

---

## Phase 5 — Prononciation 🔲 DIFFÉRÉE

- Emplacement réservé : `tutor/pronunciation.py` (stub)
- Option légère : exploiter les logprobs par token de Whisper (déjà disponibles)
- Option ultérieure : wav2vec2 / speechbrain dédié
- **Ne pas implémenter avant stabilisation complète des phases 1-4**

---

## Phase 6 — Fine-tuning sur données réelles 🔲 APRÈS DONNÉES

- Exporter `training_samples` via `scripts/export_dataset.py` (format Alpaca JSONL)
- Réentraîner sur Colab avec `notebooks/finetune_colab.ipynb`
- **Uniquement après plusieurs semaines de sessions réelles**

---

## Métriques à instrumenter (dès maintenant)

| Métrique | Description |
|---|---|
| `first_attempt_accuracy` | Réussite sans aide |
| `error_recurrence` | Réapparition des mêmes erreurs |
| `delayed_retention` | Conservation après plusieurs jours |
| `transfer_accuracy` | Réutilisation en contexte nouveau |

---

## Modèles installés (Ollama)

| Modèle | Taille | Usage |
|---|---|---|
| `tutor-1.5b` | 986 MB | Profil PC / 6 GB RAM |
| `tutor-0.5b` | 397 MB | Profil mobile / 4 GB RAM |
| `qwen3:1.7b` | 1.4 GB | Référence benchmark |
| `qwen2.5:0.5b` | 397 MB | Référence ultra-rapide |

---

## Commits git à faire (en attente)

```
git add tutor/storage.py tutor/progress.py tutor/session.py tests/test_progress.py
git commit -m "Modèle de maîtrise à 5 états et ProgressTracker (Phase 2)"

git add tutor/scheduler.py tests/test_scheduler.py
git commit -m "Planificateur de révision espacée (Phase 3)"

git add tutor/session.py main.py
git commit -m "Intégration scheduler : saut d'étape, remédiation, journalisation training (Phases 3-4)"

git add ROADMAP.md
git commit -m "Mise à jour feuille de route : Phases 1 à 4 terminées"
```
