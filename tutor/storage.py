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
        self.db.commit()

    def new_session(self, course_id):
        cur = self.db.execute(
            "INSERT INTO sessions (course_id, started_at) VALUES (?, ?)",
            (course_id, time.time()),
        )
        self.db.commit()
        return cur.lastrowid

    def log_turn(self, session_id, step_id, role, text, raw_text=None, was_repaired=False, passed=None):
        self.db.execute(
            """INSERT INTO turns (session_id, step_id, role, text, raw_text, was_repaired, passed, ts)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                session_id,
                step_id,
                role,
                text,
                raw_text or text,
                int(was_repaired),
                None if passed is None else int(passed),
                time.time(),
            ),
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
