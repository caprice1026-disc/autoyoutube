# autoyoutube-shorts Skill 土台実装

This ExecPlan is a living document. The sections `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` must be kept up to date as work proceeds.

この計画はリポジトリ直下の `PLANS.md` と `AGENTS.md` に従って管理する。作業ディレクトリはリポジトリルートである。

## Purpose / Big Picture

この変更により、`autoyoutube` のローカル動画生成ワークフローを ChatGPT / Codex が安定して扱えるようにするための Skill パッケージをリポジトリ内に追加する。Phase 1〜4で追加した `inspect-render`、`timeline.png`、`fetch-visuals`、複数素材タイムライン合成を、毎回の長い説明なしで再利用できる操作マニュアルとして固定する。

## Progress

- [x] (2026-07-04) `AGENTS.md` を確認し、ExecPlanを `.agent/` 配下に作成した。
- [x] `skills/autoyoutube-shorts/SKILL.md` を追加する。
- [x] `agents/openai.yaml` を追加する。
- [x] CLIコマンド、品質レポート、視覚検査、Pexels/visuals、Codex修正ループの参照ファイルを追加する。
- [x] Skill構造の最低限テストを追加する。
- [ ] ローカルで `pytest` / `ruff` を実行し、PRに結果を記録する。

## Surprises & Discoveries

- Observation: Phase 1〜4により、Skillから参照すべきCLIと成果物がすでに揃っている。
  Evidence: `inspect-render`、`evaluate-render`、`fetch-visuals`、複数素材renderがmainに入っている前提で進められる。

## Decision Log

- Decision: Skill本体には実行コードを入れず、`autoyoutube` CLIの操作順序と判断ルールを固定する。
  Rationale: 実処理は既存CLIが担っており、SkillはCodex/ChatGPTの運用手順を安定させる役割に集中する方が保守しやすい。
  Date/Author: 2026-07-04 / ChatGPT

- Decision: `SKILL.md` は短くし、詳細な手順は `references/` 配下へ分割する。
  Rationale: Skillはコンテキスト効率が重要であり、必要な詳細だけ段階的に読む設計にするため。
  Date/Author: 2026-07-04 / ChatGPT

## Outcomes & Retrospective

Phase 5では、`skills/autoyoutube-shorts/` にSkill entrypoint、UI metadata、参照ドキュメントを追加した。Skillは実行コードを持たず、既存CLIの順序、品質レポートの読み方、視覚検査、Pexels/visuals、Codex修正ループを固定する構成にした。最低限の構造テストも追加した。ローカル実行環境がないため、pytestとruffの実行はPRレビュー側で行う。

## Context and Orientation

このリポジトリはYouTube Shorts向けのローカル半自動生成パイプラインである。入力は `project.youtube.json`、出力は `rendered.youtube.json`、`output.mp4`、`quality_report.json`、`inspect/`配下のPNGである。Skillはこれらの生成・検査・修正ループを案内する。

## Plan of Work

`skills/autoyoutube-shorts/` 配下にSkillパッケージを作る。`SKILL.md` には使うべき場面、必須ルール、標準ワークフロー、参照ファイルの読み分けを記述する。`references/` にはCLI一覧、品質レポートの読み方、視覚検査、Pexels/visuals、Codex修正ループを分けて置く。

## Concrete Steps

リポジトリルートで以下を確認する。

    python -m pytest -q
    python -m ruff check .

Skill利用時の基本CLIは以下である。

    python -m src.main validate-project projects/<project_id>/project.youtube.json
    python -m src.main fetch-visuals projects/<project_id>/project.youtube.json --per-query 3 --max-downloads 20
    python -m src.main render projects/<project_id>/project.youtube.json --voice-mode aivis --video-mode ffmpeg
    python -m src.main validate-render renders/<project_id>/rendered.youtube.json
    python -m src.main inspect-render renders/<project_id>/rendered.youtube.json
    python -m src.main evaluate-render renders/<project_id>/rendered.youtube.json

## Validation and Acceptance

受け入れ条件は、Skillに必須ファイルが揃い、`SKILL.md` にfrontmatterがあり、参照ファイルが存在し、テストがそれを検査できることである。実動画生成は今回の受け入れ条件には含めない。

## Idempotence and Recovery

Skillファイルはドキュメント中心であり、再実行による副作用はない。将来的にSkillをzip化する場合は、`skills/autoyoutube-shorts/` をルートとしてパッケージ化する。

## Artifacts and Notes

変更対象は、`skills/autoyoutube-shorts/`、`.agent/20260704_autoyoutube_shorts_skill.md`、`tests/test_skill_structure.py` である。

## Interfaces and Dependencies

Skill自体は追加Python依存を持たない。`autoyoutube` の既存CLI、FFmpeg、AivisSpeech、Pexels APIキー、SQLite DBを前提とする。
