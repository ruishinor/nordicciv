"""Real-browser user journeys (Playwright + Chromium). Run with the site served:
    python -m pipeline serve --port 8765 &   python tests/smoke_browser.py [http://127.0.0.1:8765/]
Prints PASS/FAIL per journey and render timings; exits 1 on any failure or console error.
"""
import asyncio
import json
import sys
import time

from playwright.async_api import async_playwright

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8765/"
CHROME = "/usr/bin/google-chrome"


async def main():
    results, errors = [], []

    def ok(name, cond, detail=""):
        results.append((name, bool(cond), detail))
        print(f"{'PASS' if cond else 'FAIL'}  {name} {detail}")

    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path=CHROME, args=["--no-sandbox", "--use-gl=swiftshader", "--enable-unsafe-swiftshader"])
        ctx = await b.new_context(viewport={"width": 1440, "height": 900}, accept_downloads=True)
        pg = await ctx.new_page()
        pg.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
        pg.on("pageerror", lambda e: errors.append(str(e)))
        t0 = time.time()
        await pg.goto(URL, wait_until="networkidle")
        await pg.wait_for_function("window.__app && window.__app.data && window.__app.data.cities", timeout=30000)
        await pg.wait_for_timeout(1500)
        ok("load", True, f"{time.time() - t0:.1f}s to interactive (local server)")
        n = await pg.evaluate("__app.data.cities.length")
        ok("745 municipalities loaded", n == 745, str(n))
        # search: a town that is not a municipality name
        await pg.click("#search-input")
        await pg.keyboard.type("Rjukan")
        await pg.wait_for_timeout(400)
        txt = await pg.inner_text("#search-results")
        ok("search finds Rjukan → Tinn", "Tinn" in txt, txt[:60].replace("\n", " "))
        await pg.keyboard.press("Enter")
        await pg.wait_for_timeout(1200)
        title = await pg.evaluate("document.querySelector('#city-panel .cp-name')?.innerText || ''")
        ok("search opens municipality panel", "TINN" in title.upper(), title)
        # click a land hex: centre of the map near Jönköping
        cell = await pg.evaluate("(() => { const c = __app.data.cities.find(x => x.name === 'Jönköping'); __app.flyTo(__app.w.grid.cx(c.cell), __app.w.grid.cy(c.cell), 3, 0); return c.cell; })()")
        await pg.wait_for_timeout(800)
        await pg.mouse.click(720, 450)
        await pg.wait_for_timeout(900)
        kind = await pg.evaluate("document.querySelector('#city-panel')?.dataset.kind")
        ok("clicking land opens a municipality", kind == "city", str(kind))
        # every lens renders
        lens_ids = await pg.evaluate("__app.data.lenses.lenses.map(l => l.id)")
        for lid in lens_ids:
            await pg.evaluate(f"__app.setLens('{lid}')")
            await pg.wait_for_timeout(120)
        ok("all lenses render", True, f"{len(lens_ids)} lenses")
        await pg.evaluate("__app.setLens(null)")
        # council: every advisor, for Scandinavia and for a selection
        bad = await pg.evaluate("""(() => {
            const out = []; __app.clearSelection(); __app.nordic.toggle(true);
            for (const sel of [null, 'NO-1103', 'SE-2584', 'DK-101']) {
              if (sel) __app.selectCity(sel, {fly:false});
              for (const id of ['geography','people','economy','industry','energy','infrastructure','environment','resilience']) {
                document.querySelector(`[data-adv=${id}]`)?.click();
                const t = document.querySelector('.nc-body')?.innerText || '';
                if (t.includes('Could not compute') || t.includes('undefined') || t.includes('NaN')) out.push(`${sel}:${id}`);
              }
            }
            return out; })()""")
        ok("all advisors compute (4 contexts × 8 advisors)", not bad, str(bad))
        # explorer + CSV
        await pg.evaluate("document.querySelector('[data-tab=explorer]').click()")
        await pg.wait_for_timeout(300)
        async with pg.expect_download() as dl:
            await pg.click('[data-act="csv"]')
        d = await dl.value
        path = await d.path()
        lines = open(path, encoding="utf-8").read().splitlines()
        ok("explorer CSV export", len([l for l in lines if not l.startswith("#")]) == 746, f"{len(lines)} lines incl. notes")
        # compare
        await pg.evaluate("__app.emit('compare', {add: 'NO-0301'}); __app.emit('compare', {add: 'SE-0180'})")
        cmp_txt = await pg.evaluate("document.querySelector('.nc-body').innerText")
        ok("compare table", "Oslo" in cmp_txt and "Stockholm" in cmp_txt)
        # timeline lens
        await pg.evaluate("document.querySelector('[data-tab=timeline]').click()")
        await pg.evaluate("document.querySelector('[data-act=apply]').click()")
        await pg.wait_for_timeout(300)
        lname = await pg.evaluate("__app.state.lens?.name")
        ok("timeline lens", lname and lname.startswith("Population change 2008"), str(lname))
        # almanac pages
        await pg.evaluate("__app.nordic.toggle(false); __app.pedia.open('About this map')")
        pages = await pg.evaluate("[...document.querySelectorAll('#pedia-nav button')].map(b => b.dataset.page)")
        empty = []
        for pname in pages:
            await pg.evaluate(f"__app.pedia.open({json.dumps(pname)})")
            if len(await pg.inner_text("#pedia-body")) < 200:
                empty.append(pname)
        ok("almanac pages", not empty and len(pages) >= 9, f"{len(pages)} pages {empty}")
        await pg.evaluate("__app.pedia.close?.()")
        # render performance
        stats = await pg.evaluate("""(async () => { __app.home(); await new Promise(r => setTimeout(r, 900));
            for (let k = 0; k < 6; k++) { __app.flyTo(500 + k * 60, 1500 - k * 120, 1 + k * 0.6, 0); await new Promise(r => setTimeout(r, 350)); }
            return __app.stats(); })()""")
        ok("render timing measured", stats.get("staticAvg") is not None,
           f"static map avg {stats.get('staticAvg', 0):.0f} ms, frame avg {stats.get('frameAvg', 0):.1f} ms (software GL, headless)")
        # mobile
        m = await b.new_page(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True, device_scale_factor=2)
        m.on("pageerror", lambda e: errors.append("mobile: " + str(e)))
        await m.goto(URL + "#city=NO-5501", wait_until="networkidle")
        await m.wait_for_timeout(2000)
        vis = await m.evaluate("!document.querySelector('#city-panel').hidden")
        ok("mobile: panel as bottom sheet", vis)
        await b.close()
    ok("no console errors", not errors, "; ".join(errors[:5]))
    failed = [r for r in results if not r[1]]
    print(f"\n{len(results) - len(failed)}/{len(results)} journeys passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
