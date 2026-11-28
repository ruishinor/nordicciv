"""NVE pilot flood layer: source scope, map interaction and actual polygon drawing."""
from pathlib import Path
from playwright.async_api import expect


async def run(browser, url, ok, errors):
    ctx = await browser.new_context(viewport={"width":1440,"height":900}, reduced_motion="reduce")
    await ctx.add_init_script("localStorage.setItem('nc-intro','1')")
    page = await ctx.new_page()
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on("console", lambda m: errors.append(m.text) if m.type=="error" else None)
    label = "51 NVE flood pilot: scoped source, default off, real drawn polygons"
    try:
        await page.goto(url.split("#")[0],wait_until="domcontentloaded")
        await page.wait_for_function("() => __app?.nveEnvironment?.groups?.has('flood200')")
        assert await page.evaluate("!__app.nveEnvironment.on['nve-flood200']")
        await page.evaluate("__app.selectCity('NO-0301',{fly:false})")
        section=page.locator("#city-panel .nve-environment")
        await expect(section).to_contain_text("southeast Norway pilot")
        await expect(section).to_contain_text("not a current warning or a property-level map")
        await section.get_by_role("button",name="Show 200-year flood zones").click()
        assert await page.evaluate("__app.nveEnvironment.on['nve-flood200']")
        await page.evaluate("""() => {const a=__app;const f=a.nveEnvironment.groups.get('flood200')[0];
            a.fitBounds(...f.bbox,{maxScale:8,ms:0});}""")
        await page.wait_for_function("() => __app.nveEnvironment.groups.get('flood200').some(f=>f.path instanceof Path2D)")
        out=Path(__file__).parent/"results"
        out.mkdir(exist_ok=True)
        await page.screenshot(path=str(out/"nve-flood-desktop.png"))
        await page.evaluate("__app.ui.setMapToggle('nve-flood200',false)")
        assert await page.evaluate("!__app.nveEnvironment.on['nve-flood200']")
        await page.evaluate("__app.selectCity('SE-0180',{fly:false})")
        await expect(page.locator("#city-panel .nve-environment")).to_have_count(0)
        ok(label,True,"NVE flood polygons drawn; scoped Norway panel; toggle off")
    except Exception as error:
        ok(label,False,str(error))
    finally:
        await ctx.close()
