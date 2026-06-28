# Pexels API検索・ダウンロード・素材キャッシュ連携

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

この計画はリポジトリ直下の `PLANS.md` に従って管理する。作業ディレクトリは `C:\Users\Hodaka\Downloads\div\autoyoutube` で、Pythonコマンドはユーザーが作成済みの `.\.venv\Scripts\python.exe` を使う。

## Purpose / Big Picture

この変更により、ユーザーは `.env` に設定した `PEXELS_API_KEY` を使ってPexels APIへ接続し、`project.youtube.json` の映像検索語からYouTube Shorts向けの動画素材を検索、ダウンロード、SQLiteへキャッシュできるようになる。既存のローカル映像素材選定とFFmpeg背景動画化の流れにPexels素材を投入するため、render処理はDBに登録済みのPexels素材を既存の `media_assets` から選ぶだけでよい。

## Progress

- [x] (2026-06-28 22:21 JST) `.env` に `PEXELS_API_KEY` が存在することを、値を表示せず確認した。
- [x] (2026-06-28 22:22 JST) Pexels APIへ `deep ocean` のportrait動画検索を実行し、HTTP 200と動画1件の応答を確認した。
- [x] (2026-06-28 22:30 JST) Pexelsクライアント、`.env` 読み込み、CLIの失敗テストを追加し、未実装エラーで失敗することを確認した。
- [x] (2026-06-28 22:36 JST) Pexels API検索結果から `MediaAsset` を作成し、動画ファイルを `assets/pexels/` に保存する実装を追加した。
- [x] (2026-06-28 22:39 JST) `fetch-pexels` と `check-pexels` CLIを追加し、DB登録まで接続した。
- [x] (2026-06-28 22:45 JST) README、dev_memo、`.env.example` を更新した。
- [x] (2026-06-28 22:48 JST) Ruff、pytest、実APIの検索疎通、download/DB登録コマンドを再実行した。

## Surprises & Discoveries

- Observation: Pexels公式ドキュメントでは動画APIの新しいベースパスは `https://api.pexels.com/v1/videos/` で、古い `https://api.pexels.com/videos/` は将来deprecatedになる。
  Evidence: 公式APIドキュメントにその注意書きがある。

- Observation: `.env` のAPIキーで `https://api.pexels.com/v1/videos/search?query=deep%20ocean&per_page=1&orientation=portrait` へ接続できた。
  Evidence: `status=200 total_results=8000 returned=1 first_id=20349819 width=2160 height=3840 files=7`。

- Observation: Python標準ライブラリ `urllib` の既定User-AgentではPexels APIがHTTP 403を返したが、`User-Agent: TriviaShortsMaker/0.1` を付けるとHTTP 200になった。
  Evidence: User-Agentなしの `urllib.request.urlopen()` は `HTTPError 403 Forbidden`、User-Agentありでは `OK 200`。

## Decision Log

- Decision: Pexels取得はまず `fetch-pexels` CLIでDBへ素材を登録し、renderは既存の `media_assets` 選定経路を使う。
  Rationale: render中に外部APIを直接呼ぶと、ネットワーク失敗やAPI制限で動画生成全体が不安定になる。先に素材をキャッシュする形にすれば、Pexels失敗時もローカル素材や既存キャッシュで運用できる。
  Date/Author: 2026-06-28 / Codex

- Decision: HTTP実装は既存のAivisSpeechクライアントと同じく標準ライブラリ `urllib` を使い、テストではtransportを差し替える。
  Rationale: 新しい外部依存を増やさず、現行コードの実装スタイルに合わせる。transportを差し替えれば、APIキーやネットワークなしで検索・download処理をテストできる。
  Date/Author: 2026-06-28 / Codex

- Decision: Pexels APIへのHTTPリクエストには `User-Agent: TriviaShortsMaker/0.1` を必ず付ける。
  Rationale: Pexels側がPython標準の既定User-Agentを拒否するケースがあり、実API疎通確認でHTTP 403が再現したため。
  Date/Author: 2026-06-28 / Codex

## Outcomes & Retrospective

`check-pexels` で `.env` の `PEXELS_API_KEY` を使った検索疎通ができるようになった。`fetch-pexels` はproject JSONから検索語を集め、1件ずつPexels動画をdownloadし、`media_assets` へPexelsメタデータ付きで登録できる。dry-run renderでは登録済みPexels素材が選ばれ、`rendered.youtube.json.visuals[0]` に `source=pexels`, `asset_id`, `pexels_id`, `local_file_path` が残ることを確認した。render中の自動Pexels検索や文ごとの素材切り替えは後続課題として残る。

## Context and Orientation

現在の映像素材の中心は `src/media/library.py` の `MediaAsset` である。`src/db/repositories.py` は `media_assets` テーブルへ登録済み素材を保存し、`src/pipeline/render_project.py` は `list_active_media_assets()` で取得した素材から `src/media/selector.py` の `select_media_asset()` を使って文ごとの素材を選ぶ。`src/render/ffmpeg_renderer.py` は最初に選ばれた素材の `local_file_path` を背景動画として使う。

Pexels APIとは、Pexelsが提供するHTTP JSON APIである。動画検索では `GET https://api.pexels.com/v1/videos/search` に `query`, `orientation`, `size`, `per_page` などを付け、HTTPヘッダー `Authorization` にAPIキーを入れる。応答には動画ID、撮影者、PexelsページURL、複数品質の動画ファイルURLが含まれる。

## Plan of Work

まず `src/env.py` を追加し、`.env` から `PEXELS_API_KEY` を `os.environ` へ読み込む小さな関数を作る。次に `src/media/pexels_client.py` を追加し、Pexels検索、動画ファイル選択、download、`MediaAsset` への変換を行う。`MediaAsset` にはPexelsメタデータ用の任意フィールドを追加し、既存ローカル素材のテストが壊れないようデフォルト値を持たせる。

`src/db/repositories.py` は `media_assets` のPexels列をINSERT/SELECTするように拡張する。`src/pipeline/render_project.py` の `visuals` 生成では、選ばれたPexels素材の `pexels_id`, `photographer`, `photographer_url`, `pexels_url`, `original_video_url` を `rendered.youtube.json` に残す。

`src/main.py` には `check-pexels` と `fetch-pexels` を追加する。`check-pexels` は検索だけを行い、疎通確認と検索結果数を出す。`fetch-pexels` はproject JSONの `script[].visual_query`, `visual_strategy.primary_query`, `visual_strategy.fallback_queries` を重複排除して検索し、選んだ動画を `assets/pexels/` に保存し、DBへ登録する。

## Concrete Steps

作業はすべてリポジトリ直下で行う。

    .\.venv\Scripts\python.exe -m pytest -q tests\test_pexels_client.py tests\test_cli_pexels.py
    .\.venv\Scripts\python.exe -m pytest -q
    .\.venv\Scripts\python.exe -m ruff check .
    .\.venv\Scripts\python.exe -m ruff format . --check
    .\.venv\Scripts\python.exe -m src.main check-pexels "deep ocean" --per-page 1

実APIのdownload確認は、API制限とファイルサイズを抑えるため1件だけ行う。

    .\.venv\Scripts\python.exe -m src.main fetch-pexels projects\trivia_submarine_black_001\project.youtube.json --per-query 1 --max-downloads 1

## Validation and Acceptance

`check-pexels` は `.env` の `PEXELS_API_KEY` を読み、APIキーを表示せずに `Pexels search succeeded` と検索件数を表示する。`fetch-pexels` は `assets/pexels/` にmp4を保存し、`media_assets` へ `source='pexels'` の行を登録する。`list-assets` でPexels素材が表示され、以後のrenderでは `source_priority` が `pexels` を含むprojectでPexels素材が選定される。

全テストは `.\.venv\Scripts\python.exe -m pytest -q` で成功する。Ruffの静的解析とformat checkも成功する。

## Idempotence and Recovery

`fetch-pexels` は同じPexels video IDとqueryから作る `asset_id` を再登録してもupsertされる。既にdownload済みのファイルがあれば再downloadしない。APIキーがない場合やHTTPエラーの場合は `AppError` で、`.env` の設定またはAPI制限を確認する手順を表示する。生成される `assets/pexels/` と `data/*.db` は `.gitignore` 対象なので、削除して再実行できる。

## Artifacts and Notes

現時点の疎通確認結果:

    status=200 total_results=8000 returned=1
    first_id=20349819 width=2160 height=3840 files=7

実装後の検証結果:

    .\.venv\Scripts\python.exe -m pytest -q
    41 passed in 1.12s

    .\.venv\Scripts\python.exe -m ruff check .
    All checks passed!

    .\.venv\Scripts\python.exe -m ruff format . --check
    44 files already formatted

    .\.venv\Scripts\python.exe -m src.main check-pexels "deep ocean" --per-page 1
    Pexels search succeeded: query=deep ocean returned=1
    first_id=20349819 width=2160 height=3840 files=7

    .\.venv\Scripts\python.exe -m src.main fetch-pexels projects\trivia_submarine_black_001\project.youtube.json --per-query 1 --max-downloads 1
    Fetched Pexels assets: 1
    pexels_37665801_deep_ocean_submarine deep ocean submarine assets\pexels\pexels_37665801_deep_ocean_submarine.mp4

## Interfaces and Dependencies

`src.env.load_dotenv(path: Path = Path(".env")) -> None` は、既存の環境変数を上書きせず `.env` を読む。

`src.media.pexels_client.PexelsClient(api_key: str | None = None, transport: PexelsTransport | None = None)` は、`search_videos(query: str, per_page: int, orientation: str | None, size: str | None) -> list[dict[str, Any]]` と `fetch_assets_for_queries(queries: list[str], output_dir: Path, per_query: int, max_downloads: int | None) -> list[MediaAsset]` を提供する。

`src.main` は `check-pexels` と `fetch-pexels` サブコマンドを提供する。

## Plan Revision Notes

2026-06-28 / Codex: ユーザーが `.env` に `PEXELS_API_KEY` を設定し、疎通確認と続きの実装を依頼したため、本ExecPlanを追加した。
