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


def test_all_command_entry_points_support_end_cta() -> None:
    make_video_wrapper = (ROOT / "scripts" / "make-video.ps1").read_text(
        encoding="utf-8"
    )
    generated_intro_wrapper = (
        ROOT / "scripts" / "make-video-with-generated-intro.ps1"
    ).read_text(encoding="utf-8")
    upload_runner = (ROOT / "scripts" / "run-upload-command-list.ps1").read_text(
        encoding="utf-8"
    )

    for wrapper in (make_video_wrapper, generated_intro_wrapper):
        assert "[switch]$AppendEndCta" in wrapper
        assert '"--append-end-cta"' in wrapper
    assert "--append-end-cta" in upload_runner
    assert "-AppendEndCta" in upload_runner
