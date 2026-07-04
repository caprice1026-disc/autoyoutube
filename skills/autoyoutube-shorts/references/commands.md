# Commands

Run commands from the repository root unless the user explicitly provides another working directory.

## Project validation

```powershell
.\.venv\Scripts\python.exe -m src.main validate-project projects\<project_id>\project.youtube.json
```

Linux/macOS equivalent:

```bash
python -m src.main validate-project projects/<project_id>/project.youtube.json
```

## Visual acquisition

Use this before real video render when Pexels footage is needed.

```powershell
.\.venv\Scripts\python.exe -m src.main fetch-visuals projects\<project_id>\project.youtube.json --per-query 3 --max-downloads 20
```

The command writes Pexels assets and `visual_plan.json`, then registers assets in SQLite.

After fetching, confirm the same `asset_id` is not selected more than once inside one render:

```powershell
$plan = Get-Content assets\pexels\<project_id>.visual_plan.json -Raw | ConvertFrom-Json
$plan.queries | Where-Object selected_asset_id | Group-Object selected_asset_id | Where-Object Count -gt 1
```

If this prints any group, revise `script[].visual_query` or `visual_strategy.fallback_queries` and fetch again.

## BGM setup

```powershell
.\.venv\Scripts\python.exe -m src.main import-bgm assets\bgm\bgm_manifest.json
.\.venv\Scripts\python.exe -m src.main list-bgm
```

## Render

Dry-run render:

```powershell
.\.venv\Scripts\python.exe -m src.main render projects\<project_id>\project.youtube.json
```

Real FFmpeg render with AivisSpeech:

```powershell
.\.venv\Scripts\python.exe -m src.main render projects\<project_id>\project.youtube.json --voice-mode aivis --video-mode ffmpeg
```

If the first render risks going over 60 seconds, shorten the narration or raise `voice.speed_scale` before you rerender.

When FFmpeg is not on PATH:

```powershell
.\.venv\Scripts\python.exe -m src.main render projects\<project_id>\project.youtube.json --voice-mode aivis --video-mode ffmpeg --ffmpeg-path "C:\path\to\ffmpeg.exe"
```

## Validate rendered output

```powershell
.\.venv\Scripts\python.exe -m src.main validate-render renders\<project_id>\rendered.youtube.json
```

## Visual inspection artifacts

```powershell
.\.venv\Scripts\python.exe -m src.main inspect-render renders\<project_id>\rendered.youtube.json
```

This should generate:

```text
renders/<project_id>/inspect/opening.png
renders/<project_id>/inspect/middle.png
renders/<project_id>/inspect/ending.png
renders/<project_id>/inspect/subtitle_XXX.png
renders/<project_id>/inspect/timeline.png
```

If Windows console encoding breaks `inspect-render`, run:

```powershell
$env:PYTHONUTF8='1'; $env:PYTHONIOENCODING='utf-8'; .\.venv\Scripts\python.exe -m src.main inspect-render renders\<project_id>\rendered.youtube.json
```

## Quality report

```powershell
.\.venv\Scripts\python.exe -m src.main evaluate-render renders\<project_id>\rendered.youtube.json
```

Read:

```text
renders/<project_id>/quality_report.json
```

Treat `VIDEO_DURATION_TOO_LONG`, `SAME_ASSET_CONSECUTIVE`, and `SAME_ASSET_REUSED` as rerender blockers even if the report only marks them as warnings.

## YouTube auth and private upload

OAuth desktop auth:

```powershell
.\.venv\Scripts\python.exe -m src.main youtube-auth
```

The command reads `secrets\client_secret.json` and writes the token to `data\youtube_token.json`.

Private upload:

```powershell
.\.venv\Scripts\python.exe -m src.main upload-youtube renders\<project_id>\rendered.youtube.json
```

Confirm `rendered.youtube.json` reports `youtube.upload.status = "uploaded_private"` before treating the run as complete.

## Development checks

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check .
```

Use the user’s platform equivalent when not on Windows.
