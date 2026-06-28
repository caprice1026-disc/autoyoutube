# エラーハンドリング強化とBGM統合

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

この計画はリポジトリ直下の `PLANS.md` に従って管理する。作業ディレクトリは `C:\Users\Hodaka\Downloads\div\autoyoutube` であり、検証コマンドはユーザーが作成した `.venv` の `.\.venv\Scripts\python.exe` を使う。

## Purpose / Big Picture

この変更により、利用者は CLI 実行時に Python の長い traceback ではなく、何が失敗したか、どのファイルや設定を直せばよいか、次に何をすべきかを読めるようになる。そのうえで、YouTube Shorts 用の安全なローカル BGM を登録し、project JSON の `bgm` 条件に合う曲を選び、FFmpeg で narration と小音量 BGM を合成できるようにする。結果として、`render --video-mode ffmpeg` は無音またはナレーションだけの動画から、BGM 付きの検査可能な mp4 へ進む。

## Progress

- [x] (2026-06-28 21:55 JST) 現状の CLI、render pipeline、FFmpeg renderer、DB schema を確認した。
- [x] (2026-06-28 22:00 JST) 本 ExecPlan を `.agent/20260628_error_handling_and_bgm.md` として作成した。
- [ ] 共通エラー型と CLI 表示のテストを追加し、失敗を確認する。
- [ ] 共通エラー型 `src/errors.py` と CLI の捕捉/表示を実装する。
- [ ] BGM トラックのデータ型、manifest 読み込み、選曲のテストを追加し、失敗を確認する。
- [ ] `src/bgm` モジュールと `import-bgm` / `list-bgm` CLI を実装する。
- [ ] FFmpeg audio mix のテストを追加し、失敗を確認する。
- [ ] `render_project` と FFmpeg renderer に BGM 選曲とミックスを組み込む。
- [ ] `.venv` で全テスト、CLI エラー表示、BGM 付き render を検証する。

## Surprises & Discoveries

- Observation: 現在の `src/main.py` は `render_project` や `FfmpegVideoRenderer` の例外を捕捉していない。
  Evidence: `main()` 内で `render_project(...)` を直接呼んでおり、`try/except` がない。
- Observation: DB schema にはすでに `bgm_tracks` と `render_bgm_usage` が存在する。
  Evidence: `db/schema.sql` に BGM ライブラリと rendered BGM 用テーブルが定義されている。

## Decision Log

- Decision: エラー表示は `AppError` という共通例外に寄せ、CLI では `Error: ...`、`Location: ...`、`Next step: ...` を表示する。
  Rationale: 利用者が修正すべきファイル、環境変数、外部コマンドをすぐ判断できる形にするため。予期しない例外は引き続き簡潔に表示し、`--debug` で traceback を出す。
  Date/Author: 2026-06-28 / Codex
- Decision: 続きの機能は Pexels より先に BGM を実装する。
  Rationale: Pexels は API キーと外部ネットワークに依存する一方、BGM はローカルファイルと manifest だけで TDD と実生成まで検証できる。先に音声ミックスを作ると、後続の Pexels 映像素材合成でも FFmpeg pipeline を再利用できる。
  Date/Author: 2026-06-28 / Codex
- Decision: BGM 登録は音声ファイル横の `bgm.json` manifest を読む方式にする。
  Rationale: MP3/WAV のメタタグは不安定で、YouTube Audio Library の権利表記や mood/intensity を自動推測するのは危険である。manifest で権利情報を明示するほうが安全で再現性が高い。
  Date/Author: 2026-06-28 / Codex

## Outcomes & Retrospective

未完了。完了時に、pytest、CLI エラー表示、BGM 登録、BGM 付き FFmpeg render、rendered JSON の BGM 情報を記録する。

## Context and Orientation

CLI の入口は `src/main.py` で、`render`、`validate-project`、`validate-render`、`init-db` を提供している。`src/pipeline/render_project.py` は project JSON の検証、音声生成、字幕生成、FFmpeg video render を担当する。`src/render/ffmpeg_renderer.py` は FFmpeg コマンドの作成と実行を担当する。DB は `src/db/database.py` で接続し、`src/db/repositories.py` が project と render summary を保存する。

BGM は background music の略で、ナレーションの背後に小さな音量で流す音楽である。この計画では `assets/bgm` のようなローカルフォルダに安全な音声ファイルと `bgm.json` を置き、SQLite の `bgm_tracks` に登録する。render 時には project JSON の `bgm.mood`、`bgm.intensity`、`bgm.allow_sources`、`bgm.avoid` に合う曲を選ぶ。選んだ曲は FFmpeg で `final_audio.wav` にミックスし、ナレーションを聞き取りやすくするため project JSON の `bgm.volume_db`、`fade_in_ms`、`fade_out_ms` を使う。

## Plan of Work

最初にエラーハンドリングを実装する。`tests/test_cli_errors.py` で、存在しない project JSON を validate したときに `Error:`、`Location:`、`Next step:` を含む表示になることを固定する。`src/errors.py` には `AppError` を定義し、各モジュールで利用者が直せる失敗をこれに変換する。CLI は `--debug` がない場合は traceback を出さず、終了コード 1 を返す。

次に BGM manifest と選曲を実装する。`tests/test_bgm_library.py` で `bgm.json` からトラックを読み、条件に合う曲が選ばれること、条件に合う曲がない場合は読みやすい `AppError` になることをテストする。DB 永続化は既存 schema の `bgm_tracks` を使い、最小限の repository 関数を追加する。

最後に FFmpeg の BGM ミックスを組み込む。`tests/test_ffmpeg_renderer.py` に BGM 入力がある場合の filter_complex を追加し、`render_project` が選曲結果を `rendered.youtube.json` の `bgm` と `credits` に反映することをテストする。実生成では、BGM が登録されていない場合は明確なエラーを出すか、project の `bgm.enabled` を false にするよう案内する。

## Concrete Steps

作業は必ず `.venv` を使う。

    .\.venv\Scripts\python.exe -m pytest tests/test_cli_errors.py -q
    .\.venv\Scripts\python.exe -m pytest tests/test_bgm_library.py -q
    .\.venv\Scripts\python.exe -m pytest tests/test_ffmpeg_renderer.py tests/test_render_project_ffmpeg.py -q
    .\.venv\Scripts\python.exe -m pytest -q

実生成確認では、テスト用の短い BGM WAV を workspace 内に生成し、`import-bgm` で登録してから `render --video-mode ffmpeg` を実行する。

## Validation and Acceptance

受け入れ条件は、`.venv` で全テストが通ること、存在しない JSON や FFmpeg 未検出などの利用者起因エラーが traceback ではなく修正指示付きの短いエラーになること、BGM manifest を登録できること、BGM が選ばれた render の `rendered.youtube.json` に `bgm.enabled=true` と credit が入ること、FFmpeg 実生成が成功することである。

## Idempotence and Recovery

`import-bgm` は同じ `track_id` を再登録しても `INSERT OR REPLACE` で更新する。render は `renders/{project_id}` の成果物を上書きできる。BGM が見つからない場合は project JSON の `bgm.enabled` を false にするか、`bgm.json` を直して再 import する。FFmpeg が見つからない場合は `--ffmpeg-path` か `FFMPEG_PATH` を使う。

## Artifacts and Notes

完了時に検証出力を追記する。

## Interfaces and Dependencies

`src/errors.py` は `AppError(message, location=None, next_step=None, details=None)` を提供する。`src/bgm/library.py` は manifest 読み込みと `BgmTrack` を提供する。`src/bgm/selector.py` は `select_bgm_track(project_bgm, tracks)` を提供する。`src/db/repositories.py` は `upsert_bgm_tracks` と `list_active_bgm_tracks` を提供する。`src/render/ffmpeg_renderer.py` は BGM 入力がある場合に narration と BGM を `filter_complex` でミックスする。

## Plan Revision Notes

2026-06-28 / Codex: ユーザーが「続きの前にエラーハンドリングをしっかり」と明示したため、本 ExecPlan を作成した。
