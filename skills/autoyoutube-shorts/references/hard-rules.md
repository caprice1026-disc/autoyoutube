# Hard rules

These rules protect the project from unsafe automation, noisy diffs, and rights/quality mistakes.

## Scope

- Keep the project focused on YouTube Shorts.
- Keep output target at 1080x1920, 9:16, MP4, H.264, AAC unless the user explicitly changes the product direction.
- Do not add automatic YouTube upload, automatic publishing, or buzz prediction unless explicitly requested.

## Human review

- Keep `manual_review.required=true` until explicit human review is recorded.
- Human review remains responsible for factual accuracy, final video quality, music rights, Pexels attribution correctness, and publishing decisions.

## Files that must not be committed

Do not commit:

```text
renders/
data/*.db
.env
assets/pexels/
assets/bgm/**/*.mp3
assets/bgm/**/*.wav
assets/bgm/**/*.m4a
assets/bgm/**/*.flac
downloaded media
render outputs
local engine folders
```

Manifest files such as `assets/bgm/bgm_manifest.json` may be committed only when they do not include private paths or rights-risky metadata.

## Credits and rights

- Preserve BGM credit metadata.
- Preserve Pexels `photographer`, `photographer_url`, `pexels_url`, and `original_video_url` metadata.
- Never delete credit generation to silence a quality check.
- If a rights or attribution question is unclear, surface it for human review rather than guessing.

## Repair behavior

- Prefer minimal targeted patches.
- Do not rewrite schemas broadly unless the error is schema-related.
- Do not change generated JSON contracts casually.
- Do not hide failures by downgrading errors to warnings.
- Do not disable tests to make a repair pass.

## Evidence-first workflow

Use these as the main evidence:

```text
rendered.youtube.json
quality_report.json
inspect/timeline.png
inspect/subtitle_XXX.png
ffmpeg_stderr.log
```

Do not rely only on a textual guess when inspection artifacts exist.
