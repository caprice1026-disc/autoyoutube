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
