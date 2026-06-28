from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Protocol
from urllib import error, parse, request

from src.env import load_dotenv
from src.errors import AppError
from src.media.library import MediaAsset


class PexelsTransport(Protocol):
    def get_json(self, path: str, query: dict[str, str]) -> dict[str, Any]: ...

    def download(self, url: str, output_path: Path) -> None: ...


class UrlLibPexelsTransport:
    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = "https://api.pexels.com",
        timeout: float = 30.0,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def get_json(self, path: str, query: dict[str, str]) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        if query:
            url = f"{url}?{parse.urlencode(query)}"
        req = request.Request(url, headers=self._headers())
        try:
            with request.urlopen(req, timeout=self.timeout) as response:
                body = response.read().decode("utf-8")
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise AppError(
                "Pexels API returned an HTTP error.",
                location=url,
                details=f"HTTP {exc.code}: {detail}",
                next_step="Check PEXELS_API_KEY, query parameters, and Pexels API limits.",
            ) from exc
        except error.URLError as exc:
            raise AppError(
                "Could not connect to Pexels API.",
                location=url,
                details=str(exc.reason),
                next_step="Check network connectivity and retry.",
            ) from exc
        loaded = json.loads(body)
        if not isinstance(loaded, dict):
            raise AppError(
                "Pexels API returned an unexpected response.",
                location=url,
                details="Expected a JSON object.",
                next_step="Retry the request or inspect the Pexels API response manually.",
            )
        return loaded

    def download(self, url: str, output_path: Path) -> None:
        req = request.Request(url, headers=self._headers())
        output_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with request.urlopen(req, timeout=self.timeout) as response:
                output_path.write_bytes(response.read())
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise AppError(
                "Pexels video download returned an HTTP error.",
                location=url,
                details=f"HTTP {exc.code}: {detail}",
                next_step="Retry the download or choose another Pexels video.",
            ) from exc
        except error.URLError as exc:
            raise AppError(
                "Could not download Pexels video.",
                location=url,
                details=str(exc.reason),
                next_step="Check network connectivity and retry.",
            ) from exc

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": self.api_key,
            "User-Agent": "TriviaShortsMaker/0.1",
        }


class PexelsClient:
    def __init__(
        self,
        api_key: str | None = None,
        transport: PexelsTransport | None = None,
    ) -> None:
        self.api_key = _resolve_api_key(api_key)
        self.transport = transport or UrlLibPexelsTransport(self.api_key)

    def search_videos(
        self,
        query: str,
        *,
        per_page: int = 1,
        orientation: str | None = "portrait",
        size: str | None = "small",
    ) -> list[dict[str, Any]]:
        params = {
            "query": query,
            "per_page": str(per_page),
        }
        if orientation:
            params["orientation"] = orientation
        if size:
            params["size"] = size
        response = self.transport.get_json("/v1/videos/search", params)
        videos = response.get("videos")
        if not isinstance(videos, list):
            raise AppError(
                "Pexels API response did not contain a videos array.",
                details=json.dumps(response, ensure_ascii=False)[:500],
                next_step="Retry the request or inspect the Pexels API response manually.",
            )
        return [video for video in videos if isinstance(video, dict)]

    def fetch_assets_for_queries(
        self,
        queries: list[str],
        *,
        output_dir: Path,
        per_query: int = 1,
        max_downloads: int | None = None,
        orientation: str | None = "portrait",
        size: str | None = "small",
    ) -> list[MediaAsset]:
        assets: list[MediaAsset] = []
        seen_asset_ids: set[str] = set()
        for query in _unique_non_empty(queries):
            for video in self.search_videos(
                query,
                per_page=per_query,
                orientation=orientation,
                size=size,
            ):
                asset = self._asset_from_video(video, query, output_dir, orientation)
                if asset.asset_id in seen_asset_ids:
                    continue
                seen_asset_ids.add(asset.asset_id)
                if not asset.local_file_path.is_file():
                    self.transport.download(
                        asset.original_video_url or "", asset.local_file_path
                    )
                assets.append(asset)
                if max_downloads is not None and len(assets) >= max_downloads:
                    return assets
        return assets

    def _asset_from_video(
        self,
        video: dict[str, Any],
        query: str,
        output_dir: Path,
        preferred_orientation: str | None,
    ) -> MediaAsset:
        video_id = str(video.get("id") or "").strip()
        if not video_id:
            raise AppError(
                "Pexels video response is missing id.",
                details=json.dumps(video, ensure_ascii=False)[:500],
                next_step="Retry with a different query.",
            )
        selected_file = _select_video_file(video, preferred_orientation)
        link = str(selected_file.get("link") or "")
        if not link:
            raise AppError(
                "Pexels video file is missing download link.",
                location=f"pexels:{video_id}",
                next_step="Retry with a different query.",
            )
        asset_id = f"pexels_{video_id}_{_slug(query)}"
        width = _optional_int(selected_file.get("width")) or _optional_int(
            video.get("width")
        )
        height = _optional_int(selected_file.get("height")) or _optional_int(
            video.get("height")
        )
        user = video.get("user") if isinstance(video.get("user"), dict) else {}
        return MediaAsset(
            asset_id=asset_id,
            source="pexels",
            local_file_path=output_dir / f"{asset_id}.mp4",
            original_width=width,
            original_height=height,
            original_duration_sec=_optional_float(video.get("duration")),
            orientation=_infer_orientation(width, height),
            selected_quality=_normalize_quality(selected_file.get("quality")),
            query=query,
            tags=_query_tags(query),
            pexels_id=video_id,
            photographer=str(user.get("name") or "") or None,
            photographer_url=str(user.get("url") or "") or None,
            pexels_url=str(video.get("url") or "") or None,
            original_video_url=link,
        )


def _resolve_api_key(api_key: str | None) -> str:
    if api_key:
        return api_key
    load_dotenv()
    resolved = os.environ.get("PEXELS_API_KEY")
    if resolved:
        return resolved
    raise AppError(
        "PEXELS_API_KEY is not set.",
        location=".env",
        next_step="Add PEXELS_API_KEY to .env or set it as an environment variable.",
    )


def _select_video_file(
    video: dict[str, Any], preferred_orientation: str | None
) -> dict[str, Any]:
    files = video.get("video_files")
    if not isinstance(files, list):
        files = []
    candidates = [
        file
        for file in files
        if isinstance(file, dict)
        and str(file.get("link") or "")
        and (
            "mp4" in str(file.get("file_type") or "").lower()
            or str(file.get("link")).lower().endswith(".mp4")
        )
    ]
    if not candidates:
        raise AppError(
            "Pexels video did not include an MP4 file.",
            location=f"pexels:{video.get('id')}",
            next_step="Retry with a different query.",
        )
    return sorted(
        candidates,
        key=lambda item: (
            0
            if _infer_orientation(
                _optional_int(item.get("width")), _optional_int(item.get("height"))
            )
            == preferred_orientation
            else 1,
            -_quality_rank(item.get("quality")),
            -(_optional_int(item.get("width")) or 0)
            * (_optional_int(item.get("height")) or 0),
        ),
    )[0]


def _unique_non_empty(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        cleaned = value.strip()
        key = cleaned.lower()
        if cleaned and key not in seen:
            seen.add(key)
            result.append(cleaned)
    return result


def _query_tags(query: str) -> list[str]:
    return [token for token in re.split(r"\s+", query.strip().lower()) if token]


def _slug(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "_", value.strip().lower()).strip("_")
    return cleaned or "query"


def _normalize_quality(value: Any) -> str:
    text = str(value or "unknown").lower()
    if text in {"sd", "hd", "uhd", "original"}:
        return text
    return "unknown"


def _quality_rank(value: Any) -> int:
    return {"sd": 1, "hd": 2, "uhd": 3, "original": 4}.get(_normalize_quality(value), 0)


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    return int(value)


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    return float(value)


def _infer_orientation(width: int | None, height: int | None) -> str:
    if width is None or height is None:
        return "unknown"
    if height > width:
        return "portrait"
    if width > height:
        return "landscape"
    return "square"
