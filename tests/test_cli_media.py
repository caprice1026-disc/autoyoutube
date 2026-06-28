from __future__ import annotations

import json
import sys
from pathlib import Path

import src.main as main_module


class FakeConnection:
    def __enter__(self) -> "FakeConnection":
        return self

    def __exit__(self, *args: object) -> None:
        return None


def test_import_media_cli_loads_manifest_and_reports_count(
    monkeypatch, capsys, tmp_path: Path
) -> None:
    video_path = tmp_path / "ocean.mp4"
    video_path.write_bytes(b"placeholder")
    manifest_path = tmp_path / "media_manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "assets": [
                    {
                        "asset_id": "ocean_portrait",
                        "local_file_path": "ocean.mp4",
                        "query": "dark ocean",
                        "tags": ["ocean"],
                        "original_width": 1080,
                        "original_height": 1920,
                        "original_duration_sec": 8.0,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    imported: list[str] = []
    monkeypatch.setattr(sys, "argv", ["tsm", "import-media", str(manifest_path)])
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
    assert imported == ["ocean_portrait"]
    assert "Imported media assets: 1" in captured.out
