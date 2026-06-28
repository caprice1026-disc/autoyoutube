# Trivia Shorts Maker for YouTube

YouTube Shorts向けの雑学ショート動画を、ローカル環境で半自動生成するためのPythonプロジェクトです。`project.youtube.json` を入力にして、音声、字幕、BGM、縦型MP4、投稿用メタデータ、検証ログを生成します。

現時点では、完全自動投稿ではなく「生成物を作り、手動レビューしてから投稿する」MVPです。

## 現在できること

- `project.youtube.json` / `rendered.youtube.json` のJSON Schema検証
- `voice.style_id` の任意指定と、AivisSpeech生成時のstyle ID優先利用
- `rendered.youtube.json` の音声、映像、字幕、credits、validation、manual_review構造の厳密検証
- SQLite DB初期化とproject/render履歴の保存
- AivisSpeech API連携、またはdry-run無音WAV生成
- WAVの実測時間に基づく字幕タイミング生成
- ローカルBGM manifestのimport、条件選定、FFmpegでのBGMミックス
- ローカル映像素材manifestのimport、条件選定、FFmpeg背景動画化
- Pexels APIの疎通確認、動画検索、download、SQLite素材キャッシュ登録
- FFmpegによる 1080x1920 / H.264 / AAC のMP4生成
- Docker ComposeによるPythonアプリとAivisSpeech Engine APIサーバーの起動定義
- CLIエラーの `Error`, `Location`, `Details`, `Next step` 形式での表示
- `--debug` 指定時のtraceback表示

未実装または今後の実装対象:

- 複数映像素材のタイムライン合成
- thumbnail.jpg生成
- 手動レビュー状態更新CLI
- YouTube upload / Analytics連携

## セットアップ

このリポジトリでは、ユーザー作成済みの仮想環境 `.venv` を使います。

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

FFmpegは `winget` などでインストールし、PATHに入れるか `--ffmpeg-path` で `ffmpeg.exe` のフルパスを渡します。

Dockerを使う場合はDocker Desktopを入れます。

```powershell
winget install -e --id Docker.DockerDesktop --accept-package-agreements --accept-source-agreements
docker --version
docker compose version
```

Windowsで `permission denied while trying to connect to the docker API at npipe:////./pipe/dockerDesktopLinuxEngine` が出る場合は、ユーザーが `docker-users` グループに入ったあと、Windowsのサインアウト/サインインでログオントークンを更新してください。

この作業環境では Docker Desktop 4.78.0、Docker CLI 29.5.3、Docker Compose v5.1.4 で確認しています。

## 主なコマンド

```powershell
.\.venv\Scripts\python.exe -m src.main init-db
.\.venv\Scripts\python.exe -m src.main validate-project projects\trivia_submarine_black_001\project.youtube.json
.\.venv\Scripts\python.exe -m src.main import-bgm assets\bgm\bgm_manifest.json
.\.venv\Scripts\python.exe -m src.main list-bgm
.\.venv\Scripts\python.exe -m src.main import-media assets\local_media\media_manifest.json
.\.venv\Scripts\python.exe -m src.main check-pexels "deep ocean" --per-page 1
.\.venv\Scripts\python.exe -m src.main fetch-pexels projects\trivia_submarine_black_001\project.youtube.json --per-query 1 --max-downloads 1
.\.venv\Scripts\python.exe -m src.main list-assets
.\.venv\Scripts\python.exe -m src.main render projects\trivia_submarine_black_001\project.youtube.json --video-mode ffmpeg --ffmpeg-path "C:\path\to\ffmpeg.exe"
.\.venv\Scripts\python.exe -m src.main validate-render renders\trivia_submarine_black_001\rendered.youtube.json
```

AivisSpeechを使う場合:

```powershell
.\.venv\Scripts\python.exe -m src.main render projects\trivia_submarine_black_001\project.youtube.json --voice-mode aivis --video-mode ffmpeg --ffmpeg-path "C:\path\to\ffmpeg.exe"
```

接続先を明示する場合は `--aivis-base-url`、または `AIVIS_SPEECH_BASE_URL` を使います。

```powershell
$env:AIVIS_SPEECH_BASE_URL = "http://127.0.0.1:10101"
.\.venv\Scripts\python.exe -m src.main render projects\trivia_submarine_black_001\project.youtube.json --voice-mode aivis --video-mode ffmpeg
```

エラーの詳細tracebackを確認したい場合は、サブコマンドの前に `--debug` を付けます。

```powershell
.\.venv\Scripts\python.exe -m src.main --debug render projects\trivia_submarine_black_001\project.youtube.json
```

## スキーマ契約

`project.youtube.json` の `voice.style_id` は任意項目です。指定した場合、AivisSpeechへのリクエストでは `speaker` より `style_id` を優先します。`speaker` は表示名やメモとして残せるため、既存project JSONはそのまま使えます。

```json
{
  "voice": {
    "engine": "aivis_speech",
    "speaker": "まお",
    "style_id": 888753760,
    "speed_scale": 1.0,
    "pitch_scale": 0.0,
    "intonation_scale": 1.0,
    "sentence_gap_ms": 180
  }
}
```

`rendered.youtube.json` は、`audio.narration_files[]`, `visuals[]`, `subtitles.items[]`, `credits.items[]`, `ffmpeg`, `youtube.upload`, `validation.warnings[]`, `validation.errors[]`, `manual_review` の主要フィールドを厳密に検証します。creditsは `type` ではなく `credit_type` に統一しています。

`render` の既定は `--video-mode dry-run` なので、FFmpegを実行しない検証用renderになります。実MP4生成では `--video-mode ffmpeg` を指定してください。

## BGM manifest

`import-bgm` は以下のようなJSONを読みます。音源ファイルはmanifestからの相対パス、または絶対パスで指定できます。

```json
{
  "tracks": [
    {
      "track_id": "generated_mystery_low",
      "file_path": "generated_mystery_low.wav",
      "title": "Generated Mystery Low",
      "artist": "Trivia Shorts Maker",
      "source": "local_original",
      "license_type": "local_safe",
      "attribution_required": false,
      "attribution_text": "BGM: Generated Mystery Low by Trivia Shorts Maker",
      "mood": "mysterious",
      "intensity": "low",
      "duration_sec": 24.0,
      "bpm": 72,
      "loopable": true,
      "allowed_platforms": ["youtube_shorts"]
    }
  ]
}
```

## 映像素材manifest

`import-media` はローカル動画ファイルをDBへ登録します。ファイルパスはmanifestからの相対パス、または絶対パスで指定できます。`render` は `project.youtube.json` の `visual_query` に近い素材を選び、最初に選定された動画をFFmpeg背景としてループ利用します。

```json
{
  "assets": [
    {
      "asset_id": "deep_sea_loop_001",
      "source": "local",
      "query": "deep sea submarine",
      "local_file_path": "deep_sea_loop_001.mp4",
      "orientation": "portrait",
      "original_duration_sec": 12.0,
      "original_width": 1080,
      "original_height": 1920,
      "selected_quality": "original",
      "license_type": "local_safe",
      "attribution_required": false,
      "attribution_text": "Video: local original footage"
    }
  ]
}
```

## Pexels素材取得

Pexels APIキーは `.env` に `PEXELS_API_KEY=...` として設定します。`.env` はGit管理しません。

疎通確認:

```powershell
.\.venv\Scripts\python.exe -m src.main check-pexels "deep ocean" --per-page 1
```

project JSONから `visual_strategy.primary_query`, `script[].visual_query`, `visual_strategy.fallback_queries` を集め、重複を除いて検索・download・DB登録します。

```powershell
.\.venv\Scripts\python.exe -m src.main fetch-pexels projects\trivia_submarine_black_001\project.youtube.json --per-query 1 --max-downloads 1
.\.venv\Scripts\python.exe -m src.main list-assets
```

download先は `assets/pexels/` です。登録後のrenderは、既存の `media_assets` 選定経路からPexels素材を選びます。API制限やネットワーク失敗でrender全体が止まることを避けるため、現時点ではrender中に自動検索せず、先に `fetch-pexels` でキャッシュしておく運用です。

## Docker / AivisSpeech Engine

AivisSpeechのAPIサーバーは `AivisSpeech-Engine` です。ローカルcloneからbuildしたい場合は、リポジトリ直下にcloneします。このディレクトリは `.gitignore` 対象です。

```powershell
git clone https://github.com/Aivis-Project/AivisSpeech-Engine.git AivisSpeech-Engine
```

公式CPUイメージを使う場合:

```powershell
docker compose --profile aivis up -d aivis-engine
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:10101/version
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:10101/speakers
docker compose run --rm app render projects/trivia_submarine_black_001/project.youtube.json --voice-mode aivis --video-mode ffmpeg
```

cloneした `AivisSpeech-Engine` からbuildする場合:

```powershell
docker compose -f docker-compose.yml -f docker-compose.aivis-build.yml --profile aivis up -d --build aivis-engine
```

AivisSpeech Engineのモデルやログは `data/aivis-engine/` に保存されます。初回起動時は既定モデルのダウンロードとBERT読み込みで時間がかかります。

## 生成される主なファイル

`render` は `renders/{project_id}/` に以下を生成します。

- `output.mp4`
- `rendered.youtube.json`
- `description.txt`
- `credits.txt`
- `subtitle.ass`
- `audio/001.wav` などの文単位音声
- `audio/narration.wav`
- `audio/final_audio.wav`
- `logs/ffmpeg_command.txt`
- `logs/ffmpeg_stderr.log`

`renders/`, `data/*.db`, `data/aivis-engine/`, `assets/bgm/`, `assets/pexels/`, `assets/fonts/`, `assets/local_media/` は生成物またはローカル素材置き場として `.gitignore` 対象です。

## 検証

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format . --check
```

現在のテストは、JSON検証、CLIエラー表示、AivisSpeechクライアント、音声結合、BGM登録/選定、ローカル映像素材登録/選定、Pexels APIクライアント、Docker Compose設定、FFmpegコマンド生成、レンダーパイプラインを対象にしています。
