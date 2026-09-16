#!/usr/bin/env python3
"""Normalise line breaks inside Chinese (`lang-zh`) blocks in index.html.

Chinese prose written across several source lines renders the newline+indent as a
visible space: "内容，\n      代码" becomes "内容， 代码".  But that space is wanted
at a CJK↔Latin boundary ("一个 0–100 的数字", "上 height/16"), so a blanket strip is
wrong too.

Rule applied per line break inside a `lang-zh` element:

    both sides CJK / full-width  ->  join with no space
    otherwise (Latin or digits)  ->  join with exactly one space

Idempotent: running it again changes nothing.  Usage:

    python paper_site/tools/tidy_zh_html.py [--check]
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

INDEX = Path(__file__).resolve().parent.parent / "index.html"

CJK = re.compile(r"[\u3000-\u303f\u3400-\u4dbf\u4e00-\u9fff\uff00-\uffef\u2018\u2019\u201c\u201d\u2014\u2026]")
TAG = re.compile(r"<[^>]+>")
ELEMENT = re.compile(
    r'(<(p|div|span|li|h3|h4|figcaption|dd|dt|td|th)\b[^>]*class="[^"]*\blang-zh\b[^"]*"[^>]*>)'
    r"(.*?)"
    r"(</\2>)",
    re.S,
)


def visible(text: str) -> str:
    return TAG.sub("", text)


def join_lines(inner: str) -> str:
    """Re-join the source lines of one element's inner HTML."""
    lines = inner.split("\n")
    if len(lines) == 1:
        return inner
    out = lines[0].rstrip()
    for raw in lines[1:]:
        nxt = raw.strip()
        prev_vis = visible(out).rstrip()
        next_vis = visible(nxt).lstrip()
        if not nxt:
            continue
        if not prev_vis or not next_vis:
            out += nxt
            continue
        a, b = prev_vis[-1], next_vis[0]
        sep = "" if (CJK.match(a) and CJK.match(b)) else " "
        out += sep + nxt
    return out


def tidy(html: str) -> tuple[str, int]:
    n = 0

    def repl(m: re.Match) -> str:
        nonlocal n
        inner = join_lines(m.group(3))
        if inner != m.group(3):
            n += 1
        return m.group(1) + inner + m.group(4)

    return ELEMENT.sub(repl, html), n


def problems(html: str) -> list[str]:
    """Spaces that are typographic errors in Chinese prose.

    A space right after, or right before, a full-width punctuation mark is the
    signature of a source line break that rendered as whitespace.  Spaces at a
    CJK↔Latin boundary are legitimate and deliberately not reported.
    """
    text = visible(html)
    out = []
    for pat, label in (
        (r"[\u4e00-\u9fff][，。；：、）】」！？]\s+[\u4e00-\u9fff]", "space after CJK punctuation"),
        (r"[\u4e00-\u9fff]\s+[，。；：、）】」！？]", "space before CJK punctuation"),
    ):
        out.extend(f"{label}: {m.group(0)!r}" for m in re.finditer(pat, text))
    return out


def main() -> int:
    src = INDEX.read_text(encoding="utf-8")
    fixed, n = tidy(src)
    strays = problems(fixed)
    if "--check" in sys.argv:
        print(f"{n} block(s) would change; {len(strays)} suspicious spaces")
        for s in strays[:12]:
            print("   ", s)
        return 1 if n or strays else 0
    if fixed != src:
        INDEX.write_text(fixed, encoding="utf-8")
    print(f"normalised {n} lang-zh block(s)")
    print(f"suspicious CJK spaces remaining: {len(strays)}")
    for s in strays[:12]:
        print("   ", s)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
