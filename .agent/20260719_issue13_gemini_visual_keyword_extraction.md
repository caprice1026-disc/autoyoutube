# Issue #13: Gemini による映像検索キーワード抽出

## 目的

ナレーションと動画素材の関連性を改善するため、Gemini を任意利用してシーンごとの英語検索キーワード、視覚意図、除外語を生成し、既存の Pexels 素材検索へ渡す。Gemini が未設定・失敗・レート制限時でも、従来の検索語を用いるため動画制作フローは停止しない。

## 進捗

- [x] Issue #13 の受け入れ条件と既存の素材取得・選択・レンダリング経路を確認した。
- [x] `master` を起点に `codex/issue-13-llm-keywords` ブランチを作成した。
- [x] Gemini REST クライアント、JSON 検証、ローカルキャッシュを実装した。
- [x] `fetch-visuals` と `make-video` に一度だけキーワード抽出を統合した。
- [x] 視覚検索計画と選択結果にキーワード根拠を記録した。
- [x] 設定例、README、テストを追加・更新した。
- [x] Ruff と pytest を実行し、実装をコミット・push した。PR #14 を `master` 宛てに作成した。

## 現状と設計判断

既存の `src/media/visual_fetcher.py` は、プロジェクト JSON の `visual_query` と `fallback_queries` を Pexels 検索に渡し、`*.visual_plan.json` に取得計画を書き出す。`src/pipeline/make_video.py` はその計画を使ってレンダリングし、最終的に `visual_assignment.json` を保存する。

Gemini SDK を追加せず、既存の Pexels クライアントと同様に標準ライブラリの HTTP 通信で Gemini の REST API を呼ぶ。これにより依存関係を増やさず、Gemini 呼び出しはプロジェクトごとに一回のバッチ要求に制限する。キャッシュキーはモデル名、プロンプト版、シーン本文から算出し、API キーを保存しない。

Gemini が返す JSON はシーン番号ごとに `primary_keywords`、`secondary_keywords`、`visual_intent`、`avoid_keywords` を持つ。主・補助語から具体的な検索語を組み立て、抽象語だけなら `visual_intent` を検索語に使う。元の検索語と既存 fallback は保持し、失敗時はプロジェクト内容を変更しない。

## 実装計画

1. `src/media/gemini_keyword_extractor.py` を追加する。環境変数の読取、Gemini REST 通信、JSON の抽出・検証、キャッシュ、プロジェクトへの検索語反映をここに閉じ込める。
2. 素材取得関数に、既に抽出済みかどうかを示す結果を渡せるようにする。単独の `fetch-visuals` では抽出を実行し、`make-video` では開始時に一回だけ実行して重複呼び出しを防ぐ。
3. `visual_plan` と `visual_assignment.json` に、抽出状態、モデル、各シーンのキーワードと視覚意図を残す。これにより選択素材と検索根拠を追跡できる。
4. 正常応答、未設定、通信エラー、壊れた JSON、キャッシュ再利用、抽象語補正を単体テストする。パイプライン側では成果物への記録をテストする。
5. `.env.example`、`.gitignore`、README に設定、任意性、失敗時フォールバック、キャッシュ位置を記載する。

## 検証方法

`.venv\Scripts\python.exe -m ruff check src tests` と `.venv\Scripts\python.exe -m pytest` を実行する。Gemini API の実呼び出しは行わず、HTTP transport を差し替えたテストで日本語入力から英語キーワードへ変換される契約を検証する。

## 変更範囲

- `src/media/gemini_keyword_extractor.py`（新規）
- `src/media/visual_fetcher.py`
- `src/pipeline/make_video.py`
- `tests/` 配下の関連テスト（新規・更新）
- `.env.example`、`.gitignore`、`README.md`

## 決定ログ

- 2026-07-19: 課金と依存関係を抑えるため Gemini SDK は追加せず、標準ライブラリ HTTP を採用する。
- 2026-07-19: API 呼び出し数を抑えるため、シーンごとの呼び出しではなくプロジェクト単位のバッチ要求とする。
- 2026-07-19: 生成メディア・DB・秘密情報・キャッシュはコミット対象にしない。
- 2026-07-19: Gemini APIの未設定・通信例外・レート制限・壊れたJSONでは、常に元の検索語へフォールバックする。

## 完了条件

受け入れ条件の各フォールバックがテストで検証され、検索・選択成果物でシーンごとの LLM 検索根拠を確認できる。Ruff と pytest が通り、`master` をベースとする PR が作成されていること。
