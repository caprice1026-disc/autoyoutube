from __future__ import annotations

from pathlib import Path

from src.render.ffmpeg_renderer import (
    FfmpegRenderRequest,
    VisualSegment,
    build_concat_command,
    build_ffmpeg_command,
    build_segment_command,
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


def test_build_segment_command_crops_and_normalizes_visual_segment(tmp_path: Path) -> None:
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
    )
    segment = VisualSegment(
        index=1,
        input_path=tmp_path / "assets" / "clip.mp4",
        output_path=render_dir / "video_segments" / "segment_001.mp4",
        start_sec=0,
        duration_sec=3.2,
        used_start_sec=1.5,
    )

    command = build_segment_command(segment, request, Path("ffmpeg"))

    assert command[:8] == ["ffmpeg", "-y", "-stream_loop", "-1", "-ss", "1.500", "-i", str(segment.input_path)]
    assert "-t" in command
    assert command[command.index("-t") + 1] == "3.200"
    video_filter = command[command.index("-vf") + 1]
    assert "scale=1080:1920:force_original_aspect_ratio=increase" in video_filter
    assert "crop=1080:1920" in video_filter
    assert "fps=30" in video_filter
    assert "-an" in command
    assert command[-1] == "video_segments/segment_001.mp4"


def test_build_concat_command_uses_concat_demuxer(tmp_path: Path) -> None:
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
    )
    concat_list = render_dir / "video_segments" / "concat.txt"
    output = render_dir / "video" / "background_timeline.mp4"

    command = build_concat_command(concat_list, output, request, Path("ffmpeg"))

    assert command == [
        "ffmpeg",
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        "video_segments/concat.txt",
        "-c",
        "copy",
        "video/background_timeline.mp4",
    ]
