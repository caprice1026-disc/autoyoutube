from __future__ import annotations

import sys
from pathlib import Path

from src.main import main


def test_validate_project_missing_file_returns_actionable_error(
    monkeypatch, capsys, tmp_path: Path
) -> None:
    missing_path = tmp_path / "missing.project.youtube.json"
    monkeypatch.setattr(sys, "argv", ["tsm", "validate-project", str(missing_path)])

    exit_code = main()

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "Error: JSON file was not found." in captured.err
    assert f"Location: {missing_path}" in captured.err
    assert "Next step: Check the path and run the command again." in captured.err
    assert "Traceback" not in captured.err


def test_render_missing_ffmpeg_path_returns_actionable_error(
    monkeypatch, capsys
) -> None:
    project_path = Path("projects/trivia_submarine_black_001/project.youtube.json")
    missing_ffmpeg = Path("C:/missing/ffmpeg.exe")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "tsm",
            "render",
            str(project_path),
            "--video-mode",
            "ffmpeg",
            "--ffmpeg-path",
            str(missing_ffmpeg),
        ],
    )

    exit_code = main()

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "Error: FFmpeg executable was not found." in captured.err
    assert f"Location: {missing_ffmpeg}" in captured.err
    assert "Next step: Install FFmpeg or pass --ffmpeg-path" in captured.err
    assert "Traceback" not in captured.err
