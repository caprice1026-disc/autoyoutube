from __future__ import annotations

import argparse
from pathlib import Path

from src.config import PROJECT_SCHEMA_PATH, RENDERED_SCHEMA_PATH
from src.db.database import init_db
from src.pipeline.render_project import render_project
from src.validators.json_validator import validate_json_file
from src.voice.aivis_client import AivisSpeechClient


def main() -> int:
    parser = argparse.ArgumentParser(description="Trivia Shorts Maker for YouTube")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("init-db", help="initialize SQLite database")
    vp = sub.add_parser("validate-project", help="validate project.youtube.json")
    vp.add_argument("path")
    vr = sub.add_parser("validate-render", help="validate rendered.youtube.json")
    vr.add_argument("path")
    rr = sub.add_parser("render", help="render project assets")
    rr.add_argument("path")
    rr.add_argument("--voice-mode", choices=["dry-run", "aivis"], default="dry-run")
    args = parser.parse_args()

    if args.command == "init-db":
        init_db()
        print("Initialized DB: data/trivia_shorts.db")
        return 0
    if args.command == "validate-project":
        return _validate(Path(args.path), PROJECT_SCHEMA_PATH, "project JSON")
    if args.command == "validate-render":
        return _validate(Path(args.path), RENDERED_SCHEMA_PATH, "rendered JSON")
    if args.command == "render":
        voice_service = AivisSpeechClient() if args.voice_mode == "aivis" else None
        output = render_project(Path(args.path), voice_service=voice_service)
        print(f"Render complete: {output}")
        return 0
    return 1


def _validate(json_path: Path, schema_path: Path, label: str) -> int:
    _, errors = validate_json_file(json_path, schema_path)
    if errors:
        print(f"{label} validation failed:")
        for error in errors:
            print(f"- {error.to_text()}")
        return 1
    print(f"{label} validation succeeded: {json_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
