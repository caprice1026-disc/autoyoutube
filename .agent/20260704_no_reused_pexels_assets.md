# 同一動画内でPexels素材を使い回さない

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

この計画はリポジトリ直下の `PLANS.md` と `AGENTS.md` に従って管理する。作業ディレクトリは `C:\Users\Hodaka\Downloads\div\autoyoutube` である。

## Purpose / Big Picture

現在のAutoYoutubeは複数の動画素材をつなげられるが、同じPexels素材または同じ登録素材が一つのShorts内で再び選ばれることがある。視聴者には同じ映像が繰り返し流れているように見え、飽きやすさにつながる。この変更により、レンダー中の素材選定は一つの動画内で既に使った `asset_id` を再利用せず、素材が足りない場合は無理に同じ動画を再利用せず既存のフォールバック映像に任せる。さらに `evaluate-render` とSkill手順に、同じ素材が再利用されていないか確認する手順を追加する。

## Progress

- [x] (2026-07-04 19:32+09:00) 既存の素材選定が直前の素材だけを避け、`A, B, A` のような再利用を許すことを確認した。
- [x] (2026-07-04 19:32+09:00) ローカルSkillの `agents/openai.yaml` に日本語UI文言があり、環境によって文字化けしやすいことを確認した。
- [x] (2026-07-04 19:40+09:00) 素材再利用を許す既存テストを、同一動画内の再利用を禁止する期待値に変更した。
- [x] (2026-07-04 19:40+09:00) 品質評価に、非連続の同一 `asset_id` 再利用を警告するテストを追加した。
- [x] (2026-07-04 19:40+09:00) レンダー選定を、動画単位の使用済み `asset_id` セットで除外する実装へ変更した。
- [x] (2026-07-04 19:40+09:00) `evaluate-render` の視覚素材チェックに、同一動画内の素材再利用警告を追加した。
- [x] (2026-07-04 19:44+09:00) private publisher Skillとリポジトリ内Skillに、台本からPexels検索語を作る手順と素材再利用確認手順を追加した。
- [x] (2026-07-04 19:44+09:00) READMEを現状の挙動に合わせて更新した。
- [x] (2026-07-04 19:50+09:00) 対象pytest、Ruff check、全体pytest、Skill validationを通した。
- [x] (2026-07-04 19:52+09:00) 変更をcommitした。
- [ ] mainへpushする。

## Surprises & Discoveries

- Observation: 既存テスト `test_render_project_avoids_consecutive_same_media_asset_when_possible` は、3カットに対して2素材しかない場合に `["ocean_a", "ocean_b", "ocean_a"]` を期待しており、今回の問題をそのまま固定していた。
  Evidence: `tests/test_render_project_ffmpeg.py` の該当テストで `asset_ids` が同じ `asset_id` の再利用を期待していた。

- Observation: ローカルSkillの `agents/openai.yaml` は不正なUTF-8バイトを含み、`apply_patch` で読み取れなかった。
  Evidence: `apply_patch` が `invalid utf-8 sequence` で失敗したため、Skill Creatorの `generate_openai_yaml.py` でUTF-8のASCII UI metadataとして再生成した。

## Decision Log

- Decision: Pexelsだけでなく、DBに登録された全てのMediaAssetで同一動画内の `asset_id` 再利用を避ける。
  Rationale: レンダー選定はPexelsとlocalを同じ `MediaAsset` として扱う。視聴者に見える問題は素材の出所に関係なく同じであり、Pexelsだけを特別扱いするとlocal素材では同じ退屈さが残る。
  Date/Author: 2026-07-04 / ChatGPT

- Decision: 素材が足りないときは既に使った素材を選び直さず、元のベースvisualを残してFFmpeg側の既存フォールバックに任せる。
  Rationale: ユーザーの要求は同じPexels素材の使い回しを避けることなので、素材不足時に再利用を優先すると要求に反する。既存レンダーは `asset_id` がないvisualを単色または既存背景として処理できる。
  Date/Author: 2026-07-04 / ChatGPT

## Outcomes & Retrospective

実装とドキュメント更新は完了した。追加・変更したテストは `test_render_project_avoids_reusing_same_media_asset_in_one_render`、`test_render_project_does_not_reuse_available_media_when_query_has_no_match`、`test_evaluate_render_reports_reused_visual_asset_within_render` である。検証では対象pytestが21件成功し、全体pytestが93件成功した。`ruff check .` は成功した。`ruff format . --check` は既存の未整形ファイルを多数指摘したため、今回触ったPythonファイルのみ `ruff format` し、対象ファイルのformat checkを成功させた。Skill validationは、リポジトリvenvにはPyYAMLが無いため失敗したが、システムPythonで `autoyoutube-private-publisher` と `autoyoutube-shorts` の両方が `Skill is valid!` になった。変更は `Avoid reusing visual assets within a render` としてcommitした。

## Context and Orientation

`src/pipeline/render_project.py` の `render_project` は `project.youtube.json` を読み、音声、字幕、BGM、映像素材を選定して `rendered.youtube.json` を出力する。映像素材は `MediaAsset` と呼ばれるDB登録済みの動画で、Pexelsから取得した動画もローカル動画も同じ型で扱う。`asset_id` は登録素材を識別する文字列で、同じ `asset_id` が `rendered.youtube.json` の `visuals[]` に複数回出ると、同じ素材を同じ動画内で使い回したことを意味する。

現在の `src/pipeline/render_project.py` は `_select_render_visuals` で `previous_asset_id` だけを覚え、直前と同じ素材を避ける。これでは1つ前以外の素材、例えば1番目と3番目に同じPexels動画が選ばれることを防げない。

`src/quality/evaluator.py` の `_visual_checks` は `SAME_ASSET_CONSECUTIVE` で連続使用だけを警告する。非連続の再利用を検出するには、これまで見た `asset_id` と最初のindexを保持し、同じ `asset_id` が後で再登場したら新しい警告を出す必要がある。

Skillは2種類ある。`C:\Users\Hodaka\.codex\skills\autoyoutube-private-publisher` は台本から動画を作成しYouTube privateへアップロードするローカルSkillである。`skills/autoyoutube-shorts` はリポジトリに同梱された、ローカル生成と検査を支援するSkillである。前者はアップロードまで、後者は公開前のローカル制作と検査までを役割にする。

## Plan of Work

最初にテストを変更する。`tests/test_render_project_ffmpeg.py` では、2素材しかない状態で3つの同じ `visual_query` を持つプロジェクトをレンダーしたとき、3つ目は `asset_id` を持たず同じ素材を再利用しないことを期待する。既存の「クエリに一致しないとき使える素材を再利用する」テストも、既に使った素材を再利用しない期待値へ変更する。

次に `tests/test_quality_evaluator.py` に、`visuals[]` が `A, B, A` になっているrendered JSONを評価したとき `SAME_ASSET_REUSED` が出るテストを追加する。連続再利用の既存テストは `SAME_ASSET_CONSECUTIVE` のまま残す。

実装では `src/pipeline/render_project.py` の `_select_render_visuals` を `used_asset_ids: set[str]` で制御する。`select_media_asset` に渡す候補は使用済み `asset_id` を除外したものにし、フォールバック選定でも同じく使用済みを除外する。候補が無くなったら `None` を返し、元のvisualを残す。

品質評価では `src/quality/evaluator.py` の `_visual_checks` に `seen_asset_indices` を追加する。直前と同じ場合は既存の `SAME_ASSET_CONSECUTIVE` を出し、直前ではないが過去に出ている場合は `SAME_ASSET_REUSED` を出す。警告の `metrics` には `asset_id`、最初に使われたindex、今回のindexを含める。

Skill更新では、ローカル private publisher Skillの `agents/openai.yaml` のUI文言をASCIIにする。`references/workflow.md` には、台本から英語Pexels検索語を作り `primary_query`、`script[].visual_query`、`fallback_queries` に反映してから `fetch-visuals` を実行する手順を追加する。さらに `evaluate-render` 後に `quality_report.json` と `rendered.youtube.json` の `visuals[].asset_id` を見て重複を確認する手順を追加する。リポジトリ同梱Skillにも同等の方針を追記する。

READMEには、レンダーは同一動画内で同じ登録素材を再利用しないこと、素材不足時は再利用ではなくフォールバックに任せること、`evaluate-render` が連続または非連続の再利用を警告することを追記する。

## Concrete Steps

リポジトリルートで以下の検証を行う。

    .\.venv\Scripts\python.exe -m pytest tests\test_render_project_ffmpeg.py tests\test_quality_evaluator.py -q
    .\.venv\Scripts\python.exe -m ruff check .
    .\.venv\Scripts\python.exe -m ruff format src\pipeline\render_project.py src\quality\evaluator.py tests\test_render_project_ffmpeg.py tests\test_quality_evaluator.py --check
    .\.venv\Scripts\python.exe -m pytest -q

Skillの構造確認は以下で行う。

    python C:\Users\Hodaka\.codex\skills\.system\skill-creator\scripts\quick_validate.py C:\Users\Hodaka\.codex\skills\autoyoutube-private-publisher
    python C:\Users\Hodaka\.codex\skills\.system\skill-creator\scripts\quick_validate.py skills\autoyoutube-shorts

mainへのpushは、作業branch上でcommit後に `origin/main` を取り込み、conflictがあればローカルを正として解決したうえで `HEAD:main` へpushする。

## Validation and Acceptance

受け入れ条件は、`tests/test_render_project_ffmpeg.py` の素材選定テストが同一動画内の `asset_id` 重複を許さなくなること、`tests/test_quality_evaluator.py` が `A, B, A` の非連続再利用を `SAME_ASSET_REUSED` として検出すること、Ruffとpytestが成功することである。

人間が動作を確認する場合は、Pexels素材が2件しかない3カットのプロジェクトをレンダーし、`rendered.youtube.json` の `visuals[].asset_id` に重複が出ないことを見る。素材が不足しているカットでは `asset_id` が無いvisualになり、同じPexels素材を再利用しない。

## Idempotence and Recovery

テスト変更とコード変更は通常のGit差分として安全に繰り返せる。レンダー出力、Pexelsダウンロード、DB、トークン、`.env` はコミットしない。push前に `git status -sb` と `git diff --stat` で対象ファイルを確認し、明示的に必要なファイルだけをstageする。merge conflictが出た場合は、ユーザー指示どおりローカル変更を正として解決し、その後Ruffとpytestを再実行する。

## Artifacts and Notes

主な変更対象は以下である。

    src/pipeline/render_project.py
    src/quality/evaluator.py
    tests/test_render_project_ffmpeg.py
    tests/test_quality_evaluator.py
    README.md
    skills/autoyoutube-shorts/references/pexels-workflow.md
    skills/autoyoutube-shorts/references/quality-report.md
    C:\Users\Hodaka\.codex\skills\autoyoutube-private-publisher\agents\openai.yaml
    C:\Users\Hodaka\.codex\skills\autoyoutube-private-publisher\references\workflow.md

## Interfaces and Dependencies

新しい外部依存は追加しない。既存の `MediaAsset`、`select_media_asset`、`evaluate-render`、`quality_report.json` を利用する。新しい品質チェックコードは `SAME_ASSET_REUSED` とし、既存の `SAME_ASSET_CONSECUTIVE` は後方互換のため残す。
