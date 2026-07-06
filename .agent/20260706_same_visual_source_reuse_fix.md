# 同一動画素材再利用対策 実装計画

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 1本の動画内で同じ元動画素材が繰り返し使われた場合に評価段階で止め、Pexelsの取得量増加とローカル素材へのフォールバックで再試行できるようにする。

**Architecture:** `asset_id` ではなく、Pexels なら `pexels_id`、ローカルならファイル実体を基準に重複判定する。評価で検出したら `make-video` の修復ループがブロック扱いにし、次の試行ではより多くのPexels候補を取り直し、必要なら DB の local stock を選び直す。加えて、一括実行スクリプトは `WARNING` 以外の失敗だけを次コマンドへ引き継がず、飛ばして次へ進む。

**Tech Stack:** Python, pytest, Ruff, PowerShell, FFmpeg, SQLite, Pexels API

---

### Task 1: 重複判定の基準を拡張する

**Files:**
- Modify: `src/media/library.py`
- Modify: `src/media/pexels_client.py`
- Modify: `src/media/selector.py`
- Modify: `src/pipeline/render_project.py`
- Modify: `src/quality/evaluator.py`
- Modify: `src/repair/quality_repair.py`
- Modify: `src/pipeline/make_video.py`
- Test: `tests/test_quality_evaluator.py`
- Test: `tests/test_render_project_ffmpeg.py`
- Test: `tests/test_media_library.py`

**Step 1: Write the failing test**

```python
def test_evaluator_detects_same_pexels_source_even_if_asset_id_differs():
    ...
```

**Step 2: Run test to verify it fails**

Run: `.\.venv\Scripts\python.exe -m pytest tests\test_quality_evaluator.py -q`

**Step 3: Write minimal implementation**

- `MediaAsset` に重複判定用の fingerprint を追加する。
- Pexels は `pexels_id` を fingerprint に使う。
- ローカルは `sha256_file(local_file_path)` を fingerprint に使う。
- render/selector/evaluator の全段で fingerprint ベースの排他を入れる。

**Step 4: Run test to verify it passes**

Run: `.\.venv\Scripts\python.exe -m pytest tests\test_quality_evaluator.py tests\test_render_project_ffmpeg.py tests\test_media_library.py -q`

**Step 5: Commit**

```bash
git add src/media/library.py src/media/pexels_client.py src/media/selector.py src/pipeline/render_project.py src/quality/evaluator.py src/repair/quality_repair.py src/pipeline/make_video.py tests/test_quality_evaluator.py tests/test_render_project_ffmpeg.py tests/test_media_library.py
git commit -m "fix: avoid reusing the same visual source"
```

### Task 2: Pexels取得量を増やして再試行する

**Files:**
- Modify: `src/pipeline/make_video.py`
- Modify: `src/media/visual_fetcher.py`
- Modify: `src/media/pexels_client.py`
- Test: `tests/test_make_video.py`
- Test: `tests/test_visual_fetcher.py`

**Step 1: Write the failing test**

```python
def test_make_video_increases_fetch_budget_after_duplicate_source_warning():
    ...
```

**Step 2: Run test to verify it fails**

Run: `.\.venv\Scripts\python.exe -m pytest tests\test_make_video.py -q`

**Step 3: Write minimal implementation**

- 重複ソースの warning は blocking として扱う。
- 再試行時に `per_query` と `max_downloads` を増やす。
- 取得済み fingerprint は次回試行で除外する。
- 候補不足時は local stock を優先して補う。

**Step 4: Run test to verify it passes**

Run: `.\.venv\Scripts\python.exe -m pytest tests\test_make_video.py tests\test_visual_fetcher.py -q`

**Step 5: Commit**

```bash
git add src/pipeline/make_video.py src/media/visual_fetcher.py src/media/pexels_client.py tests/test_make_video.py tests/test_visual_fetcher.py
git commit -m "fix: widen visual fetch retries"
```

### Task 3: 一括実行スクリプトの失敗継続を修正する

**Files:**
- Modify: `scripts/run-upload-command-list.ps1`
- Modify: `scripts/run-upload-command-list.bat`
- Test: 既存の手動実行確認

**Step 1: Write the failing test**

```powershell
# 2番目のコマンドが失敗しても 3番目へ進むことを確認する
```

**Step 2: Run test to verify it fails**

Run: `.\scripts\run-upload-command-list.bat`

**Step 3: Write minimal implementation**

- `exit code 10` は従来通り継続。
- それ以外の失敗はログに残して次のコマンドへ進む。
- 最終的に失敗があった場合は非0を返す。

**Step 4: Run test to verify it passes**

Run: `.\scripts\run-upload-command-list.bat`

**Step 5: Commit**

```bash
git add scripts/run-upload-command-list.ps1 scripts/run-upload-command-list.bat
git commit -m "fix: continue batch uploads after failures"
```

### Task 4: 仕上げの検証と共有

**Files:**
- Modify: `README.md`
- Possibly modify: `docs/auto_repair.md`

**Step 1: Run the focused tests**

Run:
`.\.venv\Scripts\python.exe -m ruff check .`
`.\.venv\Scripts\python.exe -m pytest -q --basetemp .pytest_tmp`

**Step 2: Verify behavior**

- 重複素材が出たら評価で止まる
- 再試行で Pexels 候補数が増える
- local stock へ fallback する
- 一括実行で失敗コマンドを飛ばして次へ進む

**Step 3: Commit**

```bash
git add README.md docs/auto_repair.md
git commit -m "docs: describe visual reuse recovery"
```

---

## Progress

- [x] 2026-07-06 計画を作成した
- [ ] 重複判定の基準を拡張する
- [ ] Pexels取得量を増やして再試行する
- [ ] 一括実行スクリプトの失敗継続を修正する
- [ ] 仕上げの検証を行う

## Decision Log

- Decision: 同一性判定は `asset_id` ではなく `pexels_id` / ファイル実体に寄せる。
  Rationale: 同じ元動画がクエリ違いで別 `asset_id` になる現象を防ぐため。

- Decision: 再試行時は `per_query` と `max_downloads` を増やす。
  Rationale: Pexels 側の候補数を増やす方が、local fallback だけに寄るより自然な改善になるため。

- Decision: 一括実行は失敗で停止せず、WARNING 以外の失敗だけ記録して次へ進む。
  Rationale: 長いコマンド列の途中で止まると、残りの生成が進まないため。

