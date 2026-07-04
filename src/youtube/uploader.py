from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from src.errors import AppError
from src.youtube.auth import build_youtube_service
from src.youtube.metadata import load_upload_metadata

MediaUploadFactory = Callable[..., Any]


@dataclass(frozen=True)
class YoutubeUploadResult:
    video_id: str
    watch_url: str
    uploaded_at: str


def upload_private_video(
    rendered_path: Path,
    *,
    privacy_status: str = "private",
    youtube_service: Any | None = None,
    media_upload_factory: MediaUploadFactory | None = None,
) -> YoutubeUploadResult:
    metadata = load_upload_metadata(rendered_path, privacy_status=privacy_status)
    service = youtube_service or build_youtube_service()
    media_factory = media_upload_factory or _media_file_upload
    media_body = media_factory(
        str(metadata.video_path), mimetype="video/*", resumable=True
    )
    request = service.videos().insert(
        part="snippet,status",
        body=metadata.body,
        media_body=media_body,
    )
    response = _execute_upload(request)
    video_id = str(response.get("id") or "").strip()
    if not video_id:
        raise AppError(
            "YouTube upload did not return a video id.",
            details=json.dumps(response, ensure_ascii=False),
            next_step="Check the YouTube API response and retry the upload if needed.",
        )
    uploaded_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    result = YoutubeUploadResult(
        video_id=video_id,
        watch_url=f"https://www.youtube.com/watch?v={video_id}",
        uploaded_at=uploaded_at,
    )
    _mark_uploaded(metadata.rendered_path, result)
    return result


def _execute_upload(request: Any) -> dict[str, Any]:
    try:
        if hasattr(request, "next_chunk"):
            response = None
            while response is None:
                _, response = request.next_chunk()
            return dict(response)
        if hasattr(request, "execute"):
            return dict(request.execute())
    except Exception as exc:  # pragma: no cover - defensive API boundary.
        raise AppError(
            "YouTube upload failed.",
            details=str(exc),
            next_step="Check OAuth credentials, quota, and network connectivity before retrying.",
        ) from exc
    raise AppError(
        "YouTube upload request object is unsupported.",
        next_step="Use google-api-python-client or provide a compatible test double.",
    )


def _mark_uploaded(rendered_path: Path, result: YoutubeUploadResult) -> None:
    rendered = json.loads(rendered_path.read_text(encoding="utf-8"))
    upload = rendered.setdefault("youtube", {}).setdefault("upload", {})
    upload.update(
        {
            "planned": True,
            "status": "uploaded_private",
            "youtube_video_id": result.video_id,
            "youtube_url": result.watch_url,
            "uploaded_at": result.uploaded_at,
            "error_message": None,
        }
    )
    rendered_path.write_text(
        json.dumps(rendered, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def _media_file_upload(path: str, *, mimetype: str, resumable: bool) -> Any:
    try:
        from googleapiclient.http import MediaFileUpload
    except ImportError as exc:  # pragma: no cover - depends on optional package install.
        raise AppError(
            "Google API client dependencies are not installed.",
            details=str(exc),
            next_step="Install requirements.txt in the repository virtual environment.",
        ) from exc
    return MediaFileUpload(path, mimetype=mimetype, resumable=resumable)
