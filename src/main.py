from __future__ import annotations

import argparse
import sys
import traceback
from pathlib import Path

from src.bgm.library import load_bgm_manifest
from src.config import PROJECT_SCHEMA_PATH, RENDERED_SCHEMA_PATH
from src.db.database import connect, init_db
from src.db.repositories import (
    list_active_bgm_tracks,
    list_active_media_assets,
    upsert_bgm_tracks,
    upsert_media_assets,
)
from src.env import load_dotenv
from src.errors import AppError
from src.media.library import load_media_manifest
from src.media.pexels_client import PexelsClient
from src.pipeline.render_project import render_project
from src.quality.evaluator import evaluate_render
from src.quality.inspector import inspect_render
from src.render.ffmpeg_renderer import FfmpegVideoRenderer
from src.validators.json_validator import load_json, validate_json_file
from src.voice.aivis_client import AivisSpeechClient


def main() -> int:
    parser = argparse.ArgumentParser(description="Trivia Shorts Maker for YouTube")
    parser.add_argument(
        "--debug", action="store_true", help="print traceback for unexpected failures"
    )
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("init-db", help="initialize SQLite database")
    vp = sub.add_parser("validate-project", help="validate project.youtube.json")
    vp.add_argument("path")
    vr = sub.add_parser("validate-render", help="validate rendered.youtube.json")
    vr.add_argument("path")
    er = sub.add_parser(
        "evaluate-render", help="write quality_report.json for a render"
    )
    er.add_argument("path")
    ir = sub.add_parser(
        "inspect-render", help="extract screenshot artifacts for a rendered video"
    )
    ir.add_argument("path")
    ir.add_argument("--ffmpeg-path")
    ib = sub.add_parser("import-bgm", help="import BGM tracks from a manifest JSON")
    ib.add_argument("manifest_path")
    sub.add_parser("list-bgm", help="list active BGM tracks")
    im = sub.add_parser(
        "import-media", help="import local media assets from a manifest JSON"
    )
    im.add_argument("manifest_path")
    sub.add_parser("list-assets", help="list active media assets")
    cp = sub.add_parser("check-pexels", help="check Pexels API connectivity")
    cp.add_argument("query")
    cp.add_argument("--per-page", type=int, default=1)
    cp.add_argument("--orientation", default="portrait")
    cp.add_argument("--size", default="small")
    fp = sub.add_parser("fetch-pexels", help="fetch Pexels videos for a project JSON")
    fp.add_argument("project_path")
    fp.add_argument("--output-dir", default="assets/pexels")
    fp.add_argument("--per-query", type=int, default=1)
    fp.add_argument("--max-downloads", type=int)
    fp.add_argument("--orientation", default="portrait")
    fp.add_argument("--size", default="small")
    rr = sub.add_parser("render", help="render project assets")
    rr.add_argument("path")
    rr.add_argument("--voice-mode", choices=["dry-run", "aivis"], default="dry-run")
    rr.add_argument("--video-mode", choices=["dry-run", "ffmpeg"], default="dry-run")
    rr.add_argument("--ffmpeg-path")
    rr.add_argument("--aivis-base-url")
    args = parser.parse_args()

    try:
        load_dotenv()
        if args.command == "init-db":
            init_db()
            print("Initialized DB: data/trivia_shorts.db")
            return 0
        if args.command == "validate-project":
            return _validate(Path(args.path), PROJECT_SCHEMA_PATH, "project JSON")
        if args.command == "validate-render":
            return _validate(Path(args.path), RENDERED_SCHEMA_PATH, "rendered JSON")
        if args.command == "evaluate-render":
            return _evaluate_render(Path(args.path))
        if args.command == "inspect-render":
            return _inspect_render(Path(args.path), args.ffmpeg_path)
        if args.command == "import-bgm":
            return _import_bgm(Path(args.manifest_path))
        if args.command == "list-bgm":
            return _list_bgm()
        if args.command == "import-media":
            return _import_media(Path(args.manifest_path))
        if args.command == "list-assets":
            return _list_assets()
        if args.command == "check-pexels":
            return _check_pexels(
                args.query,
                per_page=args.per_page,
                orientation=args.orientation,
                size=args.size,
            )
        if args.command == "fetch-pexels":
            return _fetch_pexels(
                Path(args.project_path),
                output_dir=Path(args.output_dir),
                per_query=args.per_query,
                max_downloads=args.max_downloads,
                orientation=args.orientation,
                size=args.size,
            )
        if args.command == "render":
            voice_service = (
                AivisSpeechClient(base_url=args.aivis_base_url)
                if args.voice_mode == "aivis"
                else None
            )
            video_renderer = (
                FfmpegVideoRenderer(args.ffmpeg_path)
                if args.video_mode == "ffmpeg"
                else None
            )
            output = render_project(
                Path(args.path),
                voice_service=voice_service,
                video_renderer=video_renderer,
            )
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


def _evaluate_render(rendered_path: Path) -> int:
    evaluate_render(rendered_path)
    print(f"Quality report written: {rendered_path.parent / 'quality_report.json'}")
    return 0


def _inspect_render(rendered_path: Path, ffmpeg_path: str | None) -> int:
    report = inspect_render(rendered_path, ffmpeg_path=ffmpeg_path)
    print(f"Inspect artifacts written: {report['inspect_dir']}")
    print(f"Summary screenshots: {len(report['screenshot_paths'])}")
    print(f"Subtitle frames: {len(report['subtitle_frame_paths'])}")
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
        print(
            f"{track.track_id}\t{track.source}\t{track.mood}/{track.intensity}\t{track.file_path}"
        )
    return 0


def _import_media(manifest_path: Path) -> int:
    assets = load_media_manifest(manifest_path)
    init_db()
    with connect() as connection:
        upsert_media_assets(connection, assets)
    print(f"Imported media assets: {len(assets)}")
    return 0


def _list_assets() -> int:
    init_db()
    with connect() as connection:
        assets = list_active_media_assets(connection)
    if not assets:
        print("No active media assets.")
        return 0
    for asset in assets:
        print(
            f"{asset.asset_id}\t{asset.source}\t{asset.orientation}\t{asset.query}\t{asset.local_file_path}"
        )
    return 0


def _check_pexels(
    query: str, *, per_page: int, orientation: str | None, size: str | None
) -> int:
    client = PexelsClient()
    videos = client.search_videos(
        query,
        per_page=per_page,
        orientation=orientation,
        size=size,
    )
    print(f"Pexels search succeeded: query={query} returned={len(videos)}")
    if videos:
        first = videos[0]
        files = (
            first.get("video_files")
            if isinstance(first.get("video_files"), list)
            else []
        )
        print(
            f"first_id={first.get('id')} width={first.get('width')} height={first.get('height')} files={len(files)}"
        )
    return 0


def _fetch_pexels(
    project_path: Path,
    *,
    output_dir: Path,
    per_query: int,
    max_downloads: int | None,
    orientation: str | None,
    size: str | None,
) -> int:
    queries = _pexels_queries_from_project(project_path)
    if not queries:
        raise AppError(
            "No Pexels search queries were found.",
            location=str(project_path),
            next_step="Add visual_strategy.primary_query, fallback_queries, or script visual_query values.",
        )
    client = PexelsClient()
    assets = client.fetch_assets_for_queries(
        queries,
        output_dir=output_dir,
        per_query=per_query,
        max_downloads=max_downloads,
        orientation=orientation,
        size=size,
    )
    init_db()
    with connect() as connection:
        upsert_media_assets(connection, assets)
    print(f"Fetched Pexels assets: {len(assets)}")
    for asset in assets:
        print(f"{asset.asset_id}\t{asset.query}\t{asset.local_file_path}")
    return 0


def _pexels_queries_from_project(project_path: Path) -> list[str]:
    project = load_json(project_path)
    visual_strategy = project.get("visual_strategy", {})
    queries: list[str] = []
    if isinstance(visual_strategy, dict):
        queries.append(str(visual_strategy.get("primary_query") or ""))
    script = project.get("script", [])
    if isinstance(script, list):
        for item in script:
            if isinstance(item, dict):
                queries.append(str(item.get("visual_query") or ""))
    if isinstance(visual_strategy, dict):
        fallback_queries = visual_strategy.get("fallback_queries", [])
        if isinstance(fallback_queries, list):
            queries.extend(str(query) for query in fallback_queries)
    return _unique_non_empty(queries)


def _unique_non_empty(values: list[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for value in values:
        normalized = value.strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        output.append(normalized)
    return output


if __name__ == "__main__":
    raise SystemExit(main())
