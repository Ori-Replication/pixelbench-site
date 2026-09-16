# PixelBench — academic showcase page

A self-contained static page that presents the project: the abstract, an interactive
case study of one drawing session (code line by line, layer by layer, with the two
`flatten` merges), the overall leaderboard, and the full 75 tasks × 13 models matrix
of all 975 generated artworks with their LLM-judge scores.

```
paper_site/
  index.html              the page (single file, no framework, no build step)
  assets/style.css         styles
  assets/app.js            case-study player + results tables + gallery
  data/scores.json         <- tools/aggregate_scores.py (source of truth)
  data/scores.js           same data as a JS global (so file:// works)
  data/raw/                raw judge scores (975 cells) kept for reproducibility
  data/SCORES_REPORT.md    data report: leaderboard, categories, correlations, anomalies
  case/src/                the verbatim session sources the animation replays
  case/frames/             293 composite canvas states (PNG, 128×128)
  case/layers/<name>/      per-layer states + each layer's final image
  case/data/session.json   code lines, statements, layers, merges, frame→line map
  case/final.png|@4x.png   the finished drawing (replay output)
  img/<task>/<model>.png   the 975 generated artworks at native resolution
  tools/                   the three scripts that build and check everything
```

## Run it

No build step, no dependencies. Either open `index.html` directly (`file://` works —
the data is loaded as JS globals, not fetched), or serve the folder:

```bash
python3 -m http.server 8137 --directory paper_site
# http://127.0.0.1:8137/index.html
```

## Rebuild the data

```bash
# 1. scores: leaderboard, per-task judge/human matrices, category means, correlations
python paper_site/tools/aggregate_scores.py

# 2. case study: replay the session sources and capture the animation frames
python paper_site/tools/build_case_frames.py --target-frames 300

# 3. copy the finished drawing into the site
python - <<'EOF'
import json, shutil
from pathlib import Path
src = Path('outputs/judge_inputs/run_final_all_models_native_pad_1over16')
for t in json.load(open('paper_site/data/scores.json'))['tasks']:
    for m, rel in t['img'].items():
        d = Path('paper_site') / rel
        d.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src / t['id'] / f'{m}.native.png', d)
EOF

# 4. re-expose both JSON files to the page as JS globals
python paper_site/tools/build_site_data.py

# 5. Chinese typography: keep newline breaks inside lang-zh blocks from rendering as
#    spaces after full-width punctuation (idempotent; --check reports drift)
python paper_site/tools/tidy_zh_html.py

# 6. verify in a real browser (needs playwright + chromium)
python3 -m http.server 8137 --directory paper_site &
python paper_site/tools/check_site.py
```

## What the case study is

`case/src/01_base_layers.py` and `case/src/02_beach_details.py` are the verbatim two
REPL steps in which GPT-6 Astra drew task #45 *Summer Seaside* (128×128) with the
[astra-pixel-art](https://github.com/Ori-Replication/astra-pixel-art-skill) skill.
`build_case_frames.py` re-executes them statement by statement against the vendored
Astra engine in `pixelbench/_vendor/astra_pixelart`, records the canvas after every
batch of drawing calls, and **fails loudly unless the replayed final canvas is
byte-identical to the PNG the original session exported**. So the animation shows the
real artefact, not a re-drawing.

The script runs the session with `Session(root=case/data/_session)`, so a rebuild leaves
a scratch directory there (`case/data/_session/`, holding the re-exported PNGs and the
layered `.pixelart.json`); it is safe to delete and is not used by the page.

Each frame is tagged with the source line that produced it, which is what lets the page
highlight the executing statement, show layers appearing at the moment `new_canvas` runs,
and animate the two `flatten` merges.

Player behaviour worth knowing when editing `assets/app.js`:

- The listing auto-scrolls to the executing line, measured with `getBoundingClientRect`
  against the scroll box itself.  `offsetTop` is relative to the page, not to the
  scrolling `<ol>`, and using it pins the panel to the bottom and hides the active line.
- A bar above the listing always names the current line, its text and its target layer, so
  the correspondence survives scrolling or a wide loop header.
- Clicking any line jumps the animation to the first frame of that statement.
- Three statements (the sparkle loop, the 128-step shore sweep, the sand speckle loop)
  account for 211 of the 293 frames.  `buildDurations()` fast-forwards frames inside any
  statement longer than 12 frames to a per-statement budget (≈2.2s, floor 22ms/frame,
  first 4 frames at normal speed), which takes a full 1× run from ~38s to ~20s.  The
  `⏩ loops` toggle restores real time; ← / → still step a single frame either way.
- The stage is a `<canvas>`, not an `<img>`.  At the compressed loop pace frames are
  5–20 ms apart and at 4× they are ~5 ms apart; re-assigning `<img src>` that fast aborts
  each decode before it paints, so the picture stops updating.  All 293 frames are
  preloaded into `Image` objects at boot and blitted synchronously with `drawImage`, and
  if the requested frame is not decoded yet the previous one stays on screen.
- Playback is a `requestAnimationFrame` loop driven by elapsed time, not a per-frame
  `setTimeout` chain: the playhead advances by wall-clock time while the stage is painted
  once per animation frame, so a busy frame can never make the animation stall or drift.
  Frames crossed within one animation frame are skipped rather than all rendered.
- `window.PixelBenchPlayer` exposes
  `frameMs/totalMs/durations/state/loaded/stageSignature` for the checker, where
  `stageSignature()` hashes the pixels currently on the stage canvas.

## Numbers on the page

Everything numeric comes from `data/scores.json`, which is generated from
`outputs/bench/run_final_all_models` (975 images), the four human rating files in
`outputs/ratings/`, and the judge run stored in `data/raw/judge_all_tasks.json`.
See `data/SCORES_REPORT.md` for the underlying report and its caveats.
