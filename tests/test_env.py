from __future__ import annotations

import os
from pathlib import Path

from src.env import load_dotenv


def test_load_dotenv_reads_key_without_overwriting_existing_value(
    tmp_path: Path, monkeypatch
) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text(
        'PEXELS_API_KEY="from-file"\nEXTRA_VALUE=loaded\n',
        encoding="utf-8",
    )
    monkeypatch.setenv("PEXELS_API_KEY", "already-set")
    monkeypatch.delenv("EXTRA_VALUE", raising=False)

    load_dotenv(env_path)

    assert os.environ["PEXELS_API_KEY"] == "already-set"
    assert os.environ["EXTRA_VALUE"] == "loaded"
