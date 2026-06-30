# evaluate-render品質検査拡張と自己改善ループ

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

この計画はリポジトリ直下の `PLANS.md` と `AGENTS.md` に従って管理する。作業ディレクトリは `C:\Users\Hodaka\Downloads\div\autoyoutube` で、Pythonコマンドは `.\.venv\Scripts\python.exe` を使う。このプロジェクトはYouTube Shorts向け動画生成に集中し、自動投稿やバズ判定は追加しない。

## Purpose / Big Picture

`evaluate-render` をMVP品質検査の中心にして、生成済み動画の機械的な破綻をより早く見つけられるようにする。ユーザーは動画生成後に `python -m src.main evaluate-render renders/.../rendered.youtube.json` を実行するだけで、音声、字幕、FFmpegログ、素材、出力ファイルの問題を `quality_report.json` として確認できる。Codexはこのレポートの `checks[]`, `auto_fixable`, `codex_hint` を読み、バズ判定ではなくコード・定数・生成処理の改善に集中できる。

## Progress

- [x] (2026-06-29 23:45 JST) 要件を読み、追加検査の対象を `evaluate-render` に集約する方針を決めた。
- [x] (2026-06-29 23:49 JST) summary、auto_fixable、codex_hintをquality reportへ追加した。
- [x] (2026-06-29 23:50 JST) 字幕読み速度、字幕行数、字幕1行文字数の検査をTDDで追加した。字幕幅とASS特殊文字の厳密検査は次段階に残した。
- [x] (2026-06-29 23:52 JST) 音声の冒頭無音、音割れ、final_audio尺、sample rate不一致をTDDで追加した。
- [x] (2026-06-29 23:54 JST) FFmpeg stderr、フォントfallback、素材解像度、素材連続利用、出力ファイルサイズの検査をTDDで追加した。
- [x] (2026-06-29 23:56 JST) 深海発光生物動画へ再評価をかけ、AUDIO_CLIPPING、FONT_FALLBACK_DETECTED、SAME_ASSET_CONSECUTIVEを自己改善対象にした。
- [x] (2026-06-29 23:59 JST) 音声ピーク正規化、Windows実環境向け字幕フォント、連続素材回避を実装し、再レンダーした。
- [x] (2026-06-30 00:02 JST) Ruff、pytest、schema検証、evaluate-renderを実行した。

## Surprises & Discoveries

- Observation: 新検査を入れた直後、深海発光生物動画のquality reportは4件のwarningを出した。
  Evidence: `AUDIO_CLIPPING`, `FONT_FALLBACK_DETECTED`, `SAME_ASSET_CONSECUTIVE` 2件が出た。

- Observation: 既定フォント `Noto Sans CJK JP` は現在のWindows/FFmpeg環境ではfallbackしていた。
  Evidence: ffmpeg stderrに `fontselect: (Noto Sans CJK JP, 400, 0) -> ArialMT` と `Glyph ... not found` が出ていた。

- Observation: `Yu Gothic UI Semibold` に変更するとDirectWrite上で `YuGothicUI-Semibold` に直接解決された。
  Evidence: 再レンダー後のstderrは `fontselect: (Yu Gothic UI Semibold, 400, 0) -> YuGothicUI-Semibold` のみで、quality reportの `FONT_FALLBACK_DETECTED` は消えた。

- Observation: AivisSpeechの結合後音声はピーク0.0dBFSに達していた。
  Evidence: 新quality reportの初回評価で `final_audio_peak_dbfs=0.0` となり、`AUDIO_CLIPPING` warningが出た。

## Decision Log

- Decision: 全項目を一度に実装せず、MVP品質検査として機械的に安定して計測できる項目から入れる。
  Rationale: OpenCVや厳密LUFS解析のような追加依存を避け、標準ライブラリ、ffprobe、既存rendered JSON、WAV読み取りだけで実装できる検査のほうが現在のローカル半自動運用に合うため。
  Date/Author: 2026-06-29 / Codex

- Decision: `quality_report.json` の既存 `status`, `checks`, `metrics` は維持し、`summary` と各checkの `metrics`, `auto_fixable`, `codex_hint` を追加する。
  Rationale: 既存CLIやテストとの互換性を保ちつつ、Codex改善ループがどの警告をどう直すか判断しやすくするため。
  Date/Author: 2026-06-29 / Codex

- Decision: 音声検査はまずWAVを直接読む。最初はfinal_audio.wavと文単位WAVを対象にし、BGM単体のMP3解析や厳密LUFSは後回しにする。
  Rationale: Python標準の `wave` と `audioop` 相当の軽量処理で、冒頭無音、RMS、ピーク、sample rate、durationを十分に検査できるため。
  Date/Author: 2026-06-29 / Codex

- Decision: final_audio.wavはピークが `DEFAULT_NARRATION_PEAK_DBFS=-3.0` を超える場合だけ正規化する。
  Rationale: AivisSpeechの出力が0dBFSに張り付く場合を避けつつ、すでに十分低い音声や無音dry-runには不要な加工をしないため。
  Date/Author: 2026-06-29 / Codex

- Decision: 現在のWindows実生成では字幕既定フォントを `Yu Gothic UI Semibold` に変更する。
  Rationale: `Noto Sans CJK JP` がローカル環境に存在せず、FFmpeg/ASSが別フォントへfallbackしていたため。Docker/Linux向けには将来フォント同梱または環境別設定へ拡張する余地を残す。
  Date/Author: 2026-06-29 / Codex

- Decision: 複数素材タイムライン本実装の前段として、素材選定では直前asset_idと同じ候補を避ける。
  Rationale: 今の単純な文単位visualsでも、候補が複数ある場合に同一素材の連続利用を減らせるため。
  Date/Author: 2026-06-29 / Codex

## Outcomes & Retrospective

完了。`evaluate-render` に `summary`, `auto_fixable`, `codex_hint`, check別metricsを追加し、字幕CPS、字幕行数、音声冒頭無音、音割れ、final_audio尺、sample rate、FFmpeg warning、フォントfallback、素材解像度、連続素材、動画ファイルサイズを検査できるようにした。

深海発光生物動画では、初回の新検査で `AUDIO_CLIPPING`, `FONT_FALLBACK_DETECTED`, `SAME_ASSET_CONSECUTIVE` が見つかった。自己改善として、`src/pipeline/render_project.py` にfinal_audio.wavのピーク正規化と直前素材回避を追加し、`src/defaults.py` の字幕フォントを現在のWindows実環境でfallbackしない `Yu Gothic UI Semibold` に変更した。

再レンダー後の `quality_report.json` は `status: pass`, `checks: []` である。主要メトリクスは、`final_audio_peak_dbfs=-3.0`, `opening_audio_rms_dbfs=-26.252`, `max_subtitle_cps=5.881`, `max_subtitle_lines=2`, `video_duration_sec=65.820998`, `duration_diff_sec=0.001` である。残課題は、映像の明るさ、動き、字幕背景コントラスト、BGMとナレーションの実RMS差、ASS特殊文字の厳密エスケープ検査である。

## Context and Orientation

CLI入口は `src/main.py` で、`evaluate-render` は `src.quality.evaluator.evaluate_render()` を呼び出す。`evaluate_render()` は `rendered.youtube.json` を読み、必須ファイル、credits、字幕長、BGM設定、manual review、ffprobeで得た実MP4情報を検査し、同じrenderディレクトリに `quality_report.json` を書く。

今回の主要編集対象は `src/quality/evaluator.py` と `tests/test_quality_evaluator.py` である。動画生成側の修正が必要になった場合のみ、`src/pipeline/render_project.py` や `src/render/ffmpeg_renderer.py` を変更する。生成済み動画、Pexels素材、BGM実ファイル、DB、`.env` はGit管理しない。

用語を定義する。RMSは音声波形の平均的な大きさを示す値で、ここでは音量の粗い目安として使う。dBFSはデジタル音声の最大値を0dBとした相対音量で、0dBに近いほど音割れしやすい。CPSはcharacters per secondの略で、字幕の文字数を表示秒数で割った読み速度である。

## Plan of Work

まず `tests/test_quality_evaluator.py` に失敗テストを追加する。テストは実FFmpegやPexelsに依存させず、tmp_pathに短いWAV、疑似stderr、疑似rendered JSONを作る。検査対象は、`SUBTITLE_CPS_TOO_HIGH`, `SUBTITLE_TOO_MANY_LINES`, `OPENING_NO_AUDIO`, `AUDIO_CLIPPING`, `FINAL_AUDIO_DURATION_MISMATCH`, `AUDIO_SAMPLE_RATE_MISMATCH`, `FFMPEG_WARNING_DETECTED`, `FONT_FALLBACK_DETECTED`, `SOURCE_RESOLUTION_TOO_LOW`, `SAME_ASSET_CONSECUTIVE`, `VIDEO_FILE_TOO_LARGE` とする。

次に `src/quality/evaluator.py` を拡張する。`_check()` は後方互換を保ったまま、任意の `metrics`, `auto_fixable`, `codex_hint` を受け取れるようにする。`evaluate_render()` は `summary` を追加し、error、warning、infoの件数を数える。字幕チェックは1行文字数、行数、CPSを測る。音声チェックは `audio.final_audio_path` と `audio.narration_files[]` のWAVを読み、冒頭無音、ピーク、RMS、sample rate、duration差分を測る。FFmpegチェックはstderrログの文字列を見てwarningやfont fallbackを拾う。素材チェックはrendered.visualsから元解像度とasset連続利用を確認する。

深海発光生物動画に再度 `evaluate-render` を実行する。もしquality reportに生成コードで直せるwarningが出たら、先に失敗テストを追加してから最小修正を行う。今回実際に出たwarningは、final_audioのピーク過大、字幕フォントfallback、連続素材利用であり、それぞれピーク正規化、既定フォント変更、直前素材回避で修正した。

## Concrete Steps

作業はすべてリポジトリ直下で行う。

    .\.venv\Scripts\python.exe -m pytest tests\test_quality_evaluator.py -q --basetemp .pytest_tmp
    .\.venv\Scripts\python.exe -m src.main evaluate-render renders\trivia_deep_sea_bioluminescence_001\rendered.youtube.json
    .\.venv\Scripts\python.exe -m src.main render projects\trivia_deep_sea_bioluminescence_001\project.youtube.json --voice-mode aivis --video-mode ffmpeg --aivis-base-url http://127.0.0.1:10101
    .\.venv\Scripts\python.exe -m src.main validate-render renders\trivia_deep_sea_bioluminescence_001\rendered.youtube.json
    .\.venv\Scripts\python.exe -m ruff check .
    .\.venv\Scripts\python.exe -m ruff format . --check
    .\.venv\Scripts\python.exe -m pytest -q --basetemp .pytest_tmp

実際の最終検証では、`ruff check .` が `All checks passed!`、`ruff format . --check` が `50 files already formatted`、`pytest -q --basetemp .pytest_tmp` が `66 passed` を返した。

サンドボックスでpytestの一時ディレクトリ走査が拒否される場合は、同じコマンドを承認付きで実行する。検証後は `.pytest_tmp` を削除する。

## Validation and Acceptance

受け入れ条件は、`quality_report.json` が `summary` を持ち、各checkが必要に応じて `auto_fixable` と `codex_hint` を持つことである。追加テストは実装前に失敗し、実装後に通る必要がある。深海発光生物動画に対する `evaluate-render` は実行でき、検査結果に基づいて少なくとも1つの自己改善判断を行う。最終的に `validate-project`、`validate-render`、`evaluate-render`、`ruff check .`、`ruff format . --check`、`pytest -q --basetemp .pytest_tmp` が成功することを確認した。

## Idempotence and Recovery

`evaluate-render` は `quality_report.json` を上書きするだけなので何度実行してもよい。renderは同じ `renders/trivia_deep_sea_bioluminescence_001/` を上書きする。Pexels素材やBGM実ファイルは既にローカルにある前提で、追加取得はこの計画では必須にしない。テスト用WAVはtmp_path配下だけに作る。

## Artifacts and Notes

最終的に確認する主要成果物は `renders/trivia_deep_sea_bioluminescence_001/quality_report.json` と `output.mp4` である。品質レポートにwarningが残る場合、それが人間レビュー対象なのかコード修正対象なのかをOutcomesに明記する。

## Interfaces and Dependencies

`src.quality.evaluator.evaluate_render(rendered_path: Path, *, video_probe: VideoProbe | None = None) -> dict[str, Any]` の公開形は維持する。新しい内部ヘルパーは `src/quality/evaluator.py` に閉じる。追加依存は入れない。音声検査は標準ライブラリの `wave` と整数演算を使う。動画の実解像度と尺は既存どおりffprobeを使う。生成側では `src.pipeline.render_project._write_peak_normalized_wav()` がfinal_audio.wavのピークを必要時だけ下げる。

## Plan Revision Notes

2026-06-29 / Codex: ユーザーが追加の機械検査項目をCLIに入れ、再度自己改善ループを回すよう依頼したため、本ExecPlanを追加した。

2026-06-30 / Codex: TDDで品質検査を追加し、深海発光生物動画のquality reportに出たwarningをもとに生成コードを改善したため、Progress、Surprises、Decision、Outcomesを更新した。
