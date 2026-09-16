#!/usr/bin/env python3
"""Replay the case-study drawing session and export an animation-ready frame set.

The case study is the 128x128 "summer seaside" scene that GPT-6 Astra drew with
the astra-pixel-art skill: two REPL steps, six layers, two ``flatten`` merges.
This script re-executes the *verbatim* step sources

    case/src/01_base_layers.py
    case/src/02_beach_details.py

statement by statement against the vendored Astra pixel-art engine, and captures
the canvas after every batch of drawing calls.  Output (all under case/):

    frames/fNNNN.png            composite of every drawing layer so far
    layers/<layer>/fNNNN.png    a layer, written only on frames where it changes
    layers/<layer>/final.png    the layer's final content (for the merge animation)
    data/session.json           code lines, statements, layers, merges, frame->line map

Nothing about the drawing is modified: the replayed final canvas is byte-compared
against the PNG the original session exported, and the script fails loudly if
they differ.  Deterministic: no randomness anywhere in the source.

Usage:  python paper_site/tools/build_case_frames.py [--target-frames 300]
"""
from __future__ import annotations

import argparse
import ast
import contextlib
import io
import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SITE = HERE.parent
REPO = SITE.parent
CASE = SITE / "case"

sys.path.insert(0, str(REPO))

from pixelbench._vendor.astra_pixelart import png as apng  # noqa: E402
from pixelbench._vendor.astra_pixelart.canvas import Canvas, flatten  # noqa: E402
from pixelbench._vendor.astra_pixelart.session import Session  # noqa: E402

STEPS = [
    {
        "n": 1,
        "file": CASE / "src" / "01_base_layers.py",
        "label": "Step 1 — base layers",
        "note": "Sky, clouds, sea and shore, each on its own canvas, merged into one base.",
    },
    {
        "n": 2,
        "file": CASE / "src" / "02_beach_details.py",
        "label": "Step 2 — props and detail",
        "note": "After inspecting the render, the agent adds distant props and foreground objects.",
    },
]

DRAW_METHODS = [
    "set", "rect", "line", "circle", "ellipse", "poly", "path", "text",
    "fill_at", "clear", "blit", "mirror", "shift", "outline", "dither", "restore",
]

DESCRIPTIONS = {
    "sky": "sky",
    "clouds": "clouds",
    "water": "sea",
    "shore": "shore",
    "sailboat_and_gulls": "sailboat & gulls",
    "beach_objects": "umbrella, towel, sandals",
    "beach_base": "merged base",
    "summer_seaside": "final merged drawing",
}


# The session's own stdout is captured verbatim, and `print(save(...))` echoes the
# absolute path of the scratch export directory.  Anything shipped must not carry the
# author's filesystem layout, so those prefixes are stripped on the way in.
SCRATCH = [
    str(CASE / "data" / "_session") + "/",
    str(CASE / "data" / "_session"),
    str(SITE) + "/",
    str(REPO) + "/",
]


def scrub_paths(text: str) -> str:
    for prefix in SCRATCH:
        text = text.replace(prefix, "")
    return text


class Replay:
    """One instrumented execution of the two step files."""

    def __init__(self, source_lines, k_events: int, mode: str, target_frames: int):
        self.k = k_events
        self.mode = mode              # "off" | "count" | "write"
        self.write = mode == "write"
        self.target_frames = target_frames
        self.blank_size = (128, 128)
        self.files = {str(s["file"]): s["n"] for s in STEPS}
        self.lines = source_lines
        self.frames: list[dict] = []
        self.layers: list[dict] = []
        self.merges: list[dict] = []
        self.stmts: list[dict] = []
        self.art: list[Canvas] = []
        self.layer_rec: dict[str, dict] = {}
        self.constructing = False
        self.pending = 0
        self.version: dict[int, int] = {}
        self.rendered: dict[int, int] = {}
        self.events = 0
        self.ops = 0
        self.line = None
        self.step = 1
        self.layer = "—"
        self._last_events = 0
        self._forced = False

    # -- tracing -----------------------------------------------------
    def tracer(self, frame, event, arg):
        if event == "call":
            return self.tracer if frame.f_code.co_filename in self.files else None
        if event == "line":
            self.line = frame.f_lineno
            self.step = self.files[frame.f_code.co_filename]
            self.events += 1
        return self.tracer

    # -- capture -----------------------------------------------------
    def capture(self, line: int, step: int, active: str, force: bool = False):
        if self.mode == "off":
            return
        if not force and self.events - self._last_events < self.k:
            return
        self._last_events = self.events
        idx = len(self.frames)
        if self.art:
            comp = flatten(self.art)
            w, h, buf = comp.to_rgba(1)
        else:
            w = h = self.blank_size[0]
            buf = bytearray(w * h * 4)
        if self.write:
            (CASE / "frames").mkdir(parents=True, exist_ok=True)
            (CASE / "frames" / f"f{idx:04d}.png").write_bytes(apng.encode_rgba(w, h, buf))
        changed = {}
        for c in self.art:
            cid = id(c)
            if self.version.get(cid, 0) <= self.rendered.get(cid, 0):
                continue
            lw, lh, lbuf = c.to_rgba(1)
            name = f"f{idx:04d}.png"
            if self.write:
                d = CASE / "layers" / c.name
                d.mkdir(parents=True, exist_ok=True)
                (d / name).write_bytes(apng.encode_rgba(lw, lh, lbuf))
                (d / "final.png").write_bytes(apng.encode_rgba(lw, lh, lbuf))
            self.rendered[cid] = self.version[cid]
            changed[c.name] = f"case/layers/{c.name}/{name}"
        self.frames.append({
            "i": idx, "line": line, "step": step, "active": active,
            "img": f"case/frames/f{idx:04d}.png", "ops": self.ops, "layers": changed,
        })

    def on_draw(self, canvas: "Canvas"):
        cid = id(canvas)
        self.version[cid] = self.version.get(cid, 0) + 1
        self.ops += 1
        if self.constructing:
            # canvas constructor background fill: attribute it to the new layer
            self.pending += 1
            return
        rec = self.layer_rec.get(canvas.name)
        if rec is not None:
            rec["draw_calls"] += 1
        self.layer = canvas.name
        if self.line is not None:
            self.capture(self.line, self.step, canvas.name)

    # -- driver ------------------------------------------------------
    def run(self):
        sess = Session(root=CASE / "data" / "_session")
        ns = sess._fresh_namespace()

        real_new = ns["new_canvas"]
        real_flatten = ns["flatten"]

        def new_canvas_probe(width, height, background=None, name=None):
            self.pending = 0
            self.constructing = True
            try:
                c = real_new(width, height, background, name)
            finally:
                self.constructing = False
            self.art.append(c)
            self.layers.append({
                "name": c.name, "label": DESCRIPTIONS.get(c.name, c.name),
                "order": len(self.art) - 1, "step": self.step,
                "created_line": self.line, "created_frame": None,
                "width": c.w, "height": c.h, "background": background,
                "draw_calls": self.pending, "colors": 0,
            })
            self.layer_rec[c.name] = self.layers[-1]
            self.capture(self.line or 0, self.step, c.name, force=True)
            self.layers[-1]["created_frame"] = len(self.frames) - 1
            return c

        def flatten_probe(layers, name=None, background=None):
            inputs = [c.name for c in layers]
            c = real_flatten(layers, name=name, background=background)
            self.merges.append({
                "name": c.name, "label": DESCRIPTIONS.get(c.name, c.name),
                "inputs": inputs, "line": self.line, "step": self.step, "frame": None,
            })
            self.capture(self.line or 0, self.step, c.name, force=True)
            self.merges[-1]["frame"] = len(self.frames) - 1
            return c

        ns["new_canvas"] = new_canvas_probe
        ns["flatten"] = flatten_probe

        if self.mode != "off":
            # frame 0: the empty canvas the agent starts from
            self.frames.append({
                "i": 0, "line": 1, "step": 1, "active": None,
                "img": "case/frames/f0000.png", "ops": 0, "layers": {},
            })
            if self.write:
                (CASE / "frames").mkdir(parents=True, exist_ok=True)
                (CASE / "frames" / "f0000.png").write_bytes(
                    apng.encode_rgba(128, 128, bytearray(128 * 128 * 4))
                )

        originals = {m: getattr(Canvas, m) for m in DRAW_METHODS}
        for m in DRAW_METHODS:
            setattr(Canvas, m, self._wrap(originals[m]))
        try:
            for step in STEPS:
                src = step["file"].read_text(encoding="utf-8")
                tree = ast.parse(src, filename=str(step["file"]))
                for stmt in tree.body:
                    code = compile(
                        ast.Module(body=[stmt], type_ignores=[]),
                        str(step["file"]), "exec",
                    )
                    rec = {
                        "step": step["n"], "first": stmt.lineno, "last": stmt.end_lineno,
                        "kind": type(stmt).__name__,
                        "text": "\n".join(
                            self.lines[step["n"]][stmt.lineno - 1:stmt.end_lineno]
                        ),
                        "frame_start": len(self.frames) - 1, "frame_end": None,
                        "ops_start": self.ops, "layer": None, "output": "",
                    }
                    buf = io.StringIO()
                    sys.settrace(self.tracer)
                    try:
                        with contextlib.redirect_stdout(buf):
                            exec(code, ns)
                    finally:
                        sys.settrace(None)
                    self.capture(stmt.end_lineno, step["n"], self.layer, force=True)
                    rec["frame_end"] = max(len(self.frames) - 1, 0)
                    rec["ops"] = self.ops - rec["ops_start"]
                    rec["layer"] = self.layer
                    rec["output"] = scrub_paths(buf.getvalue().strip()[:4000])
                    self.stmts.append(rec)
        finally:
            for m, fn in originals.items():
                setattr(Canvas, m, fn)

        final = flatten(self.art)
        w, h, buf = final.to_rgba(1)
        final_bytes = apng.encode_rgba(w, h, buf)
        if self.write:
            (CASE / "data").mkdir(parents=True, exist_ok=True)
            (CASE / "final.png").write_bytes(final_bytes)
            w4, h4, buf4 = final.to_rgba(4)
            (CASE / "final@4x.png").write_bytes(apng.encode_rgba(w4, h4, buf4))
            for name, c in [(c.name, c) for c in self.art]:
                pass
            palette = [dict(c) for c in sess.palette.to_list()] if hasattr(sess.palette, "to_list") else []
            self.palette = palette
        self.ns = ns
        self.sess = sess
        self.final_bytes = final_bytes
        return self

    def _wrap(self, fn):
        def wrapper(canvas, *a, **k):
            r = fn(canvas, *a, **k)
            self.on_draw(canvas)
            return r
        wrapper.__name__ = getattr(fn, "__name__", "wrapped")
        return wrapper


def read_sources():
    """Return {step_n: [line, ...]} plus the flat line list for the player."""
    per_step = {}
    for s in STEPS:
        per_step[s["n"]] = s["file"].read_text(encoding="utf-8").splitlines()
    return per_step


def build_lines(per_step):
    out = []
    for s in STEPS:
        for i, text in enumerate(per_step[s["n"]], start=1):
            stripped = text.strip()
            kind = "blank" if not stripped else ("comment" if stripped.startswith("#") else "code")
            out.append({"n": len(out) + 1, "step": s["n"], "line": i, "text": text, "kind": kind})
        if s is not STEPS[-1]:
            out.append({"n": len(out) + 1, "step": s["n"], "line": None, "text": "", "kind": "sep"})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--target-frames", type=int, default=300)
    args = ap.parse_args()

    per_step = read_sources()
    flat = build_lines(per_step)
    n_stmt = sum(
        len(ast.parse((s["file"]).read_text(encoding="utf-8")).body) for s in STEPS
    )

    probe = Replay(per_step, k_events=10 ** 9, mode="off", target_frames=args.target_frames).run()
    total_events = probe.events
    target = args.target_frames
    k = max(1, total_events // max(1, target - n_stmt))
    print(f"line events={total_events} statements={n_stmt} target={target} -> start k={k}")
    for _ in range(8):
        got = len(Replay(per_step, k_events=k, mode="count",
                         target_frames=target).run().frames)
        if abs(got - target) <= max(2, target * 0.03):
            break
        k = max(1, int(round(k * got / target)))
        print(f"  k={k} -> {got} frames")
    print(f"calibrated: capture every {k} line events -> {got} frames")

    for d in (CASE / "frames", CASE / "layers"):
        if d.exists():
            shutil.rmtree(d)
    run = Replay(per_step, k_events=k, mode="write", target_frames=target).run()

    ref = CASE / "src" / "reference_export.png"
    if ref.is_file():
        got, want = run.final_bytes, ref.read_bytes()
        same = got == want
        print(f"final canvas vs original session export: {'IDENTICAL' if same else 'DIFFERENT'}"
              f" ({len(got)} vs {len(want)} bytes)")
        if not same:
            raise SystemExit("replay does not reproduce the original export; refusing to write session.json")

    layer_meta = []
    for L in run.layers:
        c = next(x for x in run.art if x.name == L["name"])
        draws = sum(1 for s in run.stmts if s["layer"] == L["name"])
        L = dict(L)
        L["statements"] = draws
        L["colors"] = len({i for i in c.px if i})
        L["final"] = f"case/layers/{L['name']}/final.png"
        L["frame_first"] = L["created_frame"]
        L["frame_last"] = max(
            (f["i"] for f in run.frames if L["name"] in f["layers"]), default=L["created_frame"]
        )
        layer_meta.append(L)

    session = {
        "meta": {
            "task_id": "summer-seaside",
            "task_idx": 45,
            "title_en": "Summer Seaside",
            "title_zh": "夏日的海边",
            "prompt_en": (
                "pixel art, 128x128 resolution, summer seaside beach scene, clear blue sky with "
                "soft white clouds, bright sun, sea layered from teal near shore to deep blue at "
                "the horizon, white foam waves rolling onto golden sand, red-and-white striped "
                "beach umbrella, striped towel and flip-flops, small white sailboat far out, two "
                "gulls flying, bright fresh summer mood, strong daylight"
            ),
            "prompt_zh": (
                "像素画, 128x128分辨率, 夏日海边场景, 晴朗蓝天, 柔软白云, 明亮太阳, 大海由近岸青绿"
                "分层到远海深蓝, 白色浪花拍打金黄沙滩, 红白条纹遮阳伞, 沙滩巾与拖鞋, 远处白色小帆船, "
                "两只海鸥, 清爽夏日氛围, 强日光"
            ),
            "width": 128,
            "height": 128,
            "skill": "astra-pixel-art",
            "skill_url": "https://github.com/Ori-Replication/astra-pixel-art-skill",
            "model": "gpt-6-astra",
            "model_label": "GPT-6 Astra",
            "total_frames": len(run.frames),
            "total_statements": len(run.stmts),
            "total_draw_calls": run.ops,
            "total_events": run.events,
            "capture_every_events": run.k,
            "layers": len(run.art),
            "merges": len(run.merges),
            "colors": len([c for c in run.palette if c.get("rgba", [0, 0, 0, 0])[3] > 0]),
            "palette": [
                {"index": c.get("index"), "hex": c.get("hex"), "name": c.get("name"),
                 "rgba": c.get("rgba")}
                for c in run.palette
            ],
        },
        "steps": [
            {"n": s["n"], "label": s["label"], "note": s["note"],
             "file": f"case/src/{s['file'].name}"}
            for s in STEPS
        ],
        "lines": flat,
        "statements": run.stmts,
        "layers": layer_meta,
        "merges": run.merges,
        "frames": run.frames,
        "final": "case/final.png",
        "final4x": "case/final@4x.png",
    }
    out = CASE / "data" / "session.json"
    out.write_text(json.dumps(session, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"frames={len(run.frames)} layers={len(run.art)} statements={len(run.stmts)} "
          f"draw_calls={run.ops} colors={session['meta']['colors']}")
    print(f"merges: " + ", ".join(f"{m['name']}<-{'+'.join(m['inputs'])}@f{m['frame']}" for m in run.merges))
    print(f"wrote {out} ({out.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
