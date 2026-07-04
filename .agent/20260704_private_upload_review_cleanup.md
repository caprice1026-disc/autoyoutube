# YouTube private upload 前提のレビュー項目整理

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

この計画はリポジトリ直下の `PLANS.md` と `AGENTS.md` に従って管理する。作業ディレクトリは `C:\Users\Hodaka\Downloads\div\autoyoutube` で、Python コマンドは `.\.venv\Scripts\python.exe` を使う。このプロジェクトは YouTube Shorts 向け動画生成に集中し、今回も private upload の前後に必要な機械検査だけを残す。

## Purpose / Big Picture

ユーザーは、生成済み動画を YouTube に private 投稿し、YouTube 上で見てから公開可否を判断する運用にしたい。したがって、ローカルの `rendered.youtube.json` に `manual_review.checked` や `publish_ready` のようなレビュー用項目を新規生成する必要はない。この変更により、新しい render 出力はレビュー項目を持たず、upload CLI は `output.mp4`、説明、credits、`quality_report.json` の機械的な条件だけで private 投稿できる。

古い render 出力には `manual_review` が残っている可能性があるため、schema では任意の legacy 項目として受け付ける。これは既存の `renders\202607041820-夜の街が明るく見える理由\rendered.youtube.json` のような成果物を壊さないためである。

## Progress

- [x] (2026-07-04 20:10 JST) 完了監査で `manual_review` が schema、render 生成、DB 保存、README、quality evaluator に残っていることを確認した。
- [x] (2026-07-04 20:12 JST) 本 ExecPlan を `.agent/20260704_private_upload_review_cleanup.md` として作成した。
- [x] (2026-07-04 20:12 JST) TDD で `manual_review` が新規 render の必須項目ではないことを確認する失敗テストを追加した。
- [x] (2026-07-04 20:14 JST) production code と README を更新し、関連テストを通した。
- [x] (2026-07-04 20:18 JST) Ruff、pytest、対象動画の upload metadata 読み込み、DB schema 確認を再実行した。

## Surprises & Discoveries

- Observation: 前回修正で upload precondition から `manual_review` gate は消えていたが、生成 JSON と schema ではまだ必須だった。
  Evidence: `rg -n "manual_review|publish_ready" README.md src schemas tests` で `schemas/rendered.youtube.schema.json` の required、`src/pipeline/render_project.py` の生成、`src/db/repositories.py` の保存、`src/quality/evaluator.py` の検査が見つかった。

- Observation: RED では schema、render 生成、DB 保存の3点が期待どおり失敗した。
  Evidence: `pytest -q tests\test_json_schemas.py tests\test_render_project_ffmpeg.py::test_render_project_uses_video_renderer_and_marks_video_success tests\test_db_repositories.py tests\test_quality_evaluator.py::test_evaluate_render_does_not_require_manual_review` が `3 failed, 14 passed` を返した。

## Decision Log

- Decision: `manual_review` は新規生成しないが、schema では任意の legacy 項目として残す。
  Rationale: ユーザーの運用ではローカルレビュー項目は不要だが、既存の `rendered.youtube.json` を無効化すると過去 render の検査や upload 記録確認が壊れるため。
  Date/Author: 2026-07-04 / Codex

- Decision: `render_manual_reviews` テーブルは削除しない。
  Rationale: 既存 DB の破壊的 migration はユーザーが明示的に削除する運用であり、今回の要求は新規生成物と upload CLI の挙動整理で足りるため。新規 render 保存時は `manual_review` がある場合だけ legacy テーブルへ書く。
  Date/Author: 2026-07-04 / Codex

## Outcomes & Retrospective

完了。`src/pipeline/render_project.py` は新規 `rendered.youtube.json` に `manual_review` を出力しなくなった。`schemas/rendered.youtube.schema.json` は `manual_review` を top-level required から外し、古い成果物向けの任意フィールドとして定義だけ残した。`src/db/repositories.py` は legacy `manual_review` がある場合だけ `render_manual_reviews` に保存する。`src/quality/evaluator.py` は manual review 状態を品質検査から外した。README は private upload 後に YouTube 上でレビューする運用へ更新した。検証は `ruff check .` が `All checks passed!`、`pytest -q` が `92 passed`、対象動画の upload metadata 読み込みが no-`#Shorts` 側の `output.mp4` を解決し、DB schema 確認は列名・型の差なしで完了した。

## Context and Orientation

`src/pipeline/render_project.py` は `project.youtube.json` から `rendered.youtube.json` を作る。現在は `_build_rendered_metadata` が `manual_review` を出力している。`schemas/rendered.youtube.schema.json` は `rendered.youtube.json` の構造を定義し、現在は top-level required に `manual_review` を含めている。`src/db/repositories.py` は render 結果を SQLite に保存し、現在は `rendered["manual_review"]` を必須として `render_manual_reviews` に保存している。`src/quality/evaluator.py` は `evaluate-render` で品質検査を行い、現在は `manual_review.required` を検査している。

`manual_review` とは、ローカルで人間レビューが済んだかどうかを示す実行結果項目である。今回の運用では、レビューは YouTube private 動画上で行うため、このローカル項目を新規出力に含めない。

## Plan of Work

まず `tests/test_json_schemas.py` に、`manual_review` を削除した `rendered.youtube.json` が schema valid であることを示すテストを追加し、既存の `manual_review.publish_ready` 必須テストを legacy 項目が存在する場合だけ形を検証するテストに変更する。次に render pipeline のテストに、新規生成結果が `manual_review` を持たないことを追加する。さらに DB 保存テストで `manual_review` がない rendered dict を保存できることを確認する。

production code では、`src/pipeline/render_project.py` から `manual_review` 出力を削除する。`src/db/repositories.py` は `rendered.get("manual_review")` がある場合だけ `render_manual_reviews` に保存する。`src/quality/evaluator.py` は `_manual_review_checks` を評価対象から外す。`schemas/rendered.youtube.schema.json` は top-level required から `manual_review` を外し、property 定義は legacy 互換として残す。README は `manual_review` を主要検証項目として説明しないように更新する。

## Concrete Steps

作業はすべてリポジトリ直下で行う。

    .\.venv\Scripts\python.exe -m pytest -q tests\test_json_schemas.py tests\test_render_project_ffmpeg.py tests\test_db_repositories.py tests\test_quality_evaluator.py

最初の TDD 実行では、新しく追加した `manual_review` 不要テストが失敗することを確認する。実装後、同じテストを再実行して成功させる。その後、次を実行する。

    .\.venv\Scripts\python.exe -m ruff check .
    .\.venv\Scripts\python.exe -m pytest -q

## Validation and Acceptance

受け入れ条件は、新規 render 結果が `manual_review` を持たないこと、`manual_review` がない `rendered.youtube.json` が schema valid であること、古い `manual_review` 付き JSON は legacy として valid であること、upload metadata 読み込みが review 項目なしで成立すること、既存 DB の列名・型に差がないこと、Ruff と pytest が成功することである。最後に commit して `codex-error-handling-bgm` を GitHub へ push する。

## Idempotence and Recovery

schema と生成コードの変更は additive な互換方針であり、既存 DB を削除しない。もしテストで古い `manual_review` 付き成果物が壊れる場合は、schema property を legacy 任意項目として残しているか確認する。DB の destructive reset はこの計画では実行しない。

## Artifacts and Notes

最終的な evidence として、RED/Green の pytest 出力、Ruff 出力、DB schema 比較出力、upload metadata 読み込み出力、push 先 commit hash を記録する。

## Interfaces and Dependencies

公開 CLI は変えない。`upload-youtube` は引き続き `src.main._upload_youtube(rendered_path, privacy="private")` から `src.youtube.uploader.upload_private_video()` を呼ぶ。`src.youtube.metadata.load_upload_metadata()` は引き続き `manual_review` を参照しない。DB の `render_manual_reviews` テーブルは残すが、新規 render 保存で `manual_review` がない場合は何も書かない。

## Plan Revision Notes

2026-07-04 / Codex: 完了監査で `manual_review` が新規生成物に残っていることを見つけたため、ユーザーの private upload review 運用に合わせる追加計画として作成した。
