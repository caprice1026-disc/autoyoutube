from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

import src.media.video_audio as audio_module
import src.generated_intro_main as generated_intro_main
import src.pipeline.make_video_with_generated_intro as intro_module
from src.errors import AppError
from src.media.video_audio import remove_audio_track
from src.pipeline.make_video import MakeVideoOptions, MakeVideoResult


def test_remove_audio_track_uses_video_only_stream_copy(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "generated_intro.mp4"
    source.write_bytes(b"input")
    output = tmp_path / "generated_intro.muted.mp4"
    commands: list[list[str]] = []

    monkeypatch.setattr(audio_module, "find_ffmpeg_executable", lambda value: Path("ffmpeg"))

    def fake_run(command: list[str], **kwargs):
        commands.append(command)
        output.write_bytes(b"video only")
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(audio_module.subprocess, "run", fake_run)

    result = remove_audio_track(source, output)

    assert result == output.resolve()
    assert "-an" in commands[0]
    assert commands[0][commands[0].index("-map") + 1] == "0:v:0"
    assert commands[0][commands[0].index("-c:v") + 1] == "copy"


def test_remove_audio_track_trims_the_leading_second_before_muting(
    tmp_path: Path, monkeypatch
) -> None:
    source = tmp_path / "generated_intro.mp4"
    source.write_bytes(b"input")
    output = tmp_path / "generated_intro.muted.mp4"
    commands: list[list[str]] = []

    monkeypatch.setattr(audio_module, "find_ffmpeg_executable", lambda value: Path("ffmpeg"))

    def fake_run(command: list[str], **kwargs):
        commands.append(command)
        output.write_bytes(b"trimmed video only")
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(audio_module.subprocess, "run", fake_run)

    result = remove_audio_track(source, output, trim_start_sec=1.0)

    assert result == output.resolve()
    assert commands[0][commands[0].index("-ss") + 1] == "1.000"
    assert commands[0].index("-ss") > commands[0].index("-i")
    assert commands[0][commands[0].index("-c:v") + 1] == "libx264"
    assert "-an" in commands[0]


def test_missing_generated_intro_falls_back_to_existing_make_video(
    tmp_path: Path, monkeypatch
) -> None:
    project_path = tmp_path / "project.youtube.json"
    project_path.write_text("{}", encoding="utf-8")
    expected = MakeVideoResult(0, "success", None, None, {"stock": True})
    calls: list[MakeVideoOptions] = []

    def fake_make_video(options: MakeVideoOptions) -> MakeVideoResult:
        calls.append(options)
        return expected

    monkeypatch.setattr(intro_module.make_video_module, "make_video", fake_make_video)

    result = intro_module.make_video_with_generated_intro(
        MakeVideoOptions(project_path=project_path)
    )

    assert result is expected
    assert calls[0].project_path == project_path


def test_generated_intro_uses_the_only_project_video_when_default_is_absent(
    tmp_path: Path,
) -> None:
    project_path = tmp_path / "project.youtube.json"
    project_path.write_text("{}", encoding="utf-8")
    intro = tmp_path / "ai-created-intro.mov"
    intro.write_bytes(b"clip")

    result = intro_module._resolve_generated_intro_path(project_path, None)

    assert result == intro.resolve()


def test_generated_intro_prefers_legacy_default_name_over_other_project_video(
    tmp_path: Path,
) -> None:
    project_path = tmp_path / "project.youtube.json"
    project_path.write_text("{}", encoding="utf-8")
    default_intro = tmp_path / "generated_intro.mp4"
    default_intro.write_bytes(b"legacy clip")
    (tmp_path / "ai-created-intro.mov").write_bytes(b"other clip")

    result = intro_module._resolve_generated_intro_path(project_path, None)

    assert result == default_intro.resolve()


def test_generated_intro_rejects_multiple_project_videos_when_default_is_absent(
    tmp_path: Path,
) -> None:
    project_path = tmp_path / "project.youtube.json"
    project_path.write_text("{}", encoding="utf-8")
    (tmp_path / "first-intro.mp4").write_bytes(b"first clip")
    (tmp_path / "second-intro.webm").write_bytes(b"second clip")
    (tmp_path / "generated_intro.muted.mp4").write_bytes(b"derived clip")

    with pytest.raises(AppError, match="Multiple generated intro videos"):
        intro_module._resolve_generated_intro_path(project_path, None)


def test_generated_intro_replaces_only_first_visual(tmp_path: Path) -> None:
    intro = tmp_path / "generated_intro.mp4"
    intro.write_bytes(b"clip")
    visuals = [
        {
            "index": 2,
            "video_start_sec": 4.0,
            "source": "pexels",
            "asset_id": "second",
            "local_file_path": "second.mp4",
        },
        {
            "index": 1,
            "video_start_sec": 0.0,
            "source": "pexels",
            "asset_id": "first",
            "local_file_path": "first.mp4",
        },
    ]

    intro_module._replace_first_visual(visuals, intro)

    assert visuals[1]["source"] == "local"
    assert visuals[1]["local_file_path"] == str(intro)
    assert visuals[1]["selected_quality"] == "original"
    assert visuals[1]["asset_id"] is None
    assert "pexels_id" not in visuals[1]
    assert "photographer" not in visuals[1]
    assert visuals[0]["asset_id"] == "second"


def test_plan_only_reports_available_generated_intro(tmp_path: Path, monkeypatch) -> None:
    project_path = tmp_path / "project.youtube.json"
    project_path.write_text("{}", encoding="utf-8")
    (tmp_path / "generated_intro.mp4").write_bytes(b"clip")

    monkeypatch.setattr(
        intro_module.make_video_module,
        "make_video",
        lambda options: MakeVideoResult(0, "planned", None, None, {"queries": []}),
    )

    result = intro_module.make_video_with_generated_intro(
        MakeVideoOptions(project_path=project_path, plan_only=True)
    )

    assert result.plan["generated_intro"]["status"] == "available"
    assert result.plan["generated_intro"]["audio_policy"] == "remove"
    assert result.plan["generated_intro"]["placement"] == "replace_first_visual"


def test_generated_intro_cli_passes_end_cta_option(monkeypatch, capsys) -> None:
    calls: list[MakeVideoOptions] = []
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "generated-intro",
            "projects/sample/project.youtube.json",
            "--append-end-cta",
            "--plan-only",
        ],
    )
    monkeypatch.setattr(generated_intro_main, "load_dotenv", lambda: None)
    monkeypatch.setattr(
        generated_intro_main,
        "make_video_with_generated_intro",
        lambda options, **kwargs: (
            calls.append(options)
            or MakeVideoResult(0, "planned", None, None, {"ok": True})
        ),
    )

    exit_code = generated_intro_main.main()

    assert exit_code == 0
    assert calls[0].append_end_cta is True
    assert '"ok": true' in capsys.readouterr().out
