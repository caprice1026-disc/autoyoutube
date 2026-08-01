from __future__ import annotations

import sqlite3
import threading
import time
from pathlib import Path

from src.db.database import connect, init_db


def test_connect_waits_for_a_transient_write_lock(tmp_path: Path) -> None:
    """A short competing write must not abort a sequential render batch."""

    db_path = tmp_path / "locked.db"
    init_db(db_path)
    with sqlite3.connect(db_path) as connection:
        connection.execute("CREATE TABLE lock_probe (value INTEGER NOT NULL)")

    lock_started = threading.Event()

    def hold_write_lock() -> None:
        with sqlite3.connect(db_path) as connection:
            connection.execute("BEGIN IMMEDIATE")
            lock_started.set()
            time.sleep(7.0)

    locker = threading.Thread(target=hold_write_lock)
    locker.start()
    assert lock_started.wait(timeout=1)

    with connect(db_path) as connection:
        connection.execute("INSERT INTO lock_probe (value) VALUES (1)")

    locker.join(timeout=1)
    assert not locker.is_alive()
    with sqlite3.connect(db_path) as connection:
        assert connection.execute("SELECT value FROM lock_probe").fetchone()[0] == 1
