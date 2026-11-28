"""Laboratory performance measurement: the same scripted session on one or more builds (NC-V04, §22).

    python tests/perf.py OUT.json NAME=URL [NAME=URL ...] [--throttle 4] [--runs 3]

For each build: cold load (LCP, CLS, time to interactive data, time to first relief), continuous panning and zooming
(requestAnimationFrame intervals → median / p95 frame time and fps), municipality selection by a real click (Event
Timing duration, an INP proxy) and lens switching (time to the next painted frame). `--throttle N` emulates an
N-times slower CPU through the DevTools protocol. `--runs N` repeats the session N times per build, alternating the
build order (A B, B A, …) so neither build always runs first; results report the median, the 95th percentile and the
worst case over all samples of all runs. A fixed camera tour (overview, regional, close and very close views) times
each full redraw from the camera change to the second painted frame: cold (on arrival, tiles still loading) and
settled (the same view again once its tiles and masks are decoded).
These are laboratory numbers on the machine that runs the script — not field data; the JSON records the browser,
viewport and machine.
"""
import asyncio
import json
import os
import platform
import statistics
import sys

from playwright.async_api import async_playwright

VIEW = {"width": 1440, "height": 900}

FRAMES_JS = """() => new Promise(res => { const t = []; let last = performance.now(); let stop = false;
  const tick = (now) => { t.push(now - last); last = now; if (!stop) requestAnimationFrame(tick); };
  requestAnimationFrame(tick); window.__stopFrames = () => { stop = true; res(t.slice(1)); }; })"""


def summarise(t):
    if not t:
        return None
    t = sorted(t)
    p95 = t[min(len(t) - 1, int(len(t) * 0.95))]
    med = statistics.median(t)
    return {"frames": len(t), "median_ms": round(med, 1), "p95_ms": round(p95, 1), "worst_ms": round(t[-1], 1),
            "fps_median": round(1000 / med, 1) if med else None, "long_frames_over_50ms": sum(1 for x in t if x > 50)}


TOUR = [("overview", None, 0.42), ("regional", "Oslo", 1.2), ("regional", "Umeå", 1.6), ("mid", "Bergen", 2.6),
        ("mid", "Jönköping", 3.0), ("close", "Bergen", 6), ("close", "Tingsryd", 6), ("close", "Skurup", 6),
        ("max_zoom", "Tinn", 12), ("max_zoom", "Lom", 12), ("max_zoom", "Frederiksberg", 12), ("mid", "Narvik", 2.4)]
TOUR_JS = """async ([name, s]) => { const c = name ? __app.data.cities.find(x => x.name === name) : null;
  __app.cam.stop?.(); if (c) { __app.cam.x = c.x; __app.cam.y = c.y; __app.cam.scale = __app.cam.clampScale(s); } else { __app.home(); __app.cam.stop?.(); __app.cam.scale = __app.cam.clampScale(s); }
  const t0 = performance.now(); __app.invalidate();
  await new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r))); return performance.now() - t0; }"""


async def measure(b, url, throttle):
    ctx = await b.new_context(viewport=VIEW, device_scale_factor=1, bypass_csp=True)  # test hooks only; same for both builds
    pg = await ctx.new_page()
    cdp = await ctx.new_cdp_session(pg)
    if throttle > 1:
        await cdp.send("Emulation.setCPUThrottlingRate", {"rate": throttle})
    # a returning visitor: the v0.3 first-run hint would otherwise be the largest paint (it appears once data is in)
    await pg.add_init_script("try { localStorage.setItem('nc-intro', '1'); } catch (e) {}")
    await pg.add_init_script("""
      window.__lcp = 0; window.__cls = 0; window.__events = [];
      new PerformanceObserver(l => { for (const e of l.getEntries()) window.__lcp = e.startTime; }).observe({type: 'largest-contentful-paint', buffered: true});
      new PerformanceObserver(l => { for (const e of l.getEntries()) if (!e.hadRecentInput) window.__cls += e.value; }).observe({type: 'layout-shift', buffered: true});
      new PerformanceObserver(l => { for (const e of l.getEntries()) window.__events.push({name: e.name, d: e.duration}); }).observe({type: 'event', durationThreshold: 16, buffered: true});
    """)
    out = {}
    await pg.goto(url, wait_until="load")
    await pg.wait_for_function("window.__app && __app.data && __app.data.cities", timeout=60000)
    out["data_ready_ms"] = round(await pg.evaluate("performance.now()"))
    out["max_zoom"] = await pg.evaluate("__app.cam.maxScale")
    try:
        await pg.wait_for_function("import('./js/render/art/relief.js').then(m => m.reliefReady())", timeout=60000)
        out["relief_ready_ms"] = round(await pg.evaluate("performance.now()"))
    except Exception:
        out["relief_ready_ms"] = None  # build without the relief layer
    await pg.wait_for_timeout(2500)
    out["lcp_ms"] = round(await pg.evaluate("window.__lcp"))
    out["cls"] = round(await pg.evaluate("window.__cls"), 4)
    # pan: 3 s of drags across the south
    await pg.evaluate("(() => { const c = __app.data.cities.find(x => x.name === 'Oslo'); __app.cam.x = c.x; __app.cam.y = c.y; __app.cam.scale = 1.6; __app.invalidate(); })()")
    await pg.wait_for_timeout(1500)
    fut = asyncio.ensure_future(pg.evaluate(FRAMES_JS))
    await pg.wait_for_timeout(50)
    for k in range(4):
        await pg.mouse.move(900, 450)
        await pg.mouse.down()
        await pg.mouse.move(400, 300 + 40 * k, steps=40)
        await pg.mouse.up()
        await pg.wait_for_timeout(120)
    await pg.evaluate("window.__stopFrames()")
    out["pan"] = summarise(await fut)
    # zoom in and out through the level-of-detail thresholds
    fut = asyncio.ensure_future(pg.evaluate(FRAMES_JS))
    await pg.wait_for_timeout(50)
    for d in [-300] * 6 + [300] * 6:
        await pg.mouse.move(720, 450)
        await pg.mouse.wheel(0, d)
        await pg.wait_for_timeout(180)
    await pg.wait_for_timeout(600)
    await pg.evaluate("window.__stopFrames()")
    out["zoom"] = summarise(await fut)
    # selection by a real click on a banner (Event Timing)
    await pg.evaluate("(() => { const c = __app.cityById.get('NO-4601'); __app.cam.x = c.x; __app.cam.y = c.y; __app.cam.scale = 2; __app.invalidate(); })()")
    await pg.wait_for_timeout(1500)
    sx, sy = await pg.evaluate("(() => { const c = __app.cityById.get('NO-4601'); return __app.cam.toScreen(c.x, c.y); })()")
    await pg.evaluate("window.__events = []")
    await pg.mouse.click(sx + 4, sy + 30)
    await pg.wait_for_timeout(800)
    ev = await pg.evaluate("window.__events.filter(e => ['pointerdown','pointerup','click','mousedown','mouseup'].includes(e.name)).map(e => e.d)")
    out["select_event_ms_max"] = round(max(ev), 1) if ev else "< 16 (no event above the 16 ms threshold)"
    # lens switching: time from the call to the next painted frame
    lens = []
    for lid in ("density", "growth", "specialisation", "income", None, "density"):
        t = await pg.evaluate(f"""new Promise(res => {{ const t0 = performance.now(); __app.setLens({json.dumps(lid)});
            requestAnimationFrame(() => requestAnimationFrame(() => res(performance.now() - t0))); }})""")
        lens.append(round(t, 1))
        await pg.wait_for_timeout(300)
    out["lens_switch_ms"] = lens
    out["lens_switch_cached_ms"] = lens[-1]
    # camera tour: each view redrawn from scratch. "cold" = the first redraw on arrival (tiles and masks may still be
    # loading); "settled" = the same view redrawn again once everything for it has loaded and been decoded (the cost
    # of every later redraw there, e.g. after a pan stops).
    settle = 2500 if throttle == 1 else 7000
    await pg.evaluate("__app.setLens(null); __app.clearSelection()")  # the terrain view (the lens test left one on)
    await pg.wait_for_timeout(500)
    cold, settled, illus = {}, {}, []
    for cls, name, sc in TOUR:
        t_start = await pg.evaluate("performance.now()")
        t = await pg.evaluate(TOUR_JS, [name, sc])
        cold.setdefault(cls, []).append(round(t, 1))
        await pg.wait_for_timeout(settle)
        for _ in range(3):
            t = await pg.evaluate(TOUR_JS, [name, sc])
            settled.setdefault(cls, []).append(round(t, 1))
            await pg.wait_for_timeout(150)
        st = await pg.evaluate("import('./js/render/art/illustrate.js').then(m => m.illustrationState?.()?.last || null).catch(() => null)")
        st = st if st and st.get("at", 0) >= t_start else None  # illustrated during this view, or not at all
        illus.append([cls, name, st])
    out["tour_cold"], out["tour_warm"], out["tour_illustration"] = cold, settled, illus
    # close-zoom panning (illustrated ground in v0.3)
    await pg.evaluate("(() => { const c = __app.data.cities.find(x => x.name === 'Bergen'); __app.cam.stop?.(); __app.cam.x = c.x; __app.cam.y = c.y; __app.cam.scale = __app.cam.clampScale(6); __app.invalidate(); })()")
    await pg.wait_for_timeout(2000)
    fut = asyncio.ensure_future(pg.evaluate(FRAMES_JS))
    await pg.wait_for_timeout(50)
    for k in range(4):
        await pg.mouse.move(900, 450)
        await pg.mouse.down()
        await pg.mouse.move(500, 380 + 30 * k, steps=40)
        await pg.mouse.up()
        await pg.wait_for_timeout(150)
    await pg.evaluate("window.__stopFrames()")
    out["close_pan"] = summarise(await fut)
    out["heap_mb"] = round((await pg.evaluate("performance.memory ? performance.memory.usedJSHeapSize : 0")) / 1e6, 1)
    # canvas memory held by the illustration layer (decoded mask tiles × class canvases of 512² RGBA), v0.3 only
    out["illustration_tiles"] = await pg.evaluate("import('./js/render/art/illustrate.js').then(m => m.illustrationState?.() || null).catch(() => null)")
    out["app_perf"] = await pg.evaluate("window.__perf ? window.__perf() : null")
    await ctx.close()
    return out


def aggregate(runs):
    """Combine several runs of one build: frame and redraw samples pooled (median, p95, worst)."""
    def pool(vals):
        v = sorted(x for x in vals if isinstance(x, (int, float)))
        if not v:
            return None
        return {"n": len(v), "median_ms": round(statistics.median(v), 1), "p95_ms": round(v[min(len(v) - 1, int(len(v) * 0.95))], 1), "worst_ms": round(v[-1], 1)}
    out = {"runs": len(runs), "max_zoom": runs[-1].get("max_zoom")}
    for k in ("data_ready_ms", "relief_ready_ms", "lcp_ms", "heap_mb"):
        out[k] = pool([r.get(k) for r in runs])
    for k in ("pan", "zoom", "close_pan"):
        rs = [r.get(k) for r in runs if r.get(k)]
        out[k] = {"median_of_medians_ms": round(statistics.median([x["median_ms"] for x in rs]), 1),
                  "p95_ms_worst_run": max(x["p95_ms"] for x in rs), "worst_ms": max(x["worst_ms"] for x in rs),
                  "long_frames_over_50ms": sum(x["long_frames_over_50ms"] for x in rs)} if rs else None
    out["lens_switch"] = pool([x for r in runs for x in r.get("lens_switch_ms", [])])
    for ph in ("cold", "warm"):
        classes = sorted({c for r in runs for c in r.get(f"tour_{ph}", {})})
        out[f"redraw_{ph}"] = {c: pool([x for r in runs for x in r.get(f"tour_{ph}", {}).get(c, [])]) for c in classes}
    out["illustration_tiles"] = runs[-1].get("illustration_tiles")
    out["select_event_ms_max"] = [r.get("select_event_ms_max") for r in runs]
    return out


async def main():
    out_path = sys.argv[1]
    throttle, nruns = 1, 1
    builds = []
    args = sys.argv[2:]
    for flag in ("--throttle", "--runs"):
        if flag in args:
            v = int(args[args.index(flag) + 1])
            args = args[: args.index(flag)] + args[args.index(flag) + 2:]
            throttle, nruns = (v, nruns) if flag == "--throttle" else (throttle, v)
    for a in args:
        n, u = a.split("=", 1)
        builds.append((n, u))
    res = {"conditions": {"viewport": VIEW, "cpu_throttle": throttle, "runs": nruns, "machine": platform.platform(), "cpus": os.cpu_count(),
                          "note": "headless Chromium with SwiftShader (software GPU) unless a real GPU is available; laboratory data"}}
    raw = {n: [] for n, _ in builds}
    async with async_playwright() as p:
        exe = os.environ.get("NORDICCIV_CHROME")
        b = await p.chromium.launch(executable_path=exe or None, args=["--no-sandbox", "--use-gl=swiftshader", "--enable-unsafe-swiftshader"])
        res["conditions"]["browser"] = b.version
        for k in range(nruns):
            for n, u in (builds if k % 2 == 0 else list(reversed(builds))):
                r = await measure(b, u, throttle)
                raw[n].append(r)
                print(f"run {k + 1} {n}: max zoom {r['max_zoom']}; pan {r['pan']['median_ms'] if r.get('pan') else None} ms, close pan {r['close_pan']['median_ms'] if r.get('close_pan') else None} ms", flush=True)
        await b.close()
    for n, _ in builds:
        res[n] = aggregate(raw[n])
    res["raw"] = raw
    with open(out_path, "w") as f:
        json.dump(res, f, indent=1)


asyncio.run(main())
