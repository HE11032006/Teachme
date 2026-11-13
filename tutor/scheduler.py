"""Planificateur de repetition espacee et parcours adaptatif (Phase 3 & Phase 4).

Gere :
1. L'injection des competences a reviser (J+1, J+2, J+4, J+7, J+14).
2. Le saut d'etape si 3 reussites spontanees consecutives.
3. La sequence de remediation ciblee apres 3 echecs consecutifs.
"""

import time
from typing import List, Optional


class ReviewScheduler:
    def __init__(self, store):
        self.store = store

    def get_due_reviews(self) -> List[str]:
        """Retourne la liste des identifiants de competences a reviser maintenant."""
        if not self.store:
            return []
        rows = self.store.get_competencies_due_for_review()
        return [row[0] for row in rows]

    def should_skip_step(self, comp_id: str) -> bool:
        """Saut d'etape automatique si la competence a 3 reussites spontanees consecutives (Phase 4)."""
        if not self.store:
            return False
        row = self.store.get_competency(comp_id)
        if not row:
            return False
        # row: (id, state, consecutive_successes, consecutive_failures, recurring_errors, last_eval, next_rev)
        successes = row[2]
        state = row[1]
        return successes >= 3 and state in ("UTILISE_SPONTANEMENT", "MAITRISE_RETENU")

    def needs_remediation(self, comp_id: str) -> bool:
        """Declenche une sequence de remediation ciblee si 3 echecs consecutifs (Phase 4)."""
        if not self.store:
            return False
        row = self.store.get_competency(comp_id)
        if not row:
            return False
        failures = row[3]
        return failures >= 3

