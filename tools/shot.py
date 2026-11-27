"""Headless screenshot + console log of the app (tools/shot.py URL OUT.png [w h] [js-to-run])."""
import sys, asyncio, json, time
from playwright.async_api import async_playwright
async def main():
    url = sys.argv[1]; out = sys.argv[2]
    w = int(sys.argv[3]) if len(sys.argv) > 3 else 1400; h = int(sys.argv[4]) if len(sys.argv) > 4 else 900
    js = sys.argv[5] if len(sys.argv) > 5 else None
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path="/usr/bin/google-chrome", args=["--no-sandbox", "--use-gl=swiftshader", "--enable-unsafe-swiftshader"])
        pg = await b.new_page(viewport={"width": w, "height": h}, device_scale_factor=1)
        logs = []
        pg.on("console", lambda m: logs.append(f"[{m.type}] {m.text}"))
        pg.on("pageerror", lambda e: logs.append(f"[pageerror] {e}"))
        t0 = time.time()
        await pg.goto(url, wait_until="networkidle")
        await pg.wait_for_timeout(2500)
        if js:
            r = await pg.evaluate(js)
            if r is not None: logs.append(f"[eval] {json.dumps(r)[:3000]}")
            await pg.wait_for_timeout(1500)
        await pg.screenshot(path=out)
        logs.append(f"[time] {time.time()-t0:.1f}s")
        print("\n".join(logs[-60:]))
        await b.close()
asyncio.run(main())
