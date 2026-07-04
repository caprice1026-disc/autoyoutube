from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.errors import AppError
from src.youtube.metadata import load_upload_metadata


def _write_render_files(
    tmp_path: Path,
    *,
    manual_checked: bool = True,
    quality_error_count: int = 0,
    stale_output_paths: bool = False,
) -> Path:
    render_dir = tmp_path / "render"
    render_dir.mkdir()
    (render_dir / "output.mp4").write_bytes(b"fake mp4")
    (render_dir / "description.txt").write_text(
        "Main description\n#Shorts\n", encoding="utf-8"
    )
    (render_dir / "credits.txt").write_text("Music: Test Track\n", encoding="utf-8")
    (render_dir / "quality_report.json").write_text(
        json.dumps({"summary": {"error_count": quality_error_count}}),
        encoding="utf-8",
    )
    output_dir = tmp_path / "render #Shorts" if stale_output_paths else render_dir
    rendered = {
        "project_id": "sample",
        "output": {
            "video_path": str(output_dir / "output.mp4"),
            "description_path": str(output_dir / "description.txt"),
            "credits_path": str(output_dir / "credits.txt"),
        },
        "youtube": {
            "title": "Sample Title #Shorts",
            "description": "Fallback description",
            "hashtags": ["#Shorts"],
            "tags": ["sample", "trivia"],
            "category_hint": "education",
            "privacy_status": "private",
            "made_for_kids": False,
            "contains_synthetic_voice": True,
            "upload": {"planned": False, "status": "not_uploaded"},
        },
        "manual_review": {
            "required": True,
            "checked": manual_checked,
            "publish_ready": manual_checked,
        },
    }
    rendered_path = render_dir / "rendered.youtube.json"
    rendered_path.write_text(json.dumps(rendered), encoding="utf-8")
    return rendered_path


def test_load_upload_metadata_builds_private_video_insert_body(tmp_path: Path) -> None:
    rendered_path = _write_render_files(tmp_path)

    metadata = load_upload_metadata(rendered_path, privacy_status="private")

    assert metadata.video_path == rendered_path.parent / "output.mp4"
    assert metadata.body == {
        "snippet": {
            "title": "Sample Title #Shorts",
            "description": "Main description\n#Shorts\n\nCredits:\nMusic: Test Track\n",
            "tags": ["sample", "trivia"],
            "categoryId": "27",
        },
        "status": {
            "privacyStatus": "private",
            "selfDeclaredMadeForKids": False,
            "containsSyntheticMedia": True,
        },
    }


def test_load_upload_metadata_rejects_non_private_privacy(tmp_path: Path) -> None:
    rendered_path = _write_render_files(tmp_path)

    with pytest.raises(AppError, match="Only private YouTube uploads are supported"):
        load_upload_metadata(rendered_path, privacy_status="unlisted")


def test_load_upload_metadata_does_not_require_manual_review_checked(
    tmp_path: Path,
) -> None:
    rendered_path = _write_render_files(tmp_path, manual_checked=False)

    metadata = load_upload_metadata(rendered_path, privacy_status="private")

    assert metadata.video_path == rendered_path.parent / "output.mp4"


def test_load_upload_metadata_uses_render_dir_file_when_json_output_path_is_stale(
    tmp_path: Path,
) -> None:
    rendered_path = _write_render_files(tmp_path, stale_output_paths=True)

    metadata = load_upload_metadata(rendered_path, privacy_status="private")

    assert metadata.video_path == rendered_path.parent / "output.mp4"
    assert metadata.body["snippet"]["description"].startswith("Main description")


def test_load_upload_metadata_requires_quality_report_without_errors(
    tmp_path: Path,
) -> None:
    rendered_path = _write_render_files(tmp_path, quality_error_count=1)

    with pytest.raises(AppError, match="quality_report.json has errors"):
        load_upload_metadata(rendered_path, privacy_status="private")
