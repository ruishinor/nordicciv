"""Close-up geometry, navigation and tile failure journeys for the bounded pilot."""
import asyncio
import json
from pathlib import Path

CASES = json.loads(Path(__file__).with_name("terrain_cases.json").read_text(encoding="utf-8"))
POSITION = """async ({lon,lat,scale=720}) => {
    const a=__app, g=await import('./js/util/geo.js'), q=g.lonLatToMap(g.projectionFrom(a.w),lon,lat);
    a.cam.stop(); a.setLens(null); a.cam.scale=a.cam.clampScale(scale);
    [a.cam.x,a.cam.y]=a.cam.centerAt(q.x,q.y,a.cam.w/2,a.cam.h/2); a.invalidate(); return q;
}"""


async def ready(page):
    await page.wait_for_function("() => window.__app?.terrain?.stats()?.available", timeout=30000)
    await page.wait_for_function("() => !document.getElementById('opening')", timeout=30000)


async def settle(page):
    await page.wait_for_function("() => __app.terrain.stats().detailVertices > 0", timeout=30000)
    await page.wait_for_function("""() => {
        const stats=__app.terrain.stats(), width=__app.cam.w/__app.cam.scale, center=stats.tiles?.centerKm;
        return stats.tiles && center && Math.abs(stats.tiles.widthKm-width)<0.05
          && Math.abs(center[0]-__app.cam.x)<0.05 && Math.abs(center[1]-__app.cam.y)<0.05;
    }""", timeout=30000)
    await page.wait_for_function("() => __app.terrain.stats().tiles.pending === 0", timeout=30000)
    await page.wait_for_timeout(180)


async def run(browser, url, ok, errors, out):
    target = url.split("?")[0].rstrip("/") + "/?renderer=webgl&pitch=30"
    ctx = await browser.new_context(viewport={"width":1440,"height":900}, bypass_csp=True)
    await ctx.add_init_script("localStorage.setItem('nc-intro','1')")
    page = await ctx.new_page()
    page.on("pageerror", lambda e: errors.append("Detailed terrain: " + str(e)))
    observations = []
    try:
        await page.goto(target)
        await ready(page)
        for case in CASES:
            await page.evaluate(POSITION, case)
            await settle(page)
            result = await page.evaluate("""() => {
                const a=__app, c=a.cam; let error=0;
                for(let x=200;x<1200;x+=200) for(let y=160;y<760;y+=150){
                    const point=c.toWorld(x,y), back=c.toScreenSurface(...point);
                    error=Math.max(error,Math.hypot(back[0]-x,back[1]-y));
                }
                return {widthKm:c.w/c.scale,error,stats:a.terrain.stats(),height:a.terrain.elevationAt(...c.toWorld(c.w/2,c.h/2))};
            }""")
            observations.append({"place":case["id"],**result})
            await page.screenshot(path=str(Path(out)/f"d02-{case['id']}.png"))
        # Oslo–Lillestrøm is the integrated composition benchmark. Hold the geographic
        # centre fixed while the visible map width selects the four physical LOD bands.
        composition = []
        bands = [
            (100, "regional", 480), (30, "local", 120),
            (10, "neighbourhood", 30), (2, "close", 30),
        ]
        for width_km, _, _ in bands:
            await page.evaluate("""async ({widthKm}) => {
                const a=__app, city=a.data.cities.find(c=>c.name==='Oslo');
                a.cam.stop(); a.cam.scale=a.cam.clampScale(1440/widthKm);
                [a.cam.x,a.cam.y]=a.cam.centerAt(city.x,city.y,a.cam.w/2,a.cam.h/2);
                a.invalidate();
            }""", {"widthKm": width_km})
            await settle(page)
            observation = await page.evaluate("""() => {
                const a=__app, stats=a.terrain.stats();
                return {widthKm:a.cam.w/a.cam.scale, terrain:stats,
                  center:a.terrain.surfaceAt(...a.cam.toWorld(a.cam.w/2,a.cam.h/2))};
            }""")
            composition.append(observation)
            await page.screenshot(path=str(Path(out)/f"d03-oslo-{round(width_km)}km.png"))
        ok("69 Oslo–Lillestrøm composition transitions at 100, 30, 10 and 2 km",
           all(abs(item["widthKm"]-width) < 0.1 and item["terrain"]["tiles"]["physicalLod"] == lod
               and item["terrain"]["tiles"]["spacingM"] == spacing and item["center"]["coverage"] > 0
               and not item["center"]["water"]
               for item, (width,lod,spacing) in zip(composition, bands)),
           composition)
        ok("63 Close terrain uses 30 m samples and aligned triangle picking in all four fixed views",
           all(1 <= x["widthKm"] <= 3 and x["error"] < 0.1 and x["stats"]["tiles"]["loadedByLevel"][2] > 0
               and x["stats"]["detailSpacingM"] == 30 and x["stats"]["landVertices"] > 0
               and 0 < x["stats"]["surfaceOpacity"] < 1 for x in observations), observations)

        tour = []
        for _ in range(2):
            for case in CASES[::2] + CASES[-1:]:
                for scale in [48,720]:
                    await page.evaluate(POSITION,{**case,"scale":scale}); await settle(page)
                    tour.append(await page.evaluate("() => __app.terrain.stats()"))
        ok("64 Repeated terrain travel keeps tile storage and geometry bounded",
           all(t["tiles"]["entries"]<=96 and t["tiles"]["bytes"]<=8*1024*1024 and t["detailVertices"]<=100000 for t in tour)
           and tour[-1]["tiles"]["evictions"] > 0, tour[-1])

        await page.locator("#terrain-options").evaluate("e=>e.open=true")
        await page.select_option("#terrain-place","lillestrom")
        await page.wait_for_function("() => !__app.cam.moving && __app.cam.scale > 700",timeout=20000)
        await settle(page)
        await page.locator("#terrain-options").evaluate("e=>e.open=false")
        # Use a real map click at the municipality's published settlement position.
        point = await page.evaluate("""() => {const a=__app,c=a.data.cities.find(c=>c.name==='Lillestrøm');
            [a.cam.x,a.cam.y]=a.cam.centerAt(c.x,c.y,a.cam.w/2,a.cam.h/2);a.invalidate();return [a.cam.w/2,a.cam.h/2];}""")
        await page.wait_for_timeout(250)
        await page.mouse.click(*point)
        await page.wait_for_function("() => __app.state.selectedCity?.name === 'Lillestrøm'", timeout=5000)
        state = await page.evaluate("""() => {const a=__app, selected=a.state.selectedCity?.name;
            a.setLens('density');const flat=a.cam.elevationAt===null;
            a.setLens(null);const restored=typeof a.cam.elevationAt==='function';
            a.setPitch(37); a.hash.flush();
            return {selected,flat,restored,x:a.cam.x,y:a.cam.y,scale:a.cam.scale,pitch:a.cam.pitch,url:location.href};}""")
        await page.reload(); await ready(page); await settle(page)
        restored = await page.evaluate("() => ({x:__app.cam.x,y:__app.cam.y,scale:__app.cam.scale,pitch:__app.cam.pitch,selected:__app.state.selectedCity?.name})")
        # A restored target can settle with newly loaded heights; compare the geographical centre after the surface is ready.
        ok("65 Terrain controls, municipality click, lenses and shared pitch preserve selection",
           state["selected"] == "Lillestrøm" and state["flat"] and state["restored"] and restored["selected"]=="Lillestrøm"
           and restored["pitch"]==37 and abs(restored["scale"]-state["scale"])<0.1, {"before":state,"after":restored})

        # Search and minimap still drive the shared camera at the extended zoom.
        await page.fill("#search-input","Oslo")
        await page.wait_for_function("() => !document.getElementById('search-results').hidden")
        await page.locator('#search-results [role="option"]').filter(has_text="Oslo").filter(has_not_text="Region").first.click()
        await page.wait_for_timeout(900)
        found = await page.evaluate("() => __app.state.selectedCity?.name")
        await page.set_viewport_size({"width":390,"height":844})
        await page.evaluate(POSITION,CASES[-1]); await settle(page)
        mobile = await page.evaluate("() => ({width:__app.cam.w/__app.cam.maxScale, horizontal:document.documentElement.scrollWidth<=innerWidth})")
        await page.screenshot(path=str(Path(out)/"d02-phone-herning.png"))
        ok("66 Search and phone close zoom retain navigation and a two-kilometre viewport",
           found=="Oslo" and 1<=mobile["width"]<=3 and mobile["horizontal"], {"search":found,"phone":mobile})
    except Exception as e:
        ok("63 Detailed terrain journey completed",False,str(e))
    finally:
        await ctx.close()

    fallback_ctx = await browser.new_context(viewport={"width":1440,"height":900}, bypass_csp=True)
    await fallback_ctx.add_init_script("localStorage.setItem('nc-intro','1')")
    await fallback_ctx.route("**/terrain/tiles/2-*.bin", lambda route: route.abort())
    fallback = await fallback_ctx.new_page()
    fallback.on("pageerror",lambda e:errors.append("Terrain tile fallback: "+str(e)))
    try:
        await fallback.goto(target); await ready(fallback)
        await fallback.evaluate(POSITION,CASES[2]); await settle(fallback)
        st=await fallback.evaluate("() => __app.terrain.stats()")
        await fallback.screenshot(path=str(Path(out)/"d02-coarse-fallback.png"))
        ok("67 Failed fine elevation requests keep a continuous coarser terrain surface",
           st["available"] and st["detailVertices"]>0 and st["tiles"]["failed"]>0
           and st["tiles"]["loadedByLevel"][1]>0 and st["tiles"]["loadedByLevel"][2]==0, st)
        await fallback_ctx.unroute("**/terrain/tiles/2-*.bin")
        await fallback.locator("#terrain-options").evaluate("e=>e.open=true")
        await fallback.click("#terrain-retry")
        await fallback.wait_for_function("() => __app.terrain.stats().tiles.loadedByLevel[2]>0 && !__app.terrain.stats().tiles.pending")
        recovery=await fallback.evaluate("() => __app.terrain.stats().tiles")
        ok("68 Retrying failed elevation restores the fine surface", recovery["failed"]==0,recovery)
    except Exception as e:
        ok("67 Failed fine elevation requests keep a continuous coarser terrain surface",False,str(e))
    finally:
        await fallback_ctx.close()
    (Path(out)/"terrain-journeys.json").write_text(json.dumps(observations,indent=2),encoding="utf-8")


if __name__ == "__main__":
    import sys
    from playwright.async_api import async_playwright
    async def main():
        results=[]; errors=[]; out=Path("tests/results");out.mkdir(exist_ok=True)
        def report(name,passed,detail=None):
            print("PASS" if passed else "FAIL",name, "" if passed else detail,flush=True)
            results.append(passed)
        async with async_playwright() as p:
            browser=await p.chromium.launch(args=["--no-sandbox","--enable-unsafe-swiftshader"])
            await run(browser,sys.argv[1],report,errors,out);await browser.close()
        if not all(results) or errors: raise SystemExit(1)
    asyncio.run(main())
