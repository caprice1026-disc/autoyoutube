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

## Quality report

```powershell
.\.venv\Scripts\python.exe -m src.main evaluate-render renders\<project_id>\rendered.youtube.json
```

Read:

```text
renders/<project_id>/quality_report.json
```

## Development checks

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check .
```

Use the user’s platform equivalent when not on Windows.
