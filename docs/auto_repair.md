# auto repair

`make-video` の自動改善ループは、`quality_report.json` の機械可読なcheckを読み、機械的に直せるものだけを対象に再試行します。事実確認、台本短縮、タイトル改善、BGMの雰囲気判断は自動では行いません。

## 設定

既定設定は `config/auto_repair.youtube_shorts.json` にあります。

優先順位は次の通りです。

```text
CLI引数 > 環境変数 > config/auto_repair.youtube_shorts.json > コード上のデフォルト
```

attempt上限は `AUTOYOUTUBE_MAX_FIX_ATTEMPTS` でも上書きできます。

```powershell
$env:AUTOYOUTUBE_MAX_FIX_ATTEMPTS = "3"
.\.venv\Scripts\python.exe -m src.main make-video projects\example_project.youtube.json
```

## 自動改善するもの

初期実装では、過去のprivate publisher運用で手動改善していた内容を優先しています。

- `SAME_ASSET_CONSECUTIVE`: 同じ素材の連続使用を避ける
- `SAME_ASSET_REUSED`: 同じ素材の再利用を避ける
- `SOURCE_RESOLUTION_TOO_LOW`: 低解像度素材を避ける
- Pexels候補不足やfetch失敗: 候補数を増やすか、DB上のlocal stockへfallbackする
- `inspect-render` の一部失敗: failure logへ残し、`evaluate-render` で品質判定を続ける

重複や低解像度の素材が見つかった場合、対象 `asset_id` をそのrun内の `rejected_asset_ids` に入れ、次attemptでは選定対象から外します。同時に `per_query` を増やしてPexels候補を広げます。

## 動画尺の扱い

`VIDEO_DURATION_TOO_LONG` は既定ではwarning扱いです。60秒を超えただけでは停止せず、台本短縮も自動では行いません。

過去の運用と同じように読み上げ速度と文間を自動調整したい場合だけ、設定で明示的に有効化します。

```json
{
  "duration": {
    "auto_increase_speed_for_duration": true
  }
}
```

有効時は、次attemptで `voice.speed_scale` を少し上げ、`voice.sentence_gap_ms` を短くします。元のproject JSONは変更せず、attempt用JSONだけを変更します。

## ログ

`repair_log.json` にはattemptごとのcheckとfixを記録します。

```json
{
  "schema_version": "repair-log-1.0.0",
  "project_id": "example_project",
  "seed": 123456789,
  "max_attempts": 5,
  "final_status": "success",
  "final_attempt": 2,
  "attempts": [
    {
      "attempt": 1,
      "render_dir": "renders/example/attempts/attempt_001",
      "quality_report_path": "renders/example/attempts/attempt_001/quality_report.json",
      "checks": [
        {
          "code": "SAME_ASSET_REUSED",
          "level": "warning",
          "auto_fixable": true
        }
      ],
      "fixes": [
        {
          "action": "reject_asset_and_reselect",
          "asset_id": "pexels_123",
          "reason": "SAME_ASSET_REUSED"
        }
      ]
    }
  ]
}
```

`failure_log.json` には環境、外部API、render、quality、encodingの失敗分類を記録します。`visual_assignment.json` には最終採用attemptで使った素材を記録します。

## 自動改善しないもの

- 台本短縮
- 事実確認
- 動画内容と台本の文脈一致
- タイトル改善
- 説明文改善
- BGMの雰囲気判断
- 合成メディア開示判断

これらは人間レビュー対象です。
