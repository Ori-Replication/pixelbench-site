# PixelBench — aggregated scores report

- run: `run_final_all_models` | judge: **gpt-6-astra** (category_hybrid, temperature 0.2, max_tokens 250)
- 75 tasks x 13 models = 975 judge cells; 4 human raters (per-task full ranking, rank 1 = best)
- judge preprocessing: native -> left W/16, top H/16 transparent padding -> NEAREST 512x512
- generated: 2026-09-16T08:38:09Z

## Agreement with the human ranking

| metric | value |
|---|---:|
| mean over tasks of Kendall tau-b (primary) | **0.5756** |
| task-level bootstrap 95% CI | [0.5330, 0.6180] |
| mean over tasks of Spearman | 0.7022 |
| pooled Spearman over 975 pairs | 0.5899 |
| judge vs consensus of the other three raters (leave-one-out tau-b) | 0.5599 |
| held-out rater vs the other three (leave-one-out tau-b) | 0.5956 |
| rater vs rater (mean pairwise tau-b) | 0.5285 |

## Model leaderboard

| # | model | judge mean | judge rank | human mean rank | human rank |
|---:|---|---:|---:|---:|---:|
| 1 | GPT-6 Astra (`gpt-6-astra`) | 85.20 | 1 | 3.057 | 1 |
| 2 | GPT-6 Astra (no vision) (`gpt-6-astra-novision`) | 84.11 | 2 | 3.467 | 2 |
| 3 | GPT-5.6 Sol (`gpt-5.6-sol`) | 82.05 | 3 | 5.200 | 4 |
| 4 | Qwen3.8 Max (`qwen3.8-max`) | 81.65 | 4 | 6.040 | 6 |
| 5 | Gemini 3.8 Flash (`gemini-3.8-flash`) | 80.93 | 5 | 5.060 | 3 |
| 6 | Claude Opus 5 (`claude-opus-5`) | 80.16 | 6 | 5.683 | 5 |
| 7 | Kimi K3 (`kimi-k3`) | 79.48 | 7 | 6.717 | 7 |
| 8 | GLM-5.3 Flash (`glm-5.3-flash`) | 78.39 | 8 | 7.573 | 8 |
| 9 | DeepSeek-V4 Flash (`deepseek-v4-flash`) | 77.96 | 9 | 8.043 | 9 |
| 10 | DeepSeek-V4 Pro (`deepseek-v4-pro`) | 75.76 | 10 | 9.017 | 10 |
| 11 | Gemini 3.1 Pro Preview (`gemini-3.1-pro-preview`) | 70.60 | 11 | 9.153 | 11 |
| 12 | Kimi K2.7 Code (`kimi-k2.7-code`) | 66.79 | 12 | 10.853 | 12 |
| 13 | Qwen3.5 397B A17B (`qwen3.5-397b-a17b`) | 65.45 | 13 | 11.137 | 13 |

## Judge mean by category

| category | n | GPT-6 Astra | DeepSeek-V4 Flash | DeepSeek-V4 Pro | GPT-5.6 Sol | Gemini 3.1 Pro Preview | Gemini 3.8 Flash | Kimi K2.7 Code | Qwen3.5 397B A17B | Kimi K3 | GLM-5.3 Flash | Qwen3.8 Max | Claude Opus 5 | GPT-6 Astra (no vision) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| UI类 | 7 | 86.7 | 86.1 | 84.6 | 87.6 | 84.6 | 88.4 | 76.6 | 73.0 | 85.1 | 85.1 | 85.6 | 88.3 | 86.6 |
| 人物类 | 13 | 84.2 | 72.3 | 72.8 | 81.2 | 63.7 | 81.7 | 61.3 | 59.9 | 76.2 | 75.0 | 78.3 | 76.2 | 83.4 |
| 场景类 | 16 | 85.2 | 76.8 | 68.9 | 79.9 | 59.6 | 81.5 | 60.7 | 58.1 | 76.9 | 73.3 | 79.8 | 77.5 | 82.1 |
| 材质类 | 5 | 82.4 | 79.0 | 75.2 | 82.2 | 70.4 | 74.4 | 71.2 | 72.4 | 78.0 | 77.8 | 79.4 | 78.8 | 82.0 |
| 物品类 | 21 | 86.8 | 81.7 | 79.1 | 84.3 | 77.8 | 80.5 | 71.7 | 72.0 | 83.7 | 82.4 | 85.1 | 82.0 | 86.2 |
| 特效类 | 3 | 83.3 | 69.0 | 83.3 | 76.7 | 71.3 | 70.0 | 67.3 | 71.0 | 80.0 | 76.7 | 81.0 | 80.0 | 81.3 |
| 生物类 | 10 | 84.2 | 75.7 | 75.4 | 79.6 | 72.1 | 81.3 | 64.2 | 60.3 | 75.7 | 78.6 | 80.3 | 80.8 | 84.1 |

## Note on the judge model

The judge is `gpt-6-astra`, which is also one of the 13 evaluated models and ranks first under its own scoring. The human raters also place it first, and the leave-one-out numbers above put the judge (0.5599) between the human pairwise level (0.5285) and a held-out human (0.5956). An independent pilot judge (`gemini-3.8-flash`, which is not the top-ranked model) produced the same ordering, with a pooled Spearman of 0.623.
