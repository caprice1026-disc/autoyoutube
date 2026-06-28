from __future__ import annotations

import argparse
import sys
import traceback
from pathlib import Path

from src.bgm.library import load_bgm_manifest
from src.config import PROJECT_SCHEMA_PATH, RENDERED_SCHEMA_PATH
from src.db.database import connect, init_db
from src.db.repositories import list_active_bgm_tracks, upsert_bgm_tracks
from src.errors import AppError
from src.pipeline.render_project import render_project
from src.render.ffmpeg_renderer import FfmpegVideoRenderer
from src.validators.json_validator import validate_json_file
from src.voice.aivis_client import AivisSpeechClient


def main() -> int:
    parser = argparse.ArgumentParser(description="Trivia Shorts Maker for YouTube")
    parser.add_argument("--debug", action="store_true", help="print traceback for unexpected failures")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("init-db", help="initialize SQLite database")
    vp = sub.add_parser("validate-project", help="validate project.youtube.json")
    vp.add_argument("path")
    vr = sub.add_parser("validate-render", help="validate rendered.youtube.json")
    vr.add_argument("path")
    ib = sub.add_parser("import-bgm", help="import BGM tracks from a manifest JSON")
    ib.add_argument("manifest_path")
    sub.add_parser("list-bgm", help="list active BGM tracks")
    rr = sub.add_parser("render", help="render project assets")
    rr.add_argument("path")
    rr.add_argument("--voice-mode", choices=["dry-run", "aivis"], default="dry-run")
    rr.add_argument("--video-mode", choices=["dry-run", "ffmpeg"], default="dry-run")
    rr.add_argument("--ffmpeg-path")
    args = parser.parse_args()

    try:
        if args.command == "init-db":
            init_db()
            print("Initialized DB: data/trivia_shorts.db")
            return 0
        if args.command == "validate-project":
            return _validate(Path(args.path), PROJECT_SCHEMA_PATH, "project JSON")
        if args.command == "validate-render":
            return _validate(Path(args.path), RENDERED_SCHEMA_PATH, "rendered JSON")
        if args.command == "import-bgm":
            return _import_bgm(Path(args.manifest_path))
        if args.command == "list-bgm":
            return _list_bgm()
        if args.command == "render":
            voice_service = AivisSpeechClient() if args.voice_mode == "aivis" else None
            video_renderer = FfmpegVideoRenderer(args.ffmpeg_path) if args.video_mode == "ffmpeg" else None
            output = render_project(Path(args.path), voice_service=voice_service, video_renderer=video_renderer)
            print(f"Render complete: {output}")
            return 0
    except AppError as exc:
        print(exc.to_cli_text(), file=sys.stderr)
        return 1
    except Exception as exc:  # pragma: no cover - defensive CLI boundary
        if args.debug:
            traceback.print_exc()
        else:
            print(
                AppError(
                    "Unexpected failure.",
                    details=str(exc),
                    next_step="Run the command again with --debug and inspect the traceback.",
                ).to_cli_text(),
                file=sys.stderr,
            )
        return 1
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


def _import_bgm(manifest_path: Path) -> int:
    tracks = load_bgm_manifest(manifest_path)
    init_db()
    with connect() as connection:
        upsert_bgm_tracks(connection, tracks)
    print(f"Imported BGM tracks: {len(tracks)}")
    return 0


def _list_bgm() -> int:
    init_db()
    with connect() as connection:
        tracks = list_active_bgm_tracks(connection)
    if not tracks:
        print("No active BGM tracks.")
        return 0
    for track in tracks:
        print(f"{track.track_id}\t{track.source}\t{track.mood}/{track.intensity}\t{track.file_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
