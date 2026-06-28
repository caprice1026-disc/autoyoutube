# ローカル映像素材の登録・選定・FFmpeg背景化

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

この計画はリポジトリ直下の `PLANS.md` に従って管理する。作業ディレクトリは `C:\Users\Hodaka\Downloads\div\autoyoutube` で、Pythonコマンドはユーザーが作成済みの `.\.venv\Scripts\python.exe` を使う。

## Purpose / Big Picture

この変更により、ユーザーはPexels APIキーがなくてもローカルに置いた映像素材をmanifestから登録し、`project.youtube.json` の `visual_query` に合う素材を選んで、FFmpeg生成動画の背景として使えるようになる。今は単色背景のMP4生成までできているが、実際の映像素材を使う経路がない。ローカル素材でDB登録、選定、FFmpeg入力、`rendered.youtube.json` の記録を先に作ることで、後続のPexels API取得を同じ `media_assets` テーブルと選定処理へ差し込める。

## Progress

- [x] (2026-06-28 20:44 JST) 現状READMEを更新し、BGMとFFmpeg実生成までの操作を整理した。
- [x] (2026-06-28 20:45 JST) 本ExecPlanを作成した。
- [x] (2026-06-28 21:00 JST) ローカル映像素材manifestの読み込み、DB登録、条件選定の失敗テストを追加した。
- [x] (2026-06-28 21:02 JST) `src/media` モジュールと `import-media` / `list-assets` CLI を実装した。
- [x] (2026-06-28 21:04 JST) `render_project` が選定した素材を `rendered.youtube.json` の `visuals` に反映するようにした。
- [x] (2026-06-28 21:05 JST) FFmpeg renderer がローカル映像素材を背景入力として受け取り、9:16へクロップまたはスケールして出力するようにした。
- [x] (2026-06-28 21:43 JST) READMEを最終更新し、Docker/AivisSpeech Engineの検証結果も反映した。
- [x] (2026-06-28 21:47 JST) `.\.venv\Scripts\python.exe -m pytest -q` で `34 passed` を確認した。
- [x] (2026-06-28 21:56 JST) `ruff check . --fix` と `ruff format .` を実行し、`ruff check .` / `ruff format . --check` / pytestで再検証した。

## Surprises & Discoveries

- Observation: DB schemaには既に `media_assets` と `render_visual_items` があるため、新しい永続化先を作る必要はない。
  Evidence: `db/schema.sql` に素材キャッシュ用テーブルとrender visual item用テーブルが定義済み。

## Decision Log

- Decision: Pexels API本体ではなく、まずローカル映像素材manifestを実装する。
  Rationale: PexelsはAPIキーとネットワーク状態に依存する。一方、ローカル素材はテストと実生成を完全にローカルで検証でき、DBスキーマ、選定、FFmpeg合成の土台を先に固められる。
  Date/Author: 2026-06-28 / Codex

- Decision: 初期実装では、script itemごとに選定した素材情報を `rendered.youtube.json` に残し、FFmpeg背景としては最初の選定素材を動画全体にループ利用する。
  Rationale: 文ごとのタイムライン切り替えはfilter graphが大きくなり、今回の小さな実装単位を超える。まず実映像を背景として使えることを実証し、後続で文単位切り替えに拡張する。
  Date/Author: 2026-06-28 / Codex

## Outcomes & Retrospective

ローカル映像素材のmanifest読み込み、DB登録、選定、CLI、FFmpeg背景入力への接続を実装した。初期実装では、script itemごとの `visuals` に選定素材を記録し、FFmpeg背景としては最初に見つかった選定素材を動画全体へループ適用する。文単位で映像を切り替えるタイムライン合成は後続課題として残した。

## Context and Orientation

CLIの入口は `src/main.py` である。`render_project` は `src/pipeline/render_project.py` にあり、project JSONの検証、音声生成、字幕生成、動画レンダー、`rendered.youtube.json` の作成、DB保存を行う。FFmpegコマンドは `src/render/ffmpeg_renderer.py` で組み立てる。DBアクセスは `src/db/repositories.py` に集約されている。

映像素材とは、Shorts動画の背景に使うMP4などの動画ファイルを指す。DBでは `media_assets` に素材そのものの情報を保存し、render結果では `visuals` 配列と `render_visual_items` に、どのscript itemでどの素材を使ったかを残す。

## Plan of Work

まず `tests/test_media_library.py` を追加し、`media_manifest.json` からローカル映像素材を読み込み、相対パスを絶対パスへ解決し、`MediaAsset` として扱えることを確認する。次にDB round tripを追加し、`upsert_media_assets` と `list_active_media_assets` が既存の `media_assets` テーブルで動くことを確認する。さらに `select_media_asset` が `visual_query` と `source_priority` に基づいて、used_countの低い素材を選ぶことをテストする。

次に `src/media/library.py` と `src/media/selector.py` を追加し、`src/db/repositories.py` に素材登録と一覧取得を追加する。`src/main.py` には `import-media` と `list-assets` を追加する。

最後に `render_project` と `FfmpegVideoRenderer` をつなぐ。`render_project` はscript itemごとに素材を選び、`visuals` の `source`, `local_file_path`, `original_width`, `original_height`, `orientation`, `selected_quality`, `asset_id` を埋める。`FfmpegVideoRenderer` は最初のvisualの `local_file_path` が存在する場合に、単色canvasではなくその動画を `-stream_loop -1 -i` で入力し、1080x1920へ `scale` と `crop` で合わせる。

## Concrete Steps

作業はすべてリポジトリ直下で行う。

    .\.venv\Scripts\python.exe -m pytest -q tests\test_media_library.py
    .\.venv\Scripts\python.exe -m pytest -q tests\test_ffmpeg_renderer.py tests\test_render_project_ffmpeg.py
    .\.venv\Scripts\python.exe -m pytest -q

実生成検証では、FFmpegの `lavfi` で短いローカルMP4素材を `assets/local_media/` に生成し、manifest import後に `render --video-mode ffmpeg` を実行する。

## Validation and Acceptance

受け入れ条件は次のとおりである。`import-media` がmanifestを読み込み、`list-assets` に登録済み素材が表示される。render後の `rendered.youtube.json` の `visuals` には `asset_id` と実在する `local_file_path` が入る。FFmpegコマンドログには単色 `color=` ではなく素材動画入力と `scale/crop` フィルタが入る。`output.mp4` はffprobeで1080x1920のH.264/AACとして確認できる。全テストは `.\.venv\Scripts\python.exe -m pytest -q` で成功する。

## Idempotence and Recovery

`import-media` は同じ `asset_id` を再importしても上書き更新できるようにする。生成物である `assets/local_media/`, `data/*.db`, `renders/` は `.gitignore` 対象なので、必要なら削除して再生成できる。FFmpeg素材が見つからない場合は `AppError` で対象パスと次の修正手順を表示する。

## Artifacts and Notes

追加された主な成果物は `src/media/`, `tests/test_media_library.py`, `tests/test_cli_media.py` である。外部cloneである `AivisSpeech-Engine/` をpytest収集対象から外すため `pytest.ini` も追加した。RuffをrequirementsとREADMEの検証手順に追加した。`ruff check .` と `ruff format . --check` は成功し、`.\.venv\Scripts\python.exe -m pytest -q` は `34 passed` になった。実生成検証はDocker/Aivis対応のREADME更新後にまとめて行う。

## Interfaces and Dependencies

`src/media/library.py` は `MediaAsset` と `load_media_manifest(path: Path) -> list[MediaAsset]` を提供する。`src/media/selector.py` は `select_media_asset(script_item, visual_strategy, assets) -> MediaAsset | None` を提供する。`src/db/repositories.py` は `upsert_media_assets(connection, assets)` と `list_active_media_assets(connection)` を提供する。`src/render/ffmpeg_renderer.py` の `FfmpegRenderRequest` は任意の `background_video_path` を持ち、指定がある場合はその動画を背景に使う。

## Plan Revision Notes

2026-06-28 / Codex: ユーザーがREADME更新、続きの実装、README再更新、GitHub pushを一連で依頼したため、本ExecPlanを作成した。
