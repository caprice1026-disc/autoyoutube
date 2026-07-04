# AutoYoutube Private Publisher Skill 最適化計画

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

この計画はリポジトリ直下の `PLANS.md` と `AGENTS.md` に従って管理する。作業ディレクトリは `C:\Users\Hodaka\Downloads\div\autoyoutube` であり、Python コマンドは `.\.venv\Scripts\python.exe` を使う。

## Purpose / Big Picture

`autoyoutube-private-publisher` とリポジトリ内の `autoyoutube-shorts` を、実際の運用結果に合わせて更新する。主眼は次の3点である。

1. `.env` の `PEXELS_API_KEY` と `secrets\client_secret.json` を前提条件として明記する。
2. 実行時に露出した失敗点を Skill に反映する。具体的には、字幕の見切れ回避、同一 Pexels 素材の再利用禁止、`inspect-render` の Windows 文字化け対策、レンダー時間の余白確保を扱う。
3. ローカル Skill と repo 内 Skill の両方を同じ方針に揃え、必要なら `agents/openai.yaml` も更新する。

## Progress

- [x] (2026-07-04) 既存の Skill 定義と参考資料を読み、現行の前提を確認した。
- [x] (2026-07-04) 実運用のレンダー結果を踏まえ、改善点を整理した。
- [x] (2026-07-04) Skill 本体と参照ファイルを更新した。
- [x] (2026-07-04) `quick_validate.py` を UTF-8 前提で通した。
- [x] (2026-07-04) repo 側の Skill 更新を commit / push した。

## Surprises & Discoveries

- `inspect-render` は Windows の既定文字コードだと FFmpeg 出力の解釈に失敗することがある。
- 1 本の動画で同じ Pexels 素材が再利用されると、評価上は `SAME_ASSET_REUSED` として扱うべきだった。
- 実レンダーでは字幕が長すぎると見切れるため、目安となる安全な長さを Skill に明示した方がよい。
- Skill の日本語文面を含むファイルは `quick_validate.py` で UTF-8 モードが必要だった。

## Decision Log

- Decision: `.env` と `secrets\client_secret.json` を既定の前提として Skill に明記する。
  Rationale: 毎回確認させるより、固定されたローカル前提として扱う方が運用に合うため。
  Date/Author: 2026-07-04 / Codex

- Decision: `inspect-render` の Windows 向け文字化け対策を手順に入れる。
  Rationale: 実運用で再現した失敗を回避でき、レビューの摩擦を減らせるため。
  Date/Author: 2026-07-04 / Codex

- Decision: 同一 render 内の Pexels 素材重複は upload 前停止扱いにする。
  Rationale: 視聴体験の低下を避けるため、検出した時点で再取得・再レンダーに戻す方がよい。
  Date/Author: 2026-07-04 / Codex

- Decision: Skill の検証は `PYTHONUTF8=1` を付けて実行する。
  Rationale: 日本語を含む Skill ファイルを Python の既定文字コードで読むと `quick_validate.py` が失敗するため。
  Date/Author: 2026-07-04 / Codex

## Outcomes & Retrospective

更新後の Skill は、台本から project JSON を組み、Pexels と BGM を選び、AivisSpeech と FFmpeg でレンダーし、品質検査を回し、private upload までを一貫して案内する。実運用で判明した失敗点を反映し、再現性の高い手順に寄せた。
`quick_validate.py` は UTF-8 モードで両方の Skill を通過した。repo 側の変更は commit して `origin/master` に push した。

## Context and Orientation

対象ファイルは次の通り。

- `C:\Users\Hodaka\.codex\skills\autoyoutube-private-publisher\SKILL.md`
- `C:\Users\Hodaka\.codex\skills\autoyoutube-private-publisher\references\workflow.md`
- `skills\autoyoutube-shorts\SKILL.md`
- `skills\autoyoutube-shorts\references\commands.md`
- `skills\autoyoutube-shorts\references\quality-report.md`
- `skills\autoyoutube-shorts\references\visual-inspection.md`
- `skills\autoyoutube-shorts\references\pexels-workflow.md`
- `skills\autoyoutube-shorts\agents\openai.yaml`
- `C:\Users\Hodaka\.codex\skills\autoyoutube-private-publisher\agents\openai.yaml`

## Plan of Work

1. Local Skill を更新する。
2. Repo Skill を更新する。
3. `agents/openai.yaml` を必要に応じて再生成する。
4. Skill 形状を検証する。
5. 変更を commit / push する。

## Concrete Steps

ローカル Skill の要点は次のとおり。

- `.env` に `PEXELS_API_KEY` がある前提を明記する。
- `secrets\client_secret.json` を YouTube OAuth の前提にする。
- `#Shorts` の維持、private upload、実レンダー、品質評価、再レンダーの順序を簡潔に整理する。
- `inspect-render` 実行時の Windows UTF-8 対応を補足する。
- 字幕の長さ目安を「見切れ回避の上限」として明示する。

Repo Skill 側は次のとおり。

- `project.youtube.json` の作成と検証。
- Pexels の query 設計と重複回避。
- `validate-render` / `inspect-render` / `evaluate-render` の順番。
- `SAME_ASSET_REUSED` を upload 前停止条件として強める。
- 必要なら `youtube-auth` の前提を追記する。

## Validation and Acceptance

以下を満たしたら完了とする。

- `quick_validate.py` 相当で Skill 構造が妥当。
- `SKILL.md` と `agents/openai.yaml` の内容が一致している。
- 変更内容が実運用の観点で矛盾しない。
- repo 側変更がある場合は `ruff` と `pytest` を通す前提を維持する。

## Idempotence and Recovery

Skill の更新は冪等に行う。途中で内容が崩れても、既存の `SKILL.md` をベースに戻して再編集できる。push 時に conflict が出た場合はローカルの内容を優先する。

## Artifacts and Notes

- 生成物や render 出力は commit しない。
- Skill そのものと、それに付随する `agents/openai.yaml` は commit 対象。

## Interfaces and Dependencies

- `.env`: `PEXELS_API_KEY`
- `secrets\client_secret.json`: YouTube OAuth client secret
- `.\.venv\Scripts\python.exe`
- `scripts\quick_validate.py`

## Plan Revision Notes

2026-07-04 / Codex: 実際の private publisher 実行で見えた前提と失敗点を Skill に反映するため、本 ExecPlan を追加した。
