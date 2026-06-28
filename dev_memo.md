# 開発メモ

## 現在の実装状況

- `schemas/project.youtube.schema.json` と `schemas/rendered.youtube.schema.json` は、JSONとして正しい形に整形済みです。1行に圧縮された状態ではなく、差分確認やレビューがしやすいインデント付きの形式になっています。
- `projects/trivia_submarine_black_001/project.youtube.json` は、`schemas/project.youtube.schema.json` で検証できるサンプルプロジェクトとして利用できます。
- `src/validators/json_validator.py` には、JSONファイルの読み込み、JSON Schemaによる検証、検証エラーの読みやすい文字列表現が実装されています。
- `src/main.py` には、DB初期化、project JSON検証、仮レンダー、rendered JSON検証を行うCLIが実装されています。
- `src/pipeline/render_project.py` の仮レンダー処理は、外部API、音声合成、Pexels、FFmpegを実行せずに、`rendered.youtube.json` や説明文、字幕、クレジット、ログのプレースホルダーを生成するMVP段階の実装です。
- `tests/` 配下にpytest用テストを追加し、スキーマ自体の妥当性、サンプルproject JSONの検証、余分なプロパティの拒否、検証エラーパスの整形を確認できるようにしました。

## テスト方針

- `requirements.txt` に `pytest` を追加し、依存関係をインストールした環境で `python -m pytest` を実行できるようにしています。
- スキーマ整形だけでなく、JSON Schemaとして壊れていないことを `Draft202012Validator.check_schema` で確認します。
- サンプルproject JSONが現在のprojectスキーマに適合することを確認します。
- `additionalProperties=false` のような重要な制約が効いていることを、あえて不正な項目を追加したテストで確認します。
- 検証エラーが `$.items[1].name` のように原因箇所を追いやすい形式で返ることを確認します。

## 今後の課題

- 仮レンダー処理のテストを追加し、`rendered.youtube.json`、字幕、説明文、クレジット、DB保存の内容を一時ディレクトリ上で検証できるようにする必要があります。
- `src/pipeline/render_project.py` の `_build_rendered` は現状1行に近い大きな辞書リテラルを返しているため、保守しやすい小さな関数へ分割する余地があります。
- 将来的にAivisSpeech、Pexels、FFmpegを接続する場合は、外部依存を直接呼び出す前に抽象化層を作り、ユニットテストではモックやスタブで置き換えられる設計にするのが安全です。
- rendered JSONのサンプルファイルを追加すると、`schemas/rendered.youtube.schema.json` に対する実データ検証テストもより分かりやすくなります。
- CLIの正常系・異常系テストを追加し、終了コードと日本語メッセージが期待どおりであることを確認すると、運用時の品質が上がります。
