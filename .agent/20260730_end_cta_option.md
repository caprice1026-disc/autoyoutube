# 終端CTA読み上げを任意追加する

このExec Planは作業中に更新する生きた文書である。`PLANS.md` の要件に従い、`Progress`、`Surprises & Discoveries`、`Decision Log`、`Outcomes & Retrospective`を常に実態に合わせて更新する。

## Purpose / Big Picture

利用者は `make-video` 実行時に `--append-end-cta` を付けるだけで、動画の最後に「高評価とチャンネル登録、ぜひお願いします！」という短い呼びかけをAivisSpeechで読み上げ、字幕としても表示できるようになる。フラグを省略した既存コマンドの出力、JSON、尺は変更しない。PowerShellの通常ラッパー、生成AI導入動画ラッパー、バッチ実行ランナーも同じ指定を受け渡せるようにする。

呼びかけは宣伝だけで視聴体験を損なわないよう、21文字で字幕の1行上限24文字以内に収める。CTAは内部の実行用プロジェクトコピーへ一つの台本項目として追加するため、既存の音声合成、字幕生成、タイムライン、Pexels映像選択、品質評価をそのまま使える。元の `projects/.../project.youtube.json` は書き換えない。

## Progress

- [x] (2026-07-30 13:00Z) 現行の `make-video`、生成AI導入動画、PowerShellラッパー、バッチランナー、音声・字幕タイムラインを調査した。
- [x] (2026-07-30 13:00Z) CTAの文言、フラグ名、追加位置、映像取得方法を決定した。
- [x] (2026-07-30 13:20Z) 失敗する回帰テストを追加し、未実装時に `append_end_cta` の未定義、CLIフラグ未認識、PowerShell入口未対応で失敗することを確認した。
- [x] (2026-07-30 13:35Z) `MakeVideoOptions`、CLI、実行用プロジェクト正規化、PowerShellラッパー、生成AI導入CLI、バッチランナーを最小限変更した。
- [x] (2026-07-30 13:50Z) 対象テスト21件、Ruff、全pytestを実行し、既存Pexels改善分を含む差分を確認した（全170件成功）。
- [ ] このExec Planの結果を更新し、意図した全変更をコミットして `origin/master` へpushする。

## Surprises & Discoveries

- Observation: `render_project` は台本の各項目を順に音声、ASS字幕、映像区間へ変換する。
  Evidence: `src/pipeline/render_project.py` の `_generate_voice_and_timing` は `project["script"]` を走査し、音声ファイル、字幕、`visuals` を同時に作成する。

- Observation: `make-video` は実行ごとに `inputs/project.original.json` と `inputs/project.attempt_001.json` を出力する。
  Evidence: `src/pipeline/make_video.py` は読み込んだプロジェクトを実行ディレクトリの `inputs/` に保存してからレンダリングする。

- Observation: プロジェクトスキーマの台本上限は18項目である。
  Evidence: `schemas/project.youtube.schema.json` の `script.maxItems` は18であるため、18項目の入力へCTAを追加する場合は明確なエラーにする必要がある。

- Observation: サンドボックス内のpytestは既定の共有一時ディレクトリにアクセスできず、セットアップ時に `WinError 5` となる。
  Evidence: 通常実行は `C:\Users\Hodaka\AppData\Local\Temp\pytest-of-Hodaka` の `os.scandir` で失敗したが、承認済みのサンドボックス外実行では対象21件が通過した。

- Observation: この環境では直接の `./scripts/make-video.ps1` 実行が実行ポリシーで拒否される。
  Evidence: `powershell -NoProfile -ExecutionPolicy Bypass -File ...` で同じ `-AppendEndCta -PlanOnly` が成功した。既存バッチランナーもこの方針でPowerShellを起動している。

## Decision Log

- Decision: CLIフラグを `--append-end-cta`、PowerShellスイッチを `-AppendEndCta` とする。
  Rationale: 効果と位置が明確で、既存の `--upload-youtube` や `-UploadYoutube` と同じ命名規則で使える。
  Date/Author: 2026-07-30 / Codex

- Decision: 文言は「高評価とチャンネル登録、ぜひお願いします！」に固定する。
  Rationale: 高評価と登録の両方を明示しつつ、21文字で字幕の通常上限24文字以内に収まり、読み上げも冗長にならない。
  Date/Author: 2026-07-30 / Codex

- Decision: CTAは元ファイルではなく実行用プロジェクトコピーの台本末尾へ追加する。
  Rationale: 既存の音声・字幕・映像・品質評価を再利用でき、ユーザーが管理するプロジェクトJSONを汚染しない。
  Date/Author: 2026-07-30 / Codex

- Decision: CTAの映像検索語は `youtube like subscribe button animation vertical` とする。
  Rationale: 末尾台本にも映像区間が必要であり、既存のPexels取得・選択機構に委ねることで専用の映像合成機構を増やさない。
  Date/Author: 2026-07-30 / Codex

## Outcomes & Retrospective

実装は完了し、対象21テストと全170件のpytestが通過した。`--append-end-cta --plan-only`、生成AI導入CLI、`-AppendEndCta -PlanOnly` のPowerShellラッパーで、CTA文言と専用映像検索語が計画に出ることを確認した。Ruffは違反なしで、残作業はコミットとpushだけである。

## Context and Orientation

`src/main.py` は `python -m src.main make-video ...` の引数を解析し、`MakeVideoOptions` を作って `src/pipeline/make_video.py` の `make_video` を呼び出す。`MakeVideoOptions` はパイプライン全体の入力値である。`make_video` はプロジェクトJSONを読み、入力コピーを作り、必要なPexels映像を取得し、各試行で `render_project` を呼び出す。

`src/pipeline/render_project.py` の `render_project` は台本の全項目を順番に処理する。各項目の `text` はAivisSpeechの音声、ASS字幕、タイムライン情報になり、`visual_query` は映像選択に使われる。したがってCTAを特別な音声経路で実装する必要はない。実行時に末尾台本項目を加えるだけで、通常動画と生成AI導入動画の両方に同じ効果が出る。

`src/generated_intro_main.py` と `scripts/make-video-with-generated-intro.ps1` は生成AI導入動画用の入口である。`scripts/make-video.ps1` は通常動画用のWindows入口である。`scripts/run-upload-command-list.ps1` はコマンドリストのUnix形式をPowerShell引数へ変換する。これらの入口がフラグを落とさずパイプラインへ渡すことをテストする。

## Plan of Work

最初に `tests/test_make_video.py` へ、`append_end_cta=True` のときだけ実行用プロジェクトの末尾にCTA項目が現れ、元のプロジェクトファイルが変わらないことを確認するテストを加える。さらにCLI引数から `MakeVideoOptions.append_end_cta` が渡るテストを加える。これらはフラグと実装がない状態で失敗する。

次に `src/pipeline/project_normalization.py` へ、深いコピーを作ってCTA項目を末尾へ追加する関数と、文言、映像検索語、推定尺の定数を置く。台本が18項目なら `AppError` で安全に拒否する。`src/pipeline/make_video.py` はCLI由来の真偽値を受け、Pexels用のCLIキーワード適用後にこの関数を呼び、追加済みコピーを計画・入力保存・レンダリングに使う。

その後、`src/main.py` と `src/generated_intro_main.py` に `--append-end-cta` を追加する。PowerShellの二つのラッパーに `-AppendEndCta` を加え、Python CLIに転送する。バッチランナーはUnix形式の `--append-end-cta` をPowerShell形式へ変換する。`docs/make_video.md` と `docs/generated_intro_video.md` に利用例を1つずつ追加する。

最後に、対象テスト、Ruff、全pytest、plan-only実行を行う。実行結果でプランのCTA情報と追加台本を確認し、既存の未コミットPexels改善とExec Plan群も差分・テストで確認してから、ユーザーの指示どおりまとめて `master` のリモートへpushする。

## Concrete Steps

作業ディレクトリは `C:\Users\Hodaka\Downloads\div\autoyoutube` とする。

1. `tests/test_make_video.py` に望む公開APIを使った失敗テストを追加する。

       .\.venv\Scripts\python.exe -m pytest tests\test_make_video.py -k end_cta -q

   実装前は `MakeVideoOptions` が `append_end_cta` を受け取れず、失敗することを確認する。

2. `src/pipeline/project_normalization.py` と `src/pipeline/make_video.py` に最小実装を追加し、同じテストを再実行する。CTA項目は次の値を持つ。

       text: 高評価とチャンネル登録、ぜひお願いします！
       visual_query: youtube like subscribe button animation vertical
       estimated_duration_sec: 3.0
       caption_style_hint: punchline

3. `src/main.py`、`src/generated_intro_main.py`、PowerShellラッパー、バッチランナー、テスト、ドキュメントを更新する。CLI経由テストを実行する。

       .\.venv\Scripts\python.exe -m pytest tests\test_make_video.py tests\test_generated_intro.py tests\test_upload_runner_contract.py -q

4. `--plan-only` で実際のPexels取得・音声合成を避け、CTAを有効にした計画に末尾CTAの検索語が含まれることを確認する。

       .\.venv\Scripts\python.exe -m src.main make-video <既存のproject.youtube.json> --append-end-cta --plan-only

5. 最終検証を行う。

       .\.venv\Scripts\python.exe -m ruff check .
       .\.venv\Scripts\python.exe -m pytest
       git diff --check

   Ruffは `All checks passed!`、pytestは失敗0件、`git diff --check` は出力なしが受入条件である。

## Validation and Acceptance

受入条件は、フラグなしのテストプロジェクトが既存の3台本項目のままであること、`--append-end-cta` 付きの実行用入力JSONと最終レンダーが4項目目のCTAを含むこと、CTAの音声と字幕が末尾に現れること、元のプロジェクトJSONが変更されないことである。`--plan-only` ではCTAの映像検索語が計画に現れ、外部API・音声・動画レンダリングを実行しないことも確認する。

生成AI導入動画の入口でも同じ `--append-end-cta` が `MakeVideoOptions` に渡り、PowerShellラッパーとバッチランナーがフラグを落とさないことを回帰テストで確認する。全テストとRuffの成功後だけコミットする。

## Idempotence and Recovery

CTAは入力プロジェクトを深いコピーして実行ディレクトリへ保存するため、同じコマンドを再実行しても `projects/` のJSONは増殖・上書きされない。最大18項目の台本へ追加しようとした場合は、レンダリングを始める前に安全なエラーで止める。失敗したレンダリングは既存の `renders/<run_id>/` に残るため、原因確認後に同じコマンドを再実行できる。

## Artifacts and Notes

重要な差分は、台本コピーを作る関数、`MakeVideoOptions.append_end_cta`、二つのCLI入口、二つのPowerShell入口、バッチ変換である。生成メディア、DB、Pexels取得物、render出力はコミットしない。既存の `src/media/pexels_client.py` と `tests/test_pexels_client.py` の未コミット改善は別の作業だが、ユーザーが「これまでの変更を含めて」と指定したため、最終段階で差分とテストを検証して同じコミットに含める。

## Interfaces and Dependencies

`src/pipeline/project_normalization.py` に次の公開関数を追加する。

    def project_with_end_cta(project: dict[str, Any]) -> dict[str, Any]:

この関数は元の辞書を変更せず、台本末尾に1項目を追加したコピーを返す。追加できない場合は `src.errors.AppError` を送出する。

`src/pipeline/make_video.py` の `MakeVideoOptions` に次を追加する。

    append_end_cta: bool = False

`src/main.py` と `src/generated_intro_main.py` は `--append-end-cta` を `store_true` として解析し、このフィールドに渡す。PowerShellでは対応する `[switch]$AppendEndCta` を受け、Unix形式のバッチ入力では `--append-end-cta` を `-AppendEndCta` に変換する。

## Plan Revision Notes

2026-07-30 / Codex: 初版作成。ユーザー指定の「コマンドで任意に有効化」「高評価とチャンネル登録への一言」「既存変更を含むpush」を、元JSON非変更・既存パイプライン再利用という方針に具体化した。

2026-07-30 / Codex: テスト先行で実装し、CTAの視覚素材はCLIキーワードの上書き処理後に末尾台本へ追加することにした。これにより `--query-mode override` でもCTA専用の映像検索語を失わない。

2026-07-30 / Codex: 実装後の対象テストは21件、全pytestは170件成功した。通常CLI、生成AI導入CLI、PowerShellラッパーのplan-only実行でCTAのエンドツーエンド引数伝搬を確認した。
