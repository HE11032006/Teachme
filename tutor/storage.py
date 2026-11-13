"""Stockage local SQLite : sessions et tours de parole."""

import sqlite3
import time
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    course_id TEXT NOT NULL,
    started_at REAL NOT NULL,
    ended_at REAL
);

CREATE TABLE IF NOT EXISTS turns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL REFERENCES sessions(id),
    step_id TEXT,
    role TEXT NOT NULL,
    text TEXT NOT NULL,
    raw_text TEXT,
    was_repaired INTEGER DEFAULT 0,
    passed INTEGER,
    stt_confidence REAL,
    ts REAL NOT NULL
);

-- Modele de maitrise a 5 etats (§4.3)
CREATE TABLE IF NOT EXISTS competencies (
    id TEXT PRIMARY KEY,               -- ex: 'intro.name', 'intro.city', 'intro.age'
    state TEXT NOT NULL,               -- DECOUVERTE, COMPRIS, UTILISE_AVEC_AIDE, UTILISE_SPONTANEMENT, MAITRISE_RETENU
    consecutive_successes INTEGER DEFAULT 0,
    consecutive_failures INTEGER DEFAULT 0,
    recurring_errors_count INTEGER DEFAULT 0,
    last_evaluated_at REAL NOT NULL,
    next_review_at REAL                -- Pour la repetition espacee (Phase 3)
);

-- Table dediee aux echantillons de fine-tuning (§4.8)
CREATE TABLE IF NOT EXISTS training_samples (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER REFERENCES sessions(id),
    step_id TEXT,
    raw_text TEXT NOT NULL,
    cleaned_text TEXT NOT NULL,
    was_repaired INTEGER DEFAULT 0,
    self_corrected INTEGER DEFAULT 0,
    llm_response TEXT,
    target_correction TEXT,
    stt_confidence REAL,
    ts REAL NOT NULL
);
"""


class Store:
    def __init__(self, path):
        if str(path) != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(str(path))
        self.db.executescript(SCHEMA)
        self._migrate()

    def _migrate(self):
        """Ajoute les colonnes manquantes si la base existait deja avec l'ancien schema."""
        cur = self.db.execute("PRAGMA table_info(turns)")
        cols = {row[1] for row in cur.fetchall()}
        if "raw_text" not in cols:
            self.db.execute("ALTER TABLE turns ADD COLUMN raw_text TEXT")
        if "was_repaired" not in cols:
            self.db.execute("ALTER TABLE turns ADD COLUMN was_repaired INTEGER DEFAULT 0")
        if "stt_confidence" not in cols:
            self.db.execute("ALTER TABLE turns ADD COLUMN stt_confidence REAL")
        self.db.commit()

    def new_session(self, course_id):
        cur = self.db.execute(
            "INSERT INTO sessions (course_id, started_at) VALUES (?, ?)",
            (course_id, time.time()),
        )
        self.db.commit()
        return cur.lastrowid

    def log_turn(self, session_id, step_id, role, text, raw_text=None, was_repaired=False, passed=None, stt_confidence=None):
        self.db.execute(
            """INSERT INTO turns (session_id, step_id, role, text, raw_text, was_repaired, passed, stt_confidence, ts)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                session_id,
                step_id,
                role,
                text,
                raw_text or text,
                int(was_repaired),
                None if passed is None else int(passed),
                stt_confidence,
                time.time(),
            ),
        )
        self.db.commit()

    def log_training_sample(self, session_id, step_id, raw_text, cleaned_text, was_repaired, self_corrected, llm_response, target_correction, stt_confidence):
        """Enregistre un exemple d'entrainement de haute qualite (§4.8)."""
        self.db.execute(
            """INSERT INTO training_samples (session_id, step_id, raw_text, cleaned_text, was_repaired, self_corrected, llm_response, target_correction, stt_confidence, ts)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                session_id,
                step_id,
                raw_text,
                cleaned_text,
                int(was_repaired),
                int(self_corrected),
                llm_response,
                target_correction,
                stt_confidence,
                time.time(),
            ),
        )
        self.db.commit()

    def get_competencies_due_for_review(self, current_time=None):
        """Retourne les competences dont la date de revision est echue (Phase 3)."""
        now = current_time or time.time()
        cur = self.db.execute(
            """SELECT id, state, next_review_at FROM competencies
               WHERE next_review_at IS NOT NULL AND next_review_at <= ?
               ORDER BY next_review_at ASC""",
            (now,),
        )
        return cur.fetchall()

    def get_competency(self, comp_id):
        cur = self.db.execute(
            "SELECT id, state, consecutive_successes, consecutive_failures, recurring_errors_count, last_evaluated_at, next_review_at FROM competencies WHERE id = ?",
            (comp_id,),
        )
        return cur.fetchone()

    def save_competency(self, comp_id, state, successes, failures, errors_count, next_review_at=None):
        self.db.execute(
            """INSERT INTO competencies (id, state, consecutive_successes, consecutive_failures, recurring_errors_count, last_evaluated_at, next_review_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(id) DO UPDATE SET
                   state = excluded.state,
                   consecutive_successes = excluded.consecutive_successes,
                   consecutive_failures = excluded.consecutive_failures,
                   recurring_errors_count = excluded.recurring_errors_count,
                   last_evaluated_at = excluded.last_evaluated_at,
                   next_review_at = excluded.next_review_at""",
            (comp_id, state, successes, failures, errors_count, time.time(), next_review_at),
        )
        self.db.commit()

    def close_session(self, session_id):
        self.db.execute(
            "UPDATE sessions SET ended_at = ? WHERE id = ? AND ended_at IS NULL",
            (time.time(), session_id),
        )
        self.db.commit()

    def turns(self, session_id):
        cur = self.db.execute(
            """SELECT step_id, role, text, raw_text, was_repaired, passed
               FROM turns WHERE session_id = ? ORDER BY id""",
            (session_id,),
        )
        return cur.fetchall()

    def export_training_samples(self):
        """Exporte les tours 'student' et 'tutor' ordonnes sous forme de paires pour fine-tuning."""
        cur = self.db.execute(
            """SELECT session_id, role, text, raw_text, was_repaired, step_id
               FROM turns ORDER BY session_id, id"""
        )
        rows = cur.fetchall()
        samples = []
        for i in range(len(rows) - 1):
            s_sess, s_role, s_text, s_raw, s_repaired, s_step = rows[i]
            t_sess, t_role, t_text, _t_raw, _t_rep, _t_step = rows[i + 1]
            if s_sess == t_sess and s_role == "student" and t_role == "tutor":
                samples.append({
                    "raw_input": s_raw,
                    "cleaned_input": s_text,
                    "was_repaired": bool(s_repaired),
                    "tutor_response": t_text,
                    "step_id": s_step,
                })
        return samples

    def close(self):
        self.db.close()
