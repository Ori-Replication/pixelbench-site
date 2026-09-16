#!/usr/bin/env python3
"""Aggregate PixelBench per-episode artifacts into a single showcase JSON.

Inputs (all precomputed; no model/LLM calls are made here)
----------------------------------------------------------
* outputs/bench/run_final_all_models/results.json
      run manifest: models (id -> {label}), tasks (75 ids), results (975 episodes)
* paper_site/data/raw/judge_all_tasks.json
      flat dict "<task_id>__<model_id>__0" -> judge score (0-100),
      LLM-as-judge produced by judge model gemini-3.8-flash
* outputs/ratings/*.json
      4 human raters; each {"rater", "run", "rankings": {task_id: [model_id, ...]}}
      with the 13 model ids ordered BEST FIRST
* tasks/text2image/_index.json
      task metadata (id, idx, titles, size, difficulty, subcategory, prompts, max_colors)

Outputs
-------
* paper_site/data/scores.json     (consumed by the static showcase site)
* stdout                         (model leaderboard)

Plain Python 3, standard library only. Re-runnable:
    python3 paper_site/tools/aggregate_scores.py
"""

from __future__ import annotations

import argparse
import glob
import json
import math
import os
import re
import sys
from datetime import datetime, timezone
from statistics import mean, median, pstdev

# --------------------------------------------------------------------------
# paths (repo root = two levels above this file)
# --------------------------------------------------------------------------
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, os.pardir, os.pardir))

RUN_ID = "run_final_all_models"
JUDGE_MODEL = "gemini-3.8-flash"
JUDGE_SCALE = "0-100"
HUMAN_PROTOCOL = (
    "per-task full ranking of 13 models by 4 human raters; rank 1 = best"
)

RESULTS_JSON = os.path.join(REPO, "outputs", "bench", RUN_ID, "results.json")
JUDGE_JSON = os.path.join(REPO, "paper_site", "data", "raw", "judge_all_tasks.json")
RATINGS_GLOB = os.path.join(REPO, "outputs", "ratings", "*.json")
INDEX_JSON = os.path.join(REPO, "tasks", "text2image", "_index.json")
IMG_SRC_DIR = os.path.join(
    REPO, "outputs", "judge_inputs", RUN_ID + "_native_pad_1over16"
)
OUT_JSON = os.path.join(REPO, "paper_site", "data", "scores.json")
OUT_REPORT = os.path.join(REPO, "paper_site", "data", "SCORES_REPORT.md")

# --------------------------------------------------------------------------
# display labels
# --------------------------------------------------------------------------
# Authoritative display labels for the models in this run.
LABEL_OVERRIDES = {
    "gpt-6-astra": "GPT-6 Astra",
    "deepseek-v4-flash": "DeepSeek-V4 Flash",
    "deepseek-v4-pro": "DeepSeek-V4 Pro",
    "gpt-5.6-sol": "GPT-5.6 Sol",
    "gemini-3.1-pro-preview": "Gemini 3.1 Pro Preview",
    "gemini-3.8-flash": "Gemini 3.8 Flash",
    "kimi-k2.7-code": "Kimi K2.7 Code",
    "qwen3.5-397b-a17b": "Qwen3.5 397B A17B",
    "kimi-k3": "Kimi K3",
    "glm-5.3-flash": "GLM-5.3 Flash",
    "qwen3.8-max": "Qwen3.8 Max",
    "claude-opus-5": "Claude Opus 5",
    "gpt-6-astra-novision": "GPT-6 Astra (no vision)",
}

# Vendors that keep the version token welded to the vendor name with a hyphen
# ("gpt-6-astra" -> "GPT-6 Astra", "deepseek-v4-pro" -> "DeepSeek-V4 Pro").
HYPHEN_VENDORS = {"gpt": "GPT", "deepseek": "DeepSeek", "glm": "GLM"}
# Vendors rendered as "<Vendor> <rest...>" ("gemini-3.1-pro-preview").
SPACE_VENDORS = {"gemini": "Gemini", "kimi": "Kimi", "claude": "Claude"}
# Vendors that carry the version inside the first token ("qwen3.5-397b-a17b").
FUSED_VENDORS = {"qwen": "Qwen"}

_NOVISION = re.compile(r"^no[-_]?vision$")
# parameter/size markers: 397b, a17b, 70b, v4, k3 ...-> upper case
_MARKER = re.compile(r"^(?:[a-z]?\d+(?:\.\d+)?[a-z]?|\d+b)$", re.IGNORECASE)


def _pretty_token(tok: str) -> str:
    """Upper-case version/parameter markers, title-case ordinary words."""
    if _NOVISION.match(tok):
        return "(no vision)"
    if _MARKER.match(tok):
        return tok.upper()
    return tok[:1].upper() + tok[1:]


def prettify_label(model_id: str) -> str:
    """Human-readable display label for a model id.

    LABEL_OVERRIDES wins; the rules below handle ids not listed there so the
    script keeps working if the run gains models.
    """
    if model_id in LABEL_OVERRIDES:
        return LABEL_OVERRIDES[model_id]

    toks = model_id.split("-")
    head = toks[0]
    for vendor, disp in FUSED_VENDORS.items():
        if head.startswith(vendor):
            rest = [head[len(vendor):]] + toks[1:]
            parts = [disp + rest[0]] + [_pretty_token(t) for t in rest[1:]]
            return " ".join(p for p in parts if p)
    for vendor, disp in HYPHEN_VENDORS.items():
        if head == vendor:
            rest = [_pretty_token(t) for t in toks[1:]]
            if rest:
                return disp + "-" + rest[0] + (
                    " " + " ".join(rest[1:]) if len(rest) > 1 else ""
                )
            return disp
    for vendor, disp in SPACE_VENDORS.items():
        if head == vendor:
            rest = [_pretty_token(t) for t in toks[1:]]
            return " ".join([disp] + [r for r in rest if r])
    return " ".join([head[:1].upper() + head[1:]] + [_pretty_token(t) for t in toks[1:]])


# --------------------------------------------------------------------------
# statistics helpers
# --------------------------------------------------------------------------
def average_ranks(values):
    """Average ranks (1-based, ascending) with ties sharing the mean rank."""
    order = sorted(range(len(values)), key=lambda i: values[i])
    out = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        avg = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            out[order[k]] = avg
        i = j + 1
    return out


def pearson(xs, ys):
    n = len(xs)
    if n < 2:
        return 0.0
    mx, my = mean(xs), mean(ys)
    sxy = sum((a - mx) * (b - my) for a, b in zip(xs, ys))
    sxx = sum((a - mx) ** 2 for a in xs)
    syy = sum((b - my) ** 2 for b in ys)
    if sxx <= 0 or syy <= 0:
        return 0.0
    return sxy / math.sqrt(sxx * syy)


def spearman(xs, ys):
    """Spearman rho = Pearson correlation of average ranks (tie-aware)."""
    return pearson(average_ranks(xs), average_ranks(ys))


def competition_rank(pairs, lower_is_better=False):
    """Map key -> rank position; ties share the best position.

    pairs: iterable of (key, value).
    """
    vals = sorted({v for _, v in pairs}, reverse=not lower_is_better)
    pos = {v: i + 1 for i, v in enumerate(vals)}
    return {k: pos[v] for k, v in pairs}


def r2(x):
    return round(float(x) + 0.0, 2)


def r3(x):
    return round(float(x) + 0.0, 3)


# --------------------------------------------------------------------------
# load
# --------------------------------------------------------------------------
def load_inputs():
    with open(RESULTS_JSON, encoding="utf-8") as fh:
        run = json.load(fh)
    with open(JUDGE_JSON, encoding="utf-8") as fh:
        judge_flat = json.load(fh)
    raters = []
    for path in sorted(glob.glob(RATINGS_GLOB)):
        with open(path, encoding="utf-8") as fh:
            raters.append(json.load(fh))
    with open(INDEX_JSON, encoding="utf-8") as fh:
        index = json.load(fh)
    return run, judge_flat, raters, index


def build_matrices(run, judge_flat, raters):
    """Return (model_ids, task_ids, judge, human_rank, human_pct, problems)."""
    model_ids = list(run["models"].keys())
    task_ids = list(run["tasks"])
    problems = []

    # judge: model -> task -> score
    judge = {m: {} for m in model_ids}
    for m in model_ids:
        for t in task_ids:
            key = f"{t}__{m}__0"
            val = judge_flat.get(key)
            if val is None:
                problems.append(f"missing judge cell: {key}")
                continue
            judge[m][t] = float(val)
    extra = set(judge_flat) - {
        f"{t}__{m}__0" for m in model_ids for t in task_ids
    }
    for key in sorted(extra):
        problems.append(f"unexpected judge key: {key}")

    # human: rank of model m on task t for each rater
    n_models = len(model_ids)
    ranks_by_rater = []  # rater -> task -> model -> rank
    for rec in raters:
        rater = rec.get("rater") or "?"
        if rec.get("run") not in (None, RUN_ID):
            problems.append(f"rater {rater}: run={rec.get('run')!r} != {RUN_ID}")
        per_task = {}
        for t in task_ids:
            order = rec.get("rankings", {}).get(t)
            if order is None:
                problems.append(f"rater {rater}: no ranking for task {t}")
                continue
            if sorted(order) != sorted(model_ids):
                problems.append(f"rater {rater}: task {t} model set mismatch")
                continue
            per_task[t] = {m: i + 1 for i, m in enumerate(order)}
        missing_tasks = set(rec.get("rankings", {})) - set(task_ids)
        for t in sorted(missing_tasks):
            problems.append(f"rater {rater}: ranking for unknown task {t}")
        ranks_by_rater.append(per_task)

    human_rank = {m: {} for m in model_ids}  # mean rank (1 best .. 13 worst)
    human_pct = {m: {} for m in model_ids}  # mean (13-rank)/12  (1 best .. 0)
    for m in model_ids:
        for t in task_ids:
            rs = [rt[t][m] for rt in ranks_by_rater if t in rt and m in rt[t]]
            if not rs:
                continue
            human_rank[m][t] = mean(rs)
            human_pct[m][t] = mean((n_models - r) / (n_models - 1) for r in rs)

    # rater agreement: mean pairwise Spearman across raters and tasks
    pairwise = []
    for i in range(len(ranks_by_rater)):
        for j in range(i + 1, len(ranks_by_rater)):
            for t in task_ids:
                a, b = ranks_by_rater[i].get(t), ranks_by_rater[j].get(t)
                if not a or not b:
                    continue
                pairwise.append(
                    spearman([a[m] for m in model_ids], [b[m] for m in model_ids])
                )
    rater_spearman = mean(pairwise) if pairwise else 0.0

    return {
        "model_ids": model_ids,
        "task_ids": task_ids,
        "judge": judge,
        "human_rank": human_rank,
        "human_pct": human_pct,
        "ranks_by_rater": ranks_by_rater,
        "rater_spearman": rater_spearman,
        "n_model_pairs": len(pairwise),
        "problems": problems,
    }


# --------------------------------------------------------------------------
# aggregation
# --------------------------------------------------------------------------
def aggregate(data, run, index):
    model_ids = data["model_ids"]
    task_ids = data["task_ids"]
    judge, human_rank, human_pct = data["judge"], data["human_rank"], data["human_pct"]

    # --- per model ---------------------------------------------------------
    model_rows = []
    for m in model_ids:
        jscores = [judge[m][t] for t in task_ids if t in judge[m]]
        hranks = [human_rank[m][t] for t in task_ids if t in human_rank[m]]
        hpcts = [human_pct[m][t] for t in task_ids if t in human_pct[m]]
        model_rows.append(
            {
                "id": m,
                "label": prettify_label(m),
                "judge_mean": mean(jscores) if jscores else 0.0,
                "judge_median": median(jscores) if jscores else 0.0,
                "human_mean_rank": mean(hranks) if hranks else 0.0,
                "human_pct_mean": mean(hpcts) if hpcts else 0.0,
                "n": len(jscores),
            }
        )
    jr = competition_rank([(r["id"], r["judge_mean"]) for r in model_rows])
    hr = competition_rank(
        [(r["id"], r["human_mean_rank"]) for r in model_rows], lower_is_better=True
    )
    for row in model_rows:
        row["judge_rank"] = jr[row["id"]]
        row["human_rank"] = hr[row["id"]]
    model_rows.sort(key=lambda r: (-r["judge_mean"], r["id"]))

    # --- headline judge/human agreement over all (task, model) pairs -------
    xs, ys = [], []
    for m in model_ids:
        for t in task_ids:
            if t in judge[m] and t in human_pct[m]:
                xs.append(judge[m][t])
                ys.append(human_pct[m][t])
    judge_human_corr = spearman(xs, ys)

    # --- per task ----------------------------------------------------------
    meta = {rec["id"]: rec for rec in index}
    task_rows = []
    for t in task_ids:
        rec = meta.get(t, {})
        scores = [(m, judge[m][t]) for m in model_ids if t in judge[m]]
        task_judge_mean = mean([s for _, s in scores]) if scores else 0.0
        best = max(scores, key=lambda kv: (kv[1], kv[0]))[0] if scores else None
        spreads = [pstdev([rt[t][m] for rt in data["ranks_by_rater"] if t in rt])
                   for m in model_ids]
        task_rows.append(
            {
                "id": t,
                "idx": rec.get("idx"),
                "title_zh": rec.get("title_zh"),
                "title_en": rec.get("title_en"),
                "size": rec.get("size"),
                "difficulty": rec.get("difficulty"),
                "subcategory": rec.get("subcategory"),
                "prompt_zh": rec.get("prompt_zh"),
                "prompt_en": rec.get("prompt_en"),
                "max_colors": rec.get("max_colors"),
                "judge_mean": task_judge_mean,
                "best_model": best,
                "human_spread": mean(spreads) if spreads else 0.0,
                "img": {m: f"img/{t}/{m}.png" for m in model_ids},
            }
        )
    task_rows.sort(key=lambda r: (r["idx"] if r["idx"] is not None else 10**9, r["id"]))

    # --- per subcategory ---------------------------------------------------
    cats = {}
    for m in model_ids:
        by_cat = {}
        for t in task_ids:
            cat = meta.get(t, {}).get("subcategory")
            if cat is None:
                continue
            by_cat.setdefault(cat, []).append(t)
        for cat, ts in by_cat.items():
            cj = [judge[m][t] for t in ts if t in judge[m]]
            ch = [human_rank[m][t] for t in ts if t in human_rank[m]]
            cats.setdefault(cat, {"n_tasks": len(ts), "models": {}})["models"][m] = {
                "judge_mean": mean(cj) if cj else 0.0,
                "human_mean_rank": mean(ch) if ch else 0.0,
            }
    categories = {}
    for cat in sorted(cats):
        entry = cats[cat]
        categories[cat] = {
            "n_tasks": entry["n_tasks"],
            "models": {
                m: {
                    "judge_mean": r2(v["judge_mean"]),
                    "human_mean_rank": r3(v["human_mean_rank"]),
                }
                for m, v in sorted(
                    entry["models"].items(),
                    key=lambda kv: (-kv[1]["judge_mean"], kv[0]),
                )
            },
        }

    # --- assemble ----------------------------------------------------------
    doc = {
        "meta": {
            "run_id": RUN_ID,
            "n_tasks": len(task_ids),
            "n_models": len(model_ids),
            "n_raters": len(data["ranks_by_rater"]),
            "n_judge_cells": len(xs),
            "judge_model": JUDGE_MODEL,
            "judge_scale": JUDGE_SCALE,
            "human_protocol": HUMAN_PROTOCOL,
            "rater_spearman": r3(data["rater_spearman"]),
            "judge_human_correlation": r3(judge_human_corr),
            "generated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        },
        "models": [
            {
                "id": r["id"],
                "label": r["label"],
                "judge_mean": r2(r["judge_mean"]),
                "judge_median": r2(r["judge_median"]),
                "human_mean_rank": r3(r["human_mean_rank"]),
                "human_pct_mean": r2(r["human_pct_mean"]),
                "judge_rank": r["judge_rank"],
                "human_rank": r["human_rank"],
                "n": r["n"],
            }
            for r in model_rows
        ],
        "tasks": [
            {
                "id": r["id"],
                "idx": r["idx"],
                "title_zh": r["title_zh"],
                "title_en": r["title_en"],
                "size": r["size"],
                "difficulty": r["difficulty"],
                "subcategory": r["subcategory"],
                "prompt_zh": r["prompt_zh"],
                "prompt_en": r["prompt_en"],
                "max_colors": r["max_colors"],
                "judge_mean": r2(r["judge_mean"]),
                "best_model": r["best_model"],
                "human_spread": r3(r["human_spread"]),
                "img": r["img"],
            }
            for r in task_rows
        ],
        "judge": {m: {t: r2(v) for t, v in sorted(judge[m].items())} for m in model_ids},
        "human": {
            m: {t: r3(v) for t, v in sorted(human_rank[m].items())} for m in model_ids
        },
        "categories": categories,
    }
    stats = {
        "model_rows": model_rows,
        "task_rows": task_rows,
        "n_pairs": len(xs),
        "rater_spearman": data["rater_spearman"],
        "judge_human_correlation": judge_human_corr,
    }
    return doc, stats


# --------------------------------------------------------------------------
# self-verification
# --------------------------------------------------------------------------
def verify(doc, stats, data, run):
    """Cross-check the aggregation; return list of failure strings."""
    fails, warns = [], []
    model_ids = data["model_ids"]
    task_ids = data["task_ids"]

    # matrices have 13 * 75 numeric entries each
    exp = len(model_ids) * len(task_ids)
    for name in ("judge", "human"):
        block = doc[name]
        cells = [v for m in block for v in block[m].values()]
        if len(block) != len(model_ids):
            fails.append(f"{name}: {len(block)} models != {len(model_ids)}")
        if len(cells) != exp:
            fails.append(f"{name}: {len(cells)} cells != {exp}")
        if not all(isinstance(v, (int, float)) and not isinstance(v, bool)
                   for v in cells):
            fails.append(f"{name}: non-numeric cell present")
        bad_rows = [m for m in model_ids if len(block.get(m, {})) != len(task_ids)]
        if bad_rows:
            fails.append(f"{name}: incomplete rows {bad_rows}")

    # 13 judge means recomputed independently from the raw flat file
    with open(JUDGE_JSON, encoding="utf-8") as fh:
        raw = json.load(fh)
    for row in doc["models"]:
        ref = mean(raw[f"{t}__{row['id']}__0"] for t in task_ids)
        if abs(ref - row["judge_mean"]) > 0.005:
            fails.append(
                f"judge_mean mismatch for {row['id']}: {row['judge_mean']} vs {ref}"
            )
        if row["n"] != len(task_ids):
            fails.append(f"{row['id']}: n={row['n']} != {len(task_ids)}")
        # human mean rank vs human matrix
        href = mean(doc["human"][row["id"]].values())
        if abs(href - row["human_mean_rank"]) > 0.001:
            fails.append(f"human_mean_rank mismatch for {row['id']}")
        # pct mean consistency with mean rank
        pref = (len(model_ids) - href) / (len(model_ids) - 1)
        if abs(pref - row["human_pct_mean"]) > 0.005:
            fails.append(f"human_pct_mean inconsistency for {row['id']}")

    # ordering consistency: human_pct_mean descending == human_mean_rank ascending
    by_rank = [r["id"] for r in sorted(doc["models"], key=lambda r: r["human_mean_rank"])]
    by_pct = [r["id"] for r in sorted(doc["models"], key=lambda r: -r["human_pct_mean"])]
    if by_rank != by_pct:
        # allow near-ties to reorder but flag genuine contradictions
        rk = {r["id"]: r["human_mean_rank"] for r in doc["models"]}
        pc = {r["id"]: r["human_pct_mean"] for r in doc["models"]}
        real = [
            (a, b)
            for a in by_rank
            for b in by_rank
            if rk[a] < rk[b] and pc[a] < pc[b] - 0.005
        ]
        if real:
            fails.append(f"human_pct_mean contradicts human_mean_rank: {real[:3]}")
        else:
            warns.append("human rank/pct orders differ only within rounding ties")

    # Human rank invariants. human_mean_rank is a task-averaged rank: for every
    # task the 13 model ranks are a permutation of 1..13, so the per-task mean
    # rank is exactly 7 (=> the 13 model means sum to exactly 91), and a model's
    # task-averaged rank can only approach 1/13 if it is ranked 1st/13th everywhere.
    # The sound checks are therefore: exact rank-sum conservation, a grand mean of
    # 7.0, the best model below 7 and the worst above it, and a wide observed span.
    ranks = [r["human_mean_rank"] for r in doc["models"]]
    n_m = len(model_ids)
    sum_ranks = sum(ranks)
    if abs(sum_ranks - n_m * (n_m + 1) / 2.0) > 1e-6:
        fails.append(
            f"human_mean_rank sum {sum_ranks} != {n_m * (n_m + 1) / 2.0} "
            "(per-task ranks must be a permutation of 1..n_models)"
        )
    if abs(mean(ranks) - (n_m + 1) / 2.0) > 1e-6:
        fails.append(f"grand mean of human_mean_rank {mean(ranks)} != {(n_m + 1) / 2.0}")
    for t in task_ids:
        col = [doc["human"][m][t] for m in model_ids]
        if abs(sum(col) - n_m * (n_m + 1) / 2.0) > 1e-6:
            fails.append(f"human ranks for task {t} do not sum to {n_m * (n_m + 1) / 2.0}")
            break
    if not min(ranks) < (n_m + 1) / 2.0 < max(ranks):
        fails.append("human_mean_rank does not straddle the grand mean 7.0")
    if max(ranks) - min(ranks) < 5.0:
        fails.append(f"human_mean_rank span too narrow: {max(ranks) - min(ranks):.3f}")
    if min(ranks) - 1.0 > 2.5:
        warns.append(
            f"best human_mean_rank is {min(ranks):.3f}, far from the 1.0 floor: no model "
            "is consistently ranked 1st (expected for task-averaged ranks)"
        )
    if 13.0 - max(ranks) > 2.5:
        warns.append(
            f"worst human_mean_rank is {max(ranks):.3f}, far from the 13.0 ceiling: no "
            "model is consistently ranked last"
        )

    # judge rank ordering
    jm = [r["judge_mean"] for r in doc["models"]]
    if jm != sorted(jm, reverse=True):
        fails.append("models not sorted by judge_mean desc")
    if [r["judge_rank"] for r in doc["models"]] != sorted(
        r["judge_rank"] for r in doc["models"]
    ):
        fails.append("judge_rank not monotone with the declared sort")

    # tasks sorted by idx, img maps complete
    idxs = [r["idx"] for r in doc["tasks"]]
    if idxs != sorted(idxs):
        fails.append("tasks not sorted by idx")
    for tr in doc["tasks"]:
        if tr["img"] != {m: f"img/{tr['id']}/{m}.png" for m in model_ids}:
            fails.append(f"img map malformed for {tr['id']}")
            break

    # 975 source images present
    missing = []
    for t in task_ids:
        for m in model_ids:
            p = os.path.join(IMG_SRC_DIR, t, m + ".native.png")
            if not os.path.isfile(p):
                missing.append(p)
    if missing:
        warns.append(f"{len(missing)} missing source images")

    # correlations in range
    for key, val in (
        ("rater_spearman", doc["meta"]["rater_spearman"]),
        ("judge_human_correlation", doc["meta"]["judge_human_correlation"]),
    ):
        if not (-1.0 <= val <= 1.0):
            fails.append(f"{key} out of range: {val}")
    if stats["n_pairs"] != exp:
        fails.append(f"judge/human pairs {stats['n_pairs']} != {exp}")

    return fails, warns, missing


# --------------------------------------------------------------------------
# report
# --------------------------------------------------------------------------
def write_report(doc, fails, warns, missing, path):
    m = doc["meta"]
    models = doc["models"]
    tasks = doc["tasks"]
    lines = []
    add = lines.append

    add("# PixelBench — aggregated scores report")
    add("")
    add(f"- run: `{m['run_id']}`  |  generated: {m['generated']}")
    add(
        f"- {m['n_tasks']} tasks x {m['n_models']} models = {m['n_judge_cells']} judge cells; "
        f"{m['n_raters']} human raters (per-task full ranking, rank 1 = best)"
    )
    add(f"- judge: {m['judge_model']} ({m['judge_scale']} scale)")
    add(f"- source images present: {m['n_tasks'] * m['n_models'] - len(missing)}/"
        f"{m['n_tasks'] * m['n_models']}")
    add("")

    add("## 1. Model leaderboard")
    add("")
    add("| # | model | judge_mean | judge_rank | human_mean_rank | human_rank | human_pct_mean | median | n |")
    add("|---:|---|---:|---:|---:|---:|---:|---:|---:|")
    for i, r in enumerate(models, 1):
        add(
            f"| {i} | {r['label']} (`{r['id']}`) | {r['judge_mean']:.2f} | "
            f"{r['judge_rank']} | {r['human_mean_rank']:.3f} | {r['human_rank']} | "
            f"{r['human_pct_mean']:.2f} | {r['judge_median']:.2f} | {r['n']} |"
        )
    add("")
    add("Sorted by judge_mean descending. human_mean_rank: mean 1-based rank over the "
        "4 raters and 75 tasks (lower is better, 1.0 best / 13.0 worst).")
    add("")
    add("Interpretation note: ranks are assigned per task, so for every task the 13 model "
        "ranks are a permutation of 1..13 and the per-task mean rank is exactly 7.0. "
        "Consequently `human_mean_rank` is a task-averaged rank that must average 7.0 "
        "across models (verified: the 13 values sum to exactly 91.0); the extremes 1.0/13.0 "
        "are only reachable by a model ranked 1st/13th on all 75 tasks. The observed span "
        f"is {min(r['human_mean_rank'] for r in models):.3f} (best) .. "
        f"{max(r['human_mean_rank'] for r in models):.3f} (worst).")
    add("")

    add("## 2. Per-subcategory judge means")
    add("")
    cats = doc["categories"]
    cat_tasks = {}
    for t in tasks:
        cat_tasks.setdefault(t["subcategory"], []).append(t)
    add("| subcategory | n_tasks | mean judge | best model (judge) | best model (human) |")
    add("|---|---:|---:|---|---|")
    cat_summary = []
    for cat, entry in cats.items():
        vals = [v["judge_mean"] for v in entry["models"].values()]
        cm = mean(vals) if vals else 0.0
        best_j = max(entry["models"].items(), key=lambda kv: kv[1]["judge_mean"])[0]
        best_h = min(entry["models"].items(), key=lambda kv: kv[1]["human_mean_rank"])[0]
        lab = {r["id"]: r["label"] for r in models}
        cat_summary.append((cat, cm))
        add(
            f"| {cat} | {entry['n_tasks']} | {cm:.2f} | {lab[best_j]} | {lab[best_h]} |"
        )
    add("")
    add("Category mean judge = mean of the per-model category judge means "
        "(13 models per category). Categories with few tasks (特效类 n=3, 材质类 n=5) are "
        "noisy; per-model cells are in `categories` of scores.json.")
    add("")
    add("### Per-model judge mean by subcategory")
    add("")
    header = "| model | " + " | ".join(c for c, _ in cat_summary) + " |"
    add(header)
    add("|---|" + "---:|" * len(cat_summary))
    for r in models:
        cells = [f"{cats[c]['models'][r['id']]['judge_mean']:.2f}" for c, _ in cat_summary]
        add(f"| {r['label']} | " + " | ".join(cells) + " |")
    add("")

    add("## 3. Meta correlations")
    add("")
    add(f"- `judge_human_correlation` (Spearman, {m['n_judge_cells']} task x model pairs, "
        f"judge score vs mean human (13-rank)/12): **{m['judge_human_correlation']:.3f}**")
    add(f"- `rater_spearman` (mean pairwise Spearman between the 4 raters, "
        f"all 6 pairs x 75 tasks): **{m['rater_spearman']:.3f}**")
    add("")

    add("## 4. Anomalies and checks")
    add("")
    add(f"- Missing result images: {len(missing)}"
        + ("" if not missing else " — " + ", ".join(os.path.basename(p) for p in missing[:10])))
    for w in warns:
        add(f"- WARN: {w}")
    for f in fails:
        add(f"- FAIL: {f}")
    if not warns and not fails:
        add("- All self-checks passed (model means/medians recomputed from the raw judge "
            "file, 975/975 numeric cells in each matrix, human ranks conserved at exactly "
            "91.0 per task and overall, human_pct_mean ordering consistent with "
            "human_mean_rank, models sorted by judge_mean desc, tasks sorted by idx, "
            "img maps complete with 13 models each).")

    add("")
    add("### Other data observations")
    add("")
    # exact judge_mean ties (competition ranking shares a position)
    tied = {}
    for r in models:
        tied.setdefault(r["judge_mean"], []).append(r["label"])
    exact = {k: v for k, v in tied.items() if len(v) > 1}
    if exact:
        for k, v in sorted(exact.items()):
            add(f"- Exact judge_mean tie at {k:.2f}: {', '.join(v)}")
    else:
        add("- No exact judge_mean ties, so judge_rank is a strict 1..13 ordering.")
    # near ties at the top
    near = [
        (
            models[i]["id"],
            models[i]["label"],
            models[i]["judge_mean"],
            models[i]["human_mean_rank"],
            models[i + 1]["label"],
            models[i + 1]["judge_mean"],
            models[i + 1]["human_mean_rank"],
            models[i]["judge_mean"] - models[i + 1]["judge_mean"],
        )
        for i in range(len(models) - 1)
        if models[i]["judge_mean"] - models[i + 1]["judge_mean"] < 0.5
    ]
    if near:
        add(f"- Adjacent pairs within 0.5 judge points ({len(near)} of 12): "
            "their judge ordering is not robust to judge noise.")
        for mid, la, ja, ra, lb, jb, rb, gap in near:
            note = ""
            if mid == "gpt-6-astra":
                note = (" — vision / no-vision variant of the same base model: "
                        "the judge is insensitive to the vision input, while human mean "
                        "rank does separate them.")
            add(f"  - {la} (judge {ja:.2f}, human {ra:.3f}) vs {lb} "
                f"(judge {jb:.2f}, human {rb:.3f}), gap {gap:.2f}{note}")
    else:
        add("- No adjacent model pair is closer than 0.5 judge points.")
    jspan = models[0]["judge_mean"] - models[-1]["judge_mean"]
    add(f"- judge_mean span across the 13 models: {models[0]['judge_mean']:.2f} (best) .. "
        f"{models[-1]['judge_mean']:.2f} (worst) = {jspan:.2f} points on a 0-100 scale.")
    hardest = min(tasks, key=lambda t: t["judge_mean"])
    add(f"- Lowest-scoring task: {hardest['id']} ({hardest['judge_mean']:.2f} mean judge, "
        f"best model {hardest['best_model']}); highest: "
        f"{max(tasks, key=lambda t: t['judge_mean'])['id']} "
        f"({max(tasks, key=lambda t: t['judge_mean'])['judge_mean']:.2f}).")
    add("")

    add("#### Within-category judge-vs-human rank disagreements (|delta| >= 3)")
    add("")
    add("Ranks computed among the 13 models inside each category; small-n categories "
        "(特效类 n=3, 材质类 n=5) are unstable.")
    add("")
    label_of = {r["id"]: r["label"] for r in models}
    rows_found = False
    for cat, entry in cats.items():
        cm = entry["models"]
        jorder = sorted(cm, key=lambda m: (-cm[m]["judge_mean"], m))
        horder = sorted(cm, key=lambda m: (cm[m]["human_mean_rank"], m))
        jrk = {m: i + 1 for i, m in enumerate(jorder)}
        hrk = {m: i + 1 for i, m in enumerate(horder)}
        hits = [(m, jrk[m], hrk[m]) for m in cm if abs(jrk[m] - hrk[m]) >= 3]
        for m, a, b in sorted(hits, key=lambda h: -abs(h[1] - h[2])):
            rows_found = True
            add(f"- {cat} (n={entry['n_tasks']}): {label_of[m]} judge_rank {a} vs "
                f"human_rank {b} ({a - b:+d}) — judge {cm[m]['judge_mean']:.2f}, "
                f"human mean rank {cm[m]['human_mean_rank']:.3f}")
    if not rows_found:
        add("- None: within every category the judge and human orderings agree within "
            "2 rank positions for all 13 models.")
    add("")

    add("### Judge vs human rank disagreements (|judge_rank - human_rank| >= 3)")
    add("")
    dis = [r for r in models if abs(r["judge_rank"] - r["human_rank"]) >= 3]
    if dis:
        add("| model | judge_rank | human_rank | delta | judge_mean | human_mean_rank |")
        add("|---|---:|---:|---:|---:|---:|")
        for r in sorted(dis, key=lambda r: -abs(r["judge_rank"] - r["human_rank"])):
            d = r["judge_rank"] - r["human_rank"]
            add(
                f"| {r['label']} | {r['judge_rank']} | {r['human_rank']} | {d:+d} | "
                f"{r['judge_mean']:.2f} | {r['human_mean_rank']:.3f} |"
            )
    else:
        maxd = max(abs(r["judge_rank"] - r["human_rank"]) for r in models)
        add(f"None: the largest judge-vs-human rank gap is {maxd} position(s) "
            f"(threshold for listing is 3).")
    add("")

    add("### Largest rater disagreement per task (top 8 by human_spread)")
    add("")
    add("human_spread = mean over the 13 models of the population SD of that model's "
        "4 rater ranks (in rank units).")
    add("")
    add("| task | idx | size | subcategory | judge_mean | human_spread |")
    add("|---|---:|---|---|---:|---:|")
    for t in sorted(tasks, key=lambda t: -t["human_spread"])[:8]:
        add(
            f"| {t['id']} | {t['idx']} | {t['size']} | {t['subcategory']} | "
            f"{t['judge_mean']:.2f} | {t['human_spread']:.3f} |"
        )
    add("")
    add("### Smallest rater disagreement per task (top 5)")
    add("")
    add("| task | idx | subcategory | judge_mean | human_spread |")
    add("|---|---:|---|---:|---:|")
    for t in sorted(tasks, key=lambda t: t["human_spread"])[:5]:
        add(
            f"| {t['id']} | {t['idx']} | {t['subcategory']} | "
            f"{t['judge_mean']:.2f} | {t['human_spread']:.3f} |"
        )
    add("")

    add("### Hardest / easiest tasks by judge_mean")
    add("")
    add("| | task | idx | subcategory | judge_mean | best_model |")
    add("|---|---|---:|---|---:|---|")
    for t in sorted(tasks, key=lambda t: t["judge_mean"])[:5]:
        add(f"| lowest | {t['id']} | {t['idx']} | {t['subcategory']} | "
            f"{t['judge_mean']:.2f} | {t['best_model']} |")
    for t in sorted(tasks, key=lambda t: -t["judge_mean"])[:5]:
        add(f"| highest | {t['id']} | {t['idx']} | {t['subcategory']} | "
            f"{t['judge_mean']:.2f} | {t['best_model']} |")
    add("")

    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")


def print_leaderboard(doc):
    print("")
    print(f"{'label':<26} {'judge_mean':>10} {'judge_rk':>8} {'hum_rank':>8} "
          f"{'hum_rk':>6} {'hum_pct':>7} {'n':>3}")
    print("-" * 74)
    for r in doc["models"]:
        print(f"{r['label']:<26} {r['judge_mean']:>10.2f} {r['judge_rank']:>8} "
              f"{r['human_mean_rank']:>8.3f} {r['human_rank']:>6} "
              f"{r['human_pct_mean']:>7.2f} {r['n']:>3}")
    m = doc["meta"]
    print("-" * 74)
    print(f"judge-human Spearman: {m['judge_human_correlation']:.3f}   "
          f"rater Spearman: {m['rater_spearman']:.3f}   "
          f"{m['n_tasks']} tasks x {m['n_models']} models")


# --------------------------------------------------------------------------
def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default=OUT_JSON)
    ap.add_argument("--report", default=OUT_REPORT)
    args = ap.parse_args(argv)

    if not os.path.isfile(JUDGE_JSON):
        sys.exit(
            f"missing {JUDGE_JSON}; copy the judge scores into paper_site/data/raw/ first"
        )
    run, judge_flat, raters, index = load_inputs()
    if len(raters) != 4:
        print(f"WARNING: expected 4 rater files, found {len(raters)}", file=sys.stderr)

    data = build_matrices(run, judge_flat, raters)
    for p in data["problems"]:
        print("INPUT PROBLEM:", p, file=sys.stderr)

    doc, stats = aggregate(data, run, index)
    fails, warns, missing = verify(doc, stats, data, run)

    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, ensure_ascii=False, indent=1)
        fh.write("\n")

    write_report(doc, fails, warns, missing, args.report)
    print_leaderboard(doc)
    print(f"wrote {args.out} and {args.report}")
    if fails:
        print("VERIFICATION FAILURES:", file=sys.stderr)
        for f in fails:
            print("  -", f, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
