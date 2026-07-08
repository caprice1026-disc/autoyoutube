from __future__ import annotations

import argparse
import json
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
from src.media.visual_fetcher import fetch_visuals_for_project
from src.pipeline.make_video import MakeVideoOptions, make_video
from src.pipeline.render_project import render_project
from src.quality.evaluator import evaluate_render
from src.quality.inspector import inspect_render
from src.render.ffmpeg_renderer import FfmpegVideoRenderer
from src.validators.json_validator import load_json, validate_json_file
from src.voice.aivis_client import AivisSpeechClient
from src.youtube.analytics_summary import (
    format_console_summary,
    generate_youtube_analytics_summary,
)
from src.youtube.auth import authorize_youtube_upload
from src.youtube.uploader import upload_private_video


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
    fv = sub.add_parser(
        "fetch-visuals",
        help="fetch and score Pexels visual candidates for a project JSON",
    )
    fv.add_argument("project_path")
    fv.add_argument("--output-dir", default="assets/pexels")
    fv.add_argument("--per-query", type=int, default=3)
    fv.add_argument("--max-downloads", type=int)
    fv.add_argument("--orientation", default="portrait")
    fv.add_argument("--size", default="small")
    fv.add_argument("--plan-path")
    rr = sub.add_parser("render", help="render project assets")
    rr.add_argument("path")
    rr.add_argument("--voice-mode", choices=["dry-run", "aivis"], default="dry-run")
    rr.add_argument("--video-mode", choices=["dry-run", "ffmpeg"], default="dry-run")
    rr.add_argument("--ffmpeg-path")
    rr.add_argument("--aivis-base-url")
    mv = sub.add_parser(
        "make-video",
        help="fetch visuals, render, inspect, evaluate, and auto-retry a project",
    )
    mv.add_argument("project_path")
    mv.add_argument(
        "--visual-keyword",
        "--video-keyword",
        "--pexels-keyword",
        action="append",
        default=[],
        dest="visual_keyword",
        help="Pexels video search keyword. Can be specified multiple times.",
    )
    mv.add_argument(
        "--visual-keywords",
        "--video-keywords",
        "--pexels-keywords",
        dest="visual_keywords",
        help="Comma-separated Pexels video search keywords.",
    )
    mv.add_argument(
        "--query-mode", choices=["append", "override", "fallback"], default="append"
    )
    mv.add_argument("--per-query", type=int)
    mv.add_argument("--max-downloads", type=int)
    mv.add_argument(
        "--orientation", choices=["portrait", "landscape", "square"], default="portrait"
    )
    mv.add_argument("--size", choices=["small", "medium", "large"], default="small")
    mv.add_argument("--voice-mode", choices=["dry-run", "aivis"], default="aivis")
    mv.add_argument("--video-mode", choices=["dry-run", "ffmpeg"], default="ffmpeg")
    mv.add_argument("--aivis-base-url")
    mv.add_argument("--ffmpeg-path")
    mv.add_argument("--bgm-id")
    mv.add_argument("--seed", type=int)
    auto_fix_group = mv.add_mutually_exclusive_group()
    auto_fix_group.add_argument("--auto-fix", dest="auto_fix", action="store_true")
    auto_fix_group.add_argument("--no-auto-fix", dest="auto_fix", action="store_false")
    mv.set_defaults(auto_fix=True)
    mv.add_argument("--max-fix-attempts", type=int)
    mv.add_argument("--plan-only", action="store_true")
    mv.add_argument("--dry-run", action="store_true")
    mv.add_argument(
        "--upload-youtube",
        action="store_true",
        help="upload the final rendered video to YouTube as private when render succeeds",
    )
    mv.add_argument("--skip-fetch-visuals", action="store_true")
    mv.add_argument("--skip-inspect", action="store_true")
    mv.add_argument("--skip-evaluate", action="store_true")
    mv.add_argument("--config-path")
    ya = sub.add_parser("youtube-auth", help="authorize YouTube upload access")
    ya.add_argument("--client-secrets", default="secrets/client_secret.json")
    ya.add_argument("--token-path", default="data/youtube_token.json")
    yas = sub.add_parser(
        "youtube-analytics-summary",
        help="summarize uploaded YouTube videos with the Analytics API",
    )
    yas.add_argument("--days", type=int, default=28)
    yas.add_argument("--client-secrets", default="secrets/client_secret.json")
    yas.add_argument("--token-path", default="data/youtube_token.json")
    yas.add_argument(
        "--output-path", default="data/youtube_analytics_summary.json"
    )
    uy = sub.add_parser(
        "upload-youtube", help="upload a rendered video to YouTube as private"
    )
    uy.add_argument("rendered_path")
    uy.add_argument("--privacy", default="private")
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
        if args.command == "fetch-visuals":
            return _fetch_visuals(
                Path(args.project_path),
                output_dir=Path(args.output_dir),
                per_query=args.per_query,
                max_downloads=args.max_downloads,
                orientation=args.orientation,
                size=args.size,
                plan_path=Path(args.plan_path) if args.plan_path else None,
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
        if args.command == "make-video":
            return _make_video(args)
        if args.command == "youtube-auth":
            return _youtube_auth(
                Path(args.client_secrets),
                Path(args.token_path),
            )
        if args.command == "youtube-analytics-summary":
            return _youtube_analytics_summary(
                days=args.days,
                client_secrets_path=Path(args.client_secrets),
                token_path=Path(args.token_path),
                output_path=Path(args.output_path),
            )
        if args.command == "upload-youtube":
            return _upload_youtube(Path(args.rendered_path), privacy=args.privacy)
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
    if report.get("timeline_png_path"):
        print(f"Timeline PNG: {report['timeline_png_path']}")
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


def _fetch_visuals(
    project_path: Path,
    *,
    output_dir: Path,
    per_query: int,
    max_downloads: int | None,
    orientation: str | None,
    size: str | None,
    plan_path: Path | None,
) -> int:
    client = PexelsClient()
    result = fetch_visuals_for_project(
        project_path,
        client=client,
        output_dir=output_dir,
        per_query=per_query,
        max_downloads=max_downloads,
        orientation=orientation,
        size=size,
        plan_path=plan_path,
    )
    init_db()
    with connect() as connection:
        upsert_media_assets(connection, result.assets)
    print(f"Fetched visual assets: {len(result.assets)}")
    print(f"Visual plan written: {result.plan_path}")
    for asset in result.assets:
        print(f"{asset.asset_id}\t{asset.query}\t{asset.local_file_path}")
    return 0


def _youtube_auth(client_secrets_path: Path, token_path: Path) -> int:
    authorize_youtube_upload(client_secrets_path, token_path)
    print(f"YouTube OAuth token ready: {token_path.as_posix()}")
    return 0


def _youtube_analytics_summary(
    *,
    days: int,
    client_secrets_path: Path,
    token_path: Path,
    output_path: Path,
) -> int:
    summary = generate_youtube_analytics_summary(
        days=days,
        client_secrets_path=client_secrets_path,
        token_path=token_path,
        output_path=output_path,
    )
    print(f"YouTube analytics summary written: {output_path.as_posix()}")
    for line in format_console_summary(summary):
        print(line)
    return 0


def _upload_youtube(rendered_path: Path, *, privacy: str) -> int:
    result = upload_private_video(
        _resolve_rendered_path(rendered_path), privacy_status=privacy
    )
    print(f"YouTube upload complete: {result.video_id}")
    print(result.watch_url)
    return 0


def _make_video(args: argparse.Namespace) -> int:
    keywords = list(args.visual_keyword or [])
    if args.visual_keywords:
        keywords.extend(
            keyword.strip()
            for keyword in args.visual_keywords.split(",")
            if keyword.strip()
        )
    result = make_video(
        MakeVideoOptions(
            project_path=Path(args.project_path),
            visual_keywords=keywords,
            query_mode=args.query_mode,
            per_query=args.per_query,
            max_downloads=args.max_downloads,
            orientation=args.orientation,
            size=args.size,
            voice_mode=args.voice_mode,
            video_mode=args.video_mode,
            aivis_base_url=args.aivis_base_url,
            ffmpeg_path=args.ffmpeg_path,
            bgm_id=args.bgm_id,
            seed=args.seed,
            auto_fix=args.auto_fix,
            max_fix_attempts=args.max_fix_attempts,
            plan_only=args.plan_only,
            dry_run=args.dry_run,
            skip_fetch_visuals=args.skip_fetch_visuals,
            skip_inspect=args.skip_inspect,
            skip_evaluate=args.skip_evaluate,
            config_path=Path(args.config_path) if args.config_path else None,
        )
    )
    if args.upload_youtube and result.status in {"success", "success_with_warnings"}:
        if args.dry_run or args.video_mode == "dry-run":
            print(
                "[make-video] upload requested but dry-run/video-mode=dry-run was selected; skipping upload"
            )
        elif result.final_rendered_path is None:
            print(
                "[make-video] upload requested but no final rendered JSON was produced."
            )
        else:
            print("[make-video] uploading final render to YouTube as private")
            upload_result = upload_private_video(
                result.final_rendered_path, privacy_status="private"
            )
            print(f"YouTube upload complete: {upload_result.video_id}")
            print(upload_result.watch_url)
    if args.plan_only:
        print(json.dumps(result.plan, ensure_ascii=False, indent=2))
    else:
        print(f"make-video status: {result.status}")
        if result.run_dir is not None:
            print(f"Run directory: {result.run_dir}")
        if result.final_rendered_path is not None:
            print(f"Final rendered JSON: {result.final_rendered_path}")
    return result.exit_code


def _resolve_rendered_path(path: Path) -> Path:
    if path.suffix.lower() == ".json":
        return path
    return path / "rendered.youtube.json"


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
