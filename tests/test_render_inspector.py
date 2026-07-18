from __future__ import annotations

import json
import subprocess
import wave
from pathlib import Path


def _rendered(render_dir: Path) -> dict:
    return {
        "project_id": "inspect_project",
        "render_id": "render_inspect",
        "output": {
            "video_path": str(render_dir / "output.mp4"),
        },
        "target": {
            "planned_duration_sec": 6.0,
            "actual_duration_sec": 6.0,
            "resolution": {"width": 1080, "height": 1920},
            "fps": 30,
        },
        "audio": {
            "final_audio_path": str(render_dir / "audio" / "final_audio.wav"),
        },
        "subtitles": {
            "items": [
                {"index": 1, "text": "最初の字幕", "start_sec": 0.0, "end_sec": 2.0},
                {"index": 2, "text": "次の字幕", "start_sec": 2.2, "end_sec": 4.0},
            ]
        },
    }


def _write_wav(path: Path, *, duration_sec: float = 1.0) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(44100)
        wav.writeframes(b"\x01\x00" * int(44100 * duration_sec))


def test_inspect_render_extracts_summary_subtitle_and_timeline_frames(
    monkeypatch,
    tmp_path: Path,
) -> None:
    from src.quality.inspector import inspect_render

    render_dir = tmp_path / "render"
    render_dir.mkdir()
    (render_dir / "output.mp4").write_bytes(b"fake mp4")
    _write_wav(render_dir / "audio" / "final_audio.wav", duration_sec=6.0)
    rendered_path = render_dir / "rendered.youtube.json"
    rendered_path.write_text(json.dumps(_rendered(render_dir)), encoding="utf-8")
    ffmpeg_path = render_dir / "ffmpeg.exe"
    ffmpeg_path.write_text("fake ffmpeg", encoding="utf-8")

    def fake_run(cmd, *, capture_output, check, text, **kwargs):
        Path(cmd[-1]).write_bytes(b"fake png")
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    report = inspect_render(rendered_path, ffmpeg_path=ffmpeg_path)

    assert report["render_id"] == "render_inspect"
    assert report["project_id"] == "inspect_project"
    assert len(report["screenshot_paths"]) == 3
    assert len(report["subtitle_frame_paths"]) == 2
    assert report["timeline_png_path"].endswith("timeline.png")
    assert (render_dir / "inspect" / "opening.png").is_file()
    assert (render_dir / "inspect" / "middle.png").is_file()
    assert (render_dir / "inspect" / "ending.png").is_file()
    assert (render_dir / "inspect" / "subtitle_001.png").is_file()
    assert (render_dir / "inspect" / "subtitle_002.png").is_file()
    assert (render_dir / "inspect" / "timeline.png").is_file()
    assert (render_dir / "inspect" / "timeline_parts" / "waveform.png").is_file()
    assert (render_dir / "inspect" / "timeline_parts" / "subtitles.png").is_file()
    written = json.loads((render_dir / "inspect" / "inspect_report.json").read_text())
    assert written == report


def test_evaluate_render_includes_existing_inspect_artifacts(tmp_path: Path) -> None:
    from src.quality.evaluator import evaluate_render

    render_dir = tmp_path / "render"
    (render_dir / "logs").mkdir(parents=True)
    (render_dir / "inspect").mkdir(parents=True)
    (render_dir / "output.mp4").write_bytes(b"fake mp4")
    (render_dir / "subtitle.ass").write_text("subtitle", encoding="utf-8")
    (render_dir / "description.txt").write_text("description", encoding="utf-8")
    (render_dir / "credits.txt").write_text("credits", encoding="utf-8")
    (render_dir / "logs" / "ffmpeg_command.txt").write_text("ffmpeg", encoding="utf-8")
    (render_dir / "logs" / "ffmpeg_stderr.log").write_text("", encoding="utf-8")
    (render_dir / "video.mp4").write_bytes(b"fake video")
    (render_dir / "inspect" / "opening.png").write_bytes(b"png")
    (render_dir / "inspect" / "middle.png").write_bytes(b"png")
    (render_dir / "inspect" / "ending.png").write_bytes(b"png")
    (render_dir / "inspect" / "subtitle_001.png").write_bytes(b"png")
    (render_dir / "inspect" / "timeline.png").write_bytes(b"png")
    _write_wav(render_dir / "audio" / "final_audio.wav")

    rendered = {
        "project_id": "inspect_project",
        "render_id": "render_inspect",
        "output": {
            "video_path": str(render_dir / "output.mp4"),
            "subtitle_ass_path": str(render_dir / "subtitle.ass"),
            "credits_path": str(render_dir / "credits.txt"),
            "description_path": str(render_dir / "description.txt"),
        },
        "target": {
            "actual_duration_sec": 1.0,
            "resolution": {"width": 1080, "height": 1920},
            "fps": 30,
        },
        "voice": {"sample_rate": 44100},
        "audio": {
            "final_audio_path": str(render_dir / "audio" / "final_audio.wav"),
            "narration_files": [],
        },
        "bgm": {"enabled": False},
        "visuals": [
            {
                "source": "local",
                "asset_id": "local_001",
                "local_file_path": str(render_dir / "video.mp4"),
                "original_width": 1080,
                "original_height": 1920,
            }
        ],
        "subtitles": {"items": [{"text": "短い字幕", "start_sec": 0.0, "end_sec": 1.0}]},
        "credits": {"items": []},
        "ffmpeg": {
            "command_log_path": str(render_dir / "logs" / "ffmpeg_command.txt"),
            "stderr_log_path": str(render_dir / "logs" / "ffmpeg_stderr.log"),
        },
        "manual_review": {"required": True},
    }
    rendered_path = render_dir / "rendered.youtube.json"
    rendered_path.write_text(json.dumps(rendered), encoding="utf-8")

    report = evaluate_render(
        rendered_path,
        video_probe=lambda _path: {
            "duration_sec": 1.0,
            "width": 1080,
            "height": 1920,
            "fps": 30.0,
        },
    )

    assert len(report["artifacts"]["screenshot_paths"]) == 3
    assert len(report["artifacts"]["subtitle_frame_paths"]) == 1
    assert report["artifacts"]["timeline_png_path"].endswith("timeline.png")


def test_timeline_sample_points_leave_margin_before_video_end() -> None:
    from src.quality.inspector import _timeline_sample_points

    duration_sec = 33.166
    points = _timeline_sample_points(duration_sec)

    assert points[-1] <= duration_sec - 0.5
