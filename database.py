# database.py

import sqlite3
from pathlib import Path
from datetime import datetime


class BrowserDatabase:
    """Handles all SQLite operations for history and bookmarks."""

    def __init__(self, db_path: str = "browser.db") -> None:
        self.db_path = Path(db_path)
        self._initialize_database()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def _initialize_database(self) -> None:
        with self._connect() as conn:
            cursor = conn.cursor()

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    url TEXT NOT NULL,
                    title TEXT,
                    visited_at TEXT NOT NULL
                )
                """
            )

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS bookmarks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    url TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )

            conn.commit()

    # ---------------- HISTORY ---------------- #

    def add_history(self, url: str, title: str) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO history (url, title, visited_at)
                VALUES (?, ?, ?)
                """,
                (url, title, datetime.utcnow().isoformat()),
            )
            conn.commit()

    def get_history(self) -> list[tuple]:
        with self._connect() as conn:
            return conn.execute(
                """
                SELECT title, url, visited_at
                FROM history
                ORDER BY visited_at DESC
                """
            ).fetchall()

    # ---------------- BOOKMARKS ---------------- #

    def add_bookmark(self, title: str, url: str) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO bookmarks (title, url, created_at)
                VALUES (?, ?, ?)
                """,
                (title, url, datetime.utcnow().isoformat()),
            )
            conn.commit()

    def get_bookmarks(self) -> list[tuple]:
        with self._connect() as conn:
            return conn.execute(
                """
                SELECT title, url, created_at
                FROM bookmarks
                ORDER BY created_at DESC
                """
            ).fetchall()