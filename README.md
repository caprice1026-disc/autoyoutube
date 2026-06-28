# Trivia Shorts Maker for YouTube

YouTube Shorts向けの雑学ショート動画を、ローカル環境で半自動生成するための基盤MVPです。

現時点では外部API、AivisSpeech、Pexels、FFmpegは呼び出しません。まずは `project.youtube.json` を読み込み、JSON Schemaで検証し、SQLiteへ保存し、仮の `rendered.youtube.json` と投稿補助ファイルを生成します。

## セットアップ

```bash
python -m pip install -r requirements.txt
```

## 主なコマンド

```bash
python -m src.main init-db
python -m src.main validate-project projects/trivia_submarine_black_001/project.youtube.json
python -m src.main render projects/trivia_submarine_black_001/project.youtube.json
python -m src.main validate-render renders/trivia_submarine_black_001/rendered.youtube.json
```

## 生成される主なファイル

`render` コマンドは `renders/{project_id}/` に以下を生成します。

- `rendered.youtube.json`
- `description.txt`
- `credits.txt`
- `subtitle.ass`
- `logs/ffmpeg_command.txt`
- `logs/ffmpeg_stderr.log`

`renders/` と `data/*.db` は生成物のためGit管理対象外です。
