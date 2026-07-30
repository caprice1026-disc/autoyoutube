from __future__ import annotations

from pathlib import Path
from urllib import request

import pytest

from src.errors import AppError
from src.media.pexels_client import (
    PexelsClient,
    UrlLibPexelsTransport,
    _select_video_file,
)


class FakeTransport:
    def __init__(self) -> None:
        self.downloads: list[tuple[str, Path]] = []

    def get_json(self, path: str, query: dict[str, str]) -> dict:
        assert path == "/v1/videos/search"
        assert query["query"] == "deep ocean"
        return {
            "total_results": 1,
            "videos": [
                {
                    "id": 20349819,
                    "width": 2160,
                    "height": 3840,
                    "duration": 12,
                    "url": "https://www.pexels.com/video/deep-ocean-20349819/",
                    "image": "https://images.pexels.com/videos/20349819/thumb.jpg",
                    "user": {
                        "name": "Pexels Creator",
                        "url": "https://www.pexels.com/@creator",
                    },
                    "video_files": [
                        {
                            "id": 1,
                            "quality": "sd",
                            "file_type": "video/mp4",
                            "width": 540,
                            "height": 960,
                            "link": "https://videos.pexels.com/video-files/sd.mp4",
                        },
                        {
                            "id": 2,
                            "quality": "hd",
                            "file_type": "video/mp4",
                            "width": 1080,
                            "height": 1920,
                            "link": "https://videos.pexels.com/video-files/hd.mp4",
                        },
                    ],
                }
            ],
        }

    def download(self, url: str, output_path: Path) -> None:
        self.downloads.append((url, output_path))
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"fake mp4")


def test_fetch_assets_for_queries_downloads_pexels_video_and_returns_media_asset(
    tmp_path: Path,
) -> None:
    transport = FakeTransport()
    client = PexelsClient(api_key="test-key", transport=transport)

    assets = client.fetch_assets_for_queries(
        ["deep ocean"], output_dir=tmp_path, per_query=1, max_downloads=1
    )

    assert len(assets) == 1
    asset = assets[0]
    assert asset.asset_id == "pexels_20349819_deep_ocean"
    assert asset.source == "pexels"
    assert asset.pexels_id == "20349819"
    assert asset.photographer == "Pexels Creator"
    assert asset.photographer_url == "https://www.pexels.com/@creator"
    assert asset.pexels_url == "https://www.pexels.com/video/deep-ocean-20349819/"
    assert asset.original_video_url == "https://videos.pexels.com/video-files/hd.mp4"
    assert asset.local_file_path.is_file()
    assert asset.original_width == 1080
    assert asset.original_height == 1920
    assert asset.original_duration_sec == 12
    assert asset.orientation == "portrait"
    assert asset.selected_quality == "hd"
    assert asset.query == "deep ocean"
    assert "deep" in asset.tags
    assert transport.downloads == [
        (
            "https://videos.pexels.com/video-files/hd.mp4",
            tmp_path / "pexels_20349819_deep_ocean.mp4",
        )
    ]


def test_pexels_client_requires_api_key(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("PEXELS_API_KEY", raising=False)

    with pytest.raises(AppError, match="PEXELS_API_KEY is not set"):
        PexelsClient()


def test_url_lib_transport_sends_user_agent(monkeypatch) -> None:
    captured_headers: dict[str, str] = {}

    class FakeResponse:
        headers = {}

        def __enter__(self) -> "FakeResponse":
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def read(self) -> bytes:
            return b'{"videos": []}'

    def fake_urlopen(req: request.Request, timeout: float) -> FakeResponse:
        captured_headers.update(dict(req.header_items()))
        return FakeResponse()

    monkeypatch.setattr(request, "urlopen", fake_urlopen)
    transport = UrlLibPexelsTransport("test-key")

    transport.get_json("/v1/videos/search", {"query": "ocean"})

    assert captured_headers["User-agent"] == "TriviaShortsMaker/0.1"


def test_url_lib_transport_download_streams_chunks_to_disk(monkeypatch, tmp_path: Path) -> None:
    read_sizes: list[int] = []

    class ChunkedResponse:
        def __init__(self) -> None:
            self.chunks = [b"first", b"second", b""]

        def __enter__(self) -> "ChunkedResponse":
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def read(self, size: int) -> bytes:
            read_sizes.append(size)
            return self.chunks.pop(0)

    def fake_urlopen(req: request.Request, timeout: float) -> ChunkedResponse:
        return ChunkedResponse()

    monkeypatch.setattr(request, "urlopen", fake_urlopen)
    output_path = tmp_path / "download.mp4"

    UrlLibPexelsTransport("test-key").download(
        "https://videos.pexels.com/video-files/test.mp4", output_path
    )

    assert output_path.read_bytes() == b"firstsecond"
    assert read_sizes == [64 * 1024, 64 * 1024, 64 * 1024]


def test_select_video_file_prefers_smallest_portrait_file_at_target_resolution() -> None:
    video = {
        "video_files": [
            {
                "quality": "uhd",
                "file_type": "video/mp4",
                "width": 2160,
                "height": 3840,
                "link": "https://videos.pexels.com/video-files/uhd.mp4",
            },
            {
                "quality": "hd",
                "file_type": "video/mp4",
                "width": 1080,
                "height": 1920,
                "link": "https://videos.pexels.com/video-files/hd.mp4",
            },
        ]
    }

    selected = _select_video_file(video, "portrait")

    assert selected["quality"] == "hd"
