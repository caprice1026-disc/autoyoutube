from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_upload_runner_supports_both_video_wrappers() -> None:
    runner = (ROOT / "scripts" / "run-upload-command-list.ps1").read_text(
        encoding="utf-8"
    )
    assert "make-video-with-generated-intro.sh" in runner
    assert "make-video-with-generated-intro.ps1" in runner
    assert "--generated-intro-path" in runner
    assert "-GeneratedIntroPath" in runner
    assert "scripts/make-video(?:-with-generated-intro)?" in runner
    assert "$commands = @(" in runner
    assert "make-video(?:-with-generated-intro)?\\.ps1" in runner
