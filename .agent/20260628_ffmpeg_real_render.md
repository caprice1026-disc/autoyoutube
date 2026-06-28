# FFmpegで実際のYouTube Shorts用mp4を生成する

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

この計画はリポジトリ直下の `PLANS.md` に従って管理する。作業ディレクトリは `C:\Users\Hodaka\Downloads\div\autoyoutube` であり、検証コマンドはユーザーが作成した `.venv` の `.\.venv\Scripts\python.exe` を使う。

## Purpose / Big Picture

この変更により、利用者は `project.youtube.json` から `renders/{project_id}/output.mp4` を実際に生成できるようになる。現時点では Pexels 素材と BGM はまだ統合しないが、既存の文単位音声、結合済み音声、ASS 字幕を FFmpeg で 1080x1920 の縦動画へ合成する。これにより「JSONを読む、音声と字幕を作る、rendered JSONを出す」段階から、「YouTube Shorts として検査できる mp4 を出す」段階へ進む。

## Progress

- [x] (2026-06-28 21:10 JST) `winget install --id Gyan.FFmpeg -e --accept-package-agreements --accept-source-agreements` を実行し、FFmpeg 8.1.2 のインストール完了を確認した。
- [x] (2026-06-28 21:12 JST) 現在のシェルでは PATH が未更新だが、WinGet 配下の `ffmpeg.exe` 実体パスを確認した。
- [x] (2026-06-28 21:18 JST) FFmpeg command builder と renderer のテストを追加し、未実装の `src.render` import error を確認した。
- [x] (2026-06-28 21:24 JST) `src/render/ffmpeg_renderer.py` を追加し、FFmpeg 実行、コマンドログ、stderrログ保存を実装した。
- [x] (2026-06-28 21:26 JST) `render_project` と CLI に `--video-mode ffmpeg` と `--ffmpeg-path` を追加し、実生成を選べるようにした。
- [x] (2026-06-28 21:32 JST) `.venv` で全テストを実行し、FFmpeg 実生成、schema 検証、ffprobe 確認を行った。

## Surprises & Discoveries

- Observation: winget は `Gyan.FFmpeg` をインストールし、`ffmpeg`、`ffplay`、`ffprobe` のコマンドラインエイリアスを追加した。
  Evidence: winget の出力に「コマンド ライン エイリアスが追加されました: "ffmpeg"」と「インストールが完了しました」が表示された。
- Observation: インストール直後の現在の PowerShell セッションでは PATH が更新されていない。
  Evidence: winget の出力に「パス環境変数が変更されました; 新しい値を使用するにはシェルを再起動してください。」と表示された。
- Observation: FFmpeg 実体は WinGet の package directory に存在する。
  Evidence: `C:\Users\Hodaka\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1.2-full_build\bin\ffmpeg.exe` を検出した。
- Observation: sandbox 内 pytest は Windows の一時ディレクトリと `.tmp/pytest` の権限に当たり、テスト対象外の PermissionError を出した。
  Evidence: `PermissionError: [WinError 5] アクセスが拒否されました。: 'C:\Users\Hodaka\AppData\Local\Temp\pytest-of-Hodaka'` が出たため、通常権限で同じ pytest を実行した。

## Decision Log

- Decision: 今回の実生成は FFmpeg の `color` 入力で 1080x1920 の背景を生成し、既存の `final_audio.wav` と `subtitle.ass` を合成する。
  Rationale: Pexels 素材取得と BGM 選曲は別フェーズの要件であり、まず mp4 生成パイプラインを安全に通すことが目的である。カラー背景なら外部素材なしで再現可能に検証できる。
  Date/Author: 2026-06-28 / Codex
- Decision: CLI は既定を従来どおり dry-run とし、実生成は `--video-mode ffmpeg` を明示したときだけ行う。
  Rationale: FFmpeg がない環境でも既存の dry-run 検証を壊さず、実生成したい環境では明示的に切り替えられるため。
  Date/Author: 2026-06-28 / Codex

## Outcomes & Retrospective

完了。`.\.venv\Scripts\python.exe -m pytest -q` は通常権限で `12 passed in 0.46s` だった。実生成は `.\.venv\Scripts\python.exe -m src.main render projects\trivia_submarine_black_001\project.youtube.json --video-mode ffmpeg --ffmpeg-path "C:\Users\Hodaka\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1.2-full_build\bin\ffmpeg.exe"` で成功し、`renders/trivia_submarine_black_001/output.mp4` が生成された。`validate-render` は成功し、`ffprobe` は `codec_name=h264`、`width=1080`、`height=1920` を返した。`rendered.youtube.json` の `status` は `success`、FFmpeg version は `ffmpeg version 8.1.2-full_build-www.gyan.dev` で、警告は dry-run voice のみ残っている。

## Context and Orientation

CLI の入口は `src/main.py` で、現在の `render` コマンドは `src/pipeline/render_project.py` の `render_project` を呼ぶ。`render_project` は project JSON を検証し、`audio/001.wav` などの文単位 WAV、`audio/narration.wav`、`audio/final_audio.wav`、`subtitle.ass`、`description.txt`、`credits.txt`、`rendered.youtube.json` を生成する。前フェーズで `voice_service` を差し替えられるようになっており、既定では silent placeholder WAV を生成する。

FFmpeg は動画と音声を変換・合成する外部コマンドである。この計画では Python の `subprocess.run` で `ffmpeg.exe` を呼び出す。FFmpeg の標準エラー出力には処理ログが出るため、要件どおり `renders/{project_id}/logs/ffmpeg_stderr.log` に保存する。実行したコマンドは `renders/{project_id}/logs/ffmpeg_command.txt` に保存する。

## Plan of Work

まず `tests/test_ffmpeg_renderer.py` を追加し、FFmpeg コマンドが縦長カラー背景、結合済み音声、ASS 字幕、libx264、aac、yuv420p、mp4 出力を含むことをテストする。次に `tests/test_render_project_ffmpeg.py` を追加し、偽 video renderer を渡したときに `render_project` が `output.mp4` を成果物として扱い、`rendered.youtube.json` の `status` と `ffmpeg` 情報を更新することをテストする。

実装では `src/render/ffmpeg_renderer.py` を追加する。`build_ffmpeg_command` は command list を返す純粋関数にし、テストしやすくする。`FfmpegVideoRenderer.render` は command を保存し、`subprocess.run` で FFmpeg を実行し、stderr を保存し、失敗時は終了コードと stderr の末尾を含む `RuntimeError` を出す。

最後に `src/main.py` と `src/pipeline/render_project.py` を拡張する。`render` コマンドは `--video-mode dry-run|ffmpeg` と `--ffmpeg-path` を受け取る。`--ffmpeg-path` が省略された場合は `FFMPEG_PATH` 環境変数、PATH 上の `ffmpeg`、WinGet の package directory の順に探す。

## Concrete Steps

作業は必ず `.venv` を使う。

    .\.venv\Scripts\python.exe -m pytest tests/test_ffmpeg_renderer.py -q
    .\.venv\Scripts\python.exe -m pytest tests/test_render_project_ffmpeg.py -q
    .\.venv\Scripts\python.exe -m pytest -q
    .\.venv\Scripts\python.exe -m src.main render projects/trivia_submarine_black_001/project.youtube.json --video-mode ffmpeg --ffmpeg-path "<detected ffmpeg.exe>"
    .\.venv\Scripts\python.exe -m src.main validate-render renders/trivia_submarine_black_001/rendered.youtube.json
    "<detected ffprobe.exe>" -v error -select_streams v:0 -show_entries stream=width,height,codec_name -of default=noprint_wrappers=1 renders/trivia_submarine_black_001/output.mp4

TDD のため、実装前に新規テストが失敗することを確認する。実生成では FFmpeg 実行が外部コマンドのため、失敗時には `logs/ffmpeg_stderr.log` の末尾を確認する。

## Validation and Acceptance

受け入れ条件は、`.venv` で全テストが通ること、`--video-mode ffmpeg` で `renders/trivia_submarine_black_001/output.mp4` が生成されること、`rendered.youtube.json` が schema 検証に合格すること、`ffprobe` で動画 stream が `width=1080`、`height=1920`、`codec_name=h264` と確認できることである。

## Idempotence and Recovery

`render` は同じ `renders/{project_id}` 配下の成果物を上書きするため、繰り返し実行できる。FFmpeg インストール直後に PATH が反映されていない場合は、検出済みの `ffmpeg.exe` を `--ffmpeg-path` に渡す。FFmpeg 実行に失敗した場合、`logs/ffmpeg_command.txt` と `logs/ffmpeg_stderr.log` を見れば同じコマンドを再実行できる。

## Artifacts and Notes

完了時に実行結果を追記する。

## Interfaces and Dependencies

`src/render/ffmpeg_renderer.py` は `FfmpegRenderRequest`、`build_ffmpeg_command(request, ffmpeg_path)`、`find_ffmpeg_executable(explicit_path=None)`、`FfmpegVideoRenderer` を提供する。`src/pipeline/render_project.py` は `video_renderer` を任意で受け取り、指定された場合だけ `output.mp4` を実生成する。`src/main.py` は `--video-mode ffmpeg` で `FfmpegVideoRenderer` を作成する。

## Plan Revision Notes

2026-06-28 / Codex: FFmpeg インストールと実生成をユーザーが明示したため、本 ExecPlan を `.agent` 配下に追加した。

2026-06-28 / Codex: 実装完了に伴い、進捗、発見、成果を更新した。現時点の mp4 は FFmpeg のカラー背景、dry-run の無音音声、ASS 字幕による実生成であり、Pexels 素材と BGM は後続フェーズに残る。
