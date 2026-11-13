"""Métriques pédagogiques §6 du Brief Technique.

Ne pas mesurer le nombre de bonnes réponses. Mesurer :
  - first_attempt_accuracy  : réussite sans aide (0.0–1.0)
  - error_recurrence        : taux d'erreurs récurrentes (mêmes étapes échouées sur plusieurs sessions)
  - delayed_retention       : conservation après J+7 (état compétence >= UTILISE_SPONTANEMENT)
  - transfer_accuracy       : réussite sur une étape déjà vue dans une session précédente
  - speaking_fluency        : % de réponses sans réparation vocale (proxy fluidité orale)

Toutes les métriques opèrent sur la base SQLite existante (tables turns et competencies).

Utilisation :
    from tutor.metrics import compute_metrics, print_report
    store = Store(cfg.db_path)
    m = compute_metrics(store)
    print_report(m)
"""

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class PedagogicalMetrics:
    # Premier essai réussi sans aide (was_repaired=0)
    first_attempt_accuracy: float = 0.0
    first_attempt_total: int = 0
    first_attempt_success: int = 0

    # Erreurs récurrentes : même étape échouée dans >= 2 sessions différentes
    error_recurrence_rate: float = 0.0
    recurring_error_steps: List[str] = field(default_factory=list)

    # Rétention différée : compétences évaluées à J+7 et état >= UTILISE_SPONTANEMENT
    delayed_retention_rate: float = 0.0
    retained_count: int = 0
    reviewed_count: int = 0

    # Transfert : réussite premier essai sur une étape déjà vue dans une session précédente
    transfer_accuracy: float = 0.0
    transfer_total: int = 0
    transfer_success: int = 0

    # Fluidité orale proxy : % de tours sans réparation vocale
    speaking_fluency: float = 0.0
    fluent_turns: int = 0
    total_student_turns: int = 0

    # Résumé textuel prêt à afficher
    summary: str = ""


def compute_metrics(store) -> PedagogicalMetrics:
    """Calcule toutes les métriques pédagogiques à partir de la base SQLite."""
    m = PedagogicalMetrics()
    db = store.db

    # --- 1. First-attempt accuracy ---
    # Premier tour student par (session, étape), avec was_repaired=0 (sans aide)
    cur = db.execute("""
        SELECT t.passed, t.was_repaired
        FROM turns t
        WHERE t.role = 'student' AND t.passed IS NOT NULL
          AND t.id = (
              SELECT MIN(t2.id) FROM turns t2
              WHERE t2.session_id = t.session_id
                AND t2.step_id = t.step_id
                AND t2.role = 'student'
          )
    """)
    rows = cur.fetchall()
    m.first_attempt_total = len(rows)
    # Réussite spontanée = passed=1 ET pas de réparation
    m.first_attempt_success = sum(1 for r in rows if r[0] == 1 and r[1] == 0)
    if m.first_attempt_total > 0:
        m.first_attempt_accuracy = m.first_attempt_success / m.first_attempt_total

    # --- 2. Error recurrence ---
    # Étapes échouées dans au moins 2 sessions différentes
    cur = db.execute("""
        SELECT step_id, COUNT(DISTINCT session_id) AS fail_sessions
        FROM turns
        WHERE role = 'student' AND passed = 0 AND step_id IS NOT NULL
        GROUP BY step_id
        HAVING fail_sessions >= 2
        ORDER BY fail_sessions DESC
    """)
    recurring = cur.fetchall()
    m.recurring_error_steps = [r[0] for r in recurring]

    cur2 = db.execute("""
        SELECT COUNT(DISTINCT step_id) FROM turns
        WHERE role = 'student' AND passed = 0 AND step_id IS NOT NULL
    """)
    total_failed = (cur2.fetchone() or [0])[0]
    if total_failed > 0:
        m.error_recurrence_rate = len(m.recurring_error_steps) / total_failed

    # --- 3. Delayed retention ---
    # Compétences dont l'évaluation finale est >= 7 jours après le premier tour
    seven_days = 7 * 24 * 3600
    cur = db.execute("""
        SELECT c.id, c.state, c.last_evaluated_at,
               (SELECT MIN(t.ts) FROM turns t
                WHERE t.step_id = SUBSTR(c.id, INSTR(c.id, '.') + 1)
                  AND t.role = 'student' AND t.passed IS NOT NULL) AS first_seen
        FROM competencies c
        WHERE c.last_evaluated_at IS NOT NULL
    """)
    for comp_id, state, last_eval, first_seen in cur.fetchall():
        if first_seen is None:
            continue
        if (last_eval - first_seen) >= seven_days:
            m.reviewed_count += 1
            if state in ("UTILISE_SPONTANEMENT", "MAITRISE_RETENU"):
                m.retained_count += 1
    if m.reviewed_count > 0:
        m.delayed_retention_rate = m.retained_count / m.reviewed_count

    # --- 4. Transfer accuracy (proxy) ---
    # Réussite premier essai sur une étape déjà vue dans au moins une session précédente
    cur = db.execute("""
        SELECT t.step_id, t.session_id, t.passed
        FROM turns t
        WHERE t.role = 'student' AND t.passed IS NOT NULL
          AND t.id = (
              SELECT MIN(t2.id) FROM turns t2
              WHERE t2.session_id = t.session_id
                AND t2.step_id = t.step_id
                AND t2.role = 'student'
          )
        ORDER BY t.session_id
    """)
    seen_steps: Dict[str, int] = {}  # step_id → nombre de sessions précédentes
    for step_id, session_id, passed in cur.fetchall():
        if step_id is None:
            continue
        prev = seen_steps.get(step_id, 0)
        if prev >= 1:
            m.transfer_total += 1
            if passed == 1:
                m.transfer_success += 1
        seen_steps[step_id] = prev + 1
    if m.transfer_total > 0:
        m.transfer_accuracy = m.transfer_success / m.transfer_total

    # --- 5. Speaking fluency proxy ---
    cur = db.execute("""
        SELECT was_repaired FROM turns
        WHERE role = 'student' AND passed IS NOT NULL
    """)
    fluency_rows = cur.fetchall()
    m.total_student_turns = len(fluency_rows)
    m.fluent_turns = sum(1 for r in fluency_rows if r[0] == 0)
    if m.total_student_turns > 0:
        m.speaking_fluency = m.fluent_turns / m.total_student_turns

    m.summary = _build_summary(m)
    return m


def _build_summary(m: PedagogicalMetrics) -> str:
    lines = [
        "=== Rapport pédagogique ===",
        f"Premier essai réussi     : {m.first_attempt_accuracy:.0%}  "
        f"({m.first_attempt_success}/{m.first_attempt_total})",
        f"Erreurs récurrentes      : {m.error_recurrence_rate:.0%}  "
        f"— étapes : {', '.join(m.recurring_error_steps) or 'aucune'}",
        f"Rétention après J+7      : {m.delayed_retention_rate:.0%}  "
        f"({m.retained_count}/{m.reviewed_count} compétences)",
        f"Réussite en transfert    : {m.transfer_accuracy:.0%}  "
        f"({m.transfer_success}/{m.transfer_total})",
        f"Fluidité orale (proxy)   : {m.speaking_fluency:.0%}  "
        f"({m.fluent_turns}/{m.total_student_turns} sans reprise)",
    ]
    return "\n".join(lines)


def print_report(m: PedagogicalMetrics) -> None:
    """Affiche le rapport dans le terminal."""
    print(m.summary)

