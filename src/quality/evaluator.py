from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.defaults import (
    MAX_BGM_VOLUME_DB,
    MAX_SUBTITLE_CHARS,
    MIN_SUBTITLE_DURATION_SEC,
    TARGET_HEIGHT,
    TARGET_WIDTH,
)
from src.errors import AppError
from src.validators.json_validator import load_json


def evaluate_render(rendered_path: Path) -> dict[str, Any]:
    rendered_path = rendered_path.resolve()
    if not rendered_path.is_file():
        raise AppError(
            "rendered JSON was not found.",
            location=str(rendered_path),
            next_step="Run render first, then pass the generated rendered.youtube.json.",
        )
    rendered = load_json(rendered_path)
    checks: list[dict[str, Any]] = []
    checks.extend(_file_checks(rendered))
    checks.extend(_credit_checks(rendered))
    checks.extend(_subtitle_checks(rendered))
    checks.extend(_bgm_checks(rendered))
    checks.extend(_manual_review_checks(rendered))
    metrics = _metrics(rendered)
    report = {
        "render_id": rendered["render_id"],
        "project_id": rendered["project_id"],
        "status": _status(checks),
        "checks": checks,
        "metrics": metrics,
    }
    report_path = rendered_path.parent / "quality_report.json"
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return report


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
            )
        )
    return checks


def _subtitle_checks(rendered: dict[str, Any]) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    for index, item in enumerate(rendered.get("subtitles", {}).get("items", [])):
        text = str(item.get("text") or "")
        if len(text) > MAX_SUBTITLE_CHARS:
            checks.append(
                _check(
                    "SUBTITLE_TOO_LONG",
                    "warning",
                    f"subtitles.items[{index}]",
                    f"字幕が{len(text)}文字で、推奨値{MAX_SUBTITLE_CHARS}文字を超えています。",
                    "字幕の自動改行、または文分割ロジックを追加してください。",
                )
            )
        duration = float(item["end_sec"]) - float(item["start_sec"])
        if duration < MIN_SUBTITLE_DURATION_SEC:
            checks.append(
                _check(
                    "SUBTITLE_TOO_SHORT",
                    "warning",
                    f"subtitles.items[{index}]",
                    f"字幕表示時間が{duration:.2f}秒で、推奨値{MIN_SUBTITLE_DURATION_SEC:.2f}秒未満です。",
                    "文の分割や読み上げ速度を調整してください。",
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
            )
        ]
    return []


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
        )
    ]


def _metrics(rendered: dict[str, Any]) -> dict[str, Any]:
    subtitles = rendered.get("subtitles", {}).get("items", [])
    subtitle_lengths = [len(str(item.get("text") or "")) for item in subtitles]
    subtitle_durations = [
        float(item["end_sec"]) - float(item["start_sec"]) for item in subtitles
    ]
    resolution = rendered["target"]["resolution"]
    return {
        "duration_sec": rendered["target"].get("actual_duration_sec"),
        "width": resolution["width"],
        "height": resolution["height"],
        "fps": rendered["target"].get("fps"),
        "subtitle_count": len(subtitles),
        "max_subtitle_chars": max(subtitle_lengths, default=0),
        "min_subtitle_duration_sec": min(subtitle_durations, default=None),
        "bgm_volume_db": rendered.get("bgm", {}).get("volume_db"),
        "has_bgm": bool(rendered.get("bgm", {}).get("enabled")),
        "has_pexels_visual": any(
            visual.get("source") == "pexels" for visual in rendered.get("visuals", [])
        ),
        "target_width": TARGET_WIDTH,
        "target_height": TARGET_HEIGHT,
    }


def _status(checks: list[dict[str, Any]]) -> str:
    levels = {check["level"] for check in checks}
    if "error" in levels:
        return "error"
    if "warning" in levels:
        return "warning"
    return "pass"


def _check(
    code: str, level: str, target: str, message: str, suggestion: str
) -> dict[str, Any]:
    return {
        "code": code,
        "level": level,
        "target": target,
        "message": message,
        "suggestion": suggestion,
    }


def _resolve_path(path_text: str) -> Path:
    path = Path(path_text)
    if path.is_absolute():
        return path
    return Path.cwd() / path
