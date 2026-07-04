# fetch-visuals

`fetch-visuals` は、`project.youtube.json` のテーマ・台本・visual queryをもとに、Pexelsから複数の映像候補を取得し、候補ごとのスコアを `visual_plan.json` として保存するコマンドです。

既存の `fetch-pexels` は単純な事前取得コマンドとして残し、`fetch-visuals` はPhase 3以降の複数素材選定・タイムライン合成に向けた上位コマンドとして使います。

## 使い方

```powershell
.\.venv\Scripts\python.exe -m src.main fetch-visuals projects\trivia_xxx\project.youtube.json --per-query 3 --max-downloads 20
```

出力先を明示する場合:

```powershell
.\.venv\Scripts\python.exe -m src.main fetch-visuals projects\trivia_xxx\project.youtube.json --output-dir assets\pexels --plan-path assets\pexels\trivia_xxx.visual_plan.json
```

## 入力に使うquery

以下を重複排除して使います。

```text
visual_strategy.primary_query
script[].visual_query
visual_strategy.fallback_queries[]
```

同じqueryが複数箇所にある場合は、script indexや推定秒数をまとめて `visual_plan.json` に記録します。

## 出力

```text
assets/pexels/
  pexels_123_deep_ocean.mp4
  pexels_456_glowing_jellyfish.mp4
  trivia_xxx.visual_plan.json
```

## visual_plan.json

例:

```json
{
  "schema_version": "visual-plan-1.0.0",
  "project_id": "trivia_xxx",
  "fetch": {
    "provider": "pexels",
    "output_dir": "assets/pexels",
    "per_query": 3,
    "max_downloads": 20,
    "orientation": "portrait",
    "size": "small"
  },
  "summary": {
    "query_count": 5,
    "downloaded_asset_count": 12,
    "queries_with_candidates": 5
  },
  "queries": [
    {
      "query": "deep ocean",
      "source": "visual_strategy.primary_query+script.visual_query",
      "script_indices": [1],
      "target_duration_sec": 3.5,
      "candidate_count": 3,
      "selected_asset_id": "pexels_123_deep_ocean",
      "candidates": [
        {
          "asset_id": "pexels_123_deep_ocean",
          "score": 85,
          "reasons": [
            "orientation matches portrait",
            "meets 1080x1920 target",
            "duration covers target script window",
            "quality=hd",
            "credit metadata is complete"
          ]
        }
      ]
    }
  ]
}
```

## スコアリング方針

加点:

```text
- portrait orientation
- 1080x1920以上
- scriptの想定尺をカバーできるduration
- HD以上のquality
- Pexels credit metadataが揃っている
```

減点:

```text
- landscapeでcropが強くなりそう
- 解像度が低い
- scriptの想定尺に対して短い
- used_countが高い
```

## Phase 4へのつながり

Phase 4では、この `visual_plan.json` をもとに、scriptごとに候補素材を割り当てて、複数素材タイムライン合成を行う予定です。

```text
script[1] -> selected_asset_id A
script[2] -> selected_asset_id B
script[3] -> selected_asset_id C
```
