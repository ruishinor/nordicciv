"""Fixed geographical views and warm render measurements. No source downloads.

python tests/terrain_review.py URL OUT [--baseline]
"""
import asyncio
import json
import os
import platform
import statistics
import sys
from pathlib import Path

from playwright.async_api import async_playwright

CASES = json.loads(Path(__file__).with_name("terrain_cases.json").read_text(encoding="utf-8"))


async def main():
    url, out = sys.argv[1], Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)
    baseline = "--baseline" in sys.argv
    results = {"platform": platform.platform(), "viewport": [1440, 900], "baseline": baseline, "cases": []}
    async with async_playwright() as p:
        browser = await p.chromium.launch(executable_path=os.environ.get("NORDICCIV_CHROME"),
            args=["--no-sandbox", "--enable-unsafe-swiftshader"])
        results["browser"] = browser.version
        ctx = await browser.new_context(viewport={"width": 1440, "height": 900}, bypass_csp=True)
        await ctx.add_init_script("localStorage.setItem('nc-intro','1')")
        page = await ctx.new_page()
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        await page.goto(url.rstrip("/") + "/?renderer=webgl&pitch=24")
        await page.wait_for_function("() => window.__app?.terrain?.stats()?.available", timeout=60000)
        await page.wait_for_function("() => !document.getElementById('opening')", timeout=60000)
        await page.wait_for_timeout(1500)
        for case in CASES:
            for scale in ([48] if baseline else [48, 720]):
                await page.evaluate("""async ({lon, lat, scale}) => {
                    const a = __app, g = await import('./js/util/geo.js');
                    const q = g.lonLatToMap(g.projectionFrom(a.w), lon, lat);
                    a.cam.stop(); a.clearSelection(); a.setLens(null); a.cam.scale = scale;
                    [a.cam.x, a.cam.y] = a.cam.centerAt(q.x, q.y, a.cam.w/2, a.cam.h/2);
                    a.invalidate(); window.__reviewPoint = q;
                }""", {**case, "scale": scale})
                await page.wait_for_timeout(1800)
                if not baseline:
                    await page.wait_for_function("""() => {
                        const t=__app.terrain.stats().tiles, width=__app.cam.w/__app.cam.scale;
                        return t && Math.abs(t.widthKm-width)<0.05;
                    }""", timeout=30000)
                    await page.wait_for_function("() => !__app.terrain.stats().tiles?.pending", timeout=30000)
                    # Loading changes the sampled surface. Keep the geographical target at the centre.
                    await page.evaluate("""() => { const a=__app, q=__reviewPoint;
                        [a.cam.x,a.cam.y]=a.cam.centerAt(q.x,q.y,a.cam.w/2,a.cam.h/2); a.invalidate(); }""")
                    await page.wait_for_timeout(700)
                name = f"{case['id']}-{scale}"
                await page.screenshot(path=str(out / (name + ".png")))
                samples = []
                for _ in range(5):
                    samples.append(await page.evaluate("""async () => { const t=performance.now(); __app.invalidate();
                        await new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)));
                        return {paint:performance.now()-t, static:__app.stats().staticLast, frame:__app.stats().frameLast}; }"""))
                detail = await page.evaluate("""() => ({terrain:__app.terrain.stats(), perf:__perf(),
                    camera:{x:__app.cam.x,y:__app.cam.y,scale:__app.cam.scale,pitch:__app.cam.pitch,widthKm:__app.cam.w/__app.cam.scale},
                    heapBytes:performance.memory?.usedJSHeapSize ?? null})""")
                results["cases"].append({**case, "id": name, "samples": samples,
                    "paintMedianMs": statistics.median(x["paint"] for x in samples), **detail})
                print(name, round(results["cases"][-1]["paintMedianMs"], 1), flush=True)
        results["errors"] = errors
        (out / "measurements.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
        await browser.close()
        if errors:
            raise RuntimeError(errors)


if __name__ == "__main__":
    asyncio.run(main())
