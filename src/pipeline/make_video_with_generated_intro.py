from __future__ import annotations

from pathlib import Path
from typing import Any

import src.pipeline.make_video as make_video_module
from src.pipeline.make_video import MakeVideoOptions, MakeVideoResult
from src.render.ffmpeg_renderer import FfmpegVideoRenderer
from src.media.video_audio import remove_audio_track

DEFAULT_GENERATED_INTRO_FILENAME = "generated_intro.mp4"
MUTED_GENERATED_INTRO_FILENAME = "generated_intro.muted.mp4"
GENERATED_INTRO_TRIM_START_SEC = 1.0


def make_video_with_generated_intro(
    options: MakeVideoOptions,
    *,
    generated_intro_path: Path | None = None,
) -> MakeVideoResult:
    """Run make-video while replacing only the first visual with a local AI clip.

    The clip is created manually and placed beside project.youtube.json.  When it
    is absent, this function deliberately delegates to the existing make-video
    workflow unchanged, including Gemini keyword extraction and stock fetching.
    """

    project_path = options.project_path.resolve()
    source_path = _resolve_generated_intro_path(project_path, generated_intro_path)
    if source_path is None:
        _log("generated intro not found; falling back to the existing stock workflow")
        return make_video_module.make_video(options)

    if options.plan_only:
        result = make_video_module.make_video(options)
        plan = dict(result.plan)
        plan["generated_intro"] = {
            "requested": True,
            "status": "available",
            "source_path": str(source_path),
            "audio_policy": "remove",
            "placement": "replace_first_visual",
        }
        return MakeVideoResult(
            exit_code=result.exit_code,
            status=result.status,
            run_dir=result.run_dir,
            final_rendered_path=result.final_rendered_path,
            plan=plan,
        )

    intro_path = source_path
    if not options.dry_run and options.video_mode == "ffmpeg":
        intro_path = remove_audio_track(
            source_path,
            project_path.parent / MUTED_GENERATED_INTRO_FILENAME,
            ffmpeg_path=options.ffmpeg_path,
            trim_start_sec=GENERATED_INTRO_TRIM_START_SEC,
        )
        _log(
            "removed generated intro audio and trimmed its leading "
            f"{GENERATED_INTRO_TRIM_START_SEC:.1f}s: {intro_path}"
        )

    original_renderer = make_video_module.FfmpegVideoRenderer
    generated_intro = intro_path.resolve()

    class GeneratedIntroRenderer(FfmpegVideoRenderer):
        def render(
            self,
            *,
            render_dir: Path,
            duration_sec: float,
            target: dict,
            logs_dir: Path,
            bgm: dict | None = None,
            visuals: list[dict] | None = None,
        ) -> dict[str, str | bool]:
            _replace_first_visual(visuals, generated_intro)
            return super().render(
                render_dir=render_dir,
                duration_sec=duration_sec,
                target=target,
                logs_dir=logs_dir,
                bgm=bgm,
                visuals=visuals,
            )

    make_video_module.FfmpegVideoRenderer = GeneratedIntroRenderer
    try:
        return make_video_module.make_video(options)
    finally:
        make_video_module.FfmpegVideoRenderer = original_renderer


def _resolve_generated_intro_path(
    project_path: Path, explicit_path: Path | None
) -> Path | None:
    candidate = explicit_path or Path(DEFAULT_GENERATED_INTRO_FILENAME)
    if not candidate.is_absolute():
        candidate = project_path.parent / candidate
    candidate = candidate.resolve()
    return candidate if candidate.is_file() else None


def _replace_first_visual(
    visuals: list[dict[str, Any]] | None, generated_intro_path: Path
) -> None:
    if not visuals:
        return
    first = min(
        visuals,
        key=lambda item: float(item.get("video_start_sec") or item.get("index") or 0),
    )
    for key in (
        "pexels_id",
        "photographer",
        "photographer_url",
        "pexels_url",
        "original_video_url",
    ):
        first.pop(key, None)
    first.update(
        {
            # render_visuals.asset_id references media_assets. A manually
            # generated local clip is intentionally not a fetched media asset.
            "asset_id": None,
            "source": "local",
            "local_file_path": str(generated_intro_path),
            "selected_quality": "original",
            "used_start_sec": 0,
        }
    )


def _log(message: str) -> None:
    print(f"[make-video-with-generated-intro] {message}")
