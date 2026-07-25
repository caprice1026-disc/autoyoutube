from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.env import load_dotenv
from src.pipeline.make_video import MakeVideoOptions
from src.pipeline.make_video_with_generated_intro import make_video_with_generated_intro
from src.youtube.uploader import upload_private_video


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Render a project with a manually generated intro clip"
    )
    parser.add_argument("project_path")
    parser.add_argument("--generated-intro-path")
    parser.add_argument(
        "--visual-keyword",
        "--video-keyword",
        "--pexels-keyword",
        action="append",
        default=[],
        dest="visual_keyword",
    )
    parser.add_argument("--visual-keywords", "--video-keywords", "--pexels-keywords")
    parser.add_argument(
        "--query-mode", choices=["append", "override", "fallback"], default="append"
    )
    parser.add_argument("--per-query", type=int)
    parser.add_argument("--max-downloads", type=int)
    parser.add_argument(
        "--orientation", choices=["portrait", "landscape", "square"], default="portrait"
    )
    parser.add_argument("--size", choices=["small", "medium", "large"], default="small")
    parser.add_argument("--voice-mode", choices=["dry-run", "aivis"], default="aivis")
    parser.add_argument("--video-mode", choices=["dry-run", "ffmpeg"], default="ffmpeg")
    parser.add_argument("--aivis-base-url")
    parser.add_argument("--ffmpeg-path")
    parser.add_argument("--bgm-id")
    parser.add_argument("--seed", type=int)
    parser.add_argument("--max-fix-attempts", type=int)
    parser.add_argument("--no-auto-fix", action="store_true")
    parser.add_argument("--plan-only", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--upload-youtube", action="store_true")
    parser.add_argument("--skip-fetch-visuals", action="store_true")
    parser.add_argument("--skip-inspect", action="store_true")
    parser.add_argument("--skip-evaluate", action="store_true")
    parser.add_argument("--config-path")
    args = parser.parse_args()

    load_dotenv()
    keywords = list(args.visual_keyword or [])
    if args.visual_keywords:
        keywords.extend(
            item.strip() for item in args.visual_keywords.split(",") if item.strip()
        )

    result = make_video_with_generated_intro(
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
            auto_fix=not args.no_auto_fix,
            max_fix_attempts=args.max_fix_attempts,
            plan_only=args.plan_only,
            dry_run=args.dry_run,
            skip_fetch_visuals=args.skip_fetch_visuals,
            skip_inspect=args.skip_inspect,
            skip_evaluate=args.skip_evaluate,
            config_path=Path(args.config_path) if args.config_path else None,
        ),
        generated_intro_path=(
            Path(args.generated_intro_path) if args.generated_intro_path else None
        ),
    )

    if args.upload_youtube and result.status in {"success", "success_with_warnings"}:
        if args.dry_run or args.video_mode == "dry-run":
            print("[make-video-with-generated-intro] upload skipped in dry-run mode")
        elif result.final_rendered_path is not None:
            upload = upload_private_video(
                result.final_rendered_path, privacy_status="private"
            )
            print(f"YouTube upload complete: {upload.video_id}")
            print(upload.watch_url)

    if args.plan_only:
        print(json.dumps(result.plan, ensure_ascii=False, indent=2))
    else:
        print(f"make-video-with-generated-intro status: {result.status}")
        if result.run_dir is not None:
            print(f"Run directory: {result.run_dir}")
        if result.final_rendered_path is not None:
            print(f"Final rendered JSON: {result.final_rendered_path}")
    return result.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
