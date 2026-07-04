from __future__ import annotations

from pathlib import Path

from src.render.ffmpeg_renderer import (
    FfmpegRenderRequest,
    FfmpegVideoSegment,
    _visual_background_segments,
    build_ffmpeg_command,
)


def test_build_ffmpeg_command_uses_vertical_canvas_audio_subtitles_and_mp4(
    tmp_path: Path,
) -> None:
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
    assert command[-11:] == [
        "-t",
        "4.900",
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-r",
        "30",
        "-c:a",
        "aac",
        "output.mp4",
    ]


def test_build_ffmpeg_command_can_mix_bgm(tmp_path: Path) -> None:
    render_dir = tmp_path / "render"
    request = FfmpegRenderRequest(
        render_dir=render_dir,
        duration_sec=10,
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
        bgm_path=tmp_path / "bgm" / "mystery.wav",
        bgm_volume_db=-26,
        bgm_fade_in_sec=0.5,
        bgm_fade_out_sec=1.2,
    )

    command = build_ffmpeg_command(request, Path("ffmpeg"))

    assert "-stream_loop" in command
    assert str(tmp_path / "bgm" / "mystery.wav").replace("\\", "/") in command
    assert "-filter_complex" in command
    filter_complex = command[command.index("-filter_complex") + 1]
    assert "volume=0.050119" in filter_complex
    assert "afade=t=in:st=0:d=0.500" in filter_complex
    assert "afade=t=out:st=8.800:d=1.200" in filter_complex
    assert "amix=inputs=2:duration=first" in filter_complex
    assert command[-16:] == [
        "-shortest",
        "-t",
        "10.000",
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-r",
        "30",
        "-c:a",
        "aac",
        "-map",
        "0:v",
        "-map",
        "[aout]",
        "output.mp4",
    ]


def test_build_ffmpeg_command_can_use_background_video(tmp_path: Path) -> None:
    render_dir = tmp_path / "render"
    background_path = tmp_path / "assets" / "ocean.mp4"
    request = FfmpegRenderRequest(
        render_dir=render_dir,
        duration_sec=10,
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
        background_video_path=background_path,
    )

    command = build_ffmpeg_command(request, Path("ffmpeg"))

    assert "color=c=0x07111f:s=1080x1920:r=30:d=10.000" not in command
    assert command[:6] == [
        "ffmpeg",
        "-y",
        "-stream_loop",
        "-1",
        "-i",
        background_path.as_posix(),
    ]
    video_filter = command[command.index("-vf") + 1]
    assert "scale=1080:1920:force_original_aspect_ratio=increase" in video_filter
    assert "crop=1080:1920" in video_filter
    assert "subtitles=subtitle.ass" in video_filter


def test_build_ffmpeg_command_concatenates_background_video_segments(
    tmp_path: Path,
) -> None:
    render_dir = tmp_path / "render"
    first_path = tmp_path / "assets" / "street.mp4"
    second_path = tmp_path / "assets" / "lights.mp4"
    request = FfmpegRenderRequest(
        render_dir=render_dir,
        duration_sec=5.0,
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
        background_video_segments=[
            FfmpegVideoSegment(path=first_path, duration_sec=2.0),
            FfmpegVideoSegment(path=second_path, duration_sec=3.0),
        ],
    )

    command = build_ffmpeg_command(request, Path("ffmpeg"))

    assert command.count("-stream_loop") == 2
    assert first_path.as_posix() in command
    assert second_path.as_posix() in command
    assert "-vf" not in command
    assert "-filter_complex" in command
    filter_complex = command[command.index("-filter_complex") + 1]
    assert "trim=duration=2.000,setpts=PTS-STARTPTS" in filter_complex
    assert "trim=duration=3.000,setpts=PTS-STARTPTS" in filter_complex
    assert "concat=n=2:v=1:a=0[vcat]" in filter_complex
    assert "subtitles=subtitle.ass[vout]" in filter_complex
    assert command[-16:] == [
        "-shortest",
        "-t",
        "5.000",
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-r",
        "30",
        "-c:a",
        "aac",
        "-map",
        "[vout]",
        "-map",
        "2:a",
        "output.mp4",
    ]


def test_visual_background_segments_include_gap_until_next_visual(
    tmp_path: Path,
) -> None:
    first_path = tmp_path / "street.mp4"
    second_path = tmp_path / "lights.mp4"
    first_path.write_bytes(b"first")
    second_path.write_bytes(b"second")
    visuals = [
        {
            "asset_id": "street",
            "local_file_path": str(first_path),
            "video_start_sec": 0.0,
            "video_end_sec": 1.0,
            "used_duration_sec": 1.0,
        },
        {
            "asset_id": "lights",
            "local_file_path": str(second_path),
            "video_start_sec": 1.4,
            "video_end_sec": 3.0,
            "used_duration_sec": 1.6,
        },
    ]

    segments = _visual_background_segments(visuals)

    assert segments == [
        FfmpegVideoSegment(path=first_path, duration_sec=1.4),
        FfmpegVideoSegment(path=second_path, duration_sec=1.6),
    ]
