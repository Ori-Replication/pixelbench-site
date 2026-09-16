# PixelBench — aggregated scores report

- run: `run_final_all_models`  |  generated: 2026-09-16T06:45:34Z
- 75 tasks x 13 models = 975 judge cells; 4 human raters (per-task full ranking, rank 1 = best)
- judge: gemini-3.8-flash (0-100 scale)
- source images present: 975/975

## 1. Model leaderboard

| # | model | judge_mean | judge_rank | human_mean_rank | human_rank | human_pct_mean | median | n |
|---:|---|---:|---:|---:|---:|---:|---:|---:|
| 1 | GPT-6 Astra (`gpt-6-astra`) | 83.39 | 1 | 3.057 | 1 | 0.83 | 85.00 | 75 |
| 2 | GPT-6 Astra (no vision) (`gpt-6-astra-novision`) | 83.32 | 2 | 3.467 | 2 | 0.79 | 85.00 | 75 |
| 3 | GPT-5.6 Sol (`gpt-5.6-sol`) | 80.67 | 3 | 5.200 | 4 | 0.65 | 82.00 | 75 |
| 4 | Gemini 3.8 Flash (`gemini-3.8-flash`) | 80.19 | 4 | 5.060 | 3 | 0.66 | 82.00 | 75 |
| 5 | Qwen3.8 Max (`qwen3.8-max`) | 78.09 | 5 | 6.040 | 6 | 0.58 | 80.00 | 75 |
| 6 | Claude Opus 5 (`claude-opus-5`) | 76.15 | 6 | 5.683 | 5 | 0.61 | 78.00 | 75 |
| 7 | Kimi K3 (`kimi-k3`) | 76.05 | 7 | 6.717 | 7 | 0.52 | 78.00 | 75 |
| 8 | GLM-5.3 Flash (`glm-5.3-flash`) | 75.59 | 8 | 7.573 | 8 | 0.45 | 78.00 | 75 |
| 9 | DeepSeek-V4 Flash (`deepseek-v4-flash`) | 73.33 | 9 | 8.043 | 9 | 0.41 | 74.00 | 75 |
| 10 | DeepSeek-V4 Pro (`deepseek-v4-pro`) | 69.84 | 10 | 9.017 | 10 | 0.33 | 72.00 | 75 |
| 11 | Gemini 3.1 Pro Preview (`gemini-3.1-pro-preview`) | 63.61 | 11 | 9.153 | 11 | 0.32 | 68.00 | 75 |
| 12 | Kimi K2.7 Code (`kimi-k2.7-code`) | 61.35 | 12 | 10.853 | 12 | 0.18 | 62.00 | 75 |
| 13 | Qwen3.5 397B A17B (`qwen3.5-397b-a17b`) | 59.01 | 13 | 11.137 | 13 | 0.16 | 62.00 | 75 |

Sorted by judge_mean descending. human_mean_rank: mean 1-based rank over the 4 raters and 75 tasks (lower is better, 1.0 best / 13.0 worst).

Interpretation note: ranks are assigned per task, so for every task the 13 model ranks are a permutation of 1..13 and the per-task mean rank is exactly 7.0. Consequently `human_mean_rank` is a task-averaged rank that must average 7.0 across models (verified: the 13 values sum to exactly 91.0); the extremes 1.0/13.0 are only reachable by a model ranked 1st/13th on all 75 tasks. The observed span is 3.057 (best) .. 11.137 (worst).

## 2. Per-subcategory judge means

| subcategory | n_tasks | mean judge | best model (judge) | best model (human) |
|---|---:|---:|---|---|
| UI类 | 7 | 73.78 | GPT-6 Astra | Gemini 3.8 Flash |
| 人物类 | 13 | 71.03 | GPT-6 Astra | GPT-6 Astra |
| 场景类 | 16 | 75.92 | GPT-6 Astra | GPT-6 Astra |
| 材质类 | 5 | 64.49 | GPT-6 Astra (no vision) | GPT-6 Astra (no vision) |
| 物品类 | 21 | 76.44 | GPT-6 Astra (no vision) | GPT-6 Astra |
| 特效类 | 3 | 64.31 | Gemini 3.8 Flash | GPT-5.6 Sol |
| 生物类 | 10 | 76.66 | GPT-6 Astra | GPT-6 Astra |

Category mean judge = mean of the per-model category judge means (13 models per category). Categories with few tasks (特效类 n=3, 材质类 n=5) are noisy; per-model cells are in `categories` of scores.json.

### Per-model judge mean by subcategory

| model | UI类 | 人物类 | 场景类 | 材质类 | 物品类 | 特效类 | 生物类 |
|---|---:|---:|---:|---:|---:|---:|---:|
| GPT-6 Astra | 84.14 | 84.00 | 86.31 | 71.40 | 84.86 | 68.33 | 84.80 |
| GPT-6 Astra (no vision) | 81.71 | 83.15 | 85.31 | 74.80 | 85.43 | 72.33 | 84.60 |
| GPT-5.6 Sol | 79.57 | 78.00 | 84.06 | 72.00 | 83.38 | 73.00 | 80.40 |
| Gemini 3.8 Flash | 82.14 | 77.15 | 82.25 | 72.60 | 82.57 | 79.33 | 78.50 |
| Qwen3.8 Max | 77.86 | 75.77 | 81.69 | 63.20 | 82.38 | 62.00 | 78.80 |
| Claude Opus 5 | 79.57 | 71.31 | 79.25 | 65.00 | 78.29 | 65.67 | 79.30 |
| Kimi K3 | 77.43 | 73.08 | 81.19 | 62.00 | 79.19 | 65.67 | 74.30 |
| GLM-5.3 Flash | 76.71 | 71.77 | 78.19 | 63.80 | 78.29 | 62.33 | 79.80 |
| DeepSeek-V4 Flash | 72.57 | 70.46 | 76.31 | 73.00 | 75.00 | 54.33 | 75.20 |
| DeepSeek-V4 Pro | 72.43 | 66.62 | 71.38 | 49.00 | 73.67 | 66.33 | 73.20 |
| Gemini 3.1 Pro Preview | 60.71 | 61.00 | 61.38 | 58.40 | 67.10 | 58.00 | 69.60 |
| Kimi K2.7 Code | 56.14 | 57.38 | 61.31 | 51.80 | 63.43 | 54.00 | 72.80 |
| Qwen3.5 397B A17B | 58.14 | 53.69 | 58.38 | 61.40 | 60.14 | 54.67 | 65.30 |

## 3. Meta correlations

- `judge_human_correlation` (Spearman, 975 task x model pairs, judge score vs mean human (13-rank)/12): **0.623**
- `rater_spearman` (mean pairwise Spearman between the 4 raters, all 6 pairs x 75 tasks): **0.670**

## 4. Anomalies and checks

- Missing result images: 0
- All self-checks passed (model means/medians recomputed from the raw judge file, 975/975 numeric cells in each matrix, human ranks conserved at exactly 91.0 per task and overall, human_pct_mean ordering consistent with human_mean_rank, models sorted by judge_mean desc, tasks sorted by idx, img maps complete with 13 models each).

### Other data observations

- No exact judge_mean ties, so judge_rank is a strict 1..13 ordering.
- Adjacent pairs within 0.5 judge points (4 of 12): their judge ordering is not robust to judge noise.
  - GPT-6 Astra (judge 83.39, human 3.057) vs GPT-6 Astra (no vision) (judge 83.32, human 3.467), gap 0.07 — vision / no-vision variant of the same base model: the judge is insensitive to the vision input, while human mean rank does separate them.
  - GPT-5.6 Sol (judge 80.67, human 5.200) vs Gemini 3.8 Flash (judge 80.19, human 5.060), gap 0.48
  - Claude Opus 5 (judge 76.15, human 5.683) vs Kimi K3 (judge 76.05, human 6.717), gap 0.10
  - Kimi K3 (judge 76.05, human 6.717) vs GLM-5.3 Flash (judge 75.59, human 7.573), gap 0.46
- judge_mean span across the 13 models: 83.39 (best) .. 59.01 (worst) = 24.38 points on a 0-100 scale.
- Lowest-scoring task: slash-effect (39.31 mean judge, best model gemini-3.8-flash); highest: arcane-instrument-giant (92.38).

#### Within-category judge-vs-human rank disagreements (|delta| >= 3)

Ranks computed among the 13 models inside each category; small-n categories (特效类 n=3, 材质类 n=5) are unstable.

- 人物类 (n=13): Claude Opus 5 judge_rank 8 vs human_rank 5 (+3) — judge 71.31, human mean rank 5.635
- 材质类 (n=5): Gemini 3.8 Flash judge_rank 3 vs human_rank 11 (-8) — judge 72.60, human mean rank 7.900
- 材质类 (n=5): DeepSeek-V4 Flash judge_rank 2 vs human_rank 8 (-6) — judge 73.00, human mean rank 6.950
- 材质类 (n=5): Qwen3.8 Max judge_rank 8 vs human_rank 2 (+6) — judge 63.20, human mean rank 4.850
- 材质类 (n=5): DeepSeek-V4 Pro judge_rank 13 vs human_rank 9 (+4) — judge 49.00, human mean rank 7.300
- 特效类 (n=3): Gemini 3.8 Flash judge_rank 1 vs human_rank 10 (-9) — judge 79.33, human mean rank 9.667
- 特效类 (n=3): Qwen3.8 Max judge_rank 9 vs human_rank 5 (+4) — judge 62.00, human mean rank 4.833
- 特效类 (n=3): Claude Opus 5 judge_rank 6 vs human_rank 3 (+3) — judge 65.67, human mean rank 4.333
- 特效类 (n=3): GLM-5.3 Flash judge_rank 8 vs human_rank 11 (-3) — judge 62.33, human mean rank 9.833
- 特效类 (n=3): DeepSeek-V4 Flash judge_rank 12 vs human_rank 9 (+3) — judge 54.33, human mean rank 8.333
- 生物类 (n=10): Gemini 3.8 Flash judge_rank 7 vs human_rank 3 (+4) — judge 78.50, human mean rank 4.950
- 生物类 (n=10): GLM-5.3 Flash judge_rank 4 vs human_rank 7 (-3) — judge 79.80, human mean rank 6.925
- 生物类 (n=10): Gemini 3.1 Pro Preview judge_rank 12 vs human_rank 9 (+3) — judge 69.60, human mean rank 7.425

### Judge vs human rank disagreements (|judge_rank - human_rank| >= 3)

None: the largest judge-vs-human rank gap is 1 position(s) (threshold for listing is 3).

### Largest rater disagreement per task (top 8 by human_spread)

human_spread = mean over the 13 models of the population SD of that model's 4 rater ranks (in rank units).

| task | idx | size | subcategory | judge_mean | human_spread |
|---|---:|---|---|---:|---:|
| rpg-grass-material | 63 | 16x16 | 材质类 | 64.08 | 2.981 |
| seamless-carpet-pattern | 65 | 32x32 | 材质类 | 78.85 | 2.771 |
| retro-film-camera | 6 | 32x32 | 物品类 | 80.31 | 2.740 |
| rts-factory-icon | 69 | 32x32 | UI类 | 73.85 | 2.615 |
| green-pear | 7 | 32x32 | 物品类 | 66.54 | 2.500 |
| minecraft-dirt-material | 61 | 16x16 | 材质类 | 60.54 | 2.452 |
| dining-table | 15 | 64x64 | 物品类 | 75.46 | 2.389 |
| portable-cassette-player | 10 | 32x32 | 物品类 | 82.15 | 2.293 |

### Smallest rater disagreement per task (top 5)

| task | idx | subcategory | judge_mean | human_spread |
|---|---:|---|---:|---:|
| dragon-hatchling | 42 | 生物类 | 73.85 | 0.786 |
| e-scooter-rider | 25 | 人物类 | 72.85 | 0.834 |
| east-hero-full-body | 34 | 人物类 | 70.85 | 0.911 |
| sky-pirate-girl | 23 | 人物类 | 69.31 | 0.914 |
| glow-jellyfish | 35 | 生物类 | 76.46 | 0.947 |

### Hardest / easiest tasks by judge_mean

| | task | idx | subcategory | judge_mean | best_model |
|---|---|---:|---|---:|---|
| lowest | slash-effect | 66 | 特效类 | 39.31 | gemini-3.8-flash |
| lowest | minecraft-stone-material | 62 | 材质类 | 52.54 | gemini-3.8-flash |
| lowest | minecraft-dirt-material | 61 | 材质类 | 60.54 | claude-opus-5 |
| lowest | swordsman-walk-animation | 30 | 人物类 | 62.62 | gpt-5.6-sol |
| lowest | rpg-grass-material | 63 | 材质类 | 64.08 | deepseek-v4-flash |
| highest | arcane-instrument-giant | 21 | 物品类 | 92.38 | gpt-6-astra |
| highest | void-eye | 43 | 生物类 | 84.62 | kimi-k3 |
| highest | open-pocket-watch | 20 | 物品类 | 83.62 | gpt-6-astra-novision |
| highest | farm-chicken | 37 | 生物类 | 83.15 | qwen3.8-max |
| highest | portable-cassette-player | 10 | 物品类 | 82.15 | gemini-3.8-flash |

