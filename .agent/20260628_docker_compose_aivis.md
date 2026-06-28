# AivisSpeech Dockerサーバー前提のdocker-compose対応

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

この計画はリポジトリ直下の `PLANS.md` に従って管理する。作業ディレクトリは `C:\Users\Hodaka\Downloads\div\autoyoutube` で、Pythonコマンドはユーザーが作成済みの `.\.venv\Scripts\python.exe` を使う。

## Purpose / Big Picture

この変更により、AivisSpeech EngineをDocker上のHTTPサーバーとして起動し、Trivia Shorts Maker本体もDocker Compose内からそのサーバーへ接続できるようになる。ローカル実行ではこれまで通り `http://127.0.0.1:10101` を使い、Compose内ではサービス名 `aivis-engine` を使って `http://aivis-engine:10101` へ接続する。これにより、最終的にFFmpeg、Python実行環境、AivisSpeechサーバーをdocker-composeに寄せるための足場ができる。

## Progress

- [x] (2026-06-28 21:05 JST) `AivisSpeech` ディレクトリを確認し、現在のgitlinkはAivisSpeechアプリ側であり、APIサーバー本体はAivisSpeech Engineとして別扱いであることを確認した。
- [x] (2026-06-28 21:08 JST) AivisSpeech clientが `AIVIS_SPEECH_BASE_URL` を読むテストと、CLIが `--aivis-base-url` を渡すテストを追加し、失敗を確認した。
- [x] (2026-06-28 21:10 JST) `Dockerfile`, `.dockerignore`, `docker-compose.yml`, `docker-compose.aivis-build.yml` の存在と内容をテスト化し、失敗を確認した。
- [x] (2026-06-28 21:14 JST) Aivis base URLの環境変数対応、CLI引数、Dockerfile、composeを実装した。
- [x] (2026-06-28 21:17 JST) `.\.venv\Scripts\python.exe -m pytest -q` で `33 passed` を確認した。
- [x] (2026-06-28 21:28 JST) `https://github.com/Aivis-Project/AivisSpeech-Engine` を `AivisSpeech-Engine/` にcloneした。
- [x] (2026-06-28 21:35 JST) Docker Desktopをwingetで導入し、Docker CLIとDocker Composeのversionを確認した。
- [x] (2026-06-28 21:40 JST) `ghcr.io/aivis-project/aivisspeech-engine:cpu-latest` を起動し、`/version`, `/speakers`, アプリ側 `AivisSpeechClient.synthesize_to_file()` の疎通を確認した。
- [x] (2026-06-28 21:42 JST) `docker compose --profile aivis config` とbuild overrideのconfigを確認した。
- [x] (2026-06-28 21:47 JST) 外部cloneのtestsをpytestが収集しないよう `pytest.ini` を追加し、`.\.venv\Scripts\python.exe -m pytest -q` で `34 passed` を確認した。
- [x] (2026-06-28 21:56 JST) Ruffを導入し、`ruff check . --fix`, `ruff format .`, `ruff check .`, `ruff format . --check`, pytestを順に実行した。

## Surprises & Discoveries

- Observation: `AivisSpeech` はこのリポジトリではgitlinkであり、`Dockerfile` は含まれていなかった。
  Evidence: `git ls-tree HEAD AivisSpeech` は mode `160000` を返し、`Get-ChildItem -Recurse -Filter Dockerfile AivisSpeech` は空だった。

- Observation: AivisSpeechアプリREADMEはAPI hostとして `http://127.0.0.1:10101` を示している。
  Evidence: `AivisSpeech\README.md` に `host: "http://127.0.0.1:10101"` が記載されている。

- Observation: 公式AivisSpeech EngineのCPUイメージは初回起動時に既定モデルをダウンロードし、その後APIが起動する。
  Evidence: `docker logs autoyoutube-aivis-test` に既定モデル2件のdownload/install、BERT読み込み、`Uvicorn running on http://0.0.0.0:10101` が出力された。

- Observation: 現在のWindowsログオンセッションでは通常権限のDocker Engine接続が拒否されるが、Docker DesktopとCLI自体は導入済みである。
  Evidence: 通常権限の `docker info` は `permission denied while trying to connect to the docker API at npipe:////./pipe/dockerDesktopLinuxEngine`、昇格時の `docker info --format '{{.ServerVersion}}'` は `29.5.3` を返した。

## Decision Log

- Decision: Python側のAivis接続先は `AIVIS_SPEECH_BASE_URL` 環境変数で切り替える。
  Rationale: ホスト実行では `127.0.0.1`、Compose内ではDocker DNSのサービス名 `aivis-engine` が必要になる。コードに固定値を増やすより、環境変数とCLI引数で上書き可能にするほうが安全である。
  Date/Author: 2026-06-28 / Codex

- Decision: `docker-compose.yml` の `aivis-engine` は `AIVIS_ENGINE_IMAGE` で差し替えられるimageサービスにし、ローカルcloneからbuildする場合は `docker-compose.aivis-build.yml` を重ねる。
  Rationale: 現在の `AivisSpeech` gitlinkにはDockerfileがないため、無条件に `./AivisSpeech` からbuildすると失敗する。image指定とbuild overrideを分けることで、ユーザーの実際のEngine Docker構成に合わせやすくする。
  Date/Author: 2026-06-28 / Codex

## Outcomes & Retrospective

`AivisSpeechClient` は `AIVIS_SPEECH_BASE_URL` を読み、CLIの `render` は `--aivis-base-url` で明示的に接続先を渡せるようになった。DockerfileはPython実行環境とFFmpegを含み、docker-composeは `app` と `aivis-engine` のサービスを定義した。`AivisSpeech-Engine/` はGitHubからclone済みで、公式CPUイメージ `ghcr.io/aivis-project/aivisspeech-engine:cpu-latest` のAPI疎通とアプリ側クライアントの短文合成まで確認した。
外部cloneである `AivisSpeech-Engine/` がpytest収集対象になるとEngine側の開発依存に引っ張られるため、このプロジェクトのテスト範囲を `pytest.ini` で `tests/` に限定した。

## Context and Orientation

AivisSpeech連携の実装は `src/voice/aivis_client.py` にある。CLIの `render --voice-mode aivis` は `src/main.py` で `AivisSpeechClient` を作成し、`src/pipeline/render_project.py` に渡す。Docker化では、`Dockerfile` がこのPythonアプリをコンテナ化し、`docker-compose.yml` がアプリとAivisSpeech Engineサーバーを同じDockerネットワークへ置く。

## Plan of Work

`AivisSpeechClient` のデフォルト接続先を環境変数から読むように変更する。`src/main.py` の `render` サブコマンドに `--aivis-base-url` を追加し、必要なら環境変数よりもCLI引数を優先できるようにする。DockerfileではPython 3.13 slimを使い、FFmpegをaptでインストールし、`ENTRYPOINT ["python", "-m", "src.main"]` とする。Composeでは `AIVIS_SPEECH_BASE_URL` を `http://aivis-engine:10101` に設定し、ホストからも `10101:10101` でEngineへアクセスできるようにする。

## Concrete Steps

実行した検証コマンド:

    .\.venv\Scripts\python.exe -m pytest -q tests\test_aivis_client.py tests\test_cli_aivis_config.py tests\test_docker_compose.py
    .\.venv\Scripts\python.exe -m pytest -q

ComposeでAivisSpeech Engine imageを使う場合の例:

    docker compose --profile aivis up -d aivis-engine
    Invoke-WebRequest -UseBasicParsing http://127.0.0.1:10101/version
    Invoke-WebRequest -UseBasicParsing http://127.0.0.1:10101/speakers
    docker compose run --rm app render projects/trivia_submarine_black_001/project.youtube.json --voice-mode aivis --video-mode ffmpeg

Engine cloneからbuildする場合は、Engine側にDockerfileがあることを確認し、必要に応じて次を使う:

    docker compose -f docker-compose.yml -f docker-compose.aivis-build.yml --profile aivis up -d --build aivis-engine

## Validation and Acceptance

`.\.venv\Scripts\python.exe -m pytest -q` が成功すること。`AIVIS_SPEECH_BASE_URL=http://aivis-engine:10101` を設定した `AivisSpeechClient()` がそのURLを使うこと。`render --voice-mode aivis --aivis-base-url http://aivis-engine:10101` が作成したclientへURLを渡すこと。`Dockerfile` と `docker-compose.yml` により、PythonアプリはCompose内で `aivis-engine` サービス名を参照できること。ホストから `http://127.0.0.1:10101/version` と `/speakers` へ到達でき、`AivisSpeechClient.synthesize_to_file()` がWAVを生成できること。

## Idempotence and Recovery

Docker生成物はリポジトリに保存しない。Engine image名やbuild contextが環境に合わない場合は、`AIVIS_ENGINE_IMAGE` または `AIVIS_ENGINE_CONTEXT` を変更して再実行する。ホスト実行へ戻す場合は `AIVIS_SPEECH_BASE_URL` を未設定にするか、`--aivis-base-url http://127.0.0.1:10101` を渡す。

## Artifacts and Notes

`docker-compose.yml` は既定で公式CPUイメージ `ghcr.io/aivis-project/aivisspeech-engine:cpu-latest` を使う。GPUやローカルbuildへ切り替える場合は `AIVIS_ENGINE_IMAGE` または `docker-compose.aivis-build.yml` を使う。`AivisSpeech-Engine/` はclone済みだが、外部リポジトリなので `.gitignore` 対象にしている。

## Interfaces and Dependencies

`src.voice.aivis_client.AivisSpeechClient(base_url: str | None = None)` は、`base_url` が指定された場合はそれを使い、未指定なら `AIVIS_SPEECH_BASE_URL`、それもなければ `http://127.0.0.1:10101` を使う。`src.main` の `render` は `--aivis-base-url` を受け付ける。`docker-compose.yml` の `app` サービスは `AIVIS_SPEECH_BASE_URL` を `http://aivis-engine:10101` として渡す。

## Plan Revision Notes

2026-06-28 / Codex: ユーザーがAivisSpeechをDockerサーバーとして起動する想定と、最終的なdocker-compose化を明示したため、本ExecPlanを追加した。
