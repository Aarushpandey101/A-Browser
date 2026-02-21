# database.py

import json
import sqlite3
from datetime import datetime
from pathlib import Path


class BrowserDatabase:
    """Handles SQLite operations for browser data."""

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
                    folder TEXT NOT NULL DEFAULT 'Favorites',
                    position INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL
                )
                """
            )

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS passwords (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    site TEXT NOT NULL,
                    username TEXT NOT NULL,
                    password TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    payload TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )

            conn.commit()

    def add_history(self, url: str, title: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO history (url, title, visited_at) VALUES (?, ?, ?)",
                (url, title, datetime.utcnow().isoformat()),
            )

    def add_bookmark(self, title: str, url: str, folder: str = "Favorites", position: int = 0) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO bookmarks (title, url, folder, position, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (title, url, folder, position, datetime.utcnow().isoformat()),
            )

    def get_bookmarks(self) -> list[tuple]:
        with self._connect() as conn:
            return conn.execute(
                """
                SELECT id, title, url, folder, position, created_at
                FROM bookmarks
                ORDER BY folder ASC, position ASC, created_at DESC
                """
            ).fetchall()

    def replace_bookmarks(self, bookmarks: list[dict]) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM bookmarks")
            for row in bookmarks:
                conn.execute(
                    """
                    INSERT INTO bookmarks (title, url, folder, position, created_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        row.get("title", "Untitled"),
                        row.get("url", ""),
                        row.get("folder", "Favorites"),
                        int(row.get("position", 0)),
                        row.get("created_at", datetime.utcnow().isoformat()),
                    ),
                )

    def add_password(self, site: str, username: str, password: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO passwords (site, username, password, created_at) VALUES (?, ?, ?, ?)",
                (site, username, password, datetime.utcnow().isoformat()),
            )

    def get_password(self, site: str) -> tuple[str, str] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT username, password FROM passwords WHERE site = ? ORDER BY id DESC LIMIT 1",
                (site,),
            ).fetchone()
        return row if row else None

    def save_session(self, tabs: list[str]) -> None:
        with self._connect() as conn:
            payload = json.dumps({"tabs": tabs})
            conn.execute(
                """
                INSERT INTO sessions (id, payload, updated_at)
                VALUES (1, ?, ?)
                ON CONFLICT(id) DO UPDATE SET payload=excluded.payload, updated_at=excluded.updated_at
                """,
                (payload, datetime.utcnow().isoformat()),
            )

    def load_session(self) -> list[str]:
        with self._connect() as conn:
            row = conn.execute("SELECT payload FROM sessions WHERE id = 1").fetchone()
        if not row:
            return []
        try:
            parsed = json.loads(row[0])
            tabs = parsed.get("tabs", [])
            return [u for u in tabs if isinstance(u, str)]
        except json.JSONDecodeError:
            return []
