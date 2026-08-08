from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

import src.main as main_module


@dataclass(frozen=True)
class FakeUploadResult:
    video_id: str
    watch_url: str


def test_youtube_auth_cli_calls_authorize_upload(monkeypatch, capsys) -> None:
    calls: list[tuple[Path, Path]] = []
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "tsm",
            "youtube-auth",
            "--client-secrets",
            "secrets/client_secret.json",
            "--token-path",
            "data/youtube_token.json",
        ],
    )
    monkeypatch.setattr(
        main_module,
        "authorize_youtube_upload",
        lambda client_secrets_path, token_path: calls.append(
            (client_secrets_path, token_path)
        ),
    )

    exit_code = main_module.main()

    captured = capsys.readouterr()
    assert exit_code == 0
    assert calls == [
        (Path("secrets/client_secret.json"), Path("data/youtube_token.json"))
    ]
    assert "YouTube OAuth token ready: data/youtube_token.json" in captured.out


def test_upload_youtube_cli_uses_private_uploader(monkeypatch, capsys) -> None:
    calls: list[tuple[Path, str]] = []
    monkeypatch.setattr(
        sys,
        "argv",
        ["tsm", "upload-youtube", "renders/sample/rendered.youtube.json"],
    )

    def fake_upload_private_video(
        rendered_path: Path, *, privacy_status: str
    ) -> FakeUploadResult:
        calls.append((rendered_path, privacy_status))
        return FakeUploadResult(
            video_id="abc123",
            watch_url="https://www.youtube.com/watch?v=abc123",
        )

    monkeypatch.setattr(main_module, "upload_private_video", fake_upload_private_video)

    exit_code = main_module.main()

    captured = capsys.readouterr()
    assert exit_code == 0
    assert calls == [(Path("renders/sample/rendered.youtube.json"), "private")]
    assert "YouTube upload complete: abc123" in captured.out
    assert "https://www.youtube.com/watch?v=abc123" in captured.out


def test_upload_youtube_cli_accepts_render_directory(monkeypatch, capsys) -> None:
    calls: list[tuple[Path, str]] = []
    monkeypatch.setattr(
        sys,
        "argv",
        ["tsm", "upload-youtube", "renders/sample"],
    )

    def fake_upload_private_video(
        rendered_path: Path, *, privacy_status: str
    ) -> FakeUploadResult:
        calls.append((rendered_path, privacy_status))
        return FakeUploadResult(
            video_id="abc123",
            watch_url="https://www.youtube.com/watch?v=abc123",
        )

    monkeypatch.setattr(main_module, "upload_private_video", fake_upload_private_video)

    exit_code = main_module.main()

    captured = capsys.readouterr()
    assert exit_code == 0
    assert calls == [(Path("renders/sample/rendered.youtube.json"), "private")]
    assert "YouTube upload complete: abc123" in captured.out


def test_youtube_analytics_summary_cli_calls_summary_generator(
    monkeypatch, capsys
) -> None:
    calls: list[dict[str, object]] = []
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "tsm",
            "youtube-analytics-summary",
            "--days",
            "14",
            "--output-path",
            "data/youtube_analytics_summary.json",
        ],
    )
    monkeypatch.setattr(main_module, "load_dotenv", lambda: None)

    def fake_generate_youtube_analytics_summary(**kwargs: object) -> dict[str, object]:
        calls.append(dict(kwargs))
        return {
            "analyzed_video_count": 1,
            "video_count": 1,
            "start_date": "2026-07-01",
            "end_date": "2026-07-14",
            "totals": {"views": 123, "likes": 4, "comments": 2, "shares": 1},
            "weighted_averages": {
                "average_view_duration": 12.34,
                "average_view_percentage": 56.78,
            },
            "top_by_views": [
                {
                    "youtube_title": "Sample Title",
                    "views": 123,
                    "average_view_percentage": 56.78,
                }
            ],
            "top_by_retention": [
                {
                    "youtube_title": "Sample Title",
                    "views": 123,
                    "average_view_percentage": 56.78,
                }
            ],
        }

    monkeypatch.setattr(
        main_module,
        "generate_youtube_analytics_summary",
        fake_generate_youtube_analytics_summary,
    )
    monkeypatch.setattr(
        main_module,
        "format_console_summary",
        lambda summary: ["Analyzed videos: 1 / 1"],
    )

    exit_code = main_module.main()

    captured = capsys.readouterr()
    assert exit_code == 0
    assert calls == [
        {
            "days": 14,
            "client_secrets_path": Path("secrets/client_secret.json"),
            "token_path": Path("data/youtube_token.json"),
            "output_path": Path("data/youtube_analytics_summary.json"),
        }
    ]
    assert "YouTube analytics summary written: data/youtube_analytics_summary.json" in captured.out
    assert "Analyzed videos: 1 / 1" in captured.out


def test_youtube_analytics_evaluate_rejects_nonpositive_days_before_api_call(
    monkeypatch, capsys
) -> None:
    calls: list[dict[str, object]] = []
    monkeypatch.setattr(
        sys,
        "argv",
        ["tsm", "youtube-analytics-evaluate", "--recent-days", "0"],
    )
    monkeypatch.setattr(main_module, "load_dotenv", lambda: None)
    monkeypatch.setattr(
        main_module,
        "generate_youtube_analytics_summary",
        lambda **kwargs: calls.append(dict(kwargs)),
    )

    exit_code = main_module.main()

    captured = capsys.readouterr()
    assert exit_code == 1
    assert calls == []
    assert "recent_days must be at least 1" in captured.err
