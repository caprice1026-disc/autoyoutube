from __future__ import annotations

from pathlib import Path
from typing import Any

from src.errors import AppError


YOUTUBE_SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
    "https://www.googleapis.com/auth/yt-analytics.readonly",
]

def authorize_youtube_upload(
    client_secrets_path: Path = Path("secrets/client_secret.json"),
    token_path: Path = Path("data/youtube_token.json"),
) -> Any:
    if not client_secrets_path.is_file():
        raise AppError(
            "YouTube OAuth client secrets file was not found.",
            location=str(client_secrets_path),
            next_step="Create an OAuth desktop client in Google Cloud Console and save it at secrets/client_secret.json.",
        )
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError as exc:  # pragma: no cover - depends on optional package install.
        raise AppError(
            "Google API client dependencies are not installed.",
            details=str(exc),
            next_step="Install requirements.txt in the repository virtual environment.",
        ) from exc

    credentials = None
    if token_path.is_file():
        credentials = Credentials.from_authorized_user_file(
            str(token_path), [YOUTUBE_UPLOAD_SCOPE]
        )
    if credentials and credentials.expired and credentials.refresh_token:
        credentials.refresh(Request())
    if not credentials or not credentials.valid:
        flow = InstalledAppFlow.from_client_secrets_file(
            str(client_secrets_path), scopes=[YOUTUBE_UPLOAD_SCOPE]
        )
        credentials = flow.run_local_server(port=0)

    token_path.parent.mkdir(parents=True, exist_ok=True)
    token_path.write_text(credentials.to_json(), encoding="utf-8")
    return credentials


def build_youtube_service(
    *,
    client_secrets_path: Path = Path("secrets/client_secret.json"),
    token_path: Path = Path("data/youtube_token.json"),
) -> Any:
    credentials = authorize_youtube_upload(client_secrets_path, token_path)
    try:
        from googleapiclient.discovery import build
    except ImportError as exc:  # pragma: no cover - depends on optional package install.
        raise AppError(
            "Google API client dependencies are not installed.",
            details=str(exc),
            next_step="Install requirements.txt in the repository virtual environment.",
        ) from exc
    return build("youtube", "v3", credentials=credentials)
