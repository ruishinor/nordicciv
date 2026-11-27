"""Laboratory performance measurement: the same scripted session on one or more builds (NC-V04, §22).

    python tests/perf.py OUT.json NAME=URL [NAME=URL ...] [--throttle 4]

For each build: cold load (LCP, CLS, time to interactive data, time to first relief), continuous panning and zooming
(requestAnimationFrame intervals → median / p95 frame time and fps), municipality selection by a real click (Event
Timing duration, an INP proxy) and lens switching (time to the next painted frame). `--throttle N` emulates an
N-times slower CPU through the DevTools protocol. These are laboratory numbers on the machine that runs the script —
not field data; the JSON records the browser, viewport and machine.
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
    return {"frames": len(t), "median_ms": round(med, 1), "p95_ms": round(p95, 1), "fps_median": round(1000 / med, 1) if med else None,
            "long_frames_over_50ms": sum(1 for x in t if x > 50)}


async def measure(b, url, throttle):
    ctx = await b.new_context(viewport=VIEW, device_scale_factor=1)
    pg = await ctx.new_page()
    cdp = await ctx.new_cdp_session(pg)
    if throttle > 1:
        await cdp.send("Emulation.setCPUThrottlingRate", {"rate": throttle})
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
    out["heap_mb"] = round((await pg.evaluate("performance.memory ? performance.memory.usedJSHeapSize : 0")) / 1e6, 1)
    out["app_perf"] = await pg.evaluate("window.__perf ? window.__perf() : null")
    await ctx.close()
    return out


async def main():
    out_path = sys.argv[1]
    throttle = 1
    builds = []
    args = sys.argv[2:]
    if "--throttle" in args:
        throttle = int(args[args.index("--throttle") + 1])
        args = args[: args.index("--throttle")] + args[args.index("--throttle") + 2:]
    for a in args:
        n, u = a.split("=", 1)
        builds.append((n, u))
    res = {"conditions": {"viewport": VIEW, "cpu_throttle": throttle, "machine": platform.platform(), "cpus": os.cpu_count(),
                          "note": "headless Chromium with SwiftShader (software GPU) unless a real GPU is available; laboratory data"}}
    async with async_playwright() as p:
        exe = os.environ.get("NORDICCIV_CHROME")
        b = await p.chromium.launch(executable_path=exe or None, args=["--no-sandbox", "--use-gl=swiftshader", "--enable-unsafe-swiftshader"])
        res["conditions"]["browser"] = b.version
        for n, u in builds:
            res[n] = await measure(b, u, throttle)
            print(n, json.dumps(res[n]))
        await b.close()
    with open(out_path, "w") as f:
        json.dump(res, f, indent=1)


asyncio.run(main())
