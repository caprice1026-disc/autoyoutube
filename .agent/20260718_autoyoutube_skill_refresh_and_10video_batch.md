# AutoYoutubeスキル更新と40秒動画10本の実行計画

## 目的

現在のCLI実装と `autoyoutube-private-publisher` スキルの手順を照合し、差分があればスキルを現行実装に合わせて更新する。その後、指定された10テーマの40秒前後のプロジェクトJSONを作成し、既定BGMで実レンダリング、品質確認、必要に応じた修正を行う。アップロードはユーザーが明示した範囲に限り、YouTubeでは非公開として扱う。

## 作業方針

1. `src/main.py`、`src/pipeline/make_video.py`、設定、BGMマニフェスト、既存テストを読み、スキルのコマンド・既定値・完了条件を照合する。
2. 差分がある場合は、現行の `make-video` 統合フロー、auto-repair、品質レポート、private upload の実際の挙動をスキルと参照文書へ反映する。
3. 10本の `projects/shorts40_*/project.youtube.json` をUTF-8で作成し、各台本は8〜10カット、対象物が冒頭で特定できる具体的な英語visual queryを持たせる。
4. プロジェクトJSONの検証、DB/BGM初期化、Pexels接続確認、素材取得、AivisSpeech確認、`make-video` 実行の順で進める。
5. 各動画で `validate-render`、`quality_report.json`、`inspect` を確認し、エラー、素材重複、60秒超過がある場合はアップロードを止めて修正する。

## 受入条件

- スキルと現行CLIの差分が記録され、必要な更新がUTF-8で反映されている。
- 10本すべてのプロジェクトJSONがスキーマ検証を通過する。
- 各動画が実音声・FFmpegで生成され、品質レポートのエラー数が0である。
- 生成物・DB・秘密情報をGitへ追加しない。
- ユーザーがアップロードを求めた場合のみ、品質確認後にprivateで実行し、URLとrendered JSONの記録を確認する。

## 進捗

- [x] 現行CLIとスキルの差分調査
- [ ] スキルと参照文書の更新
- [ ] 10本のプロジェクトJSON作成・検証
- [ ] 素材取得・音声・レンダリング
- [ ] 品質確認と必要な修正
- [ ] （明示された場合）YouTube非公開アップロード

## 判断ログ

- 40秒テストは `target.duration_sec=40` を基準にする。ただし音声実測で多少変動するため、60秒上限と品質レポートを最終判定に使う。
- BGMは既存の `DEFAULT_BGM_TRACK_ID` とマニフェストに合わせ、ユーザー指定どおり既定曲を使う。
- 製品差や安全設計に関する説明は、JSONの `fact_check_notes` とYouTube disclaimerに明記し、公開せずprivateで人手確認可能な状態にする。
