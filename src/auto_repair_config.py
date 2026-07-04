from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from src.config import ROOT_DIR

DEFAULT_MAX_FIX_ATTEMPTS = 5
DEFAULT_CONFIG_PATH = ROOT_DIR / "config" / "auto_repair.youtube_shorts.json"


def load_auto_repair_config(config_path: Path | None = None) -> dict[str, Any]:
    path = config_path or DEFAULT_CONFIG_PATH
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def resolve_max_fix_attempts(
    *,
    cli_value: int | None = None,
    config: dict[str, Any] | None = None,
    env: dict[str, str] | None = None,
) -> int:
    if cli_value is not None:
        return max(1, int(cli_value))

    environ = env if env is not None else os.environ
    env_value = environ.get("AUTOYOUTUBE_MAX_FIX_ATTEMPTS")
    if env_value:
        try:
            return max(1, int(env_value))
        except ValueError:
            return DEFAULT_MAX_FIX_ATTEMPTS

    repair = (config or {}).get("repair", {})
    if isinstance(repair, dict) and repair.get("max_attempts") is not None:
        try:
            return max(1, int(repair["max_attempts"]))
        except (TypeError, ValueError):
            return DEFAULT_MAX_FIX_ATTEMPTS

    return DEFAULT_MAX_FIX_ATTEMPTS
