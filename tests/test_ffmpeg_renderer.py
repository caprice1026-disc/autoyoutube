from __future__ import annotations

from pathlib import Path

from src.render.ffmpeg_renderer import FfmpegRenderRequest, build_ffmpeg_command


def test_build_ffmpeg_command_uses_vertical_canvas_audio_subtitles_and_mp4(tmp_path: Path) -> None:
    render_dir = tmp_path / "render"
    request = FfmpegRenderRequest(
        render_dir=render_dir,
        duration_sec=4.9,
        width=1080,
        height=1920,
        fps=30,
        audio_path=render_dir / "audio" / "final_audio.wav",
        subtitle_path=render_dir / "subtitle.ass",
        output_path=render_dir / "output.mp4",
        logs_dir=render_dir / "logs",
        video_codec="libx264",
        audio_codec="aac",
        pix_fmt="yuv420p",
    )

    command = build_ffmpeg_command(request, Path("ffmpeg"))

    assert command[:2] == ["ffmpeg", "-y"]
    assert "color=c=0x07111f:s=1080x1920:r=30:d=4.900" in command
    assert "audio/final_audio.wav" in command
    assert "subtitles=subtitle.ass" in command
    assert command[-9:] == ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", "30", "-c:a", "aac", "output.mp4"]
