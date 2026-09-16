#!/usr/bin/env python3
"""Headless browser check for the PixelBench showcase page.

Loads index.html in Chromium, drives the case-study player, exercises the gallery
controls, and asserts that everything the page promises is actually on screen.
Run while a static server is serving paper_site/:

    python -m http.server 8137 --directory paper_site &
    python paper_site/tools/check_site.py --url http://127.0.0.1:8137/index.html
"""
from __future__ import annotations

import argparse
import json
import sys

from playwright.sync_api import sync_playwright

FAILS: list[str] = []
CHECKS = 0


def check(name: str, ok: bool, detail: str = "") -> None:
    global CHECKS
    CHECKS += 1
    print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"  — {detail}" if detail else ""))
    if not ok:
        FAILS.append(f"{name}: {detail}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:8137/index.html")
    ap.add_argument("--shot", default="/tmp/pixelbench_showcase.png")
    args = ap.parse_args()

    errors: list[str] = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 1000})
        page.on("console", lambda m: errors.append(f"{m.type}: {m.text}") if m.type == "error" else None)
        page.on("pageerror", lambda e: errors.append(f"pageerror: {e}"))
        page.goto(args.url, wait_until="load")
        page.wait_for_timeout(900)

        # ── structure ────────────────────────────────────────────────
        TITLE_EN = "PixelBench — Evaluating Language Models for Pixel-Art Creation"
        TITLE_ZH = "面向像素画创作的语言模型评测基准"
        check("document title", TITLE_EN in page.title(), page.title())
        check("hero subtitle matches the paper title",
              page.inner_text(".subtitle.lang-en") == TITLE_EN.replace("PixelBench — ", ""),
              page.inner_text(".subtitle.lang-en"))
        check("citation title matches", TITLE_EN.replace(" — ", ": ") in page.inner_text(".bibtex"),
              page.inner_text(".bibtex").splitlines()[1].strip())
        # exact old title strings only: the abstract legitimately talks about
        # "generation and instruction-guided editing" as the task families
        check("no stale title left anywhere",
              "for Pixel Art Generation and Editing" not in page.content()
              and "像素画生成与编辑的语言模型评测基准" not in page.content())
        page.click("#langToggle")
        page.wait_for_timeout(300)
        check("zh subtitle matches", page.inner_text(".subtitle.lang-zh") == TITLE_ZH,
              page.inner_text(".subtitle.lang-zh"))
        page.click("#langToggle")
        page.wait_for_timeout(300)
        check("hero image loaded", page.eval_on_selector(
            ".hero-art img", "i => i.complete && i.naturalWidth > 0"))

        # ── case player ──────────────────────────────────────────────
        code_lines = page.eval_on_selector_all("#codeList li:not(.sep)", "n => n.length")
        check("code lines rendered", code_lines == 137, f"{code_lines} lines")
        layer_cards = page.eval_on_selector_all("#layerStrip .lyr", "n => n.length")
        check("layer cards", layer_cards == 6, f"{layer_cards}")
        marks = page.eval_on_selector_all("#timeline .tl-mark", "n => n.length")
        check("timeline marks", marks == 8, f"{marks} (6 layers + 2 merges)")
        check("figure 2 block removed", page.eval_on_selector_all("#layerGallery, #mergeSteps", "n => n.length") == 0)
        figs = page.eval_on_selector_all(".fig-label strong .lang-en", "n => n.map(x => x.textContent)")
        check("figures renumbered without gaps",
              figs == ["Figure 1", "Table 1", "Figure 2", "Table 2", "Protocol", "Figure 3"], str(figs))
        meta_cells = page.eval_on_selector_all("#caseMeta div", "n => n.length")
        check("case meta strip", meta_cells == 6, f"{meta_cells}")
        check("prompt shown", len(page.inner_text("#casePrompt")) > 100)

        # every layer thumbnail in the strip must resolve
        page.eval_on_selector("#scrub", "el => { el.value = 292; el.dispatchEvent(new Event('input')) }")
        page.wait_for_timeout(600)
        broken = page.evaluate("""() => Array.from(document.querySelectorAll('#layerStrip img'))
            .filter(i => !i.complete || i.naturalWidth === 0).map(i => i.src)""")
        check("layer thumbnails at frame 292", not broken, f"{len(broken)} broken")
        state = page.evaluate("""() => ({
            frame: document.querySelector('#roFrame').textContent,
            line: document.querySelector('#roLine').textContent,
            ops: document.querySelector('#roOps').textContent,
            active: document.querySelectorAll('#codeList li.active').length,
            stmt: document.querySelectorAll('#codeList li.stmt').length,
            stage: document.querySelector('#stageCanvas').width + 'x' + document.querySelector('#stageCanvas').height,
            out: document.querySelector('#outBox').textContent.trim().slice(0, 40),
            pending: document.querySelectorAll('#layerStrip .lyr.pending').length,
        })""")
        check("playhead at end", state["frame"] == "292" and state["line"] == "73", json.dumps(state))
        check("final stage frame drawn", page.evaluate(
            "() => PixelBenchPlayer.loaded().drawn") == 292,
            str(page.evaluate("() => PixelBenchPlayer.loaded()")))
        check("active code line highlighted", state["active"] == 1, f"{state['active']}")
        check("statement block highlighted", state["stmt"] >= 1, f"{state['stmt']}")
        check("all layers born at end", state["pending"] == 0, f"{state['pending']} pending")
        full_out = page.inner_text("#outBox")
        check("REPL output shown", "colors=49" in full_out, full_out[:60].replace("\n", " "))
        check("draw-call counter", state["ops"] == "1269", state["ops"])

        # scrubbing back must reset layer visibility
        page.eval_on_selector("#scrub", "el => { el.value = 0; el.dispatchEvent(new Event('input')) }")
        page.wait_for_timeout(300)
        early = page.evaluate("""() => ({
            pending: document.querySelectorAll('#layerStrip .lyr.pending').length,
            count: document.querySelector('#layerCount').textContent,
            active: document.querySelector('#codeList li.active').textContent.trim(),
        })""")
        check("frame 0 hides uncreated layers", early["pending"] == 6 and early["count"] == "0", json.dumps(early))

        # playback advances the playhead (at a pace that matches the schedule)
        page.eval_on_selector("#scrub", "el => { el.value = 0; el.dispatchEvent(new Event('input')) }")
        page.wait_for_timeout(150)
        page.click("#btnPlay")
        page.wait_for_timeout(2000)
        sched = page.evaluate("""() => {
            const P = window.PixelBenchPlayer;
            let t = 0; for (let i = 1; i <= 20; i++) t += P.frameMs(i);
            return {planMs: t, frame: P.state().frame};
        }""")
        page.click("#btnPlay")
        check("playback advances", sched["frame"] >= 5, f"frame {sched['frame']} after 2s")
        # the schedule must actually be what the scheduler uses: no ReferenceError,
        # and the playhead must keep up with the planned pace
        check("playhead keeps up with the schedule",
              sched["frame"] >= max(5, int(2000 / (sched["planMs"] / 20)) - 4),
              f"frame {sched['frame']} vs plan {sched['planMs']:.0f}ms for 20 frames")

        # loop compression: long texture loops must be fast-forwarded, and the whole
        # run must fit in a sane wall-clock budget at 1x
        comp = page.evaluate("""() => {
            const P = window.PixelBenchPlayer, S = window.PIXELBENCH_SESSION;
            const longStmts = S.statements.filter(st => st.frame_end - st.frame_start >= 12);
            const fast = P.durations().filter(d => d < 100).length;
            return {total: P.totalMs() / 1000, fast, longStmts: longStmts.length,
                    loopSpanMs: (() => { let t = 0; for (let i = 19; i <= 237; i++) t += P.frameMs(i); return t / 1000; })()};
        }""")
        check("long loops are compressed", comp["longStmts"] == 3 and comp["fast"] > 100,
              f"{comp['fast']} compressed frames across {comp['longStmts']} long statements")
        check("full playback fits a sane budget", comp["total"] <= 26,
              f"{comp['total']:.1f}s total, loop segment {comp['loopSpanMs']:.1f}s")
        # the stage is a canvas: it must keep repainting at high speed.  With an
        # <img src> stage, fast playback aborted every decode and the picture froze.
        page.wait_for_timeout(200)
        for _ in range(80):
            if page.evaluate("() => { const l = PixelBenchPlayer.loaded(); return l.ready >= l.total; }"):
                break
            page.wait_for_timeout(150)
        loaded = page.evaluate("() => PixelBenchPlayer.loaded()")
        check("all frames preloaded", loaded["ready"] == loaded["total"] and loaded["total"] == 293,
              json.dumps(loaded))

        def sample_playback(speed: str, ms: int = 2500):
            page.eval_on_selector(f".chip[data-speed='{speed}']", "el => el.click()")
            page.eval_on_selector("#scrub", "el => { el.value = 0; el.dispatchEvent(new Event('input')) }")
            page.wait_for_timeout(150)
            sigs, blanks, fr = [], 0, []
            page.click("#btnPlay")
            waited = 0
            while waited < ms:
                page.wait_for_timeout(90)
                waited += 90
                r = page.evaluate("""() => {
                    const cv = document.querySelector('#stageCanvas');
                    const d = cv.getContext('2d').getImageData(0, 0, cv.width, cv.height).data;
                    let opaque = 0, h = 2166136261;
                    for (let i = 0; i < d.length; i += 4) {
                        if (d[i + 3] > 0) opaque++;
                        h ^= d[i] + d[i + 1] * 3 + d[i + 2] * 7 + d[i + 3] * 11; h = Math.imul(h, 16777619);
                    }
                    return {sig: h >>> 0, opaque, frame: PixelBenchPlayer.state().frame};
                }""")
                sigs.append(r["sig"])
                fr.append(r["frame"])
                # frames 0-1 are the empty canvas the agent starts from, so a blank
                # stage is only a bug once drawing has begun
                if r["opaque"] == 0 and r["frame"] > 2:
                    blanks += 1
            page.click("#btnPlay")
            page.wait_for_timeout(120)
            return sigs, blanks, fr

        for speed in ("4", "2", "1"):
            sigs, blanks, fr = sample_playback(speed)
            distinct = len(set(sigs))
            check(f"stage keeps repainting at {speed}x", distinct >= 8,
                  f"{distinct} distinct canvas images in {len(sigs)} samples, frame {fr[0]} -> {fr[-1]}")
            check(f"stage never blank once drawing starts ({speed}x)", blanks == 0,
                  f"{blanks} blank samples after frame 2")
            check(f"playhead moves forward at {speed}x", fr[-1] > fr[0] + 3, f"{fr[0]} -> {fr[-1]}")

        page.eval_on_selector("#scrub", "el => { el.value = 0; el.dispatchEvent(new Event('input')) }")
        page.wait_for_timeout(200)
        start_opaque = page.evaluate("""() => {
            const cv = document.querySelector('#stageCanvas');
            const d = cv.getContext('2d').getImageData(0, 0, cv.width, cv.height).data;
            let n = 0; for (let i = 3; i < d.length; i += 4) if (d[i] > 0) n++; return n;
        }""")
        page.eval_on_selector("#scrub", "el => { el.value = 3; el.dispatchEvent(new Event('input')) }")
        page.wait_for_timeout(200)
        drawn_opaque = page.evaluate("""() => {
            const cv = document.querySelector('#stageCanvas');
            const d = cv.getContext('2d').getImageData(0, 0, cv.width, cv.height).data;
            let n = 0; for (let i = 3; i < d.length; i += 4) if (d[i] > 0) n++; return n;
        }""")
        check("blank canvas at frame 0, filled after the first layer",
              start_opaque == 0 and drawn_opaque > 10000, f"{start_opaque} -> {drawn_opaque} opaque pixels")

        # toggling the fast-forward off restores real time
        page.click("#loopFast")
        page.wait_for_timeout(150)
        slow = page.evaluate("() => PixelBenchPlayer.totalMs() / 1000")
        page.click("#loopFast")
        check("loop toggle changes the schedule", slow > comp["total"] * 1.5,
              f"{slow:.1f}s with loops at real time vs {comp['total']:.1f}s compressed")

        # the code panel must keep the executing line on screen while playing
        hidden = []
        for fr in (20, 60, 120, 200, 250):
            page.eval_on_selector("#scrub", f"el => {{ el.value = {fr}; el.dispatchEvent(new Event('input')) }}")
            page.wait_for_timeout(160)
            r = page.evaluate("""() => {
                const code = document.querySelector('#codeList');
                const el = code.querySelector('li.active');
                if (!el) return {ok: false, why: 'no active line'};
                const cr = code.getBoundingClientRect(), er = el.getBoundingClientRect();
                const now = document.querySelector('#nowLine').textContent;
                const codeTxt = document.querySelector('#nowCode').textContent.trim();
                return {ok: er.top >= cr.top - 1 && er.bottom <= cr.bottom + 1,
                        echo: el.querySelector('.src').textContent.trim() === codeTxt,
                        now, line: el.querySelector('.ln').textContent};
            }""")
            if not r.get("ok") or not r.get("echo") or ('L' + r.get("line")) != r.get("now"):
                hidden.append((fr, r))
        check("executing line stays visible and echoed in the bar", not hidden, str(hidden[:2]))

        # clicking a code line jumps the animation to that statement
        page.evaluate("() => document.querySelector('#codeList').children[70].click()")
        page.wait_for_timeout(250)
        jump = page.evaluate("""() => ({frame: PixelBenchPlayer.state().frame,
            stmt: (() => { const S = window.PIXELBENCH_SESSION, f = PixelBenchPlayer.state().frame;
                           const st = S.statements.find(x => f >= x.frame_start && f <= x.frame_end);
                           return st ? st.first : null; })()})""")
        check("clicking a code line jumps to its statement", jump["frame"] > 0, str(jump))

        # the merge beat must still fire (scheduler and overlay both changed)
        page.eval_on_selector(".chip[data-speed='4']", "el => el.click()")
        page.eval_on_selector("#scrub", "el => { el.value = 235; el.dispatchEvent(new Event('input')) }")
        page.wait_for_timeout(150)
        page.click("#btnPlay")
        saw_merge = False
        for _ in range(60):
            page.wait_for_timeout(80)
            if page.evaluate("() => document.querySelector('#mergeOverlay').classList.contains('on')"):
                saw_merge = True
                break
        check("merge overlay appears during playback", saw_merge)
        page.wait_for_timeout(2600)
        after = page.evaluate("""() => ({
            hidden: !document.querySelector('#mergeOverlay').classList.contains('on'),
            frame: PixelBenchPlayer.state().frame,
            playing: PixelBenchPlayer.state().playing})""")
        check("merge overlay clears and playback carries on",
              after["hidden"] and after["frame"] > 239 and after["playing"], json.dumps(after))
        page.click("#btnPlay")
        page.eval_on_selector(".chip[data-speed='1']", "el => el.click()")

        # a merge frame past the playhead renders the overlay
        page.eval_on_selector("#scrub", "el => { el.value = 250; el.dispatchEvent(new Event('input')) }")
        page.wait_for_timeout(200)
        check("merge event recorded in data",
              page.evaluate("() => PIXELBENCH_SESSION.merges.map(m => m.frame).join(',')") == "239,289",
              page.evaluate("() => PIXELBENCH_SESSION.merges.map(m => m.name).join(',')"))

        # ── editing suite (coming soon) ──────────────────────────────
        sec = page.eval_on_selector("#editing", """e => {
            const before = e.compareDocumentPosition(document.querySelector('#results'));
            return {badge: (e.querySelector('.soon-badge .lang-en') || e.querySelector('.soon-badge')).textContent.trim(),
                    count: e.querySelector('.soon-count b').textContent.trim(),
                    cards: e.querySelectorAll('.soon-card').length,
                    beforeResults: (before & Node.DOCUMENT_POSITION_FOLLOWING) !== 0,
                    text: e.textContent};
        }""")
        check("editing section present with coming-soon badge",
              sec["badge"].lower() == "coming soon" and sec["count"] == "25", json.dumps(
                  {"badge": sec["badge"], "count": sec["count"]}))
        check("editing section has its three cards", sec["cards"] == 3, str(sec["cards"]))
        check("editing section sits above the results", sec["beforeResults"])
        check("editing section states the task count",
              "25" in sec["text"] and "editing" in sec["text"].lower())
        check("abstract suite card flags the editing suite as forthcoming",
              page.eval_on_selector_all("#abstract .tiny-badge", "n => n.length") == 1)
        page.click("#langToggle")
        page.wait_for_timeout(300)
        zh = page.eval_on_selector("#editing", "e => e.textContent")
        check("editing section translated", "即将发布" in zh and "25" in zh, zh[:60].replace("\n", " "))
        page.click("#langToggle")
        page.wait_for_timeout(300)

        # ── results ──────────────────────────────────────────────────
        lb_rows = page.eval_on_selector_all("#lbTable tbody tr", "n => n.length")
        check("leaderboard rows", lb_rows == 13, f"{lb_rows}")
        first = page.inner_text("#lbTable tbody tr:first-child")
        check("GPT-6 Astra leads", "GPT-6 Astra" in first and "83.39" in first, first.replace("\n", " | "))
        check("stat band", page.eval_on_selector_all("#statBand div", "n => n.length") == 6)
        check("scatter points", page.eval_on_selector_all("#scatter circle.pt", "n => n.length") == 13)
        check("heat table cells",
              page.eval_on_selector_all("#heatTable tbody td", "n => n.length") == 13 * 7,
              str(page.eval_on_selector_all("#heatTable tbody td", "n => n.length")))
        check("correlation shown", page.inner_text("#rhoJudge") == "0.623", page.inner_text("#rhoJudge"))
        notes = page.eval_on_selector_all("#agreementNotes li", "n => n.length")
        check("agreement notes", notes == 5, f"{notes}")
        note_txt = page.inner_text("#agreementNotes")
        check("rank-agreement claim matches data",
              "13 of 13" in note_txt and "12 of 13" not in note_txt, note_txt[:60])

        # ── gallery ──────────────────────────────────────────────────
        rows = page.eval_on_selector_all("#galBody tr", "n => n.length")
        check("gallery rows", rows == 75, f"{rows}")
        cells = page.eval_on_selector_all("#galBody td.cell", "n => n.length")
        check("gallery cells", cells == 975, f"{cells}")
        heads = page.eval_on_selector_all("#galHead th", "n => n.length")
        check("gallery header", heads == 14, f"{heads} (corner + 13 models)")
        check("legend rendered", "Judge score" in page.inner_text("#legend"))
        check("matrix section retitled",
              "Per-task qualitative results across the full task suite" in page.inner_text("#gallery h2"),
              page.inner_text("#gallery h2"))

        # lazy loading means off-screen <img> are not fetched: sample real URLs instead
        page.wait_for_timeout(400)
        imgs = page.evaluate("""async () => {
            const S = window.PIXELBENCH_SCORES, C = window.PIXELBENCH_SESSION;
            const urls = [];
            [0, 57, 74].forEach(ti => {
                const t = S.tasks[ti];
                Object.values(t.img).forEach(u => urls.push(u));
            });
            C.frames.filter((f, i) => i % 97 === 0).forEach(f => urls.push(f.img));
            C.layers.forEach(l => urls.push(l.final));
            const res = await Promise.all(urls.map(u => new Promise(r => {
                const i = new Image(); i.onload = () => r(i.naturalWidth > 0); i.onerror = () => r(false); i.src = u;
            })));
            return {total: urls.length, ok: res.filter(Boolean).length,
                    bad: urls.filter((u, k) => !res[k]).slice(0, 5)};
        }""")
        check("sampled images decode", imgs["ok"] == imgs["total"],
              f"{imgs['ok']}/{imgs['total']} " + ",".join(imgs["bad"]))

        # metric switch -> human ranks
        page.select_option("#metricSel", "human")
        page.wait_for_timeout(400)
        badge = page.inner_text("#galBody tr:nth-child(1) td.cell:nth-child(2) .score")
        check("human-rank metric renders", badge.strip() != "" and float(badge) <= 13.0, badge)

        # category filter + search
        page.select_option("#metricSel", "judge")
        page.select_option("#catSel", "场景类")
        page.wait_for_timeout(250)
        vis = page.eval_on_selector_all("#galBody tr", "rs => rs.filter(r => !r.hidden).length")
        check("category filter", vis == 16, f"{vis} scene tasks")
        page.fill("#searchBox", "cottage")
        page.wait_for_timeout(250)
        vis2 = page.eval_on_selector_all("#galBody tr", "rs => rs.filter(r => !r.hidden).length")
        check("search filter", vis2 == 1, f"{vis2} row(s) for 'cottage'")
        page.fill("#searchBox", "")
        page.select_option("#catSel", "")
        page.wait_for_timeout(250)

        # sorting actually reorders
        first_before = page.eval_on_selector("#galBody tr .rh-title", "e => e.textContent")
        page.select_option("#sortSel", "spread")
        page.wait_for_timeout(300)
        first_after = page.eval_on_selector("#galBody tr .rh-title", "e => e.textContent")
        check("sort reorders rows", first_before != first_after, f"{first_before} -> {first_after}")
        page.select_option("#sortSel", "idx")
        page.wait_for_timeout(200)

        # lightbox
        page.click("#galBody tr:nth-child(58) td.cell:nth-child(2)")
        page.wait_for_timeout(300)
        cap = page.inner_text("#lbCap")
        check("lightbox opens with caption", "Magic Forest Cottage" in cap, cap[:90])
        check("lightbox image", page.eval_on_selector("#lbImg", "i => i.complete && i.naturalWidth > 0"))
        page.keyboard.press("Escape")
        page.wait_for_timeout(200)
        check("lightbox closes", page.eval_on_selector("#lightbox", "e => e.hidden"))

        # ── language toggle ──────────────────────────────────────────
        page.click("#langToggle")
        page.wait_for_timeout(400)
        zh_title = page.eval_on_selector("#galBody tr .rh-title", "e => e.textContent")
        check("zh titles", any('\u4e00' <= c <= '\u9fff' for c in zh_title), zh_title)
        check("zh prompt", any('\u4e00' <= c <= '\u9fff' for c in page.inner_text("#casePrompt")))
        check("en blocks hidden in zh",
              page.eval_on_selector(".hero .subtitle.lang-en", "e => getComputedStyle(e).display") == "none")
        lb_zh = page.inner_text("#lbTable tbody tr:first-child")
        check("leaderboard survives lang switch", "GPT-6 Astra" in lb_zh)
        page.click("#langToggle")
        page.wait_for_timeout(300)

        # ── layout sanity ────────────────────────────────────────────
        overflow = page.evaluate("""() => {
            const de = document.documentElement;
            return {scrollW: de.scrollWidth, clientW: de.clientWidth};
        }""")
        check("no page-level horizontal overflow",
              overflow["scrollW"] <= overflow["clientW"] + 2, json.dumps(overflow))

        for width in (390, 820, 1280):
            page.set_viewport_size({"width": width, "height": 900})
            page.wait_for_timeout(250)
            o = page.evaluate("() => [document.documentElement.scrollWidth, document.documentElement.clientWidth]")
            check(f"no overflow at {width}px", o[0] <= o[1] + 2, str(o))

        page.set_viewport_size({"width": 1440, "height": 1000})
        page.wait_for_timeout(300)
        page.evaluate("() => window.scrollTo(0, 0)")
        page.wait_for_timeout(200)
        page.screenshot(path=args.shot, full_page=False)
        page.evaluate("() => document.querySelector('#results').scrollIntoView()")
        page.wait_for_timeout(300)
        page.screenshot(path=args.shot.replace('.png', '_results.png'))
        page.evaluate("() => document.querySelector('#case').scrollIntoView()")
        page.wait_for_timeout(300)
        page.screenshot(path=args.shot.replace('.png', '_case.png'))
        browser.close()

    real_errors = [e for e in errors if "favicon" not in e.lower()]
    check("no console errors", not real_errors, "; ".join(real_errors[:4]))

    print(f"\n{CHECKS - len(FAILS)}/{CHECKS} checks passed")
    if FAILS:
        print("failures:")
        for f in FAILS:
            print("  -", f)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
