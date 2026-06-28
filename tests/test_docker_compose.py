from __future__ import annotations

from pathlib import Path


def test_docker_compose_wires_app_to_aivis_engine_service() -> None:
    compose = Path("docker-compose.yml").read_text(encoding="utf-8")

    assert "aivis-engine:" in compose
    assert "ghcr.io/aivis-project/aivisspeech-engine:cpu-latest" in compose
    assert (
        "AIVIS_SPEECH_BASE_URL: ${AIVIS_SPEECH_BASE_URL:-http://aivis-engine:10101}"
        in compose
    )
    assert "10101:10101" in compose
    assert "/home/user/.local/share/AivisSpeech-Engine-Dev" in compose


def test_aivis_build_override_uses_cloned_engine_directory() -> None:
    compose = Path("docker-compose.aivis-build.yml").read_text(encoding="utf-8")

    assert "context: ${AIVIS_ENGINE_CONTEXT:-./AivisSpeech-Engine}" in compose


def test_app_dockerfile_installs_ffmpeg_and_runs_cli() -> None:
    dockerfile = Path("Dockerfile").read_text(encoding="utf-8")

    assert "FROM python:" in dockerfile
    assert "ffmpeg" in dockerfile
    assert 'ENTRYPOINT ["python", "-m", "src.main"]' in dockerfile
