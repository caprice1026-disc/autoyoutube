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
