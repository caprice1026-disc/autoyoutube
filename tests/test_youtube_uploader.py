from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.youtube.uploader import upload_private_video


class FakeInsertRequest:
    def __init__(self) -> None:
        self.calls = 0

    def next_chunk(self) -> tuple[None, dict[str, Any] | None]:
        self.calls += 1
        if self.calls == 1:
            return None, None
        return None, {"id": "abc123"}


class FakeVideosResource:
    def __init__(self) -> None:
        self.insert_kwargs: dict[str, Any] | None = None
        self.request = FakeInsertRequest()

    def insert(self, **kwargs: Any) -> FakeInsertRequest:
        self.insert_kwargs = kwargs
        return self.request


class FakeYoutubeService:
    def __init__(self) -> None:
        self.videos_resource = FakeVideosResource()

    def videos(self) -> FakeVideosResource:
        return self.videos_resource


def _write_render_files(tmp_path: Path) -> Path:
    render_dir = tmp_path / "render"
    render_dir.mkdir()
    (render_dir / "output.mp4").write_bytes(b"fake mp4")
    (render_dir / "description.txt").write_text("Description\n", encoding="utf-8")
    (render_dir / "credits.txt").write_text("Credits line\n", encoding="utf-8")
    (render_dir / "quality_report.json").write_text(
        json.dumps({"summary": {"error_count": 0}}), encoding="utf-8"
    )
    rendered = {
        "project_id": "sample",
        "output": {
            "video_path": str(render_dir / "output.mp4"),
            "description_path": str(render_dir / "description.txt"),
            "credits_path": str(render_dir / "credits.txt"),
        },
        "youtube": {
            "title": "Sample Title",
            "description": "Fallback description",
            "hashtags": [],
            "tags": ["sample"],
            "category_hint": "education",
            "privacy_status": "private",
            "made_for_kids": False,
            "contains_synthetic_voice": True,
            "upload": {"planned": False, "status": "not_uploaded"},
        },
        "manual_review": {
            "required": True,
            "checked": True,
            "publish_ready": True,
        },
    }
    rendered_path = render_dir / "rendered.youtube.json"
    rendered_path.write_text(json.dumps(rendered), encoding="utf-8")
    return rendered_path


def test_upload_private_video_calls_youtube_insert_and_updates_rendered_json(
    tmp_path: Path,
) -> None:
    rendered_path = _write_render_files(tmp_path)
    service = FakeYoutubeService()
    media_uploads: list[dict[str, Any]] = []

    def media_upload_factory(
        path: str, *, mimetype: str, resumable: bool
    ) -> dict[str, Any]:
        media = {"path": path, "mimetype": mimetype, "resumable": resumable}
        media_uploads.append(media)
        return media

    result = upload_private_video(
        rendered_path,
        youtube_service=service,
        media_upload_factory=media_upload_factory,
    )

    insert_kwargs = service.videos_resource.insert_kwargs
    assert insert_kwargs is not None
    assert insert_kwargs["part"] == "snippet,status"
    assert insert_kwargs["body"]["status"]["privacyStatus"] == "private"
    assert insert_kwargs["media_body"] == {
        "path": str(rendered_path.parent / "output.mp4"),
        "mimetype": "video/*",
        "resumable": True,
    }
    assert media_uploads[0]["path"] == str(rendered_path.parent / "output.mp4")
    assert result.video_id == "abc123"
    assert result.watch_url == "https://www.youtube.com/watch?v=abc123"
    updated = json.loads(rendered_path.read_text(encoding="utf-8"))
    assert updated["youtube"]["upload"]["status"] == "uploaded_private"
    assert updated["youtube"]["upload"]["youtube_video_id"] == "abc123"
    assert updated["youtube"]["upload"]["youtube_url"] == result.watch_url
    assert updated["youtube"]["upload"]["uploaded_at"].endswith("Z")
