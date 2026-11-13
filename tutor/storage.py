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

    def new_session(self, course_id):
        cur = self.db.execute(
            "INSERT INTO sessions (course_id, started_at) VALUES (?, ?)",
            (course_id, time.time()),
        )
        self.db.commit()
        return cur.lastrowid

    def log_turn(self, session_id, step_id, role, text, passed=None):
        self.db.execute(
            "INSERT INTO turns (session_id, step_id, role, text, passed, ts) VALUES (?, ?, ?, ?, ?, ?)",
            (session_id, step_id, role, text, None if passed is None else int(passed), time.time()),
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
            "SELECT step_id, role, text, passed FROM turns WHERE session_id = ? ORDER BY id",
            (session_id,),
        )
        return cur.fetchall()

    def close(self):
        self.db.close()
