from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.errors import AppError
from src.validators.json_validator import load_json


@dataclass(frozen=True)
class YoutubeUploadMetadata:
    rendered_path: Path
    video_path: Path
    body: dict[str, Any]


def load_upload_metadata(
    rendered_path: Path, *, privacy_status: str = "private"
) -> YoutubeUploadMetadata:
    if privacy_status != "private":
        raise AppError(
            "Only private YouTube uploads are supported.",
            details=f"Requested privacy: {privacy_status}",
            next_step="Run upload-youtube without --privacy or set --privacy private.",
        )

    rendered_path = rendered_path.resolve()
    rendered = load_json(rendered_path)
    output = rendered["output"]
    video_path = _resolve_render_file(output["video_path"], rendered_path)
    description_path = _resolve_render_file(output["description_path"], rendered_path)
    credits_path = _resolve_render_file(output["credits_path"], rendered_path)
    _validate_upload_preconditions(
        rendered_path, video_path, description_path, credits_path
    )
    youtube = rendered["youtube"]
    description = _description_with_credits(description_path, credits_path)
    body = {
        "snippet": {
            "title": str(youtube["title"]),
            "description": description,
            "tags": [str(tag) for tag in youtube.get("tags", [])],
            "categoryId": _category_id(str(youtube.get("category_hint") or "")),
        },
        "status": {
            "privacyStatus": "private",
            "selfDeclaredMadeForKids": bool(youtube.get("made_for_kids", False)),
            "containsSyntheticMedia": bool(
                youtube.get("contains_synthetic_voice", False)
            ),
        },
    }
    return YoutubeUploadMetadata(
        rendered_path=rendered_path,
        video_path=video_path,
        body=body,
    )


def _validate_upload_preconditions(
    rendered_path: Path,
    video_path: Path,
    description_path: Path,
    credits_path: Path,
) -> None:
    if not video_path.is_file() or video_path.stat().st_size == 0:
        raise AppError(
            "Output video is missing or empty.",
            location=str(video_path),
            next_step="Run render again and confirm output.mp4 exists.",
        )
    for path in [description_path, credits_path]:
        if not path.is_file():
            raise AppError(
                "Required upload metadata file is missing.",
                location=str(path),
                next_step="Run render again and confirm description.txt and credits.txt exist.",
            )

    quality_report_path = rendered_path.parent / "quality_report.json"
    if not quality_report_path.is_file():
        raise AppError(
            "quality_report.json was not found.",
            location=str(quality_report_path),
            next_step="Run evaluate-render before uploading to YouTube.",
        )
    quality_report = json.loads(quality_report_path.read_text(encoding="utf-8"))
    error_count = int(quality_report.get("summary", {}).get("error_count", 0))
    if error_count != 0:
        raise AppError(
            "quality_report.json has errors.",
            location=str(quality_report_path),
            details=f"error_count={error_count}",
            next_step="Fix quality_report errors and run evaluate-render again.",
        )


def _description_with_credits(description_path: Path, credits_path: Path) -> str:
    description = description_path.read_text(encoding="utf-8").strip()
    credits = credits_path.read_text(encoding="utf-8").strip()
    if not credits:
        return description + "\n"
    return f"{description}\n\nCredits:\n{credits}\n"


def _category_id(category_hint: str) -> str:
    normalized = category_hint.strip().lower().replace("-", "_").replace(" ", "_")
    categories = {
        "education": "27",
        "educational": "27",
        "science": "28",
        "science_technology": "28",
        "science_and_technology": "28",
        "entertainment": "24",
        "people": "22",
        "people_blogs": "22",
    }
    return categories.get(normalized, "27")


def _resolve_path(path_text: str) -> Path:
    path = Path(path_text)
    if path.is_absolute():
        return path
    return Path.cwd() / path


def _resolve_render_file(path_text: str, rendered_path: Path) -> Path:
    path = _resolve_path(path_text)
    if path.exists():
        return path
    sibling = rendered_path.parent / Path(path_text).name
    if sibling.exists():
        return sibling
    return path
