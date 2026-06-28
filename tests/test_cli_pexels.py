from __future__ import annotations

import json
import sys
from pathlib import Path

import src.main as main_module
from src.media.library import MediaAsset


class FakeConnection:
    def __enter__(self) -> "FakeConnection":
        return self

    def __exit__(self, *args: object) -> None:
        return None


class FakePexelsClient:
    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key

    def search_videos(
        self,
        query: str,
        *,
        per_page: int,
        orientation: str | None,
        size: str | None,
    ) -> list[dict]:
        assert query == "deep ocean"
        assert per_page == 1
        assert orientation == "portrait"
        assert size == "small"
        return [
            {
                "id": 20349819,
                "width": 2160,
                "height": 3840,
                "video_files": [{"id": 2}],
            }
        ]

    def fetch_assets_for_queries(
        self,
        queries: list[str],
        *,
        output_dir: Path,
        per_query: int,
        max_downloads: int | None,
        orientation: str | None,
        size: str | None,
    ) -> list[MediaAsset]:
        assert queries == ["deep ocean", "black submarine", "dark ocean"]
        assert output_dir == Path("assets/pexels")
        assert per_query == 1
        assert max_downloads == 1
        assert orientation == "portrait"
        assert size == "small"
        return [
            MediaAsset(
                asset_id="pexels_20349819_deep_ocean",
                source="pexels",
                local_file_path=output_dir / "pexels_20349819_deep_ocean.mp4",
                original_width=1080,
                original_height=1920,
                original_duration_sec=12,
                orientation="portrait",
                selected_quality="hd",
                query="deep ocean",
                tags=["deep", "ocean"],
                pexels_id="20349819",
            )
        ]


def test_check_pexels_cli_reports_search_result(monkeypatch, capsys) -> None:
    monkeypatch.setattr(sys, "argv", ["tsm", "check-pexels", "deep ocean"])
    monkeypatch.setattr(main_module, "load_dotenv", lambda: None)
    monkeypatch.setattr(main_module, "PexelsClient", FakePexelsClient)

    exit_code = main_module.main()

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Pexels search succeeded: query=deep ocean returned=1" in captured.out
    assert "first_id=20349819" in captured.out


def test_fetch_pexels_cli_reads_project_queries_and_upserts_assets(
    monkeypatch, capsys, tmp_path: Path
) -> None:
    project_path = tmp_path / "project.youtube.json"
    project_path.write_text(
        json.dumps(
            {
                "visual_strategy": {
                    "primary_query": "deep ocean",
                    "fallback_queries": ["dark ocean", "deep ocean"],
                },
                "script": [
                    {"visual_query": "deep ocean"},
                    {"visual_query": "black submarine"},
                ],
            }
        ),
        encoding="utf-8",
    )
    imported: list[str] = []
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "tsm",
            "fetch-pexels",
            str(project_path),
            "--per-query",
            "1",
            "--max-downloads",
            "1",
        ],
    )
    monkeypatch.setattr(main_module, "load_dotenv", lambda: None)
    monkeypatch.setattr(main_module, "PexelsClient", FakePexelsClient)
    monkeypatch.setattr(main_module, "init_db", lambda: None)
    monkeypatch.setattr(main_module, "connect", lambda: FakeConnection())
    monkeypatch.setattr(
        main_module,
        "upsert_media_assets",
        lambda connection, assets: imported.extend(asset.asset_id for asset in assets),
    )

    exit_code = main_module.main()

    captured = capsys.readouterr()
    assert exit_code == 0
    assert imported == ["pexels_20349819_deep_ocean"]
    assert "Fetched Pexels assets: 1" in captured.out
