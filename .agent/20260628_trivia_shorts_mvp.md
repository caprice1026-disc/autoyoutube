# Trivia Shorts Maker 基盤MVPの実装

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

この計画はリポジトリ直下の `PLANS.md` に従って管理する。作業ディレクトリは `/workspace/autoyoutube`、つまりリポジトリルートである。

## Purpose / Big Picture

この変更により、利用者は ChatGPT が作った `project.youtube.json` をローカルCLIに渡し、JSON Schemaで検証し、SQLiteへ保存し、外部APIやFFmpegを呼ばずに仮の `rendered.youtube.json` と投稿補助ファイルを生成できるようになる。これは YouTube Shorts 向け雑学動画生成パイプラインの最初の土台であり、後続のAivisSpeech、Pexels、BGM、FFmpeg連携を安全に追加するための固定された入出力契約を作る。

## Progress

- [x] (2026-06-28 00:00Z) 既存の `AGENTS.md`、`PLANS.md`、`db/schema.sql`、`.gitignore`、`README.md` を確認した。
- [x] (2026-06-28 00:05Z) `.agent/20260628_trivia_shorts_mvp.md` として日本語のExecPlanを作成した。
- [x] プロジェクト用とレンダーログ用のJSON Schemaを `schemas/` 配下に配置し、ログ用スキーマの明らかなJSON構文ミスを修正する。
- [x] Python CLI、JSON検証、SQLite初期化、project保存、仮render生成を実装する。
- [x] サンプルproject JSONを作成し、CLIで検証・保存・仮render生成を確認する。
- [ ] 変更をコミットし、PR本文を日本語で作成する。

## Surprises & Discoveries

- Observation: 既存の `db/schema.sql` は要件の主要テーブルを既に広く含んでいた。
  Evidence: `youtube_projects`、`youtube_renders`、`render_manual_reviews`、`youtube_metrics_snapshots` などが定義済みだった。

## Decision Log

- Decision: 最初のMVPでは外部API、音声生成、動画生成を行わず、仮成果物ファイルとスキーマ準拠の `rendered.youtube.json` を生成する。
  Rationale: ユーザーの「まずは、外部APIを使わずにJSONを読み、検証し、DBに保存し、仮のrendered JSONを出す」という明示要望に合わせるため。
  Date/Author: 2026-06-28 / Codex

- Decision: CLIは追加依存を避けて `argparse` を使い、JSON Schema検証のみ `jsonschema` を利用する。
  Rationale: 要件で `argparse または typer` とされており、既存リポジトリに依存管理ファイルがないため、標準ライブラリ中心の構成が最も導入しやすい。
  Date/Author: 2026-06-28 / Codex

## Outcomes & Retrospective

外部APIなしの基盤MVPが完了した。残課題は、rendered schemaをユーザー提供版により厳密に近づけること、AivisSpeech/Pexels/BGM/FFmpegの実処理を後続フェーズで追加すること。

## Context and Orientation

現在のリポジトリは小さく、ルートに `README.md`、`PLANS.md`、`AGENTS.md`、`db/schema.sql` が存在する。`db/schema.sql` はSQLite、つまり1ファイルで動く軽量データベース用のテーブル定義である。今回追加する `src/main.py` はCLIの入口で、`python -m src.main <command>` で実行する。`schemas/project.youtube.schema.json` は入力JSONの契約、`schemas/rendered.youtube.schema.json` は出力ログJSONの契約である。

## Plan of Work

まず `schemas/project.youtube.schema.json` にユーザー提供のproject schemaを保存する。次に `schemas/rendered.youtube.schema.json` にユーザー提供のrendered schemaを保存するが、提供文には同じJSONが連結されており、そのままではJSONとして読めないため、1つのJSONオブジェクトとして保存する。また `$defs.path.pattern` はNUL文字を直接入れず、JSON文字列として安全な表現にする。

次に `src/` 配下にCLIと小さなモジュールを追加する。`src/validators/json_validator.py` はJSON読み込みとスキーマ検証を担当する。`src/db/database.py` はSQLite接続と `db/schema.sql` 実行を担当する。`src/db/repositories.py` はproject JSONと仮render JSONを既存スキーマのテーブルへ保存する。`src/pipeline/render_project.py` は外部APIなしの仮レンダーを行い、`renders/{project_id}/` に `subtitle.ass`、`description.txt`、`credits.txt`、ログファイル、`rendered.youtube.json` を出力する。

## Concrete Steps

リポジトリルートで以下を実行する。

    python -m src.main init-db
    python -m src.main validate-project projects/trivia_submarine_black_001/project.youtube.json
    python -m src.main render projects/trivia_submarine_black_001/project.youtube.json
    python -m src.main validate-render renders/trivia_submarine_black_001/rendered.youtube.json

成功時は、それぞれDB初期化完了、検証成功、仮render生成完了、rendered JSON検証成功が表示される。

## Validation and Acceptance

受け入れ条件は、`python -m src.main render projects/trivia_submarine_black_001/project.youtube.json` により `renders/trivia_submarine_black_001/rendered.youtube.json` が作られ、同ファイルが `schemas/rendered.youtube.schema.json` に合格することである。さらに `data/trivia_shorts.db` に `youtube_projects` と `youtube_renders` の行が作成されることを確認する。

## Idempotence and Recovery

`init-db` は `CREATE TABLE IF NOT EXISTS` を使うため何度実行しても安全である。`render` は同じprojectに対して時刻付きの `render_id` を作るため複数回実行できる。DB保存はproject側を置換保存し、render側は新しいIDで追加する。

## Artifacts and Notes

作業完了後、代表的なCLI出力と変更ファイルをここに短く記録する。

## Interfaces and Dependencies

CLIは `python -m src.main` で起動する。サブコマンドは `init-db`、`validate-project`、`validate-render`、`render` を実装する。JSON Schema検証は Python パッケージ `jsonschema` を使う。SQLiteは標準ライブラリ `sqlite3` を使う。


## 実装完了メモ

2026-06-28 に、project/rendered schema、CLI、SQLite初期化、project保存、仮rendered JSON生成、サンプルprojectを追加した。`jsonschema` が環境に未導入だったため、`requirements.txt` を追加して依存関係を明示した。
