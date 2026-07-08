from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent


def test_youtube_auth_script_executes_help() -> None:
    result = subprocess.run(
        [sys.executable, str(ROOT_DIR / "src" / "youtube" / "auth.py"), "--help"],
        cwd=ROOT_DIR,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert "Authorize YouTube upload access for AutoYoutube." in result.stdout
