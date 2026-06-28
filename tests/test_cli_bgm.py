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


def test_import_bgm_cli_loads_manifest_and_reports_count(
    monkeypatch, capsys, tmp_path: Path
) -> None:
    audio_path = tmp_path / "mystery.wav"
    audio_path.write_bytes(b"placeholder")
    manifest_path = tmp_path / "bgm.json"
    manifest_path.write_text(
        json.dumps(
            {
                "tracks": [
                    {
                        "track_id": "mystery_low",
                        "file_path": "mystery.wav",
                        "title": "Mystery Low",
                        "artist": "Local",
                        "source": "local_original",
                        "license_type": "local_safe",
                        "mood": "mysterious",
                        "intensity": "low",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    imported: list[str] = []
    monkeypatch.setattr(sys, "argv", ["tsm", "import-bgm", str(manifest_path)])
    monkeypatch.setattr(main_module, "init_db", lambda: None)
    monkeypatch.setattr(main_module, "connect", lambda: FakeConnection())
    monkeypatch.setattr(
        main_module,
        "upsert_bgm_tracks",
        lambda connection, tracks: imported.extend(track.track_id for track in tracks),
    )

    exit_code = main_module.main()

    captured = capsys.readouterr()
    assert exit_code == 0
    assert imported == ["mystery_low"]
    assert "Imported BGM tracks: 1" in captured.out
