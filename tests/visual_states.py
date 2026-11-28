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
    return f"__app.cam.stop?.(); __app.cam.x={x}; __app.cam.y={y}; __app.cam.scale=__app.cam.clampScale({s}); __app.invalidate();"


def at_city(name, s):
    return (f"(() => {{ const c = __app.data.cities.find(x => x.name === {json.dumps(name)}); "
            f"__app.cam.stop?.(); __app.cam.x = c.x; __app.cam.y = c.y; __app.cam.scale = __app.cam.clampScale({s}); __app.invalidate(); }})()")


def select(name, s=None):
    pre = at_city(name, s) + ";" if s else ""
    return pre + f"__app.selectCity(__app.data.cities.find(x => x.name === {json.dumps(name)}), {{fly:false}});"


SH_ON = "__app.ui.setMapToggle?.('shelters', true);"


def SH_PICK(text, s, muni=None):
    """Centre on a shelter whose published address contains `text` (or the largest in `muni`) and open its card."""
    find = (f"[...d.shelters].filter((r) => r.muni === {json.dumps(muni)}).sort((p, q) => q.places - p.places)[0]" if muni
            else f"d.shelters.find((r) => (r.address || '').includes({json.dumps(text)}))")
    return (f"(() => {{ const d = __app.shelters.data, r = {find}; __app.cam.stop?.(); __app.cam.x = r.x; __app.cam.y = r.y; "
            f"__app.cam.scale = {s}; __app.invalidate(); setTimeout(() => __app.shelters.openCard(r), 400); }})()")


UP_ON = "__app.ui.setMapToggle?.('uplinks', true);"


def SCROLL_TO(title):
    """Scroll the open panel to the section with this heading."""
    return (f"setTimeout(() => [...document.querySelectorAll('#city-panel .cp-section')].find((x) => x.querySelector('h3')?.textContent === "
            f"{json.dumps(title)})?.scrollIntoView({{block: 'center'}}), 500);")


def UP_PICK(cid, s):
    """Centre on a camera uplink by id and open its card (the layer is switched on by open())."""
    return (f"(() => {{ const c = __app.uplinks.data.byId.get({json.dumps(cid)}); __app.cam.stop?.(); __app.cam.x = c.x; __app.cam.y = c.y; "
            f"__app.cam.scale = {s}; __app.invalidate(); setTimeout(() => __app.uplinks.open(c.id, {{fly: false}}), 400); }})()")


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
    # v0.3 world-identity states: ranges, forest, farmland and sharpness at close zoom
    ("15-jotunheimen-range", DESKTOP, at_city("Lom", 2.2), 0),
    ("16-skane-farmland-close", DESKTOP, at_city("Skurup", 9), 0),
    ("17-smaland-forest-close", DESKTOP, at_city("Tingsryd", 9), 0),
    ("18-northern-scandes", DESKTOP, at_city("Narvik", 1.4), 0),
    ("19-jutland-mid", DESKTOP, at_city("Herning", 3.5), 0),
    ("20-telemark-very-close", DESKTOP, at_city("Tinn", 18), 0),
    ("21-mobile-lofoten", MOBILE, at_city("Vågan", 4), 0),
    ("22-first-run", DESKTOP, "", 0),
    ("23-what-stands-out", DESKTOP, select("Røst", 6), 0),
    ("24-discovery-card", DESKTOP, "__app.explore.show(__app.explore.discoveries[0]);", 0),
    # v0.4 public shelters (the layer is off by default; each state switches it on itself)
    ("25-shelters-overview-off", DESKTOP, "__app.ui.setMapToggle?.('shelters', false); __app.home();", 1500),
    ("26-shelters-regional", DESKTOP, SH_ON + cam(560, 1430, 1.5), 0),
    ("27-shelters-local-oslo", DESKTOP, SH_ON + cam(598, 1437, 7), 0),
    ("28-shelters-selected", DESKTOP, SH_ON + SH_PICK("Holmlia bad", 12), 0),
    ("29-shelters-society-tab", DESKTOP, select("Oslo", 3.2) + "setTimeout(() => { document.querySelector('[data-cptab=\"Society\"]')?.click(); "
     "setTimeout(() => [...document.querySelectorAll('#city-panel .cp-section')].find((x) => /public shelters/i.test(x.innerText))?.scrollIntoView(), 200); }, 300);", 0),
    ("30-shelters-lens", DESKTOP, "__app.setLens('shelter_places');" + cam(560, 1150, 0.62), 0),
    ("31-shelters-mobile-card", MOBILE, SH_ON + SH_PICK("Bergen", 7, muni="NO-4601"), 0),
    # v0.5 camera uplinks (off by default; each state switches the layer on itself)
    ("32-uplinks-overview-on", DESKTOP, UP_ON + "__app.home();", 1500),
    ("33-uplinks-regional", DESKTOP, UP_ON + cam(560, 1300, 1.3), 0),
    ("34-uplinks-region-west", DESKTOP, UP_ON + cam(330, 1250, 2.6), 0),
    ("35-uplinks-local-lofoten", DESKTOP, UP_ON + at_city("Moskenes", 7), 0),
    ("36-uplinks-selected", DESKTOP, UP_PICK("ln-reinefjorden", 12), 0),
    ("37-uplinks-municipality", DESKTOP, select("Stranda", 5) + UP_ON + "setTimeout(() => [...document.querySelectorAll('#city-panel .cp-section')]"
     ".find((x) => /camera uplinks/i.test(x.innerText))?.scrollIntoView(), 500);", 0),
    ("38-uplinks-under-lens", DESKTOP, UP_ON + "__app.setLens('density');" + cam(560, 1300, 2.2), 0),
    ("39-uplinks-mobile-card", MOBILE, UP_PICK("wcc-sweden-are-areskutan", 7), 0),
    # v0.5 opening screen (captured while the start-up is held on world.json; "failed" = world.json answers 404)
    ("40-opening-desktop", DESKTOP, "opening:loading", 0),
    ("41-opening-mobile", MOBILE, "opening:loading", 0),
    ("42-opening-failed", DESKTOP, "opening:failed", 0),
    # v0.5 Open in Maps
    ("43-maps-municipality", DESKTOP, select("Bergen", 3.2) + SCROLL_TO("The real place"), 0),
    ("44-maps-sites", DESKTOP, select("Bergen", 3.2) + "setTimeout(() => { document.querySelector('[data-cptab=\"Economy\"]')?.click(); "
     "setTimeout(() => document.querySelector('#city-panel .site-list')?.scrollIntoView({block: 'center'}), 200); }, 300);", 0),
    ("45-maps-region", DESKTOP, "__app.selectState('NO-15', {fly: false});" + SCROLL_TO("The real place"), 0),
    ("46-maps-mobile-municipality", MOBILE, select("Stranda", 5) + SCROLL_TO("The real place"), 0),
    ("47-close-fjord", DESKTOP, at_city("Bergen", 12), 0),
    ("48-close-islands", DESKTOP, at_city("Vågan", 12), 0),
    ("49-close-forest", DESKTOP, at_city("Tingsryd", 12), 0),
    ("50-close-farmland", DESKTOP, at_city("Skurup", 12), 0),
    ("51-close-city", DESKTOP, at_city("Copenhagen", 12), 0),
    ("52-close-phone", MOBILE, at_city("Värmdö", 12), 0),
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
            if "first-run" not in name:  # the one-time hint would otherwise cover every after-state
                await pg.add_init_script("try { localStorage.setItem('nc-intro', '1'); } catch (e) {}")
            errs = []
            pg.on("pageerror", lambda e: errs.append(str(e)))
            t0 = time.time()
            if js.startswith("opening:"):  # the opening screen, held on world.json (or failing on it)
                failed = js.endswith("failed")

                async def held(route):  # (one parameter: Playwright passes the request as a second one if asked)
                    if failed:
                        await route.fulfill(status=404, body="not found")
                    else:
                        await asyncio.sleep(8)
                        await route.continue_()
                await ctx.route("**/data/world.json", held)
                await pg.goto(base, wait_until="commit")
                for _ in range(300):  # polled from here: the page's CSP does not allow wait_for_function's eval
                    if await pg.evaluate("(() => { const o = document.getElementById('opening'); return !!o && getComputedStyle(o).position === 'fixed' "
                                         "&& !!o.querySelector('.op-version').textContent; })()"):
                        break
                    await pg.wait_for_timeout(100)
                await pg.wait_for_timeout(4000)  # the needle has settled
                await pg.screenshot(path=str(out / f"{name}.png"))
                timings[name] = {"wall_s": round(time.time() - t0, 2), "perf": None, "errors": errs}
                print(f"{name}: {timings[name]['wall_s']}s")
                await ctx.close()
                continue
            await pg.goto(base, wait_until="networkidle")
            await pg.wait_for_function("() => window.__app && window.__app.data && window.__app.data.cities", timeout=30000)
            await pg.wait_for_timeout(2500 + extra)
            try:
                await pg.evaluate(js)
            except Exception as e:  # a state the old version cannot show
                errs.append(f"state: {e}")
            await pg.wait_for_timeout(2600)
            await pg.screenshot(path=str(out / f"{name}.png"))
            perf = await pg.evaluate("window.__perf ? window.__perf() : null")
            timings[name] = {"wall_s": round(time.time() - t0, 2), "perf": perf, "errors": errs, "zoom": await pg.evaluate("__app.cam.scale")}
            print(f"{name}: {timings[name]['wall_s']}s {errs[:1]}")
            await ctx.close()
        await b.close()
    (out / "timings.json").write_text(json.dumps(timings, indent=1))


asyncio.run(main())
