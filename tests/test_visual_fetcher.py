from __future__ import annotations

import json
from pathlib import Path

from src.media.pexels_client import PexelsClient
from src.media.visual_fetcher import fetch_visuals_for_project, score_asset, visual_query_specs


class FakeTransport:
    def __init__(self) -> None:
        self.downloads: list[tuple[str, Path]] = []
        self.queries: list[dict[str, str]] = []

    def get_json(self, path: str, query: dict[str, str]) -> dict:
        assert path == "/v1/videos/search"
        self.queries.append(query)
        query_text = query["query"]
        return {
            "videos": [
                _video(
                    1001,
                    query_text,
                    width=2160,
                    height=3840,
                    duration=12,
                    quality="hd",
                    file_width=1080,
                    file_height=1920,
                ),
                _video(
                    1002,
                    query_text,
                    width=1920,
                    height=1080,
                    duration=3,
                    quality="sd",
                    file_width=960,
                    file_height=540,
                ),
            ]
        }

    def download(self, url: str, output_path: Path) -> None:
        self.downloads.append((url, output_path))
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"fake mp4")


def _video(
    video_id: int,
    query: str,
    *,
    width: int,
    height: int,
    duration: float,
    quality: str,
    file_width: int,
    file_height: int,
) -> dict:
    slug = query.replace(" ", "-")
    return {
        "id": video_id,
        "width": width,
        "height": height,
        "duration": duration,
        "url": f"https://www.pexels.com/video/{slug}-{video_id}/",
        "user": {"name": "Creator", "url": "https://www.pexels.com/@creator"},
        "video_files": [
            {
                "id": video_id,
                "quality": quality,
                "file_type": "video/mp4",
                "width": file_width,
                "height": file_height,
                "link": f"https://videos.pexels.com/{video_id}.mp4",
            }
        ],
    }


def _project() -> dict:
    return {
        "id": "trivia_deep_sea_001",
        "visual_strategy": {
            "primary_query": "deep ocean",
            "fallback_queries": ["glowing jellyfish"],
        },
        "script": [
            {
                "index": 1,
                "text": "深海には光が届きません。",
                "visual_query": "deep ocean",
                "estimated_duration_sec": 3.5,
            },
            {
                "index": 2,
                "text": "でも光る生き物がいます。",
                "visual_query": "glowing jellyfish",
                "estimated_duration_sec": 4.0,
            },
        ],
    }


def test_visual_query_specs_deduplicate_and_preserve_script_context() -> None:
    specs = visual_query_specs(_project())

    assert [spec.query for spec in specs] == ["deep ocean", "glowing jellyfish"]
    deep_ocean = specs[0]
    assert deep_ocean.script_indices == [1]
    assert deep_ocean.target_duration_sec == 3.5
    assert "visual_strategy.primary_query" in deep_ocean.source
    assert "script.visual_query" in deep_ocean.source


def test_fetch_visuals_for_project_writes_scored_visual_plan(tmp_path: Path) -> None:
    project_path = tmp_path / "project.youtube.json"
    project_path.write_text(json.dumps(_project(), ensure_ascii=False), encoding="utf-8")
    transport = FakeTransport()
    client = PexelsClient(api_key="test-key", transport=transport)

    result = fetch_visuals_for_project(
        project_path,
        client=client,
        output_dir=tmp_path / "pexels",
        per_query=2,
        max_downloads=None,
        orientation="portrait",
        size="small",
    )

    assert result.plan_path == tmp_path / "pexels" / "trivia_deep_sea_001.visual_plan.json"
    assert result.plan_path.is_file()
    assert len(result.assets) == 2
    assert len(transport.downloads) == 2
    plan = json.loads(result.plan_path.read_text(encoding="utf-8"))
    assert plan["schema_version"] == "visual-plan-1.0.0"
    assert plan["project_id"] == "trivia_deep_sea_001"
    assert plan["summary"]["query_count"] == 2
    assert plan["summary"]["downloaded_asset_count"] == 2
    first_query = plan["queries"][0]
    assert first_query["query"] == "deep ocean"
    assert first_query["candidate_count"] == 2
    assert first_query["selected_asset_id"].startswith("pexels_1001_")
    assert first_query["candidates"][0]["score"] > first_query["candidates"][1]["score"]
    assert "orientation matches portrait" in first_query["candidates"][0]["reasons"]


def test_fetch_assets_for_queries_deduplicates_same_pexels_source(tmp_path: Path) -> None:
    class DuplicateTransport:
        def __init__(self) -> None:
            self.downloads: list[tuple[str, Path]] = []
            self.queries: list[dict[str, str]] = []

        def get_json(self, path: str, query: dict[str, str]) -> dict:
            assert path == "/v1/videos/search"
            self.queries.append(query)
            query_text = query["query"]
            return {
                "videos": [
                    _video(
                        1001,
                        query_text,
                        width=2160,
                        height=3840,
                        duration=12,
                        quality="hd",
                        file_width=1080,
                        file_height=1920,
                    )
                ]
            }

        def download(self, url: str, output_path: Path) -> None:
            self.downloads.append((url, output_path))
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(b"fake mp4")

    transport = DuplicateTransport()
    client = PexelsClient(api_key="test-key", transport=transport)

    assets = client.fetch_assets_for_queries(
        ["deep ocean", "ocean deep"],
        output_dir=tmp_path / "pexels",
        per_query=1,
        max_downloads=None,
        orientation="portrait",
        size="small",
    )

    assert len(assets) == 1
    assert len(transport.downloads) == 1
    assert assets[0].pexels_id == "1001"
    assert assets[0].asset_id.startswith("pexels_1001_")


def test_score_asset_penalizes_landscape_and_low_resolution(tmp_path: Path) -> None:
    from src.media.library import MediaAsset

    good = MediaAsset(
        asset_id="good",
        source="pexels",
        local_file_path=tmp_path / "good.mp4",
        original_width=1080,
        original_height=1920,
        original_duration_sec=10,
        orientation="portrait",
        selected_quality="hd",
        query="deep ocean",
        tags=["deep", "ocean"],
        pexels_url="https://pexels.example/video",
        photographer="Creator",
    )
    weak = MediaAsset(
        asset_id="weak",
        source="pexels",
        local_file_path=tmp_path / "weak.mp4",
        original_width=640,
        original_height=360,
        original_duration_sec=2,
        orientation="landscape",
        selected_quality="sd",
        query="deep ocean",
        tags=["deep", "ocean"],
    )

    good_score, _ = score_asset(good, target_duration_sec=5)
    weak_score, reasons = score_asset(weak, target_duration_sec=5)

    assert good_score > weak_score
    assert "landscape crop may be aggressive" in reasons
    assert "source resolution is low" in reasons
