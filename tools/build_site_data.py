#!/usr/bin/env python3
"""Expose the showcase data files to the page as plain JS globals.

The page loads ``data/scores.js`` and ``case/data/session.js`` with <script> tags
instead of fetching JSON, so ``index.html`` works both from a static server and
straight off ``file://``.

Sources of truth stay the JSON files next to them:

    data/scores.json          <- tools/aggregate_scores.py
    case/data/session.json    <- tools/build_case_frames.py

Usage:  python paper_site/tools/build_site_data.py
"""
from __future__ import annotations

import json
from pathlib import Path

SITE = Path(__file__).resolve().parent.parent

PAIRS = [
    ("data/scores.json", "data/scores.js", "PIXELBENCH_SCORES",
     "Aggregated leaderboard / per-task scores for run_final_all_models."),
    ("case/data/session.json", "case/data/session.js", "PIXELBENCH_SESSION",
     "Case-study drawing session: code lines, layers, merges, animation frames."),
]

# absolute paths that must not leak into the page
SCRUB = [
    (str(SITE / "case" / "data" / "_session"), ""),
    (str(SITE), ""),
]


def scrub(obj):
    if isinstance(obj, str):
        out = obj
        for a, b in SCRUB:
            out = out.replace(a + "/", b).replace(a, b)
        return out
    if isinstance(obj, list):
        return [scrub(x) for x in obj]
    if isinstance(obj, dict):
        return {k: scrub(v) for k, v in obj.items()}
    return obj


def main() -> None:
    for src_rel, dst_rel, name, note in PAIRS:
        src = SITE / src_rel
        data = scrub(json.loads(src.read_text(encoding="utf-8")))
        body = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
        out = SITE / dst_rel
        out.write_text(
            f"/* {note}\n   Generated from {src_rel} by tools/build_site_data.py — do not edit. */\n"
            f"window.{name} = {body};\n",
            encoding="utf-8",
        )
        print(f"{src_rel} -> {dst_rel}  ({out.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
