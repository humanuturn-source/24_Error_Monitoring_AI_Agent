"""
database.py
Local SQLite persistence for UI error-check runs, extracted page text,
and verification outcomes.
"""

import os
import sqlite3
from typing import Any, Dict, List

DB_PATH = "./data/error_checks.db"


class ErrorCheckDatabase:
    def __init__(self, db_path: str = DB_PATH) -> None:
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.db_path = db_path
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS error_check_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    query TEXT NOT NULL,
                    target_url TEXT,
                    page_title TEXT,
                    http_status INTEGER,
                    extracted_text TEXT,
                    verification_notes TEXT,
                    status TEXT DEFAULT 'COMPLETED',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.commit()

    def save_run(
        self,
        query: str,
        target_url: str,
        page_title: str,
        http_status: int | None,
        extracted_text: str,
        verification_notes: str,
        status: str = "COMPLETED",
    ) -> int:
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO error_check_runs
                    (query, target_url, page_title, http_status, extracted_text, verification_notes, status)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    query,
                    target_url,
                    page_title,
                    http_status,
                    extracted_text,
                    verification_notes,
                    status,
                ),
            )
            conn.commit()
            return int(cursor.lastrowid)

    def get_recent_runs(self, limit: int = 10) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM error_check_runs ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
            return [dict(r) for r in rows]
