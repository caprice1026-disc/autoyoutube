from __future__ import annotations

import json
import math
import re
import shutil
import subprocess
import wave
from fractions import Fraction
from pathlib import Path
from typing import Any, Callable

from src.defaults import (
    AUDIO_CLIPPING_DBFS_THRESHOLD,
    MAX_BGM_VOLUME_DB,
    MAX_DURATION_DIFF_SEC,
    MAX_FINAL_AUDIO_DURATION_DIFF_SEC,
    MAX_SHORTS_DURATION_SEC,
    MAX_SUBTITLE_CHARS,
    MAX_SUBTITLE_CPS,
    MAX_SUBTITLE_LINES,
    MAX_VIDEO_FILE_SIZE_MB,
    MIN_SOURCE_SHORT_EDGE,
    MIN_SUBTITLE_DURATION_SEC,
    OPENING_SILENCE_SEC,
    SILENCE_DBFS_THRESHOLD,
    TARGET_HEIGHT,
    TARGET_WIDTH,
)
from src.errors import AppError
from src.validators.json_validator import load_json

VideoProbe = Callable[[Path], dict[str, Any]]


def evaluate_render(
    rendered_path: Path, *, video_probe: VideoProbe | None = None
) -> dict[str, Any]:
    rendered_path = rendered_path.resolve()
    if not rendered_path.is_file():
        raise AppError(
            "rendered JSON was not found.",
            location=str(rendered_path),
            next_step="Run render first, then pass the generated rendered.youtube.json.",
        )
    rendered = load_json(rendered_path)
    probe_result = _probe_output_video(rendered, video_probe or _ffprobe_video)
    audio_checks, audio_metrics = _audio_checks(rendered)
    checks: list[dict[str, Any]] = []
    checks.extend(_file_checks(rendered))
    checks.extend(_video_checks(rendered, probe_result))
    checks.extend(audio_checks)
    checks.extend(_credit_checks(rendered))
    checks.extend(_subtitle_checks(rendered))
    checks.extend(_bgm_checks(rendered))
    checks.extend(_ffmpeg_checks(rendered))
    checks.extend(_visual_checks(rendered))
    checks.extend(_manual_review_checks(rendered))
    metrics = _metrics(rendered, probe_result, audio_metrics)
    status = _status(checks)
    report = {
        "render_id": rendered["render_id"],
        "project_id": rendered["project_id"],
        "status": status,
        "summary": _summary(status, checks),
        "checks": checks,
        "metrics": metrics,
    }
    report_path = rendered_path.parent / "quality_report.json"
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return report


def _probe_output_video(
    rendered: dict[str, Any], video_probe: VideoProbe
) -> dict[str, Any]:
    output_path = _resolve_path(rendered["output"]["video_path"])
    if not output_path.is_file() or output_path.stat().st_size == 0:
        return {"skipped": True}
    try:
        result = dict(video_probe(output_path))
    except Exception as exc:  # pragma: no cover - defensive boundary for CLI use.
        return {
            "ok": False,
            "code": "FFPROBE_FAILED",
            "error": str(exc),
        }
    if "ok" not in result:
        result["ok"] = True
    return result


def _ffprobe_video(video_path: Path) -> dict[str, Any]:
    ffprobe_path = shutil.which("ffprobe")
    if not ffprobe_path:
        return {
            "ok": False,
            "code": "FFPROBE_NOT_AVAILABLE",
            "error": "ffprobe executable was not found in PATH.",
        }
    completed = subprocess.run(
        [
            ffprobe_path,
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=width,height,avg_frame_rate",
            "-show_entries",
            "format=duration",
            "-of",
            "json",
            str(video_path),
        ],
        capture_output=True,
        check=False,
        text=True,
    )
    if completed.returncode != 0:
        return {
            "ok": False,
            "code": "FFPROBE_FAILED",
            "error": completed.stderr.strip() or completed.stdout.strip(),
        }
    data = json.loads(completed.stdout)
    stream = (data.get("streams") or [{}])[0]
    return {
        "ok": True,
        "duration_sec": _float_or_none(data.get("format", {}).get("duration")),
        "width": _int_or_none(stream.get("width")),
        "height": _int_or_none(stream.get("height")),
        "fps": _parse_frame_rate(stream.get("avg_frame_rate")),
    }


def _file_checks(rendered: dict[str, Any]) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    required_paths = {
        "output.video_path": rendered["output"]["video_path"],
        "output.subtitle_ass_path": rendered["output"]["subtitle_ass_path"],
        "output.credits_path": rendered["output"]["credits_path"],
        "output.description_path": rendered["output"]["description_path"],
        "ffmpeg.command_log_path": rendered["ffmpeg"]["command_log_path"],
        "ffmpeg.stderr_log_path": rendered["ffmpeg"]["stderr_log_path"],
    }
    for target, path_text in required_paths.items():
        path = _resolve_path(path_text)
        if not path.is_file():
            checks.append(
                _check(
                    "FILE_MISSING",
                    "error",
                    target,
                    f"必須ファイルが存在しません: {path_text}",
                    "renderを再実行するか、rendered JSONのpathを修正してください。",
                )
            )
    output_path = _resolve_path(rendered["output"]["video_path"])
    if output_path.is_file() and output_path.stat().st_size == 0:
        checks.append(
            _check(
                "OUTPUT_VIDEO_EMPTY",
                "error",
                "output.video_path",
                "output.mp4 が0 byteです。",
                "FFmpeg stderr logを確認し、renderを再実行してください。",
            )
        )

    bgm = rendered.get("bgm", {})
    if bgm.get("enabled") and bgm.get("file_path"):
        bgm_path = _resolve_path(bgm["file_path"])
        if not bgm_path.is_file():
            checks.append(
                _check(
                    "BGM_FILE_MISSING",
                    "error",
                    "bgm.file_path",
                    f"BGMファイルが存在しません: {bgm['file_path']}",
                    "BGM manifestのfile_pathを確認し、import-bgmを再実行してください。",
                )
            )

    for index, visual in enumerate(rendered.get("visuals", [])):
        media_path = _resolve_path(visual["local_file_path"])
        if not media_path.is_file():
            checks.append(
                _check(
                    "MEDIA_FILE_MISSING",
                    "error",
                    f"visuals[{index}].local_file_path",
                    f"映像素材ファイルが存在しません: {visual['local_file_path']}",
                    "素材を再取得するか、media assetのlocal_file_pathを修正してください。",
                )
            )
    return checks


def _video_checks(
    rendered: dict[str, Any], probe_result: dict[str, Any]
) -> list[dict[str, Any]]:
    if probe_result.get("skipped"):
        return []
    if probe_result.get("ok") is False:
        code = str(probe_result.get("code") or "FFPROBE_FAILED")
        return [
            _check(
                code,
                "warning",
                "output.video_path",
                f"ffprobeで動画ファイルを検査できませんでした: {probe_result.get('error') or 'unknown error'}",
                "ffprobeがPATH上にあるか、output.mp4が正常なMP4か確認してください。",
            )
        ]

    checks: list[dict[str, Any]] = []
    resolution = rendered["target"]["resolution"]
    expected_width = int(resolution["width"])
    expected_height = int(resolution["height"])
    actual_width = probe_result.get("width")
    actual_height = probe_result.get("height")
    if actual_width != expected_width or actual_height != expected_height:
        checks.append(
            _check(
                "VIDEO_DIMENSION_INVALID",
                "error",
                "output.video_path",
                f"動画解像度が{actual_width}x{actual_height}で、期待値{expected_width}x{expected_height}と一致しません。",
                "FFmpegのscale/crop設定とtarget resolutionを確認してください。",
            )
        )

    rendered_duration = _float_or_none(rendered["target"].get("actual_duration_sec"))
    video_duration = _float_or_none(probe_result.get("duration_sec"))
    if rendered_duration is not None and video_duration is not None:
        diff = abs(video_duration - rendered_duration)
        if diff > MAX_DURATION_DIFF_SEC:
            checks.append(
                _check(
                    "VIDEO_DURATION_MISMATCH",
                    "warning",
                    "target.actual_duration_sec",
                    f"実MP4尺が{video_duration:.2f}秒で、rendered JSONの{rendered_duration:.2f}秒と{diff:.2f}秒ずれています。",
                    "FFmpeg出力のduration、音声/BGMの終端、rendered JSONのactual_duration_sec算出を確認してください。",
                    metrics={
                        "rendered_duration_sec": round(rendered_duration, 3),
                        "video_duration_sec": round(video_duration, 3),
                        "duration_diff_sec": round(diff, 3),
                    },
                    auto_fixable=True,
                    codex_hint="Constrain FFmpeg output duration or fix rendered target duration calculation.",
                )
            )

    duration_for_policy = (
        video_duration if video_duration is not None else rendered_duration
    )
    if (
        duration_for_policy is not None
        and duration_for_policy > MAX_SHORTS_DURATION_SEC
    ):
        checks.append(
            _check(
                "VIDEO_DURATION_TOO_LONG",
                "warning",
                "target.actual_duration_sec",
                f"動画尺が{duration_for_policy:.2f}秒で、Shorts向けMVP上限{MAX_SHORTS_DURATION_SEC:.1f}秒を超えています。",
                "台本を短くするか、読み上げ速度・文間を調整して60秒以内に収めてください。",
                metrics={
                    "duration_sec": round(duration_for_policy, 3),
                    "max_duration_sec": MAX_SHORTS_DURATION_SEC,
                },
                auto_fixable=True,
                codex_hint="Add a duration budget check before rendering or adjust project narration speed/script length.",
            )
        )

    output_path = _resolve_path(rendered["output"]["video_path"])
    if output_path.is_file():
        size_mb = output_path.stat().st_size / (1024 * 1024)
        if size_mb > MAX_VIDEO_FILE_SIZE_MB:
            checks.append(
                _check(
                    "VIDEO_FILE_TOO_LARGE",
                    "warning",
                    "output.video_path",
                    f"動画ファイルサイズが{size_mb:.1f}MBで、推奨上限{MAX_VIDEO_FILE_SIZE_MB}MBを超えています。",
                    "CRFやpreset、素材ビットレートを確認してください。",
                    metrics={"file_size_mb": round(size_mb, 3)},
                    auto_fixable=True,
                    codex_hint="Tune FFmpeg CRF/preset or bitrate settings for Shorts output.",
                )
            )
    return checks


def _audio_checks(
    rendered: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    metrics: dict[str, Any] = {}
    audio = rendered.get("audio", {})
    final_audio_path_text = audio.get("final_audio_path")
    if not final_audio_path_text:
        return checks, metrics

    final_audio_path = _resolve_path(str(final_audio_path_text))
    if not final_audio_path.is_file():
        checks.append(
            _check(
                "RENDERED_PATH_MISSING",
                "error",
                "audio.final_audio_path",
                f"rendered JSONのfinal_audio_pathが存在しません: {final_audio_path_text}",
                "renderを再実行するか、rendered JSONのaudio pathを修正してください。",
                auto_fixable=True,
                codex_hint="Ensure render_project writes final_audio.wav before rendered JSON is persisted.",
            )
        )
        return checks, metrics

    final_stats = _read_wav_stats(final_audio_path)
    if final_stats.get("ok") is False:
        checks.append(
            _check(
                "AUDIO_ANALYSIS_FAILED",
                "warning",
                "audio.final_audio_path",
                f"final_audio.wavを解析できませんでした: {final_stats.get('error')}",
                "WAV形式とファイル破損の有無を確認してください。",
                metrics={"path": str(final_audio_path)},
                codex_hint="Keep final audio as readable PCM WAV or add a decoder-backed analyzer.",
            )
        )
        return checks, metrics

    metrics.update(
        {
            "final_audio_duration_sec": final_stats["duration_sec"],
            "final_audio_sample_rate": final_stats["sample_rate"],
            "final_audio_rms_dbfs": final_stats["rms_dbfs"],
            "final_audio_peak_dbfs": final_stats["peak_dbfs"],
            "opening_audio_rms_dbfs": final_stats["opening_rms_dbfs"],
        }
    )

    opening_rms = final_stats["opening_rms_dbfs"]
    if opening_rms <= SILENCE_DBFS_THRESHOLD:
        checks.append(
            _check(
                "OPENING_NO_AUDIO",
                "warning",
                "audio.final_audio_path",
                f"冒頭{OPENING_SILENCE_SEC:.1f}秒の音声RMSが{opening_rms:.1f}dBFSで、無音に近いです。",
                "Shortsでは冒頭の無音を短くし、最初の発話やBGM開始を前倒ししてください。",
                metrics={
                    "opening_rms_dbfs": opening_rms,
                    "threshold_dbfs": SILENCE_DBFS_THRESHOLD,
                    "window_sec": OPENING_SILENCE_SEC,
                },
                auto_fixable=True,
                codex_hint="Trim leading silence from narration or adjust audio merge timing.",
            )
        )

    peak_dbfs = final_stats["peak_dbfs"]
    if peak_dbfs >= AUDIO_CLIPPING_DBFS_THRESHOLD:
        checks.append(
            _check(
                "AUDIO_CLIPPING",
                "warning",
                "audio.final_audio_path",
                f"final_audio.wavのピークが{peak_dbfs:.2f}dBFSで、音割れに近いです。",
                "音声合成後のゲインを下げるか、正規化処理を追加してください。",
                metrics={
                    "peak_dbfs": peak_dbfs,
                    "threshold_dbfs": AUDIO_CLIPPING_DBFS_THRESHOLD,
                },
                auto_fixable=True,
                codex_hint="Add peak normalization or lower narration gain before final audio is rendered.",
            )
        )

    rendered_duration = _float_or_none(rendered["target"].get("actual_duration_sec"))
    if rendered_duration is not None:
        diff = abs(final_stats["duration_sec"] - rendered_duration)
        if diff > MAX_FINAL_AUDIO_DURATION_DIFF_SEC:
            checks.append(
                _check(
                    "FINAL_AUDIO_DURATION_MISMATCH",
                    "warning",
                    "audio.final_audio_path",
                    f"final_audio.wavが{final_stats['duration_sec']:.2f}秒で、rendered JSONの尺{rendered_duration:.2f}秒と{diff:.2f}秒ずれています。",
                    "音声結合処理とrendered target durationの算出を確認してください。",
                    metrics={
                        "final_audio_duration_sec": final_stats["duration_sec"],
                        "rendered_duration_sec": round(rendered_duration, 3),
                        "duration_diff_sec": round(diff, 3),
                    },
                    auto_fixable=True,
                    codex_hint="Use measured final_audio.wav duration as the source of truth for rendered target duration.",
                )
            )

    expected_sample_rate = _int_or_none(rendered.get("voice", {}).get("sample_rate"))
    final_sample_rate = _int_or_none(final_stats.get("sample_rate"))
    if (
        expected_sample_rate is not None
        and final_sample_rate is not None
        and final_sample_rate != expected_sample_rate
    ):
        checks.append(
            _check(
                "AUDIO_SAMPLE_RATE_MISMATCH",
                "warning",
                "audio.final_audio_path",
                f"final_audio.wavのsample rateが{final_sample_rate}Hzで、rendered voiceの{expected_sample_rate}Hzと一致しません。",
                "音声生成と結合処理のsample rateを統一してください。",
                metrics={
                    "expected_sample_rate": expected_sample_rate,
                    "actual_sample_rate": final_sample_rate,
                },
                auto_fixable=True,
                codex_hint="Resample sentence WAVs to a single project sample rate before merging.",
            )
        )

    for index, item in enumerate(audio.get("narration_files", [])):
        path_text = item.get("path")
        if not path_text:
            continue
        wav_path = _resolve_path(str(path_text))
        if not wav_path.is_file():
            continue
        sentence_stats = _read_wav_stats(wav_path, opening_sec=0.0)
        sample_rate = _int_or_none(sentence_stats.get("sample_rate"))
        if (
            sentence_stats.get("ok") is not False
            and sample_rate is not None
            and final_sample_rate is not None
            and sample_rate != final_sample_rate
        ):
            checks.append(
                _check(
                    "AUDIO_SAMPLE_RATE_MISMATCH",
                    "warning",
                    f"audio.narration_files[{index}].path",
                    f"文単位WAVのsample rateが{sample_rate}Hzで、final_audio.wavの{final_sample_rate}Hzと一致しません。",
                    "文単位WAVを結合前に同一sample rateへ揃えてください。",
                    metrics={
                        "sentence_sample_rate": sample_rate,
                        "final_audio_sample_rate": final_sample_rate,
                    },
                    auto_fixable=True,
                    codex_hint="Normalize all generated sentence WAV sample rates before merge_wav_files.",
                )
            )
    return checks, metrics


def _credit_checks(rendered: dict[str, Any]) -> list[dict[str, Any]]:
    items = rendered.get("credits", {}).get("items", [])
    checks: list[dict[str, Any]] = []
    if rendered.get("bgm", {}).get("enabled") and not any(
        item.get("credit_type") == "bgm" for item in items
    ):
        checks.append(
            _check(
                "BGM_CREDIT_MISSING",
                "error",
                "credits.items",
                "BGMが使用されていますが、bgm creditがありません。",
                "credits.items に credit_type=bgm の項目を追加してください。",
                auto_fixable=True,
                codex_hint="Generate a bgm credit item when rendered.bgm.enabled is true.",
            )
        )
    has_pexels = any(
        visual.get("source") == "pexels" for visual in rendered.get("visuals", [])
    )
    if has_pexels and not any(
        item.get("credit_type") == "video" and item.get("source") == "pexels"
        for item in items
    ):
        checks.append(
            _check(
                "PEXELS_CREDIT_MISSING",
                "error",
                "credits.items",
                "Pexels素材が使用されていますが、video creditがありません。",
                "Pexels visualから video credit を生成してください。",
                auto_fixable=True,
                codex_hint="Create deduplicated credit_type=video items from rendered.visuals where source is pexels.",
            )
        )
    return checks


def _subtitle_checks(rendered: dict[str, Any]) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    for index, item in enumerate(rendered.get("subtitles", {}).get("items", [])):
        text = str(item.get("text") or "")
        lines = _subtitle_lines(text)
        max_line_chars = _max_subtitle_line_chars(text)
        if max_line_chars > MAX_SUBTITLE_CHARS:
            checks.append(
                _check(
                    "SUBTITLE_TOO_LONG",
                    "warning",
                    f"subtitles.items[{index}]",
                    f"字幕1行が{max_line_chars}文字で、推奨値{MAX_SUBTITLE_CHARS}文字を超えています。",
                    "字幕の自動改行、または文分割ロジックを追加してください。",
                    metrics={
                        "max_line_chars": max_line_chars,
                        "max_allowed_chars": MAX_SUBTITLE_CHARS,
                    },
                    auto_fixable=True,
                    codex_hint="Wrap subtitle text with ASS \\N or split long script items.",
                )
            )
        if len(lines) > MAX_SUBTITLE_LINES:
            checks.append(
                _check(
                    "SUBTITLE_TOO_MANY_LINES",
                    "warning",
                    f"subtitles.items[{index}]",
                    f"字幕が{len(lines)}行で、推奨上限{MAX_SUBTITLE_LINES}行を超えています。",
                    "字幕の文分割や短文化を検討してください。",
                    metrics={
                        "line_count": len(lines),
                        "max_allowed_lines": MAX_SUBTITLE_LINES,
                    },
                    auto_fixable=True,
                    codex_hint="Split dense subtitles into shorter script items or reduce wrapping pressure.",
                )
            )
        duration = float(item["end_sec"]) - float(item["start_sec"])
        cps = _subtitle_cps(text, duration)
        if cps > MAX_SUBTITLE_CPS:
            checks.append(
                _check(
                    "SUBTITLE_CPS_TOO_HIGH",
                    "warning",
                    f"subtitles.items[{index}]",
                    f"字幕の読み速度が{cps:.1f}文字/秒で、推奨上限{MAX_SUBTITLE_CPS:.1f}を超えています。",
                    "台詞を分割するか、字幕表示時間を延ばしてください。",
                    metrics={
                        "chars": _subtitle_reading_chars(text),
                        "duration_sec": round(duration, 3),
                        "chars_per_sec": round(cps, 3),
                        "max_allowed_cps": MAX_SUBTITLE_CPS,
                    },
                    auto_fixable=True,
                    codex_hint="Split this script item or adjust timing so Japanese subtitle CPS stays under the threshold.",
                )
            )
        if duration < MIN_SUBTITLE_DURATION_SEC:
            checks.append(
                _check(
                    "SUBTITLE_TOO_SHORT",
                    "warning",
                    f"subtitles.items[{index}]",
                    f"字幕表示時間が{duration:.2f}秒で、推奨値{MIN_SUBTITLE_DURATION_SEC:.2f}秒未満です。",
                    "文の分割や読み上げ速度を調整してください。",
                    metrics={
                        "duration_sec": round(duration, 3),
                        "min_duration_sec": MIN_SUBTITLE_DURATION_SEC,
                    },
                    auto_fixable=True,
                    codex_hint="Avoid very short subtitle windows or merge ultra-short script items with adjacent lines.",
                )
            )
    return checks


def _bgm_checks(rendered: dict[str, Any]) -> list[dict[str, Any]]:
    bgm = rendered.get("bgm", {})
    if not bgm.get("enabled"):
        return []
    volume_db = bgm.get("volume_db")
    if volume_db is not None and float(volume_db) > MAX_BGM_VOLUME_DB:
        return [
            _check(
                "BGM_TOO_LOUD",
                "warning",
                "bgm.volume_db",
                f"BGM音量が{volume_db}dBで、推奨上限{MAX_BGM_VOLUME_DB}dBより大きいです。",
                "ナレーションを優先し、volume_dbを下げてください。",
                metrics={
                    "volume_db": float(volume_db),
                    "max_allowed_volume_db": MAX_BGM_VOLUME_DB,
                },
                auto_fixable=True,
                codex_hint="Lower project.bgm.volume_db or default BGM volume.",
            )
        ]
    return []


def _ffmpeg_checks(rendered: dict[str, Any]) -> list[dict[str, Any]]:
    stderr_path = _resolve_path(rendered["ffmpeg"]["stderr_log_path"])
    if not stderr_path.is_file():
        return []
    stderr = stderr_path.read_text(encoding="utf-8", errors="replace")
    stderr_lower = stderr.lower()
    checks: list[dict[str, Any]] = []
    warning_patterns = ["warning", "deprecated", "non-monotonous"]
    matched_warnings = [
        pattern for pattern in warning_patterns if pattern in stderr_lower
    ]
    if matched_warnings:
        checks.append(
            _check(
                "FFMPEG_WARNING_DETECTED",
                "warning",
                "ffmpeg.stderr_log_path",
                f"FFmpeg stderrに注意語が含まれています: {', '.join(matched_warnings)}",
                "ffmpeg_stderr.logを確認し、生成品質に影響するwarningか判断してください。",
                metrics={"patterns": matched_warnings},
                codex_hint="Inspect ffmpeg stderr and add targeted handling for recurring warnings.",
            )
        )

    font_name = str(
        rendered.get("subtitles", {}).get("style", {}).get("font_name") or ""
    )
    fallback_lines = _font_fallback_lines(stderr, font_name)
    if fallback_lines:
        checks.append(
            _check(
                "FONT_FALLBACK_DETECTED",
                "warning",
                "subtitles.style.font_name",
                f"指定字幕フォント '{font_name}' がFFmpeg/ASSで別フォントへfallbackしている可能性があります。",
                "OSに存在する日本語フォントへ変更するか、フォントファイルを明示指定してください。",
                metrics={"lines": fallback_lines[:3]},
                auto_fixable=True,
                codex_hint="Change the default ASS font to an installed Japanese font or bundle a font file.",
            )
        )
    return checks


def _visual_checks(rendered: dict[str, Any]) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    visuals = rendered.get("visuals", [])
    previous_asset_id: str | None = None
    for index, visual in enumerate(visuals):
        width = _int_or_none(visual.get("original_width"))
        height = _int_or_none(visual.get("original_height"))
        if (
            width is not None
            and height is not None
            and min(width, height) < MIN_SOURCE_SHORT_EDGE
        ):
            checks.append(
                _check(
                    "SOURCE_RESOLUTION_TOO_LOW",
                    "warning",
                    f"visuals[{index}]",
                    f"素材の短辺が{min(width, height)}pxで、推奨下限{MIN_SOURCE_SHORT_EDGE}px未満です。",
                    "より高解像度の素材を取得するか、別素材へ差し替えてください。",
                    metrics={
                        "original_width": width,
                        "original_height": height,
                        "min_short_edge": MIN_SOURCE_SHORT_EDGE,
                    },
                    auto_fixable=True,
                    codex_hint="Prefer higher-resolution cached media assets during selection.",
                )
            )
        asset_id = visual.get("asset_id")
        if asset_id and previous_asset_id == asset_id:
            checks.append(
                _check(
                    "SAME_ASSET_CONSECUTIVE",
                    "warning",
                    f"visuals[{index}]",
                    f"同じ素材asset_id={asset_id}が連続で使われています。",
                    "文ごとの素材選定で直前素材を避けるか、候補素材を追加してください。",
                    metrics={"asset_id": asset_id, "previous_index": index - 1},
                    auto_fixable=True,
                    codex_hint="Update media selection to avoid immediately reusing the same asset when alternatives exist.",
                )
            )
        previous_asset_id = str(asset_id) if asset_id else None
    return checks


def _manual_review_checks(rendered: dict[str, Any]) -> list[dict[str, Any]]:
    if rendered.get("manual_review", {}).get("required") is True:
        return []
    return [
        _check(
            "MANUAL_REVIEW_DISABLED",
            "error",
            "manual_review.required",
            "manual_review.required が true ではありません。",
            "投稿前の人間レビューを必須にしてください。",
            auto_fixable=True,
            codex_hint="Keep manual_review.required true until explicit human review is recorded.",
        )
    ]


def _metrics(
    rendered: dict[str, Any],
    probe_result: dict[str, Any],
    audio_metrics: dict[str, Any],
) -> dict[str, Any]:
    subtitles = rendered.get("subtitles", {}).get("items", [])
    subtitle_lengths = [
        _max_subtitle_line_chars(str(item.get("text") or "")) for item in subtitles
    ]
    subtitle_line_counts = [
        len(_subtitle_lines(str(item.get("text") or ""))) for item in subtitles
    ]
    subtitle_durations = [
        float(item["end_sec"]) - float(item["start_sec"]) for item in subtitles
    ]
    subtitle_cps = [
        _subtitle_cps(
            str(item.get("text") or ""),
            float(item["end_sec"]) - float(item["start_sec"]),
        )
        for item in subtitles
    ]
    resolution = rendered["target"]["resolution"]
    rendered_duration = _float_or_none(rendered["target"].get("actual_duration_sec"))
    video_duration = _float_or_none(probe_result.get("duration_sec"))
    metrics = {
        "duration_sec": rendered_duration,
        "rendered_duration_sec": rendered_duration,
        "width": resolution["width"],
        "height": resolution["height"],
        "fps": rendered["target"].get("fps"),
        "subtitle_count": len(subtitles),
        "max_subtitle_chars": max(subtitle_lengths, default=0),
        "max_subtitle_lines": max(subtitle_line_counts, default=0),
        "max_subtitle_cps": round(max(subtitle_cps, default=0.0), 3),
        "min_subtitle_duration_sec": min(subtitle_durations, default=None),
        "bgm_volume_db": rendered.get("bgm", {}).get("volume_db"),
        "has_bgm": bool(rendered.get("bgm", {}).get("enabled")),
        "has_pexels_visual": any(
            visual.get("source") == "pexels" for visual in rendered.get("visuals", [])
        ),
        "target_width": TARGET_WIDTH,
        "target_height": TARGET_HEIGHT,
    }
    metrics.update(audio_metrics)
    if not probe_result.get("skipped"):
        metrics.update(
            {
                "video_duration_sec": video_duration,
                "video_width": probe_result.get("width"),
                "video_height": probe_result.get("height"),
                "video_fps": probe_result.get("fps"),
            }
        )
        if rendered_duration is not None and video_duration is not None:
            metrics["duration_diff_sec"] = round(
                abs(video_duration - rendered_duration), 3
            )
    return metrics


def _summary(status: str, checks: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "status": status,
        "error_count": sum(1 for check in checks if check["level"] == "error"),
        "warning_count": sum(1 for check in checks if check["level"] == "warning"),
        "info_count": sum(1 for check in checks if check["level"] == "info"),
    }


def _status(checks: list[dict[str, Any]]) -> str:
    levels = {check["level"] for check in checks}
    if "error" in levels:
        return "error"
    if "warning" in levels:
        return "warning"
    return "pass"


def _check(
    code: str,
    level: str,
    target: str,
    message: str,
    suggestion: str,
    *,
    metrics: dict[str, Any] | None = None,
    auto_fixable: bool = False,
    codex_hint: str = "",
) -> dict[str, Any]:
    check = {
        "code": code,
        "level": level,
        "target": target,
        "message": message,
        "suggestion": suggestion,
        "auto_fixable": auto_fixable,
        "codex_hint": codex_hint,
    }
    if metrics is not None:
        check["metrics"] = metrics
    return check


def _resolve_path(path_text: str) -> Path:
    path = Path(path_text)
    if path.is_absolute():
        return path
    return Path.cwd() / path


def _max_subtitle_line_chars(text: str) -> int:
    lines = _subtitle_lines(text)
    return max((len(line) for line in lines), default=0)


def _subtitle_lines(text: str) -> list[str]:
    return [line for line in text.replace(r"\N", "\n").splitlines() if line]


def _subtitle_reading_chars(text: str) -> int:
    return len("".join(_subtitle_lines(text)))


def _subtitle_cps(text: str, duration: float) -> float:
    if duration <= 0:
        return 0.0
    return round(_subtitle_reading_chars(text) / duration, 3)


def _read_wav_stats(
    path: Path, opening_sec: float = OPENING_SILENCE_SEC
) -> dict[str, Any]:
    try:
        with wave.open(str(path), "rb") as wav:
            channels = wav.getnchannels()
            sample_width = wav.getsampwidth()
            sample_rate = wav.getframerate()
            frame_count = wav.getnframes()
            raw = wav.readframes(frame_count)
    except (OSError, wave.Error) as exc:
        return {"ok": False, "error": str(exc)}

    if sample_width != 2:
        return {
            "ok": False,
            "error": f"unsupported sample width: {sample_width}",
        }
    samples = [
        int.from_bytes(raw[index : index + sample_width], "little", signed=True)
        for index in range(0, len(raw), sample_width)
    ]
    max_value = float(2 ** (sample_width * 8 - 1) - 1)
    peak = max((abs(sample) for sample in samples), default=0)
    rms = _rms(samples)
    opening_sample_count = (
        len(samples)
        if opening_sec <= 0
        else min(len(samples), int(opening_sec * sample_rate) * max(channels, 1))
    )
    opening_rms = _rms(samples[:opening_sample_count])
    return {
        "ok": True,
        "duration_sec": round(frame_count / sample_rate, 3) if sample_rate else 0.0,
        "sample_rate": sample_rate,
        "channels": channels,
        "peak_dbfs": _dbfs(peak, max_value),
        "rms_dbfs": _dbfs(rms, max_value),
        "opening_rms_dbfs": _dbfs(opening_rms, max_value),
    }


def _rms(samples: list[int]) -> float:
    if not samples:
        return 0.0
    return math.sqrt(sum(sample * sample for sample in samples) / len(samples))


def _dbfs(value: float, max_value: float) -> float:
    if value <= 0 or max_value <= 0:
        return -120.0
    return round(min(0.0, 20 * math.log10(value / max_value)), 3)


def _font_fallback_lines(stderr: str, font_name: str) -> list[str]:
    if not font_name:
        return []
    requested = _normalize_font_name(font_name)
    lines: list[str] = []
    for line in stderr.splitlines():
        lower = line.lower()
        if "glyph" in lower and "not found" in lower:
            lines.append(line)
            continue
        if "fontselect:" not in lower or "->" not in line:
            continue
        before, after = line.split("->", 1)
        if requested in _normalize_font_name(
            before
        ) and requested not in _normalize_font_name(after):
            lines.append(line)
    return lines


def _normalize_font_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def _float_or_none(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _int_or_none(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _parse_frame_rate(value: Any) -> float | None:
    if value in (None, "", "0/0"):
        return None
    try:
        return float(Fraction(str(value)))
    except (ValueError, ZeroDivisionError):
        return _float_or_none(value)
