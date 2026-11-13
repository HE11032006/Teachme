"""Gestionnaire de progression pedagogique (Progress Tracker - §4.3).

Gere la transition des 5 etats de maitrise :
DECOUVERTE -> COMPRIS -> UTILISE_AVEC_AIDE -> UTILISE_SPONTANEMENT -> MAITRISE_RETENU
"""

import time
from enum import Enum
from typing import Optional


class MasteryState(str, Enum):
    DECOUVERTE = "DECOUVERTE"
    COMPRIS = "COMPRIS"
    UTILISE_AVEC_AIDE = "UTILISE_AVEC_AIDE"
    UTILISE_SPONTANEMENT = "UTILISE_SPONTANEMENT"
    MAITRISE_RETENU = "MAITRISE_RETENU"


# Intervalles de repetition espacee en secondes (§4.3 & Phase 3 : J+1, J+2, J+4, J+7, J+14)
SPACED_REVIEW_INTERVALS = {
    MasteryState.COMPRIS: 86400 * 1,               # J+1
    MasteryState.UTILISE_AVEC_AIDE: 86400 * 2,     # J+2
    MasteryState.UTILISE_SPONTANEMENT: 86400 * 4,  # J+4
    MasteryState.MAITRISE_RETENU: 86400 * 7,       # J+7 (puis J+14)
}


class ProgressTracker:
    def __init__(self, store):
        self.store = store

    def evaluate_attempt(self, competency_id: str, passed: bool, used_help: bool, was_repaired: bool = False) -> str:
        """Calcule et met a jour le nouvel etat de maitrise selon le resultat de l'eleve."""
        row = self.store.get_competency(competency_id) if self.store else None

        if row:
            _, state_str, successes, failures, errors_count, _, _ = row
            current_state = MasteryState(state_str)
        else:
            current_state = MasteryState.DECOUVERTE
            successes = 0
            failures = 0
            errors_count = 0

        # Calcul de la transition d'etat
        if passed:
            successes += 1
            failures = 0
            if used_help:
                new_state = MasteryState.UTILISE_AVEC_AIDE
            else:
                # Reussite spontanee sans aide
                if current_state in (MasteryState.DECOUVERTE, MasteryState.COMPRIS):
                    new_state = MasteryState.UTILISE_SPONTANEMENT
                elif current_state == MasteryState.UTILISE_AVEC_AIDE:
                    new_state = MasteryState.UTILISE_SPONTANEMENT
                elif current_state == MasteryState.UTILISE_SPONTANEMENT and successes >= 2:
                    new_state = MasteryState.MAITRISE_RETENU
                else:
                    new_state = current_state
        else:
            # Echec
            failures += 1
            successes = 0
            errors_count += 1
            # Regression si echecs repetes
            if failures >= 2 and current_state in (MasteryState.UTILISE_SPONTANEMENT, MasteryState.MAITRISE_RETENU):
                new_state = MasteryState.UTILISE_AVEC_AIDE
            else:
                new_state = current_state if current_state != MasteryState.DECOUVERTE else MasteryState.DECOUVERTE

        # Planification de la prochaine revision
        interval = SPACED_REVIEW_INTERVALS.get(new_state, 86400)
        next_review_at = time.time() + interval

        if self.store:
            self.store.save_competency(competency_id, new_state.value, successes, failures, errors_count, next_review_at)

        return new_state.value

