# エラーハンドリング強化とBGM統合 実装結果

This ExecPlan result note records the implementation outcome for `.agent/20260628_error_handling_and_bgm.md`.

## Progress

- [x] `AppError` を追加し、CLI では通常時に `Error`, `Location`, `Details`, `Next step` を表示し、`--debug` の時だけ traceback を出す形にした。
- [x] JSON 読み込み失敗、JSON構文エラー、JSON root 型不一致、FFmpeg未検出、FFmpeg実行失敗を利用者向けの短いエラーに変換した。
- [x] `src/bgm` を追加し、BGM manifest 読み込み、条件一致選定、DB登録、active track一覧取得を実装した。
- [x] `import-bgm` と `list-bgm` CLI を追加した。
- [x] FFmpeg renderer に、BGMが渡された場合だけ `filter_complex` の `amix` で narration と BGM を合成する分岐を追加した。
- [x] `render_project` でDB登録済みBGMを選び、`rendered.youtube.json` の `bgm` と `credits` に記録するようにした。
- [x] 実生成検証用にローカル生成BGMを作り、manifest import 後に FFmpeg render を実行した。

## Validation

実行した検証:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m src.main validate-project projects\trivia_submarine_black_001\project.youtube.json
.\.venv\Scripts\python.exe -m src.main import-bgm assets\bgm\bgm_manifest.json
.\.venv\Scripts\python.exe -m src.main list-bgm
.\.venv\Scripts\python.exe -m src.main render projects\trivia_submarine_black_001\project.youtube.json --video-mode ffmpeg --ffmpeg-path "C:\Users\Hodaka\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1.2-full_build\bin\ffmpeg.exe"
```

結果:

- `pytest`: `21 passed`
- project JSON validation: succeeded
- BGM import: `Imported BGM tracks: 1`
- 実生成: `renders\trivia_submarine_black_001\output.mp4`
- ffprobe確認: 1080x1920 H.264 video、AAC audio、duration 13.36秒
- `rendered.youtube.json`: `status=success`, `bgm.enabled=true`, `rendered_json_valid=true`

## Notes

`assets/bgm`, `data`, `renders` は `.gitignore` で生成物扱いになっている。今回の実生成検証では `assets/bgm/bgm_manifest.json` と `assets/bgm/generated_mystery_low.wav` をローカルに生成して使った。
