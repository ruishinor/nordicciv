// Opening screen. The markup is in index.html, so it is on screen from the first paint; this module runs as soon as it
// arrives (before the rest of the app's code has downloaded) and main.js drives it through the real start-up:
//
//   begin(names)     the essential and start-up data files main.js is about to fetch
//   read(name, res)  wraps a fetch Response: counts bytes as they arrive when the server says how many to expect
//                    (Content-Length, no compression); otherwise the file counts once it has arrived
//   settle(name)     a file is done (arrived, missing-but-optional or failed)
//   preparing()      all files are in; the map is being built — resolves after that status has been painted
//   ready()          the first map frame has been drawn: the app is released and the screen fades out
//   fail(err)        start-up failed: progress stops, a plain explanation and "Try again" are shown
//
// Nothing here is staged. The bar's length is the share of the start-up work actually done (bytes where every size is
// known, whole files where not, the map preparation last) and it is indeterminate until that share can be known; no
// percentage is shown or invented, and the screen
// never waits for an animation. Optional layers, relief tiles and extensions load after it has gone. With a warm
// cache the whole thing takes a fraction of a second and the fade is shortened to match.
//
// Accessibility: the app behind is inert until ready (index.html, lifted here), so neither pointer nor keyboard can
// reach hidden controls. Screen readers hear "Opening NordicCiv", then "Map ready" or the failure — not every step;
// the progress bar carries the current step as its value text. prefers-reduced-motion removes all movement (CSS).

const root = document.getElementById("opening");
const $ = (sel) => root?.querySelector(sel);
const fill = $(".op-fill");
const bar = $(".op-progress");
const statusEl = $(".op-status");
const live = $(".op-live");

// Status lines. The files download in parallel and finish roughly smallest first, so the lines are in that order; the
// first line with a file still on its way is shown, so a line is only ever shown while its files really are loading.
const STEPS = [
  { msg: "Loading resources and regions…", files: ["nation", "sources", "states", "resources"] },
  { msg: "Loading population and economy…", files: ["lenses"] },
  { msg: "Loading cities and settlements…", files: ["cities"] },
  { msg: "Loading the landscape…", files: ["world"] },
];
const PREPARE_SHARE = 0.12; // building the world and the first frame, after every file is in
const STALL_MS = 15000;

const t0 = performance.now();
const files = new Map(); // name → {loaded, total|null, done}
let phase = "loading"; // loading → preparing → ready | failed
let shown = 0; // the bar never moves backwards (weights firm up as headers arrive)
let lastMove = performance.now();
let stallTimer = 0;
const log = [{ t: 0, step: "Opening Scandinavia…" }];

const state = { get phase() { return phase; }, log, t0, readyMs: null, files };
window.__opening = state; // for tests and profiling

function setStatus(msg) {
  if (!statusEl || statusEl.textContent === msg) return;
  statusEl.textContent = msg;
  bar?.setAttribute("aria-valuetext", msg);
  log.push({ t: Math.round(performance.now() - t0), step: msg });
}

// Share of the start-up done. Until every file's size is known (or it has arrived) nothing is claimed: the bar stays
// indeterminate rather than guess how big the missing ones are. Then: bytes, when every size is known; otherwise whole
// files, each counted once it has arrived.
function fraction() {
  if (phase === "ready") return 1;
  const fs = [...files.values()];
  if (!fs.length || fs.some((f) => !f.done && !f.total)) return 0;
  let dl;
  if (fs.every((f) => f.total)) {
    const all = fs.reduce((a, f) => a + f.total, 0);
    dl = fs.reduce((a, f) => a + (f.done ? f.total : Math.min(f.loaded, f.total)), 0) / all;
  } else {
    dl = fs.filter((f) => f.done).length / fs.length;
  }
  return dl * (1 - PREPARE_SHARE);
}

function render() {
  if (!root || phase === "failed") return;
  const f = Math.max(shown, fraction());
  if (f > shown + 1e-4) { shown = f; lastMove = performance.now(); }
  if (fill) fill.style.transform = `scaleX(${shown.toFixed(4)})`;
  root.classList.toggle("op-indeterminate", shown === 0);
  if (phase === "loading") {
    const step = STEPS.find((s) => s.files.some((n) => files.has(n) && !files.get(n).done));
    if (step) setStatus(step.msg);
  }
}

// Byte counts arrive per network chunk; the screen is updated at most once per frame.
let renderQueued = false;
function renderSoon() {
  if (renderQueued) return;
  renderQueued = true;
  requestAnimationFrame(() => { renderQueued = false; render(); });
}

function watchStall() {
  clearInterval(stallTimer);
  stallTimer = setInterval(() => {
    if (phase !== "loading" && phase !== "preparing") return clearInterval(stallTimer);
    if (performance.now() - lastMove > STALL_MS) root?.classList.add("op-slow");
  }, 1000);
}

export function begin(names) {
  for (const n of names) if (!files.has(n)) files.set(n, { loaded: 0, total: null, done: false });
  render();
  watchStall();
}

/** Parse a fetch Response as JSON, counting its bytes for the progress bar when they can be measured honestly. */
export async function read(name, res) {
  const f = files.get(name);
  const len = +res.headers.get("content-length");
  const enc = (res.headers.get("content-encoding") || "identity").toLowerCase();
  // With compression the header counts compressed bytes while the stream yields decompressed ones: not comparable.
  if (!f || !res.body || !(len > 0) || enc !== "identity" || typeof TransformStream !== "function") return res.json();
  f.total = len;
  renderSoon();
  const counted = res.body.pipeThrough(new TransformStream({
    transform(chunk, ctl) { f.loaded += chunk.byteLength; renderSoon(); ctl.enqueue(chunk); },
  }));
  return new Response(counted).json();
}

export function settle(name) {
  const f = files.get(name);
  if (f && !f.done) { f.done = true; renderSoon(); }
}

/** All files are in: show "Preparing the map…" and let the browser paint it before the (synchronous) build. */
export function preparing() {
  if (phase !== "loading") return Promise.resolve();
  for (const f of files.values()) f.done = true;
  phase = "preparing";
  setStatus("Preparing the map…");
  render();
  return nextPaint();
}

function nextPaint() {
  // One frame, so the status is painted; a timer backs it up in a background tab, where frames do not run.
  return new Promise((resolve) => {
    let done = false;
    const go = () => { if (!done) { done = true; resolve(); } };
    requestAnimationFrame(() => setTimeout(go, 0));
    setTimeout(go, 100);
  });
}

function release() {
  for (const el of document.querySelectorAll("body > [inert]")) el.removeAttribute("inert");
}

/** The first map frame is on screen: release the app and fade the opening screen out. */
export function ready() {
  if (!root || phase === "ready" || phase === "failed") return;
  phase = "ready";
  state.readyMs = Math.round(performance.now() - t0);
  clearInterval(stallTimer);
  setStatus("Ready to explore.");
  render();
  release();
  root.removeAttribute("aria-busy");
  if (live) live.textContent = "Map ready.";
  // A quick start gets a short fade; a long one a slightly longer, calmer one. Neither holds anything up: the map
  // underneath is already live and the screen ignores the pointer while it fades.
  const quick = state.readyMs < 700;
  root.style.setProperty("--op-fade", quick ? "180ms" : "420ms");
  root.classList.add("op-done");
  const remove = () => root.remove();
  root.addEventListener("transitionend", (e) => { if (e.target === root) remove(); }, { once: false });
  setTimeout(remove, quick ? 400 : 800); // transitions do not run with reduced motion or in background tabs
}

function explain(err) {
  const msg = String(err?.message || err || "");
  if (navigator.onLine === false) {
    return { title: "You seem to be offline", body: "NordicCiv needs a connection the first time it opens Scandinavia. Check your connection and try again." };
  }
  if (/HTTP 404/.test(msg)) {
    return { title: "The map data is missing", body: "This copy of NordicCiv was published without some of its map files, so the map cannot open." };
  }
  if (/HTTP \d+|Failed to fetch|NetworkError|Load failed|network/i.test(msg)) {
    return { title: "The map didn't arrive", body: "Part of the map could not be downloaded. This is usually a passing network problem." };
  }
  if (/module|import|script/i.test(msg)) {
    return { title: "NordicCiv didn't start", body: "Part of the application could not be loaded. Reloading usually fixes it." };
  }
  return { title: "The map couldn't open", body: "Something went wrong while preparing Scandinavia." };
}

/** Start-up failed: stop the progress, say what happened in plain words, offer to try again. */
export function fail(err) {
  if (!root || phase === "ready" || phase === "failed") return;
  phase = "failed";
  clearInterval(stallTimer);
  console.error("NordicCiv could not start:", err); // the full error stays in the console for development
  const { title, body } = explain(err);
  root.classList.add("op-failed");
  root.classList.remove("op-slow", "op-indeterminate");
  root.removeAttribute("aria-busy");
  bar?.setAttribute("hidden", "");
  statusEl?.setAttribute("hidden", "");
  const box = $(".op-error");
  if (!box) return;
  const detail = String(err?.message || err || "unknown error");
  box.innerHTML = `<h2 class="op-err-title"></h2><p class="op-err-body"></p>
    <div class="op-err-act"><button type="button" class="btn op-retry">Try again</button></div>
    <details class="op-err-detail"><summary>Details for developers</summary><code></code>
      <p>Serve <code>web/</code> over HTTP after building the data (<code>python -m pipeline all</code>).</p></details>`;
  box.querySelector(".op-err-title").textContent = title;
  box.querySelector(".op-err-body").textContent = body;
  box.querySelector(".op-err-detail > code").textContent = detail;
  box.setAttribute("role", "alert");
  box.hidden = false;
  log.push({ t: Math.round(performance.now() - t0), step: `failed: ${title}` });
  const retry = box.querySelector(".op-retry");
  retry.onclick = () => location.reload();
  retry.focus();
}

// A script of the app that fails to download never reaches main.js's error handler: catch it here.
window.addEventListener("error", (e) => {
  const t = e.target;
  if (t && t !== window && t.tagName === "SCRIPT" && phase !== "ready") fail(new Error(`a script failed to load (${t.src || "module"})`));
}, true);

// The release version, from the build (web/data/version.json, written from VERSION and checked against it).
fetch("data/version.json").then((r) => (r.ok ? r.json() : null)).then((v) => {
  const el = $(".op-version");
  if (el && v && typeof v.version === "string" && /^\d+\.\d+\.\d+([-.][\w.]+)?$/.test(v.version)) el.textContent = `v${v.version}`;
}).catch(() => { /* no version shown */ });

export const opening = { begin, read, settle, preparing, ready, fail, state };
