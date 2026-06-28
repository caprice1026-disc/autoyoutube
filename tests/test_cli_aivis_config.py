from __future__ import annotations

import sys
from pathlib import Path

import src.main as main_module


class FakeAivisSpeechClient:
    instances: list["FakeAivisSpeechClient"] = []

    def __init__(self, base_url: str | None = None) -> None:
        self.base_url = base_url
        self.instances.append(self)


def test_render_cli_passes_aivis_base_url_to_voice_client(monkeypatch, capsys) -> None:
    FakeAivisSpeechClient.instances = []
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "tsm",
            "render",
            "project.youtube.json",
            "--voice-mode",
            "aivis",
            "--aivis-base-url",
            "http://aivis-engine:10101",
        ],
    )
    monkeypatch.setattr(main_module, "AivisSpeechClient", FakeAivisSpeechClient)
    monkeypatch.setattr(
        main_module,
        "render_project",
        lambda path, voice_service=None, video_renderer=None: Path(
            "renders/out/rendered.youtube.json"
        ),
    )

    exit_code = main_module.main()

    captured = capsys.readouterr()
    assert exit_code == 0
    assert FakeAivisSpeechClient.instances[0].base_url == "http://aivis-engine:10101"
    assert (
        "Render complete: renders\\out\\rendered.youtube.json" in captured.out
        or "Render complete: renders/out/rendered.youtube.json" in captured.out
    )
