# YouTube Shorts用スキーマ契約の厳密化

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

この計画はリポジトリ直下の `PLANS.md` と `AGENTS.md` に従って管理する。作業ディレクトリは `C:\Users\Hodaka\Downloads\div\autoyoutube` で、Pythonコマンドはユーザー作成済みの `.\.venv\Scripts\python.exe` を使う。

## Purpose / Big Picture

この変更により、ChatGPTが作る入力JSONとPythonが生成するrendered JSONの契約を強くし、今後の実動画E2E、DB保存範囲拡張、レビューCLI、Analytics連携の土台を安定させる。ユーザーは `voice.style_id` を任意で指定でき、指定がある場合はAivisSpeechのstyle IDを優先して音声生成できる。rendered JSONは、音声、映像、字幕、credits、validation、manual_reviewなどの主要構造が壊れていないことをJSON Schemaでより厳密に検出できる。

## Progress

- [x] (2026-06-28 23:05 JST) 現行 `project.youtube.schema.json`, `rendered.youtube.schema.json`, `render_project.py`, 関連テストを確認した。
- [x] (2026-06-28 23:06 JST) 方針書の直近推奨に従い、実装範囲をPhase 1のスキーマ整理に絞った。
- [x] (2026-06-28 23:14 JST) `voice.style_id` とrendered schema厳密化の失敗テストを追加し、期待通り失敗することを確認した。
- [x] (2026-06-28 23:20 JST) `project.youtube.schema.json` に `voice.style_id` を任意項目として追加した。
- [x] (2026-06-28 23:21 JST) `render_project.py` が `voice.style_id` をspeakerより優先してAivisSpeechへ渡すようにした。
- [x] (2026-06-28 23:28 JST) `rendered.youtube.schema.json` を主要項目の詳細版へ更新した。
- [x] (2026-06-28 23:35 JST) Ruff、pytest、CLI検証を実行した。
- [x] (2026-06-28 23:45 JST) サンプルprojectを既定Aivis Engineの `まお` / `style_id: 888753760` に更新し、Aivis実音声とFFmpegでE2E生成した。
- [x] (2026-06-28 23:48 JST) README、dev_memo、ExecPlanを更新した。

## Surprises & Discoveries

- Observation: 現行 `rendered.youtube.schema.json` は `audio`, `visuals`, `subtitles`, `credits`, `validation`, `manual_review` の多くが `additionalProperties: true` または item定義なしで、構造崩れを検出しにくい。
  Evidence: `visuals` は `type=array` と `minItems=1` のみで、各要素の必須項目が定義されていない。

- Observation: 現行 `render_project.py` はAivisSpeechへ常に `voice["speaker"]` を渡している。
  Evidence: `_generate_voice_and_timing()` 内の `voice_service.synthesize_to_file(..., voice["speaker"], ...)`。

- Observation: MoneyPrinterTurboは短尺動画生成の統合ツールだが、今回のPhase 1はスキーマ契約の整理であり、個別実装パターン参照は不要。
  Evidence: 方針書ではMoneyPrinterTurboを「必要な実装パターンだけ参照」とし、直近推奨作業はスキーマ整理と実動画E2Eである。

## Decision Log

- Decision: 今回はMoneyPrinterTurboのコード追従を行わず、現在の独自パイプラインに対するスキーマ契約強化だけを行う。
  Rationale: 方針書上、MoneyPrinterTurboは常時参照対象ではない。今回の作業はJSON SchemaとAivisSpeech style IDの入力契約であり、外部実装パターンを参照する必要がない。
  Date/Author: 2026-06-28 / Codex

- Decision: `voice.style_id` は任意項目にし、存在する場合だけspeakerより優先して音声サービスへ渡す。
  Rationale: 既存project JSONとの互換性を保ちながら、AivisSpeech Engineで安定しやすいstyle ID指定へ移行できる。
  Date/Author: 2026-06-28 / Codex

- Decision: rendered schemaでは、Python側で追加バリデーションすべき大小比較やファイル存在確認は扱わず、型、必須項目、enum、追加プロパティ制限を中心に厳密化する。
  Rationale: 方針書の「JSON Schemaで検証しない項目」に従い、Schemaが得意な構造検証とPythonが得意な実体検証を分ける。
  Date/Author: 2026-06-28 / Codex

## Outcomes & Retrospective

`project.youtube.schema.json` は既存projectを壊さず、任意の `voice.style_id` を受け付けるようになった。`render_project()` はstyle IDがある場合だけAivisSpeechへ渡すspeaker引数としてstyle IDを優先し、ない場合は従来通り `speaker` を使う。

`rendered.youtube.schema.json` は、`audio.narration_files[]`, `visuals[]`, `subtitles.items[]`, `credits.items[]`, `ffmpeg`, `youtube.upload`, `manual_review`, `validation.errors[]`, `validation.warnings[]` の型と必須項目を固定した。Pexels素材は `source == "pexels"` の時だけ、Pexels IDやphotographer、Pexels URLなどを必須にする条件分岐にした。creditsは `credit_type` に統一し、`type` aliasは受け付けない。

残る検証は方針書通りPython側で行う。具体的には `start_sec < end_sec`、ファイル存在、MP4実尺との近似、素材とsubtitleのindex対応、manual review完了前のpublish_ready禁止などである。

## Context and Orientation

`schemas/project.youtube.schema.json` はChatGPTが生成する入力JSONの契約である。現在は `voice` に `speaker` はあるが `style_id` はない。`schemas/rendered.youtube.schema.json` はPythonが生成する実行結果ログの契約である。現行は上位の必須項目はあるが、配列要素やmanual_reviewなどの詳細が緩い。

`src/pipeline/render_project.py` はrender処理の中心で、project JSONを検証し、文単位音声、字幕、映像素材、BGM、FFmpegログ、rendered JSONを作る。AivisSpeechへ渡すspeaker指定は `_generate_voice_and_timing()` で決まる。

## Plan of Work

まずテストを追加する。`tests/test_json_schemas.py` では、project schemaが `voice.style_id` を受け付けること、rendered schemaが壊れた `audio.narration_files[]`, `visuals[]`, `credits.items[]`, `validation.warnings[]`, `manual_review` を拒否することを確認する。`tests/test_render_project_voice.py` では、project JSONに `style_id` がある場合にvoice serviceへstyle IDが渡り、rendered JSONの `voice.style_id` にも残ることを確認する。

次に `schemas/project.youtube.schema.json` の `voice.properties` に `style_id` を追加する。型はinteger、最小値は0とする。必須にはしない。

次に `src/pipeline/render_project.py` で、音声生成時に `voice.get("style_id", voice["speaker"])` を使うようにする。これにより既存のspeaker名指定はそのまま動き、style IDがある時だけ優先される。

最後に `schemas/rendered.youtube.schema.json` を詳細化する。主要オブジェクトは `additionalProperties: false` を基本とし、現行 `render_project()` が出力する構造に合わせる。Pexels素材の必須化はJSON Schemaの条件分岐で `source == "pexels"` の時だけ適用する。BGM無効時と有効時の両方を通せるよう、`bgm` は共通必須項目を中心に定義する。

## Concrete Steps

作業はすべてリポジトリ直下で行う。

    .\.venv\Scripts\python.exe -m pytest -q tests\test_json_schemas.py tests\test_render_project_voice.py
    .\.venv\Scripts\python.exe -m pytest -q
    .\.venv\Scripts\python.exe -m ruff check .
    .\.venv\Scripts\python.exe -m ruff format . --check
    .\.venv\Scripts\python.exe -m src.main validate-project projects\trivia_submarine_black_001\project.youtube.json

## Validation and Acceptance

`project.youtube.schema.json` は既存サンプルを引き続き受け付け、`voice.style_id` 付きprojectも受け付ける。`render_project()` は `style_id` がある場合、AivisSpeechへstyle IDを渡す。rendered JSONは現行生成物を通しつつ、`narration_files` の必須項目欠落、`credits.items[].type` のような旧/誤キー、`manual_review.publish_ready` 欠落などを拒否する。

全テストは `.\.venv\Scripts\python.exe -m pytest -q` で成功する。Ruffの静的解析とformat checkも成功する。

## Idempotence and Recovery

この変更はスキーマとPythonの入力選択ロジックだけを変更する。DBファイルや生成動画を削除しない。既存project JSONは `style_id` なしでも有効なままにするため、過去のサンプルやdry-run renderを壊さない。スキーマ厳密化で既存rendered JSONが失敗した場合は、Python出力をschemaへ合わせるか、schemaの制約が実出力より過剰でないか確認して調整する。

## Artifacts and Notes

MoneyPrinterTurboは方針書で参照名として出てくるが、今回のスキーマ契約整理では参照実装を取り込まない。必要になるのは、後続の複数映像素材タイムライン合成やエンコーダfallbackを実装する時である。

検証結果:

    .\.venv\Scripts\python.exe -m ruff check .
    All checks passed!

    .\.venv\Scripts\python.exe -m ruff format . --check
    44 files already formatted

    .\.venv\Scripts\python.exe -m pytest -q
    49 passed in 1.26s

    .\.venv\Scripts\python.exe -m src.main validate-project projects\trivia_submarine_black_001\project.youtube.json
    project JSON validation succeeded: projects\trivia_submarine_black_001\project.youtube.json

    .\.venv\Scripts\python.exe -m src.main render projects\trivia_submarine_black_001\project.youtube.json
    Render complete: C:\Users\Hodaka\Downloads\div\autoyoutube\renders\trivia_submarine_black_001\rendered.youtube.json

    .\.venv\Scripts\python.exe -m src.main render projects\trivia_submarine_black_001\project.youtube.json --voice-mode aivis --video-mode ffmpeg --aivis-base-url http://127.0.0.1:10101
    Render complete: C:\Users\Hodaka\Downloads\div\autoyoutube\renders\trivia_submarine_black_001\rendered.youtube.json

    .\.venv\Scripts\python.exe -m src.main validate-render renders\trivia_submarine_black_001\rendered.youtube.json
    rendered JSON validation succeeded: renders\trivia_submarine_black_001\rendered.youtube.json

    ffprobe output.mp4
    codec_name=h264
    width=1080
    height=1920
    pix_fmt=yuv420p
    r_frame_rate=30/1
    audio codec_name=aac
    duration=16.800000

## Interfaces and Dependencies

`project.youtube.schema.json` の `voice` は次の任意項目を持つ。

    "style_id": {
      "type": "integer",
      "minimum": 0
    }

`src.pipeline.render_project._generate_voice_and_timing()` は、音声生成のspeaker引数として `style_id` があればその整数を、なければ従来通り `speaker` を渡す。

`rendered.youtube.schema.json` は、`audio.narration_files[]`, `visuals[]`, `subtitles.items[]`, `credits.items[]`, `ffmpeg`, `youtube.upload`, `manual_review`, `validation.errors[]`, `validation.warnings[]` の型と必須項目を固定する。

## Plan Revision Notes

2026-06-28 / Codex: ユーザーが今後の開発方針書を提示し、続きの実装を依頼したため、本ExecPlanを追加した。
