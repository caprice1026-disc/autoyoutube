from __future__ import annotations

import sqlite3
from pathlib import Path

from src.config import DB_PATH, DB_SCHEMA_PATH


def connect(db_path: Path = DB_PATH) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def init_db(db_path: Path = DB_PATH, schema_path: Path = DB_SCHEMA_PATH) -> None:
    with connect(db_path) as connection:
        connection.executescript(schema_path.read_text(encoding="utf-8"))
        _ensure_lightweight_migrations(connection)


def _ensure_lightweight_migrations(connection: sqlite3.Connection) -> None:
    _add_column_if_missing(connection, "youtube_projects", "voice_style_id", "INTEGER")
    _add_column_if_missing(
        connection, "render_voice_settings", "voice_style_id", "INTEGER"
    )


def _add_column_if_missing(
    connection: sqlite3.Connection, table: str, column: str, definition: str
) -> None:
    columns = {
        row["name"]
        for row in connection.execute(f"PRAGMA table_info({table})").fetchall()
    }
    if column not in columns:
        connection.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
