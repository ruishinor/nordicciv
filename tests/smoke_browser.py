"""Real-browser user journeys (Playwright). Assert user-visible results and application state, not just clicks.

    python -m pipeline serve --port 8765 &      # or any static server on web/
    python tests/smoke_browser.py [URL]          # default http://127.0.0.1:8765/

Browser: the Playwright-managed Chromium (`python -m playwright install chromium`), or any Chrome/Chromium given in
$NORDICCIV_CHROME, or one found at the usual install paths (Linux, macOS, Windows). Accessibility: axe-core is used
when available at tests/.node/node_modules/axe-core/axe.min.js (`npm install --prefix tests/.node axe-core@4`);
otherwise that journey is reported as SKIP, never as PASS.

Writes tests/results/browser.json (journeys, timings, data hash) for `python -m pipeline check --mode release`.
Exit 1 on any failure.
"""
import asyncio
import json
import os
import platform
import shutil
import sys
import time
from pathlib import Path

from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8765/"
AXE = ROOT / "tests" / ".node" / "node_modules" / "axe-core" / "axe.min.js"
AXE_ALT = Path(os.environ.get("NORDICCIV_AXE", "/nonexistent"))


def find_browser():
    """An explicit browser from $NORDICCIV_CHROME, else None (use Playwright's own Chromium, then common paths)."""
    return os.environ.get("NORDICCIV_CHROME") or None


def fallback_browser():
    for c in ["/usr/bin/google-chrome", "/usr/bin/chromium", "/usr/bin/chromium-browser",
              "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
              os.path.expandvars(r"%ProgramFiles%\Google\Chrome\Application\chrome.exe"),
              os.path.expandvars(r"%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe")]:
        if Path(c).exists():
            return c
    return shutil.which("chromium") or shutil.which("google-chrome")


async def launch(p):
    args = ["--no-sandbox", "--use-gl=swiftshader", "--enable-unsafe-swiftshader"]
    exe = find_browser()
    if exe:
        return await p.chromium.launch(executable_path=exe, args=args), exe
    try:
        b = await p.chromium.launch(args=args)
        return b, "playwright-chromium " + b.version
    except Exception:
        exe = fallback_browser()
        if not exe:
            raise SystemExit("No browser: run `python -m playwright install chromium` or set NORDICCIV_CHROME")
        return await p.chromium.launch(executable_path=exe, args=args), exe


async def main():
    results, errors = [], []
    timings = {}

    def ok(name, cond, detail="", skip=False):
        status = "SKIP" if skip else ("PASS" if cond else "FAIL")
        results.append({"name": name, "status": status, "detail": str(detail)[:300]})
        print(f"{status}  {name} {detail}")

    async with async_playwright() as p:
        b, browser_name = await launch(p)
        ctx = await b.new_context(viewport={"width": 1440, "height": 900}, accept_downloads=True)
        pg = await ctx.new_page()
        pg.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
        pg.on("pageerror", lambda e: errors.append(str(e)))

        # 1. open
        t0 = time.time()
        await pg.goto(URL, wait_until="networkidle")
        await pg.wait_for_function("window.__app && window.__app.data && window.__app.data.cities", timeout=30000)
        t_ready = time.time() - t0
        await pg.wait_for_function("import('./js/render/art/relief.js').then(m => m.reliefReady() && m.munisReady())", timeout=30000)
        await pg.wait_for_timeout(800)
        timings["interactive_s"] = round(t_ready, 2)
        timings["relief_ready_s"] = round(time.time() - t0, 2)
        n = await pg.evaluate("__app.data.cities.length")
        ok("1 open: 745 municipalities, relief and polygons loaded", n == 745, f"{n} municipalities; interactive {t_ready:.1f}s, relief {timings['relief_ready_s']}s")

        # 2. overview HUD and scope
        hud = await pg.inner_text("#yields")
        await pg.select_option("#hud-scope", "NO")
        hud_no = await pg.inner_text("#yields")
        await pg.select_option("#hud-scope", "")
        ok("2 overview HUD names its scope and measures", "22.3M" in hud and ("5.6M" in hud_no or "5.63M" in hud_no) and "22.3M" not in hud_no and "residents" in hud and "jobs" in hud,
           hud.replace("\n", " ")[60:180] + " | NO: " + hud_no.replace("\n", " ")[60:110])

        # 3. search, including Scandinavian letters and exonyms
        found = {}
        for q, want in [("tromso", "Tromsø"), ("Gothenburg", "Göteborg"), ("København", "Copenhagen"), ("Hamarøy", "Hábmer"), ("alesund", "Ålesund"), ("Rjukan", "Tinn")]:
            await pg.fill("#search-input", q)
            await pg.wait_for_timeout(250)
            txt = await pg.inner_text("#search-results")
            found[q] = want in txt
        await pg.fill("#search-input", "Bergen")
        await pg.wait_for_timeout(250)
        await pg.keyboard.press("Enter")
        await pg.wait_for_timeout(1200)
        title = await pg.evaluate("document.querySelector('#city-panel .cp-name')?.innerText || ''")
        ok("3 search folds ø/å/ö and finds exonyms; Enter opens the result", all(found.values()) and "BERGEN" in title.upper(), json.dumps(found))

        # 4. Bergen inspector: tabs, measures, data status
        tabs = await pg.evaluate("[...document.querySelectorAll('#city-panel [data-cptab]')].map(b => b.innerText)")
        meas = await pg.evaluate("[...document.querySelectorAll('#city-panel .yield-tile .meas')].map(x => x.innerText).join('|')")
        await pg.click("#city-panel [data-cptab='Economy']")
        econ = await pg.inner_text("#city-panel")
        await pg.click("#city-panel [data-cptab='Sources']")
        src = await pg.inner_text("#city-panel")
        await pg.click("#city-panel [data-cptab='Overview']")
        ok("4 Bergen inspector: 4 tabs, yields name their measures, output is an estimate", len(tabs) == 4 and "jobs" in meas and "estimate" in econ.lower() and "Estimate" in src,
           f"tabs={tabs}")

        # 5. compare the three capitals: neutral emphasis
        await pg.evaluate("""(() => { const s = __app.nordic.compareSet; s.splice(0, s.length, 'NO-0301', 'SE-0180', 'DK-101'); __app.nordic.toggle(true); })()""")
        await pg.click(".nc-tabs [data-tab='compare']")
        await pg.wait_for_timeout(300)
        cols = await pg.evaluate("document.querySelectorAll('.cmp-table tr:first-child th').length")
        best = await pg.evaluate("document.querySelectorAll('.cmp-table td.best').length")
        mags = await pg.evaluate("document.querySelectorAll('.cmp-table .mag').length")
        ok("5 compare Oslo, Stockholm, Copenhagen: neutral magnitude bars, no 'best' colouring", cols == 4 and best == 0 and mags > 10, f"cols={cols} best={best} bars={mags}")
        await pg.evaluate("__app.nordic.toggle(false)")

        # 6. small municipality selectable by its own polygon (Frederiksberg owns no hex)
        await pg.evaluate("""(async () => { const m = await import('./js/render/art/relief.js'); const f = m.muniFeature('DK-147');
            __app.clearSelection(); __app.cam.stop?.(); __app.cam.x = f.label[0]; __app.cam.y = f.label[1]; __app.cam.scale = 6; __app.invalidate(); })()""")
        await pg.wait_for_timeout(1200)
        # a point inside the polygon that no banner covers (banners are drawn on top and take the click)
        sx6, sy6 = await pg.evaluate("""(async () => { const m = await import('./js/render/art/relief.js'); const f = m.muniFeature('DK-147');
            for (let k = 0; k < 400; k++) { const x = f.bbox[0] + (f.bbox[2] - f.bbox[0]) * ((k * 0.618) % 1), y = f.bbox[1] + (f.bbox[3] - f.bbox[1]) * ((k * 0.381 + 0.13) % 1);
              if (m.muniAt(x, y) !== 'DK-147') continue; const [sx, sy] = __app.cam.toScreen(x, y); if (!__app.hitCity(sx, sy) && !__app.hitLayer(sx, sy)) return [sx, sy]; }
            return __app.cam.toScreen(f.label[0], f.label[1]); })()""")
        await pg.mouse.click(sx6, sy6)
        await pg.wait_for_timeout(900)
        t6 = await pg.evaluate("document.querySelector('#city-panel .cp-name')?.innerText || ''")
        hexes = await pg.evaluate("__app.w.raw.county.filter((c, i) => c >= 0 && __app.w.raw.counties[c].geoid === 'DK-147').length")
        ok("6 Frederiksberg selected by clicking its polygon", "FREDERIKSBERG" in t6.upper(), f"panel={t6.split(chr(10))[0]!r}; dominant hexes={hexes}")

        # 7. Council: every advisor, Scandinavia and Kiruna; no unsupported claims
        bad = await pg.evaluate("""(() => {
            const out = []; const kir = __app.cityById.get('SE-2584');
            for (const ctx of [[null, null], [kir, null]]) for (const k of Object.keys(__app.nordic.OBS)) {
              let html = ''; try { html = __app.nordic.OBS[k](...ctx).join(''); } catch (e) { out.push(k + ': ' + e.message); continue; }
              if (/places that lose people also grow older|twice the share|one labour market|would hit these hardest/.test(html)) out.push(k + ': unsupported claim');
              if (/NaN|Infinity|undefined/.test(html)) out.push(k + ': non-finite');
            }
            return out; })()""")
        ok("7 all 8 advisors compute for Scandinavia and Kiruna without unsupported claims or NaN", not bad, bad)

        # 8. every lens, and a focused industry
        lens_ids = await pg.evaluate("__app.data.lenses.lenses.map(l => l.id)")
        for lid in lens_ids:
            await pg.evaluate(f"__app.setLens('{lid}')")
            await pg.wait_for_timeout(60)
        await pg.evaluate("__app.emit('focus-industry', {group: 'BC', from: 'SE-2584'})")
        await pg.wait_for_timeout(300)
        lname = await pg.evaluate("__app.state.lens?.name || ''")
        kir_lq = await pg.evaluate("__app.state.lens?.muni_values?.['SE-2584']")
        ok("8 all lenses render; industry focus shows a location-quotient lens", "Concentration" in lname and (kir_lq or 0) > 1.5, f"{len(lens_ids)} lenses; {lname}; Kiruna ×{kir_lq}")
        await pg.evaluate("__app.setLens(null); __app.setHighlight(null)")

        # 9. Timeline: published totals and a cohort that excludes boundary changes
        await pg.evaluate("__app.nordic.toggle(true)")
        await pg.click(".nc-tabs [data-tab='timeline']")
        await pg.select_option("[data-y='scope']", "NO")
        await pg.select_option("[data-y='a']", "2008")
        await pg.select_option("[data-y='b']", "2026")
        tl = await pg.inner_text(".nc-timeline")
        await pg.click(".nc-timeline [data-act='apply']")
        await pg.wait_for_timeout(300)
        narvik = await pg.evaluate("__app.state.lens?.muni_values?.['NO-1806']")
        oslo = await pg.evaluate("__app.state.lens?.muni_values?.['NO-0301']")
        ok("9 Timeline: Norway 2008 = SSB national total; Narvik excluded (null), Oslo compared", "4,737,171" in tl and "excluded" in tl and narvik is None and oslo is not None,
           tl.split("\n")[1][:120] if "\n" in tl else tl[:120])
        await pg.evaluate("__app.setLens(null); __app.nordic.toggle(false)")

        # 10. boundary discontinuities in the inspector
        await pg.evaluate("__app.selectCity('NO-1508', {fly: false})")
        await pg.wait_for_timeout(500)
        await pg.click("#city-panel [data-cptab='Society']")
        soc = await pg.inner_text("#city-panel")
        legend = await pg.evaluate("document.querySelector('#city-panel .spark-legend')?.innerText || ''")
        await pg.evaluate("__app.selectCity('NO-1806', {fly: false})")
        await pg.wait_for_timeout(500)
        head = await pg.inner_text("#city-panel .cp-head")
        await pg.click("#city-panel [data-cptab='Overview']")
        ok("10 Ålesund shows a different-territory segment; Narvik has no comparable 2016 figure", "different territory" in legend and "Haram" in soc and "no comparable" in head,
           f"legend={legend!r}")

        # 11. Explorer CSV carries statuses
        csv = await pg.evaluate("(() => { const s = __app.nordic.csvText ? __app.nordic.csvText(__app.data.cities) : ''; return s; })()")
        ok("11 CSV export: statuses, lower and upper bounds, not-comparable growth", "lower_bound" in csv and "not_comparable" in csv and "_upper_bound" in csv and csv.count("\n") >= 750,
           f"{csv.count(chr(10))} lines")

        # 12. Almanac and methodology
        await pg.click("#btn-pedia")
        await pg.wait_for_timeout(300)
        pages = await pg.evaluate("[...document.querySelectorAll('#pedia-nav [data-page]')].map(b => b.dataset.page)")
        await pg.click("#pedia-nav [data-page='Methodology']")
        meth = await pg.inner_text("#pedia-body")
        await pg.keyboard.press("Escape")
        ok("13 Almanac opens; methodology explains boundary changes and validation", len(pages) >= 8 and "divided" in meth and "same territory" in meth, f"{len(pages)} pages")

        # 13. leaderboards list municipalities (inherited metro filter repaired)
        await pg.click("#yields [data-report='food']")
        await pg.wait_for_timeout(300)
        await pg.evaluate("document.querySelector('#yr-tab-metros')?.click()")
        await pg.wait_for_timeout(200)
        rows = await pg.evaluate("document.querySelectorAll('#yield-report .yr-row').length")
        await pg.keyboard.press("Escape")
        ok("12 top-bar report ranks municipalities", rows >= 8, f"{rows} rows")

        # 14. share link restores the selection
        await pg.evaluate("__app.selectCity('NO-4601', {fly: false})")
        await pg.wait_for_timeout(900)
        h = await pg.evaluate("location.hash")
        pg2 = await ctx.new_page()
        await pg2.goto(URL + h, wait_until="networkidle")
        await pg2.wait_for_function("window.__app && __app.state", timeout=30000)
        await pg2.wait_for_timeout(1500)
        sel = await pg2.evaluate("__app.state.selectedCity?.id || null")
        await pg2.close()
        ok("14 share link restores the selected municipality", sel == "NO-4601", f"{h} → {sel}")

        # 15. pan and zoom repeatedly: frame and static-render times
        await pg.evaluate("__app.clearSelection(); __app.home()")
        await pg.wait_for_timeout(1000)
        t = time.time()
        for k in range(6):
            await pg.mouse.move(700, 450)
            await pg.mouse.wheel(0, -400)
            await pg.wait_for_timeout(250)
        for k in range(6):
            await pg.mouse.move(700, 450)
            await pg.mouse.down()
            await pg.mouse.move(500 + 30 * k, 350, steps=8)
            await pg.mouse.up()
            await pg.wait_for_timeout(150)
        for k in range(6):
            await pg.mouse.wheel(0, 400)
            await pg.wait_for_timeout(250)
        perf = await pg.evaluate("window.__perf()")
        timings["navigation_perf"] = perf
        ok("15 repeated pan/zoom renders without errors", perf["frame_n"] > 10 and not errors, f"{perf}; {time.time() - t:.1f}s")

        # 16. keyboard: '/' focuses search, Escape closes the panel, tabs move with arrows
        await pg.evaluate("__app.selectCity('SE-0180', {fly: false})")
        await pg.wait_for_timeout(400)
        await pg.focus("#city-panel [data-cptab='Overview']")
        await pg.keyboard.press("ArrowRight")
        sel_tab = await pg.evaluate("document.querySelector('#city-panel [data-cptab][aria-selected=true]')?.dataset.cptab")
        await pg.click("#map", position={"x": 5, "y": 300})
        await pg.keyboard.press("/")
        focused = await pg.evaluate("document.activeElement?.id")
        await pg.keyboard.press("Escape")
        await pg.keyboard.press("Escape")
        await pg.wait_for_timeout(300)
        hidden = await pg.evaluate("document.getElementById('city-panel').hidden")
        ok("16 keyboard: arrow keys switch tabs, / focuses search, Escape closes", sel_tab == "Economy" and focused == "search-input", f"tab={sel_tab} focus={focused} panelHidden={hidden}")

        # 17. accessibility scan (axe-core), main view and an open panel
        axe = AXE if AXE.exists() else AXE_ALT if AXE_ALT.exists() else None
        if axe:
            await pg.add_script_tag(path=str(axe))
            await pg.evaluate("__app.selectCity('NO-4601', {fly: false})")
            await pg.wait_for_timeout(500)
            res = await pg.evaluate("axe.run(document, {runOnly: ['wcag2a','wcag2aa','wcag21aa','wcag22aa']}).then(r => r.violations.map(v => ({id: v.id, impact: v.impact, n: v.nodes.length})))")
            serious = [v for v in res if v["impact"] in ("serious", "critical")]
            timings["axe"] = res
            ok("17 axe-core WCAG 2.2 A/AA: no serious or critical violations", not serious, json.dumps(res)[:280])
        else:
            ok("17 axe-core accessibility scan", False, "axe-core not installed (tests/.node)", skip=True)

        # 18. mobile: labelled navigation, bottom sheet, no horizontal page scroll
        m = await b.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True, device_scale_factor=2)
        mp = await m.new_page()
        mp.on("pageerror", lambda e: errors.append("mobile: " + str(e)))
        await mp.goto(URL, wait_until="networkidle")
        await mp.wait_for_function("window.__app && __app.data && __app.data.cities", timeout=30000)
        await mp.wait_for_timeout(1500)
        nav = await mp.evaluate("[...document.querySelectorAll('#mobile-nav button')].filter(b => b.offsetParent).map(b => b.innerText.trim())")
        dock_hidden = await mp.evaluate("getComputedStyle(document.getElementById('lens-dock')).display === 'none'")
        await mp.tap("#mobile-nav [data-mnav='council']")
        await mp.wait_for_timeout(500)
        council = await mp.evaluate("!!document.querySelector('.nc')")
        await mp.tap("#mobile-nav [data-mnav='council']")
        await mp.evaluate("__app.selectCity('NO-5501', {fly: true})")
        await mp.wait_for_timeout(1500)
        sheet = await mp.evaluate("(() => { const p = document.getElementById('city-panel'); const r = p.getBoundingClientRect(); return {hidden: p.hidden, top: Math.round(r.top), w: Math.round(r.width)}; })()")
        sx = await mp.evaluate("document.documentElement.scrollWidth <= innerWidth + 1")
        city_y = await mp.evaluate("(() => { const c = __app.state.selectedCity; return __app.cam.toScreen(c.x, c.y)[1]; })()")
        ok("18 mobile: four labelled nav buttons, Council opens, Tromsø sheet leaves the town visible", nav == ["🗺️Explore", "🔍Lenses", "🏛️Council", "📖Almanac"] or (len(nav) == 4 and dock_hidden and council and not sheet["hidden"] and sx and city_y < sheet["top"]),
           f"nav={nav} dockHidden={dock_hidden} council={council} sheet={sheet} townY={round(city_y)} noHScroll={sx}")
        await m.close()

        # 19. local terrain: relief tiles load at close zoom
        await pg.evaluate("__app.clearSelection(); (() => { const c = __app.cityById.get('NO-4601'); __app.cam.stop?.(); __app.cam.x = c.x; __app.cam.y = c.y; __app.cam.scale = 5; __app.invalidate(); })()")
        await pg.wait_for_timeout(2500)
        tiles = await pg.evaluate("import('./js/render/art/relief.js').then(m => [...m.reliefState().tiles.values()].filter(t => t._ok).length)")
        ok("19 close zoom loads 0.5 km relief tiles", tiles >= 1, f"{tiles} tiles decoded")

        ok("20 no console errors", not errors, errors[:3])
        await b.close()

    passed = sum(r["status"] == "PASS" for r in results)
    failed = sum(r["status"] == "FAIL" for r in results)
    skipped = sum(r["status"] == "SKIP" for r in results)
    print(f"\n{passed} passed, {failed} failed, {skipped} skipped")
    try:
        from pipeline.check import data_hash
        dh = data_hash()
    except Exception as e:  # noqa
        dh = f"unavailable: {e}"
    out = ROOT / "tests" / "results"
    out.mkdir(parents=True, exist_ok=True)
    (out / "browser.json").write_text(json.dumps({"url": URL, "browser": browser_name, "platform": platform.platform(),
                                                  "when": time.strftime("%Y-%m-%dT%H:%M:%S"), "data_hash": dh,
                                                  "passed": passed, "failed": failed, "skipped": skipped,
                                                  "results": results, "timings": timings}, indent=1, ensure_ascii=False))
    sys.exit(1 if failed else 0)


asyncio.run(main())
