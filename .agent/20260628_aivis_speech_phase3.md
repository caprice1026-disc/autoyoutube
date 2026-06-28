# AivisSpeech 連携で文単位の音声と字幕タイミングを生成する

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

この計画はリポジトリ直下の `PLANS.md` に従って管理する。作業ディレクトリは `C:\Users\Hodaka\Downloads\div\autoyoutube` であり、コマンドはユーザーが作成した `.venv` の `.\.venv\Scripts\python.exe` を使って実行する。

## Purpose / Big Picture

この変更により、利用者は `project.youtube.json` の `script` に書いた各文をローカル AivisSpeech Engine で WAV に変換し、その実測長に基づいて `subtitle.ass` と `rendered.youtube.json` の音声タイミングを生成できるようになる。これまでは推定秒数だけを使う dry-run だったため、実際の読み上げ速度と字幕表示がずれる可能性があった。実装後はテスト用の偽 Aivis クライアントで再現可能に検証でき、ローカルで AivisSpeech が起動していれば実音声生成にも進める。

## Progress

- [x] (2026-06-28 20:25 JST) 既存実装と `.venv` のテスト実行を確認した。`.\.venv\Scripts\python.exe -m pytest -q` は 4 passed。
- [x] (2026-06-28 20:30 JST) AivisSpeech OpenAPI のローカル `AivisSpeech/openapi.json` から `/audio_query` と `/synthesis` の呼び出し形を確認した。
- [x] (2026-06-28 20:38 JST) WAV duration を測る `src/voice/duration.py` とテストを追加した。
- [x] (2026-06-28 20:38 JST) WAV を無音ギャップ付きで結合する `src/voice/audio_merge.py` とテストを追加した。
- [x] (2026-06-28 20:39 JST) AivisSpeech HTTP クライアント `src/voice/aivis_client.py` とテストを追加した。
- [x] (2026-06-28 20:45 JST) `render_project` を音声生成サービス差し替え可能にし、実測 duration を字幕と rendered JSON に反映した。
- [x] (2026-06-28 20:48 JST) `.venv` で全テストとサンプル render を実行し、成果物を確認した。

## Surprises & Discoveries

- Observation: `ffmpeg` は現在の PATH から実行できない。
  Evidence: `ffmpeg -version` が PowerShell の `CommandNotFoundException` で失敗した。
- Observation: AivisSpeech Engine は VOICEVOX 互換の `/audio_query?text=...&speaker=...` と `/synthesis?speaker=...` を提供する。
  Evidence: `AivisSpeech/openapi.json` の `paths` に該当 POST endpoint が定義されていた。
- Observation: 既存サンプルの `voice.speaker` は `"Anneli"` のような名前であり、AivisSpeech の `/audio_query` は数値 style ID を要求する。
  Evidence: `AivisSpeech/openapi.json` では `/audio_query` の `speaker` parameter が integer と定義されている。

## Decision Log

- Decision: このフェーズでは FFmpeg で mp4 を作らず、AivisSpeech 音声生成と字幕タイミングの実測化を優先する。
  Rationale: 現在の環境では `ffmpeg` が PATH にないため、外部コマンドに依存しない要件部分を先に進めるほうが安全で検証可能である。音声実測タイミングは後続の動画合成にも必要な基盤である。
  Date/Author: 2026-06-28 / Codex
- Decision: `render_project` は任意の音声サービスを受け取れる形にし、テストでは偽サービスを渡す。
  Rationale: ローカル AivisSpeech の起動状態に依存せず、TDD で文単位 WAV、duration、字幕タイミングを検証できるようにするため。
  Date/Author: 2026-06-28 / Codex
- Decision: CLI の既定は `--voice-mode dry-run` とし、実 AivisSpeech を使う場合は `--voice-mode aivis` を明示する。
  Rationale: 現在の環境では AivisSpeech Engine の起動を確認しておらず、既存の render コマンドが環境依存で失敗しないようにするため。Aivis mode では `/speakers` から話者名を style ID に解決する。
  Date/Author: 2026-06-28 / Codex

## Outcomes & Retrospective

このフェーズでは、文単位 WAV 生成、WAV duration 実測、無音ギャップ付き `narration.wav` 結合、`final_audio.wav` 出力、字幕 timing 反映、AivisSpeech HTTP クライアントを実装した。`render` コマンドは既定で dry-run の無音 WAV を作り、`--voice-mode aivis` を付けるとローカル AivisSpeech Engine の `/speakers`、`/audio_query`、`/synthesis` を使う。検証では `.\.venv\Scripts\python.exe -m pytest -q` が `10 passed in 0.44s`、サンプル render が `Render complete: C:\Users\Hodaka\Downloads\div\autoyoutube\renders\trivia_submarine_black_001\rendered.youtube.json`、rendered JSON schema 検証が成功した。

## Context and Orientation

現在の CLI 入口は `src/main.py` で、`python -m src.main render projects/trivia_submarine_black_001/project.youtube.json` が `src/pipeline/render_project.py` の `render_project` を呼ぶ。既存の `render_project` は外部 API を呼ばず、`script[].estimated_duration_sec` をそのまま使って `rendered.youtube.json`、`subtitle.ass`、`description.txt`、`credits.txt` を生成している。SQLite 保存は `src/db/repositories.py` が担当する。JSON Schema は `schemas/project.youtube.schema.json` と `schemas/rendered.youtube.schema.json` にあり、現在は `audio.narration_files` などに追加プロパティを許可している。

この計画でいう WAV は、音声データを格納する標準的な RIFF/WAVE ファイルである。Python 標準ライブラリの `wave` でフレーム数、サンプルレート、チャンネル数、サンプル幅を読み取れる。duration は `frames / framerate` で計算する。無音ギャップは、各文の WAV の間に `voice.sentence_gap_ms` ミリ秒ぶんのゼロサンプルを書き込むことで表現する。

## Plan of Work

最初に `tests/test_voice_audio.py` を追加し、短い WAV をテスト内で作って duration 測定と結合を検証する。実装ファイルは `src/voice/duration.py` と `src/voice/audio_merge.py` で、標準ライブラリだけを使う。結合関数は入力 WAV の形式が混在すると安全に結合できないため、チャンネル数、サンプル幅、サンプルレートが一致しない場合は `ValueError` を出す。

次に `tests/test_aivis_client.py` を追加し、HTTP 呼び出し部分を差し替えた偽 transport で `/audio_query` と `/synthesis` の順序、query parameter、JSON body を確認する。実装ファイルは `src/voice/aivis_client.py` とし、実運用では Python 標準の `urllib.request` を使う。環境変数や設定がない場合の base URL は `http://127.0.0.1:10101`、speaker は既存 project JSON の文字列を直接 API に渡せないため、数値に変換できない場合は明確な `ValueError` にする。

最後に `tests/test_render_project_voice.py` を追加し、偽音声サービスから 1.0 秒、1.5 秒、2.0 秒の WAV を返させる。`render_project` は `voice_service` 引数を受け取り、指定されない場合だけ AivisSpeech クライアントを作る。生成された `rendered.youtube.json` では `audio.narration_files[].actual_duration_sec` と `subtitles.items[].start_sec/end_sec` が実測 duration と gap に基づく値になり、`audio/narration.wav` が存在することを確認する。

## Concrete Steps

作業は必ず `.venv` を使う。

    .\.venv\Scripts\python.exe -m pytest tests/test_voice_audio.py -q
    .\.venv\Scripts\python.exe -m pytest tests/test_aivis_client.py -q
    .\.venv\Scripts\python.exe -m pytest tests/test_render_project_voice.py -q
    .\.venv\Scripts\python.exe -m pytest -q
    .\.venv\Scripts\python.exe -m src.main render projects/trivia_submarine_black_001/project.youtube.json

TDD のため、新しいテストは実装前に失敗することを確認する。サンプル render はローカル AivisSpeech が起動していない場合に失敗する可能性があるため、最終検証では単体テストを必須、実 Aivis 連携は環境状態を添えて報告する。

## Validation and Acceptance

受け入れ条件は、`.venv` で全テストが通ること、偽音声サービスを使った render テストで `audio/001.wav`、`audio/002.wav`、`audio/003.wav`、`audio/narration.wav`、`subtitle.ass`、`rendered.youtube.json` が生成されること、`rendered.youtube.json` が `schemas/rendered.youtube.schema.json` に合格することである。実 AivisSpeech が `http://127.0.0.1:10101` で起動しており、project の `voice.speaker` が数値 ID の場合は CLI から実 WAV を生成できる。

## Idempotence and Recovery

テストは一時ディレクトリ内の project と render 出力を使うため繰り返し実行できる。通常の CLI render は `renders/{project_id}` にファイルを上書きし、新しい `render_id` の DB 行を追加する。AivisSpeech が未起動の場合は HTTP 接続エラーになるが、既存ファイルを破壊しない。実音声生成に失敗した場合は AivisSpeech を起動し、`voice.speaker` を数値 ID に直して再実行する。

## Artifacts and Notes

完了時に代表的な pytest 出力と、生成された `rendered.youtube.json` の音声 timing 抜粋を追記する。

## Interfaces and Dependencies

`src/voice/duration.py` は `get_wav_duration(path: Path) -> float` を提供する。`src/voice/audio_merge.py` は `merge_wav_files(input_paths: list[Path], output_path: Path, gap_ms: int) -> float` を提供し、結合後 WAV の秒数を返す。`src/voice/aivis_client.py` は `AivisSpeechClient.synthesize_to_file(text: str, speaker: str | int, output_path: Path, speed_scale: float, pitch_scale: float, intonation_scale: float) -> Path` を提供する。`src/pipeline/render_project.py` は `render_project(project_path: Path, voice_service: VoiceService | None = None) -> Path` に拡張する。

## Plan Revision Notes

2026-06-28 / Codex: ユーザーが `.venv` を作成したため、すべての検証コマンドを `.venv` の Python に固定した。FFmpeg が未導入だったため、動画合成ではなく AivisSpeech 音声基盤を続きの実装対象にした。

2026-06-28 / Codex: 実装完了に伴い、進捗、発見、判断、成果を更新した。CLI は既存環境で再現可能な dry-run を既定にし、実 AivisSpeech は `--voice-mode aivis` で明示的に選ぶ設計にした。
