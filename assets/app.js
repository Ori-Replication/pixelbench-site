/* PixelBench showcase — case-study player + results + gallery.
   Data globals: window.PIXELBENCH_SCORES, window.PIXELBENCH_SESSION (see data/*.js). */
(() => {
'use strict';

const SCORES = window.PIXELBENCH_SCORES;
const SESSION = window.PIXELBENCH_SESSION;
const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => Array.from(r.querySelectorAll(s));

let LANG = document.documentElement.dataset.lang || 'en';
const pick = (en, zh) => (LANG === 'zh' ? zh : en);
const esc = (s) => String(s ?? '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

/* ───────────────────────────── language ───────────────────────────── */
function setLang(lang) {
  LANG = lang;
  document.documentElement.dataset.lang = lang;
  document.documentElement.lang = lang === 'zh' ? 'zh-Hans' : 'en';
  $('#langToggle').textContent = lang === 'zh' ? 'EN' : '中文';
  try { localStorage.setItem('pb-lang', lang); } catch (e) { /* ignore */ }
  renderCaseStatic();
  renderCatChips();
  renderScores();
}

/* ───────────────────────── case study player ───────────────────────── */
const S = SESSION;
const frameCount = S ? S.frames.length : 0;
const layerByName = new Map((S?.layers || []).map((l) => [l.name, l]));

const player = {
  i: 0, playing: false, speed: 1, timer: null, mergeBusy: false, lastOutput: '',
  stmtKey: null, compressedFrames: 0, acc: 0, lastTs: null,
};

/* ── frame images ─────────────────────────────────────────────────
   The stage is a <canvas>, not an <img>: at the compressed loop pace frames
   are 5–20 ms apart, and re-assigning <img src> that fast aborts each decode
   before it paints, so the picture freezes.  Drawing pre-decoded images onto a
   canvas is synchronous, so the stage always shows the newest frame we set. */
const frameImg = new Map();      // frame index -> Image
let framesReady = 0;
let lastDrawn = -1;
let preloadStarted = false;

function preloadFrames() {
  if (!S || preloadStarted) return;   /* language switches re-render, not re-download */
  preloadStarted = true;
  S.frames.forEach((f) => {
    const im = new Image();
    im.decoding = 'sync';
    im.onload = () => {
      framesReady++;
      updateLoadBadge();
      if (player.i === f.i) drawStage(f.i, true);
    };
    im.onerror = () => { framesReady++; updateLoadBadge(); };
    im.src = f.img;
    frameImg.set(f.i, im);
  });
}

function updateLoadBadge() {
  const el = $('#stageLoad');
  if (!el) return;
  const n = frameImg.size;
  el.textContent = framesReady >= n ? '' : `${framesReady}/${n}`;
}

function drawStage(i, force) {
  const cv = $('#stageCanvas');
  if (!cv) return;
  const ctx = cv.getContext('2d');
  const im = frameImg.get(i);
  let src = im && im.complete && im.naturalWidth ? im : null;
  if (!src) {
    /* not decoded yet: keep the last good frame on screen instead of blanking */
    const prev = frameImg.get(lastDrawn);
    if (prev && prev.complete && prev.naturalWidth) src = prev;
  }
  if (!src) return;
  if (!force && i === lastDrawn) return;
  ctx.imageSmoothingEnabled = false;
  ctx.clearRect(0, 0, cv.width, cv.height);
  ctx.drawImage(src, 0, 0, cv.width, cv.height);
  lastDrawn = i;
}

/* per-layer frame lists: [{frame, img}] in order */
const layerFrames = new Map();
if (S) {
  for (const l of S.layers) layerFrames.set(l.name, []);
  for (const f of S.frames) {
    for (const [name, img] of Object.entries(f.layers || {})) {
      if (!layerFrames.has(name)) layerFrames.set(name, []);
      layerFrames.get(name).push({ frame: f.i, img });
    }
  }
}
function layerAt(name, frame) {
  const list = layerFrames.get(name) || [];
  let cur = null;
  for (const e of list) { if (e.frame <= frame) cur = e.img; else break; }
  return cur;
}

/* flat-code index helpers */
const lineIndex = new Map();     // "step:line" -> index in code list
const stmtRanges = [];           // {first,last,frame_start,frame_end,step,layer,output,text}
function buildStmtRanges() {
  if (!S) return;
  stmtRanges.length = 0;
  S.statements.forEach((st, k) => {
    stmtRanges.push({ ...st, key: k });
  });
}
function stmtForFrame(i) {
  let best = null;
  for (const st of stmtRanges) {
    if (i >= st.frame_start && i <= st.frame_end) best = st;
    if (st.frame_start > i) break;
  }
  return best || stmtRanges[stmtRanges.length - 1] || null;
}

function renderCaseStatic() {
  if (!S) return;
  const m = S.meta;
  /* meta strip */
  const meta = $('#caseMeta');
  const rows = [
    [pick('Task', '题目'), `#${m.task_idx}`, pick(m.title_en, m.title_zh)],
    [pick('Model', '模型'), m.model_label, pick('agentic REPL', 'Agent REPL')],
    [pick('Canvas', '画布'), `${m.width}×${m.height}`, `${m.colors} ${pick('colors', '种颜色')}`],
    [pick('Layers', '图层'), String(m.layers), `${m.merges} ${pick('merges', '次合并')}`],
    [pick('Code lines', '代码行'), String(m.total_statements), pick('statements', '个语句')],
    [pick('Draw calls', '绘图调用'), String(m.total_draw_calls), `${m.total_frames} ${pick('frames', '帧')}`],
  ];
  meta.innerHTML = rows.map(([dt, dd, sub]) =>
    `<div><dt>${esc(dt)}</dt><dd>${esc(dd)} <small>${esc(sub)}</small></dd></div>`).join('');
  $('#casePrompt').textContent = pick(m.prompt_en, m.prompt_zh);
  const nCode = S.lines.filter((l) => l.kind !== 'sep').length;
  ['#fig1Lines', '#fig1LinesZh'].forEach((sel) => { const e = $(sel); if (e) e.textContent = String(nCode); });
  ['#fig1Frames', '#fig1FramesZh'].forEach((sel) => { const e = $(sel); if (e) e.textContent = String(m.total_frames); });

  /* code listing */
  const code = $('#codeList');
  code.innerHTML = '';
  lineIndex.clear();
  S.lines.forEach((ln, k) => {
    if (ln.kind === 'sep') {
      const li = document.createElement('li');
      li.className = 'sep';
      code.appendChild(li);
      return;
    }
    const li = document.createElement('li');
    li.className = 'k-' + ln.kind;
    li.dataset.step = ln.step;
    li.dataset.line = ln.line;
    li.innerHTML = `<span class="ln">${ln.line}</span><span class="src">${esc(ln.text)}</span>`;
    code.appendChild(li);
    lineIndex.set(`${ln.step}:${ln.line}`, k);
  });

  /* timeline marks */
  const tl = $('#timeline');
  $$('.tl-mark', tl).forEach((n) => n.remove());
  const track = $('.tl-track', tl);
  if (!$('.tl-fill', tl)) {
    const fill = document.createElement('div');
    fill.className = 'tl-fill';
    tl.insertBefore(fill, track.nextSibling);
  }
  const total = Math.max(1, frameCount - 1);
  const marks = [];
  S.layers.forEach((l) => marks.push({ f: l.created_frame, label: `${pick('new layer', '新建图层')} · ${l.name}`, merge: false }));
  S.merges.forEach((mg) => marks.push({ f: mg.frame, label: `${pick('flatten', '合并')} → ${mg.name}`, merge: true }));
  marks.forEach((mk) => {
    if (mk.f == null) return;
    const d = document.createElement('div');
    d.className = 'tl-mark' + (mk.merge ? ' merge' : '');
    d.style.left = (mk.f / total * 100) + '%';
    d.innerHTML = `<span>${esc(mk.label)}</span>`;
    d.addEventListener('click', () => setFrame(mk.f, true));
    tl.appendChild(d);
  });

  /* layer strip */
  const strip = $('#layerStrip');
  strip.innerHTML = '';
  S.layers.forEach((l) => {
    const d = document.createElement('div');
    d.className = 'lyr pending';
    d.dataset.layer = l.name;
    d.innerHTML = `
      <div class="lyr-thumb"><span class="ph">—</span></div>
      <div class="lyr-name" title="${esc(l.name)}">${esc(l.name)}</div>
      <div class="lyr-stat"><span class="lyr-calls">0</span> calls · <span class="lyr-colors">0</span>c</div>
      <span class="lyr-badge" hidden>${esc(pick('merged', '已合并'))}</span>`;
    d.addEventListener('click', () => l.created_frame != null && setFrame(l.created_frame, true));
    strip.appendChild(d);
  });
  $('#layerCount').textContent = '0';


  preloadFrames();
  buildStmtRanges();
  const compressed = buildDurations();
  player.compressedFrames = compressed;
  $('#scrub').max = String(Math.max(0, frameCount - 1));
  $('#roTotal').textContent = String(frameCount);
  setFrame(Math.min(player.i, frameCount - 1), false);
}

/* ── frame rendering ── */
function setFrame(i, userAction) {
  if (!S) return;
  player.i = Math.max(0, Math.min(frameCount - 1, i));
  const f = S.frames[player.i];

  drawStage(player.i);
  $('#roFrame').textContent = String(player.i);
  $('#roLine').textContent = String(f.line ?? '—');
  $('#roOps').textContent = String(f.ops);
  $('#scrub').value = String(player.i);
  $('.tl-fill').style.width = (frameCount > 1 ? player.i / (frameCount - 1) * 100 : 0) + '%';

  const st = stmtForFrame(player.i);
  const stChanged = player.stmtKey !== (st ? `${st.step}:${st.first}` : null);
  player.stmtKey = st ? `${st.step}:${st.first}` : null;
  const stepLabel = (S.steps.find((s) => s.n === f.step) || {}).label || `Step ${f.step}`;
  $('#codeStepLabel').textContent = LANG === 'zh'
    ? stepLabel.replace(/^Step (\d) — (.*)$/, '第 $1 步 · $2') : stepLabel;
  $('#stageLayerLabel').textContent = f.active ? pick('drawing to ', '正在绘制：') + f.active : pick('idle', '空闲');

  /* code highlight */
  const code = $('#codeList');
  $$('.active, .stmt', code).forEach((n) => n.classList.remove('active', 'stmt'));
  if (st) {
    for (let line = st.first; line <= st.last; line++) {
      const k = lineIndex.get(`${st.step}:${line}`);
      if (k == null) continue;
      const li = code.children[k];
      if (!li) continue;
      li.classList.add('stmt');
      if (line === f.line) li.classList.add('active');
    }
  }
  const curKey = lineIndex.get(`${f.step}:${f.line}`);
  if (curKey != null && code.children[curKey]) code.children[curKey].classList.add('active');

  /* the bar above the listing always names the line being executed, even when the
     listing itself is scrolled or the line is a wide loop header */
  const curLine = (S.lines.filter((l) => l.step === f.step && l.line === f.line)[0] || {}).text
    || (st ? st.text.split('\n')[0] : '—');
  $('#nowLine').textContent = 'L' + (f.line ?? '—');
  $('#nowCode').textContent = curLine.trim();
  $('#nowCode').title = curLine;
  const layerName = f.active || (st && st.layer) || '';
  $('#nowLayer').textContent = layerName && layerName !== '—' ? '→ ' + layerName : '';

  scrollCodeIntoView(stChanged);

  /* layer strip */
  let created = 0;
  const mergedNames = new Set();
  S.merges.forEach((mg) => { if (mg.frame != null && player.i >= mg.frame) mg.inputs.forEach((n) => mergedNames.add(n)); });
  S.layers.forEach((l) => {
    const el = $(`.lyr[data-layer="${CSS.escape(l.name)}"]`, $('#layerStrip'));
    if (!el) return;
    const born = l.created_frame != null && player.i >= l.created_frame;
    if (born) created++;
    el.classList.toggle('pending', !born);
    el.classList.toggle('active', born && f.active === l.name);
    el.classList.toggle('merged', born && mergedNames.has(l.name));
    $('.lyr-badge', el).hidden = !(born && mergedNames.has(l.name));
    if (born) {
      const src = layerAt(l.name, player.i);
      const box = $('.lyr-thumb', el);
      if (src && box.dataset.src !== src) {
        box.dataset.src = src;
        box.innerHTML = `<img src="${src}" alt="${esc(l.name)}" loading="lazy">`;
      }
      /* approximate live progress: scale total calls by how far this layer's own
         frames have progressed */
      const list = layerFrames.get(l.name) || [];
      const done = list.filter((e) => e.frame <= player.i).length;
      const frac = list.length ? done / list.length : 0;
      $('.lyr-calls', el).textContent = String(Math.round(l.draw_calls * frac));
      $('.lyr-colors', el).textContent = String(Math.max(0, Math.round(l.colors * frac)));
    } else {
      $('.lyr-calls', el).textContent = '0';
      $('.lyr-colors', el).textContent = '0';
    }
  });
  $('#layerCount').textContent = String(created);

  /* REPL output (latest non-empty output at or before the playhead) */
  let out = null;
  for (const s2 of stmtRanges) {
    if (s2.frame_start <= player.i && s2.output) out = s2;
    if (s2.frame_start > player.i) break;
  }
  if (out && player.lastOutput !== out.output) {
    player.lastOutput = out.output;
    const box = $('#outBox');
    box.innerHTML = `<span class="out-tag">step ${out.step} · line ${out.first}  ▸ </span>` + esc(out.output);
  } else if (!out && player.i < (stmtRanges[0]?.frame_start ?? 0)) {
    $('#outBox').innerHTML = '<span class="out-idle">—</span>';
  }
}

function scrollCodeIntoView(force) {
  const code = $('#codeList');
  const el = $('.active', code);
  if (!el) return;
  /* offsets measured against the scroll box itself: offsetTop would be relative to
     the page, which pinned the panel to the bottom and hid the active line. */
  const cr = code.getBoundingClientRect();
  const er = el.getBoundingClientRect();
  const relTop = er.top - cr.top;
  const pad = 56;
  if (relTop < pad || relTop + er.height > code.clientHeight - pad) {
    code.scrollTop += relTop - Math.round(code.clientHeight * 0.42);
  }
  /* long lines scroll horizontally; keep the start of the statement in view */
  if (force && code.scrollLeft !== 0) code.scrollLeft = 0;
}

/* ── merge animation beat ── */
function playMerge(mg, done) {
  const ov = $('#mergeOverlay');
  const inner = $('.mo-inner', ov);
  const ins = mg.inputs.filter((n) => layerByName.has(n));
  inner.innerHTML = ins.map((n, k) => {
    const angle = (k / ins.length) * Math.PI * 2 - Math.PI / 2;
    const tx = Math.round(Math.cos(angle) * 96), ty = Math.round(Math.sin(angle) * 74);
    return `<img src="${layerByName.get(n).final}" alt="${esc(n)}"
      style="--tx:${tx}px;--ty:${ty}px;transform:translate(${tx}px, ${ty}px)">`;
  }).join('');
  $('#moCode').textContent = `flatten([${mg.inputs.join(', ')}])`;
  ov.classList.remove('collapse');
  ov.classList.add('on');
  requestAnimationFrame(() => {
    requestAnimationFrame(() => {
      $$('.mo-inner img', ov).forEach((img) => { img.style.transform = 'translate(0,0)'; });
      setTimeout(() => {
        ov.classList.add('collapse');
        setTimeout(() => { ov.classList.remove('on', 'collapse'); done && done(); }, 620);
      }, 620);
    });
  });
}

/* ── playback timing ──────────────────────────────────────────────
   Three statements — the sparkle loop, the 128-step shore sweep and the sand
   speckle loop — account for 211 of the 293 frames, so a uniform delay spends
   most of the animation watching texture being dotted in.  Frames inside a long
   statement are therefore played on a compressed schedule: the first few stay
   readable, then the rest fast-forward until that statement's budget is used up.
   Scrub granularity and ← / → stepping stay one frame at a time either way. */
const BASE_MS = 130;
const LOOP_MIN_FRAMES = 12;    // a statement shorter than this plays at BASE_MS
const LOOP_BUDGET_MS = 2200;   // wall-clock budget for one long statement
const LOOP_FLOOR_MS = 22;      // never faster than this per frame
const LOOP_RAMP = 4;           // frames at BASE_MS before the fast-forward starts
let durations = [];
let fastLoops = true;

function buildDurations() {
  durations = new Array(frameCount).fill(BASE_MS);
  let compressed = 0;
  stmtRanges.forEach((st) => {
    const n = st.frame_end - st.frame_start;
    if (n < LOOP_MIN_FRAMES) return;
    const d = Math.max(LOOP_FLOOR_MS, Math.round(LOOP_BUDGET_MS / n));
    for (let i = st.frame_start + 1; i <= st.frame_end; i++) {
      durations[i] = (i - st.frame_start <= LOOP_RAMP) ? BASE_MS : d;
      compressed++;
    }
  });
  /* let a new layer card and a merge register before the playhead moves on */
  S.layers.forEach((l) => {
    if (l.created_frame != null) durations[l.created_frame] = Math.max(durations[l.created_frame], 300);
  });
  S.merges.forEach((mg) => {
    if (mg.frame != null) durations[mg.frame] = Math.max(durations[mg.frame], 220);
  });
  return compressed;
}

function frameMs(i) { return fastLoops ? (durations[i] ?? BASE_MS) : BASE_MS; }

function totalMs() {
  let t = 0;
  for (let i = 1; i < frameCount; i++) t += frameMs(i);
  return t;
}

/* Playback is driven by elapsed wall-clock time inside requestAnimationFrame, and
   the stage is painted once per animation frame.  A frame-by-frame setTimeout chain
   falls behind as soon as rendering costs more than the frame interval (which is
   exactly what the compressed loop pace does), and on top of that it renders every
   intermediate step; advancing the playhead by time and drawing only the resulting
   frame keeps the motion continuous at any speed. */
function playLoop(ts) {
  if (!player.playing) return;
  if (player.lastTs == null) player.lastTs = ts;
  /* a background tab or a long task must not fast-forward the whole animation */
  const dt = Math.min(Math.max(0, ts - player.lastTs), 250);
  player.lastTs = ts;
  player.acc += dt * player.speed;

  let target = player.i;
  let guard = 0;
  while (target < frameCount - 1 && player.acc >= frameMs(target + 1) && guard++ < 4000) {
    player.acc -= frameMs(target + 1);
    target++;
    const mg = S.merges.find((x) => x.frame === target);
    if (mg) {
      /* merges are set pieces: stop on them, animate, then carry on */
      setFrame(target, false);
      player.acc = 0;
      player.mergeBusy = true;
      playMerge(mg, () => {
        player.mergeBusy = false;
        if (player.playing) { player.lastTs = null; player.timer = requestAnimationFrame(playLoop); }
      });
      return;
    }
  }
  if (target !== player.i) setFrame(target, false);
  if (target >= frameCount - 1) { pause(); return; }
  player.timer = requestAnimationFrame(playLoop);
}

function play() {
  if (player.i >= frameCount - 1) setFrame(0, true);
  player.playing = true;
  player.acc = 0;
  player.lastTs = null;
  $('#playGlyph').textContent = '❚❚';
  $('#playLabel').textContent = pick('Pause', '暂停');
  $('#playLabelZh').textContent = '暂停';
  player.timer = requestAnimationFrame(playLoop);
}
function pause() {
  player.playing = false;
  if (player.timer != null) cancelAnimationFrame(player.timer);
  player.timer = null;
  $('#playGlyph').textContent = '▶';
  $('#playLabel').textContent = pick('Play', '播放');
  $('#playLabelZh').textContent = '播放';
}

function initPlayer() {
  if (!S) return;
  $('#btnPlay').addEventListener('click', () => (player.playing ? pause() : play()));
  $('#btnRestart').addEventListener('click', () => {
    pause();
    const mg = $('#mergeOverlay'); mg.classList.remove('on', 'collapse');
    setFrame(0, true);
  });
  $$('.chip[data-speed]').forEach((c) => c.addEventListener('click', () => {
    $$('.chip[data-speed]').forEach((x) => x.classList.remove('is-on'));
    c.classList.add('is-on');
    player.speed = Number(c.dataset.speed);
  }));
  const loopBtn = $('#loopFast');
  loopBtn.addEventListener('click', () => {
    fastLoops = !fastLoops;
    loopBtn.classList.toggle('is-on', fastLoops);
  });
  /* clicking a line jumps to the first frame of the statement it belongs to */
  $('#codeList').addEventListener('click', (e) => {
    const li = e.target.closest('li');
    if (!li || li.classList.contains('sep')) return;
    const step = Number(li.dataset.step), line = Number(li.dataset.line);
    const st = stmtRanges.find((x) => x.step === step && line >= x.first && line <= x.last);
    if (!st) return;
    pause();
    $('#mergeOverlay').classList.remove('on', 'collapse');
    setFrame(st.frame_start, true);
  });
  $('#scrub').addEventListener('input', (e) => {
    pause();
    $('#mergeOverlay').classList.remove('on', 'collapse');
    setFrame(Number(e.target.value), true);
  });
  document.addEventListener('keydown', (e) => {
    if (e.target.matches('input, select, textarea')) return;
    if (e.key === 'ArrowRight') { pause(); setFrame(player.i + 1, true); }
    if (e.key === 'ArrowLeft') { pause(); setFrame(player.i - 1, true); }
    if (e.key === ' ') { e.preventDefault(); player.playing ? pause() : play(); }
  });
}

/* ───────────────────────────── results ───────────────────────────── */
const SHORT = {
  'gpt-6-astra': 'Astra', 'gpt-6-astra-novision': 'Astra-nv', 'gpt-5.6-sol': 'Sol',
  'gemini-3.8-flash': 'Gem-3.8', 'qwen3.8-max': 'Qwen3.8', 'claude-opus-5': 'Opus-5',
  'kimi-k3': 'Kimi-K3', 'glm-5.3-flash': 'GLM-5.3', 'deepseek-v4-flash': 'DS-V4-F',
  'deepseek-v4-pro': 'DS-V4-P', 'gemini-3.1-pro-preview': 'Gem-3.1', 'kimi-k2.7-code': 'K2.7',
  'qwen3.5-397b-a17b': 'Qwen3.5',
};
const CAT_EN = {
  '物品类': 'Items', '人物类': 'Characters', '场景类': 'Scenes', '生物类': 'Creatures',
  '材质类': 'Materials', '特效类': 'Effects', 'UI类': 'UI',
};
const catLabel = (c) => (LANG === 'zh' ? c : (CAT_EN[c] || c));
const ord = (n) => (n === 1 ? 'st' : n === 2 ? 'nd' : n === 3 ? 'rd' : 'th');

/* rank models inside one category; ties keep the object order, so it is deterministic */
function catRankMap(d, key, higherIsBetter) {
  const order = Object.keys(d).sort((a, b) =>
    (higherIsBetter ? d[b][key] - d[a][key] : d[a][key] - d[b][key]));
  const out = {};
  order.forEach((id, k) => { out[id] = k + 1; });
  return out;
}

/* the sharpest judge-vs-human rank divergence inside a category, or null */
function worstDivergence(cat) {
  const c = SCORES.categories[cat];
  if (!c) return null;
  const d = c.models;
  const jr = catRankMap(d, 'judge_mean', true);
  const hr = catRankMap(d, 'human_mean_rank', false);
  let best = null;
  Object.keys(d).forEach((id) => {
    const delta = jr[id] - hr[id];
    if (!best || delta < best.delta) best = { id, delta, judge: jr[id], human: hr[id] };
  });
  return best;
}

/* the largest disagreement between the judge and human orderings, in rank positions */
function maxRankGap() {
  return MODELS.reduce((acc, m) => {
    const gap = Math.abs(m.judge_rank - m.human_rank);
    return gap > acc.gap ? { gap, label: m.label } : acc;
  }, { gap: 0, label: '' });
}

/* how many adjacent pairs in the overall ranking are within `eps` judge points */
function closePairs(eps) {
  let n = 0;
  for (let k = 0; k < MODELS.length - 1; k++) {
    if (MODELS[k].judge_mean - MODELS[k + 1].judge_mean < eps) n++;
  }
  return n;
}
const MET = new Map(SCORES ? SCORES.models.map((m) => [m.id, m]) : []);
const TASKS = SCORES ? SCORES.tasks : [];
const MODELS = SCORES ? SCORES.models : [];

function metricColor(t) { /* t: 0 bad .. 1 good */
  const c = Math.max(0, Math.min(1, t));
  const hue = 6 + 146 * c;
  return `hsl(${hue.toFixed(0)}, 58%, ${Math.round(36 + 6 * c)}%)`;
}
function judgeColor(v, lo, hi) { return metricColor((v - lo) / (hi - lo)); }
function rankColor(r) { return metricColor((13.5 - r) / 12.5); }

function renderScores() {
  if (!SCORES) return;
  const meta = SCORES.meta;
  const best = MODELS[0];

  /* stat band */
  $('#statBand').innerHTML = [
    [pick('Tasks', '题目'), meta.n_tasks, pick('7 categories, 16×16–256×256', '7 个类别，16×16–256×256')],
    [pick('Models', '模型'), meta.n_models, pick('general-purpose LLMs', '通用语言模型')],
    [pick('Artworks', '作品'), meta.n_judge_cells, pick('every image judged', '每张图均被打分')],
    [pick('Human raters', '人类评审'), meta.n_raters, pick('full ranking per task', '每题完整排序')],
    [pick('Top judge mean', '最高 Judge 均分'), best.judge_mean.toFixed(1), best.label],
    [pick('Judge ↔ human τ-b', 'Judge ↔ 人类 τ-b'), meta.task_mean_tau_b.toFixed(3), pick('mean over tasks, Kendall tau-b', '逐题 Kendall tau-b 的平均')],
  ].map(([dt, dd, sub]) => `<div><dt>${esc(dt)}</dt><dd>${esc(dd)} <small>${esc(sub)}</small></dd></div>`).join('');

  /* leaderboard */
  const jLo = Math.min(...MODELS.map((m) => m.judge_mean));
  const jHi = Math.max(...MODELS.map((m) => m.judge_mean));
  const hWorst = Math.max(...MODELS.map((m) => m.human_mean_rank));
  $('#lbTable tbody').innerHTML = MODELS.map((m, k) => `
    <tr class="${k === 0 ? 'top' : ''}">
      <td class="num">${k + 1}</td>
      <td class="model-name">${esc(m.label)}<br><code style="font-size:.68rem">${esc(m.id)}</code></td>
      <td class="num judge"><div class="metric">
        <div class="bar"><i style="width:${((m.judge_mean - jLo) / (jHi - jLo) * 100).toFixed(1)}%"></i></div>
        <b>${m.judge_mean.toFixed(2)}</b></div></td>
      <td class="num human"><div class="metric bar-left">
        <b>${m.human_mean_rank.toFixed(2)}</b>
        <div class="bar"><i style="width:${(m.human_mean_rank / hWorst * 100).toFixed(1)}%;
          background:${metricColor((13.5 - m.human_mean_rank) / 12.5)}"></i></div></div></td>
      <td class="num">${m.n}</td>
    </tr>`).join('');

  /* agreement notes */
  const catWorst = Object.entries(SCORES.categories).sort((a, b) => a[1].n_tasks - b[1].n_tasks);
  /* the sharpest judge-vs-human rank divergence among the two smallest categories,
     derived from the data so the sentence cannot drift away from the tables */
  const div = catWorst.slice(0, 2).map(([c]) => {
    const w = worstDivergence(c);
    if (!w) return null;
    return { cat: c, n: SCORES.categories[c].n_tasks, label: (MET.get(w.id) || {}).label || w.id,
             judge: w.judge, human: w.human, delta: w.judge - w.human };
  }).filter(Boolean).sort((a, b) => a.delta - b.delta)[0] || null;
  const topGap = MODELS[0].judge_mean - MODELS[1].judge_mean;
  const gap = maxRankGap();
  const ci = meta.task_mean_tau_b_ci95;
  const notes = LANG === 'zh' ? [
    `主指标为<strong>逐题 Kendall τ-b 的平均值 ${meta.task_mean_tau_b.toFixed(4)}</strong>（95% 区间 [${ci[0].toFixed(3)}, ${ci[1].toFixed(3)}]），即每题先算「评审分数 vs 四人平均名次」的一致性再平均，与论文冻结的协议一致。`,
    `评审模型 <code>${meta.judge_model}</code> <strong>本身也是被评测的 13 个模型之一，并在自己的评分下排名第一</strong>。人类评审也把它排在第一，因此结论不依赖评审的自我偏好，但这仍是一条需要读者知情的限制。`,
    `把参照换成「另外三位评审的共识」后：评审 <strong>${meta.judge_loo_mean.toFixed(4)}</strong>，留出的人类评审 <strong>${meta.human_loo_mean.toFixed(4)}</strong>，人类两两 <strong>${meta.human_pairwise_mean.toFixed(4)}</strong> —— 评审落在这个区间之内，因此不宜宣称超过人类。`,
    `换用独立判分器 <code>${meta.pilot_judge_model}</code>（其自身并非榜首）得到的排序完全相同，这是对评审选择的一项稳健性检查；该 pilot 协议的合并 Spearman 为 ${meta.pilot_pooled_spearman}。`,
    `13 个模型中 ${MODELS.filter((m) => Math.abs(m.judge_rank - m.human_rank) <= 1).length} 个的评审名次与人类名次相差不超过 1 位，全表最大差距为 ${gap.gap} 位（${gap.label}）。`,
    `榜首差距 <strong>${(MODELS[0].judge_mean - MODELS[1].judge_mean).toFixed(2)}</strong> 分，相邻 ${MODELS.length - 1} 对名次中有 <strong>${closePairs(0.5)}</strong> 对差距不足 0.5 分。`,
    div ? `题目数很少的类别上两种排序分歧明显：${div.cat}（n=${div.n}）中 ${div.label} 的 Judge 名次是第 ${div.judge}，人类名次却只有第 ${div.human}。` : '',
  ].filter(Boolean) : [
    `Primary metric: <strong>mean over tasks of Kendall tau-b = ${meta.task_mean_tau_b.toFixed(4)}</strong>
     (95% CI [${ci[0].toFixed(3)}, ${ci[1].toFixed(3)}]) — each task's judge-vs-human agreement is computed
     first and then averaged, matching the frozen protocol behind these numbers.`,
    `The judge <code>${meta.judge_model}</code> is <strong>also one of the 13 evaluated models and places first
     under its own scoring</strong>. Human raters place it first as well, so the conclusion does not rest on judge
     self-preference, but readers should know about the overlap.`,
    `Against the consensus of the other three raters the judge scores <strong>${meta.judge_loo_mean.toFixed(4)}</strong>,
     a held-out rater scores <strong>${meta.human_loo_mean.toFixed(4)}</strong>, and raters agree with each other at
     <strong>${meta.human_pairwise_mean.toFixed(4)}</strong> — the judge sits inside that band, so it should not be
     claimed to beat humans.`,
    `An independent pilot judge <code>${meta.pilot_judge_model}</code>, which is not the top-ranked model, produced the
     same ordering — a robustness check on the choice of judge (pooled Spearman ${meta.pilot_pooled_spearman} for that
     protocol).`,
    `${MODELS.filter((m) => Math.abs(m.judge_rank - m.human_rank) <= 1).length} of ${MODELS.length} models land within
     one rank position between the two orderings; the largest gap in the table is ${gap.gap} places (${gap.label}).`,
    `The top of the table is separated by <strong>${(MODELS[0].judge_mean - MODELS[1].judge_mean).toFixed(2)}</strong>
     judge points, and <strong>${closePairs(0.5)} of the ${MODELS.length - 1}</strong> adjacent pairs sit within 0.5.`,
    div ? `The orderings diverge in the smallest categories: in ${catLabel(div.cat)} (n=${div.n} tasks)
     ${div.label} ranks <strong>${div.judge}${ord(div.judge)}</strong> by judge score but
     <strong>${div.human}${ord(div.human)}</strong> by human preference.` : '',
  ].filter(Boolean);
  $('#agreementNotes').innerHTML = notes.map((n) => `<li>${n}</li>`).join('');
  $('#rhoJudge').textContent = meta.task_mean_tau_b.toFixed(4);
  $('#rhoJudgeZh').textContent = meta.task_mean_tau_b.toFixed(4);

  renderScatter();
  renderHeat();
  refreshControlsLang();
  refreshGalleryLang();
}

/* re-label the already-built gallery rows when the language changes */
function refreshGalleryLang() {
  const corner = $('#galHead .corner');
  if (corner) {
    corner.innerHTML = `<span style="display:block">${pick('Task ↓ / Model →', '题目 ↓ / 模型 →')}</span>`;
  }
  TASKS.forEach((t) => {
    const tr = galState.rows.get(t.id);
    if (!tr) return;
    const h = $('.rh-title', tr);
    if (h) h.textContent = pick(t.title_en, t.title_zh);
    const b = $('.rh-best', tr);
    if (b) b.textContent = `${pick('best', '最佳')}: ${(MET.get(t.best_model) || {}).label || t.best_model}`;
    const chip = $('.rh-chip.cat', tr);
    if (chip) chip.textContent = catLabel(t.subcategory);
  });
  applyGallery();
}

/* ── scatter: judge mean vs human percentile ── */
function renderScatter() {
  const W = 420, H = 300, pad = { l: 46, r: 14, t: 14, b: 34 };
  const pts = MODELS.map((m) => ({ ...m, x: m.judge_mean, y: m.human_pct_mean * 100 }));
  const xs = pts.map((p) => p.x), ys = pts.map((p) => p.y);
  const x0 = Math.min(...xs) - 2, x1 = Math.max(...xs) + 2;
  const y0 = Math.max(0, Math.min(...ys) - 5), y1 = Math.max(...ys) + 4;
  const X = (v) => pad.l + (v - x0) / (x1 - x0) * (W - pad.l - pad.r);
  const Y = (v) => H - pad.b - (v - y0) / (y1 - y0) * (H - pad.t - pad.b);
  const ticks = (a, b, n) => Array.from({ length: n + 1 }, (_, k) => a + (b - a) * k / n);
  let svg = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="judge vs human agreement">`;
  ticks(y0, y1, 4).forEach((v) => {
    svg += `<line class="grid-line" x1="${pad.l}" y1="${Y(v).toFixed(1)}" x2="${W - pad.r}" y2="${Y(v).toFixed(1)}"/>`;
    svg += `<text class="tick-label" x="${pad.l - 7}" y="${(Y(v) + 3).toFixed(1)}" text-anchor="end">${v.toFixed(0)}</text>`;
  });
  ticks(x0, x1, 5).forEach((v) => {
    svg += `<text class="tick-label" x="${X(v).toFixed(1)}" y="${H - pad.b + 14}" text-anchor="middle">${v.toFixed(0)}</text>`;
  });
  svg += `<line class="axis" x1="${pad.l}" y1="${H - pad.b}" x2="${W - pad.r}" y2="${H - pad.b}"/>`;
  svg += `<line class="axis" x1="${pad.l}" y1="${pad.t}" x2="${pad.l}" y2="${H - pad.b}"/>`;
  svg += `<text class="axis-label" x="${(W + pad.l) / 2}" y="${H - 4}" text-anchor="middle">${pick('mean judge score', 'Judge 均分')}</text>`;
  svg += `<text class="axis-label" transform="translate(12 ${(H - pad.b + pad.t) / 2}) rotate(-90)" text-anchor="middle">${pick('human percentile', '人类百分位')}</text>`;
  pts.forEach((p) => {
    const hi = p.id === MODELS[0].id;
    svg += `<circle class="pt${hi ? ' hi' : ''}" cx="${X(p.x).toFixed(1)}" cy="${Y(p.y).toFixed(1)}" r="${hi ? 6 : 4.6}"><title>${esc(p.label)} — judge ${p.judge_mean}, human ${(p.human_pct_mean).toFixed(2)}</title></circle>`;
    svg += `<text class="pt-label" x="${(X(p.x) + 8).toFixed(1)}" y="${(Y(p.y) + 3).toFixed(1)}">${esc(SHORT[p.id] || p.id)}</text>`;
  });
  svg += '</svg>';
  $('#scatter').innerHTML = svg;
}

/* ── category heat table ── */
function renderHeat() {
  const cats = Object.keys(SCORES.categories);
  const jLo = 45, jHi = 88;
  const head = `<thead><tr><th>${pick('Model', '模型')}</th>${cats.map((c) =>
    `<th>${esc(catLabel(c))} <span style="font-weight:400">n=${SCORES.categories[c].n_tasks}</span></th>`).join('')}</tr></thead>`;
  const body = MODELS.map((m) => {
    const cells = cats.map((c) => {
      const v = SCORES.categories[c].models[m.id].judge_mean;
      const col = judgeColor(v, jLo, jHi);
      return `<td style="background:${col};color:#fff" title="${esc(m.label)} · ${esc(catLabel(c))}: ${v.toFixed(1)}">${v.toFixed(1)}</td>`;
    }).join('');
    return `<tr><th>${esc(m.label)}</th>${cells}</tr>`;
  }).join('');
  $('#heatTable').innerHTML = head + `<tbody>${body}</tbody>`;
}

/* ── the 75 × 13 gallery ── */
const galState = { metric: 'judge', cat: '', sort: 'idx', q: '', best: true, zoom: false, rows: new Map() };
let fillCatsLang = null;

function refreshControlsLang() {
  const metricSel = $('#metricSel');
  if (metricSel) {
    const keep = metricSel.value;
    metricSel.innerHTML = [
      `<option value="judge">${pick('LLM judge score (0–100)', 'LLM Judge 分数（0–100）')}</option>`,
      `<option value="human">${pick('Human mean rank (1 = best)', '人类平均名次（1 最好）')}</option>`,
      `<option value="none">${pick('no numbers', '不显示数字')}</option>`,
    ].join('');
    metricSel.value = keep;
  }
  const sortSel = $('#sortSel');
  if (sortSel) {
    const keep = sortSel.value;
    sortSel.innerHTML = [
      `<option value="idx">${pick('Task order', '题目顺序')}</option>`,
      `<option value="judgemax">${pick('Easiest (row best) first', '最简单（行内最高分）优先')}</option>`,
      `<option value="judgeasc">${pick('Hardest (row best) first', '最难（行内最高分）优先')}</option>`,
      `<option value="spread">${pick('Rater disagreement', '评审分歧最大')}</option>`,
      `<option value="size">${pick('Canvas size', '画幅大小')}</option>`,
    ].join('');
    sortSel.value = keep;
  }
  const search = $('#searchBox');
  if (search) search.placeholder = pick('magic forest cottage / 魔法 / scene', '魔法森林小屋 / cottage / 场景类');
  if (fillCatsLang) fillCatsLang();
}

function galleryMetric(task, modelId) {
  const j = SCORES.judge[modelId][task.id];
  const h = SCORES.human[modelId][task.id];
  if (galState.metric === 'judge') return { text: j == null ? '—' : j.toFixed(0), color: j == null ? '#333' : judgeColor(j, 50, 92), sort: j };
  if (galState.metric === 'human') return { text: h == null ? '—' : h.toFixed(1), color: h == null ? '#333' : rankColor(h), sort: h };
  return { text: '', color: 'transparent', sort: 0 };
}

function buildGallery() {
  const head = $('#galHead');
  head.innerHTML = `<th class="corner">
      <span class="lang-en" style="display:block">Task \u2193 / Model \u2192</span>
      <span class="lang-zh" style="display:block">题目 \u2193 / 模型 \u2192</span></th>` +
    MODELS.map((m) => `<th class="sortable" data-model="${esc(m.id)}" title="${esc(pick('sort rows by this model', '按该模型排序'))}">
        <span class="m-name">${esc(m.label)}</span>
        <span class="m-sub">J ${m.judge_mean.toFixed(1)} · H ${m.human_mean_rank.toFixed(2)}</span>
        <span class="m-sort">${pick('sort ↓', '排序 ↓')}</span>
      </th>`).join('');
  head.querySelectorAll('th.sortable').forEach((th) => th.addEventListener('click', () => {
    const id = th.dataset.model;
    galState.sort = galState.sort === 'model:' + id ? 'model-asc:' + id : 'model:' + id;
    $$('#galHead th').forEach((x) => x.classList.remove('on'));
    th.classList.add('on');
    applyGallery();
  }));

  const body = $('#galBody');
  body.innerHTML = '';
  galState.rows.clear();
  TASKS.forEach((t) => {
    const tr = document.createElement('tr');
    tr.dataset.id = t.id;
    const title = pick(t.title_en, t.title_zh);
    const head2 = document.createElement('td');
    head2.className = 'rowhead';
    head2.innerHTML = `
      <span class="rh-idx">#${t.idx}</span><span class="rh-title">${esc(title)}</span>
      <div class="rh-meta">
        <span class="rh-chip size">${esc(t.size)}</span>
        <span class="rh-chip cat">${esc(catLabel(t.subcategory))}</span>
        <span class="rh-chip">Judge ${t.judge_mean.toFixed(1)}</span>
      </div>
      <div class="rh-best">${pick('best', '最佳')}: ${esc((MET.get(t.best_model) || {}).label || t.best_model)}</div>`;
    tr.appendChild(head2);
    MODELS.forEach((m) => {
      const td = document.createElement('td');
      td.className = 'cell';
      td.dataset.task = t.id;
      td.dataset.model = m.id;
      const src = t.img[m.id];
      const mt = galleryMetric(t, m.id);
      td.innerHTML = `<div class="thumb">
          <img src="${src}" alt="${esc(title)} — ${esc(m.label)}" loading="lazy"
               onerror="this.replaceWith(Object.assign(document.createElement('span'),{className:'missing',textContent:'—'}))">
          ${mt.text ? `<span class="score" style="background:${mt.color}">${mt.text}</span>` : ''}
        </div>`;
      td.addEventListener('click', () => openLightbox(t, m));
      tr.appendChild(td);
    });
    body.appendChild(tr);
    galState.rows.set(t.id, tr);
  });
}

function applyGallery() {
  /* header metric sub-labels already carry both means; cell values need refresh */
  const q = galState.q.trim().toLowerCase();
  let visible = 0;
  TASKS.forEach((t) => {
    const tr = galState.rows.get(t.id);
    const hay = [t.id, t.title_en, t.title_zh, t.subcategory, t.prompt_en, t.prompt_zh, t.size].join(' ').toLowerCase();
    const ok = (!galState.cat || t.subcategory === galState.cat) && (!q || hay.includes(q));
    tr.hidden = !ok;
    if (!ok) return;
    visible++;
    const jMax = Math.max(...MODELS.map((m) => SCORES.judge[m.id][t.id] ?? -1));
    $$('td.cell', tr).forEach((td) => {
      const m = td.dataset.model;
      const mt = galleryMetric(t, m);
      const badge = $('.score', td);
      if (badge) {
        badge.textContent = mt.text;
        badge.style.background = mt.color;
        badge.hidden = !mt.text;
      }
      const isBest = galState.best && (SCORES.judge[m][t.id] ?? -1) === jMax;
      td.classList.toggle('best', isBest);
    });
  });

  /* ordering */
  const order = TASKS.slice();
  const rowBest = (t) => Math.max(...MODELS.map((m) => SCORES.judge[m.id][t.id] ?? -1));
  if (galState.sort === 'judgemax') order.sort((a, b) => rowBest(b) - rowBest(a));
  else if (galState.sort === 'judgeasc') order.sort((a, b) => rowBest(a) - rowBest(b));
  else if (galState.sort === 'spread') order.sort((a, b) => b.human_spread - a.human_spread);
  else if (galState.sort === 'size') {
    const wh = (t) => t.size.split('x').reduce((p, c) => p * Number(c), 1);
    order.sort((a, b) => wh(b) - wh(a) || a.idx - b.idx);
  } else if (galState.sort.startsWith('model')) {
    const id = galState.sort.split(':')[1];
    const asc = galState.sort.startsWith('model-asc');
    order.sort((a, b) => {
      const va = SCORES.judge[id][a.id] ?? -1, vb = SCORES.judge[id][b.id] ?? -1;
      return asc ? va - vb : vb - va;
    });
  } else order.sort((a, b) => a.idx - b.idx);
  const body = $('#galBody');
  order.forEach((t) => body.appendChild(galState.rows.get(t.id)));

  $('#galCount').textContent = pick(
    `${visible} of ${TASKS.length} tasks shown · ${visible * MODELS.length} images · metric: ${galState.metric}`,
    `显示 ${visible}/${TASKS.length} 道题 · ${visible * MODELS.length} 张图 · 指标：${galState.metric}`);
  renderLegend();
}

function renderLegend() {
  const swatches = [];
  if (galState.metric === 'judge') {
    [60, 70, 80, 90].forEach((v) => swatches.push(
      `<span class="sw"><i style="background:${judgeColor(v, 50, 92)}"></i>${v}</span>`));
    $('#legend').innerHTML = `<span>${pick('Judge score', 'Judge 分数')}:</span>` + swatches.join('') +
      `<span>${pick('outline = best in row', '外框 = 该行最高分')}</span>` +
      `<span>${pick('click a cell for the full-size image', '点击单元格查看原尺寸大图')}</span>`;
  } else if (galState.metric === 'human') {
    [1, 4, 7, 10, 13].forEach((v) => swatches.push(
      `<span class="sw"><i style="background:${rankColor(v)}"></i>${v}</span>`));
    $('#legend').innerHTML = `<span>${pick('Human mean rank', '人类平均名次')}:</span>` + swatches.join('') +
      `<span>${pick('1 = best, 13 = worst', '1 最好，13 最差')}</span>` +
      `<span>${pick('outline = best judge score in row', '外框 = 该行 Judge 最高分')}</span>`;
  } else {
    $('#legend').innerHTML = `<span>${pick('Click a cell for the full-size image.', '点击单元格查看原尺寸大图。')}</span>`;
  }
}

function initGallery() {
  buildGallery();
  const catSel = $('#catSel');
  const cats = Array.from(new Set(TASKS.map((t) => t.subcategory)));
  const fillCats = () => {
    const keep = catSel.value;
    catSel.innerHTML = `<option value="">${pick('All categories', '全部类别')}</option>` +
      cats.map((c) => `<option value="${esc(c)}">${esc(catLabel(c))} (${TASKS.filter((t) => t.subcategory === c).length})</option>`).join('');
    catSel.value = keep;
  };
  fillCats();
  fillCatsLang = fillCats;
  $('#metricSel').addEventListener('change', (e) => { galState.metric = e.target.value; applyGallery(); });
  catSel.addEventListener('change', (e) => { galState.cat = e.target.value; applyGallery(); });
  $('#sortSel').addEventListener('change', (e) => {
    galState.sort = e.target.value;
    $$('#galHead th').forEach((x) => x.classList.remove('on'));
    applyGallery();
  });
  $('#searchBox').addEventListener('input', (e) => { galState.q = e.target.value; applyGallery(); });
  $('#bestToggle').addEventListener('change', (e) => { galState.best = e.target.checked; applyGallery(); });
  $('#zoomToggle').addEventListener('change', (e) => {
    galState.zoom = e.target.checked;
    $('#galleryTable').classList.toggle('zoom', galState.zoom);
  });
  applyGallery();
}

/* ── lightbox ── */
function openLightbox(t, m) {
  const j = SCORES.judge[m.id][t.id], h = SCORES.human[m.id][t.id];
  const img = $('#lbImg');
  img.src = t.img[m.id];
  img.alt = `${t.title_en} — ${m.label}`;
  $('#lbCap').innerHTML = `
    <span class="lb-title">#${t.idx} ${esc(t.title_en)} · ${esc(t.title_zh)}</span>
    <span>${esc(m.label)} — ${pick('judge score', 'Judge 分数')} <strong>${j == null ? '—' : j.toFixed(1)}</strong>,
      ${pick('human mean rank', '人类平均名次')} <strong>${h == null ? '—' : h.toFixed(2)}</strong>
      (${pick('run best', '本行最佳')}: ${esc((MET.get(t.best_model) || {}).label || t.best_model)},
      ${t.judge_mean.toFixed(1)})</span>
    <span class="lb-prompt">${esc(pick(t.prompt_en, t.prompt_zh))}</span>`;
  $('#lightbox').hidden = false;
}
function initLightbox() {
  $('#lbClose').addEventListener('click', () => { $('#lightbox').hidden = true; });
  $('#lightbox').addEventListener('click', (e) => { if (e.target.id === 'lightbox') $('#lightbox').hidden = true; });
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape') $('#lightbox').hidden = true; });
}

/* ── abstract category chips ── */
function renderCatChips() {
  const counts = new Map();
  TASKS.forEach((t) => counts.set(t.subcategory, (counts.get(t.subcategory) || 0) + 1));
  $('#catChips').innerHTML = Array.from(counts.entries())
    .sort((a, b) => b[1] - a[1])
    .map(([c, n]) => `<span>${esc(catLabel(c))} ${n}</span>`).join('');
}

/* ───────────────────────────── boot ───────────────────────────── */
function boot() {
  if (!SCORES || !SESSION) {
    document.body.insertAdjacentHTML('afterbegin',
      '<p style="padding:16px;background:#ffe8e8;font:14px sans-serif">' +
      'Showcase data missing: expected <code>data/scores.js</code> and <code>case/data/session.js</code>.</p>');
    return;
  }
  let saved = null;
  try { saved = localStorage.getItem('pb-lang'); } catch (e) { /* ignore */ }
  const lang = saved || ((navigator.language || '').toLowerCase().startsWith('zh') ? 'zh' : 'en');
  $('#langToggle').addEventListener('click', () => setLang(LANG === 'zh' ? 'en' : 'zh'));
  $('#protoJudge').textContent = SCORES.meta.judge_model;
  $('#protoJudgeZh').textContent = SCORES.meta.judge_model;
  $('#protoRater').textContent = SCORES.meta.rater_spearman.toFixed(3);
  $('#protoRaterZh').textContent = SCORES.meta.rater_spearman.toFixed(3);
  $('#runId1').textContent = SCORES.meta.run_id;
  $('#runId2').textContent = SCORES.meta.run_id;
  $('#judgeModel1').textContent = SCORES.meta.judge_model;
  $('#judgeModel2').textContent = SCORES.meta.judge_model;
  renderCatChips();
  initPlayer();
  /* inspection hook: lets tools/check_site.py verify the playback schedule */
  window.PixelBenchPlayer = {
    frameMs: (i) => frameMs(i),
    totalMs: () => totalMs(),
    durations: () => durations.slice(),
    fastLoops: () => fastLoops,
    state: () => ({ frame: player.i, playing: player.playing, stmtKey: player.stmtKey,
                    compressedFrames: player.compressedFrames }),
    loaded: () => ({ ready: framesReady, total: frameImg.size, drawn: lastDrawn }),
    stageSignature: () => { const cv = document.querySelector('#stageCanvas');
      const d = cv.getContext('2d').getImageData(0, 0, cv.width, cv.height).data;
      let h = 2166136261; for (let i = 0; i < d.length; i += 4) {
        h ^= d[i] + d[i + 1] * 3 + d[i + 2] * 7 + d[i + 3] * 11; h = Math.imul(h, 16777619);
      } return h >>> 0; },
  };
  initGallery();
  initLightbox();
  setLang(lang);
}
document.addEventListener('DOMContentLoaded', boot);
})();
