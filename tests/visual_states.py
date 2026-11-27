"""Capture the standard visual states at fixed viewports, camera positions and zooms (visual regression, NC-V04).

    python tests/visual_states.py BASE_URL OUT_DIR [state ...]

Every state sets the camera with app.cam directly (no flight), so the same state gives the same frame across versions.
Also records per-state timings (static render ms from the app's own perf counters) in OUT_DIR/timings.json.
Browser: the Playwright-managed Chromium, or the executable in $NORDICCIV_CHROME.
"""
import asyncio
import json
import os
import sys
import time
from pathlib import Path

from playwright.async_api import async_playwright

DESKTOP = {"width": 1440, "height": 900}
MOBILE = {"width": 390, "height": 844}


def cam(x, y, s):
    return f"__app.cam.stop?.(); __app.cam.x={x}; __app.cam.y={y}; __app.cam.scale={s}; __app.invalidate();"


def at_city(name, s):
    return (f"(() => {{ const c = __app.data.cities.find(x => x.name === {json.dumps(name)}); "
            f"__app.cam.stop?.(); __app.cam.x = c.x; __app.cam.y = c.y; __app.cam.scale = {s}; __app.invalidate(); }})()")


def select(name, s=None):
    pre = at_city(name, s) + ";" if s else ""
    return pre + f"__app.selectCity(__app.data.cities.find(x => x.name === {json.dumps(name)}), {{fly:false}});"


STATES = [
    ("01-overview", DESKTOP, "__app.home();", 1500),
    ("02-regional-south", DESKTOP, cam(560, 1450, 1.15), 0),
    ("03-bergen-profile", DESKTOP, select("Bergen", 3.2), 0),
    ("04-kiruna-council", DESKTOP, select("Kiruna", 1.6) + "document.dispatchEvent(new KeyboardEvent('keydown',{key:'c'})); window.dispatchEvent(new KeyboardEvent('keydown',{key:'c'}));", 0),
    ("05-western-norway-terrain", DESKTOP, cam(330, 1300, 2.4), 0),
    ("06-coast-fjord-detail", DESKTOP, at_city("Bergen", 9), 0),
    ("07-small-municipality-frederiksberg", DESKTOP, select("Frederiksberg", 14), 0),
    ("08-specialisation-lens", DESKTOP, "__app.setLens('specialisation');" + cam(760, 1500, 0.75), 0),
    ("09-population-density-lens", DESKTOP, "__app.setLens('density');" + cam(760, 1500, 0.75), 0),
    ("10-growth-lens-oresund", DESKTOP, "__app.setLens('growth');" + at_city("Malmö", 4), 0),
    ("11-lofoten", DESKTOP, at_city("Vågan", 3.2), 0),
    ("12-stockholm-archipelago", DESKTOP, at_city("Värmdö", 3.5), 0),
    ("13-mobile-overview", MOBILE, "__app.home();", 1500),
    ("14-mobile-tromso", MOBILE, select("Tromsø", 3.0), 0),
]


async def main():
    base, out = sys.argv[1], Path(sys.argv[2])
    only = set(sys.argv[3:])
    out.mkdir(parents=True, exist_ok=True)
    exe = os.environ.get("NORDICCIV_CHROME")
    timings = {}
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path=exe or None,
                                    args=["--no-sandbox", "--use-gl=swiftshader", "--enable-unsafe-swiftshader"])
        for name, vp, js, extra in STATES:
            if only and name not in only:
                continue
            ctx = await b.new_context(viewport=vp, device_scale_factor=1, is_mobile=vp is MOBILE, has_touch=vp is MOBILE)
            pg = await ctx.new_page()
            errs = []
            pg.on("pageerror", lambda e: errs.append(str(e)))
            t0 = time.time()
            await pg.goto(base, wait_until="networkidle")
            await pg.wait_for_function("window.__app && window.__app.data && window.__app.data.cities", timeout=30000)
            await pg.wait_for_timeout(2500 + extra)
            try:
                await pg.evaluate(js)
            except Exception as e:  # a state the old version cannot show
                errs.append(f"state: {e}")
            await pg.wait_for_timeout(2600)
            await pg.screenshot(path=str(out / f"{name}.png"))
            perf = await pg.evaluate("window.__perf ? window.__perf() : null")
            timings[name] = {"wall_s": round(time.time() - t0, 2), "perf": perf, "errors": errs}
            print(f"{name}: {timings[name]['wall_s']}s {errs[:1]}")
            await ctx.close()
        await b.close()
    (out / "timings.json").write_text(json.dumps(timings, indent=1))


asyncio.run(main())
