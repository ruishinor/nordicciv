"""Norwegian commuter partner panel, real SSB fixture and map connections."""
from pathlib import Path
from playwright.async_api import expect


async def run(browser,url,ok,errors):
    ctx=await browser.new_context(viewport={"width":1440,"height":900},reduced_motion="reduce")
    await ctx.add_init_script("localStorage.setItem('nc-intro','1')")
    page=await ctx.new_page()
    page.on("pageerror",lambda e:errors.append(str(e)))
    page.on("console",lambda m:errors.append(m.text) if m.type=="error" else None)
    label="52 Commuting: SSB direction, actual counts, map toggle and partner navigation"
    try:
        await page.goto(url.split("#")[0],wait_until="domcontentloaded")
        await page.wait_for_function("() => !!__app?.commuting")
        assert not await page.evaluate("__app.commuting.on")
        await page.evaluate("__app.selectCity('NO-3205',{fly:false})")
        section=page.locator("#city-panel .commuting-section")
        await expect(section).to_contain_text("Counts are people, not trips")
        await expect(section.locator("ul").first).to_contain_text("19,124")
        await expect(section.locator("ul").last).to_contain_text("6,058")
        assert await page.evaluate("""() => {const p=__app.commuting.index.get('NO-3205');return p.outgoing[0].id==='NO-0301'&&p.incoming[0].id==='NO-0301'}""")
        await section.get_by_role("button",name="Show connections").click()
        assert await page.evaluate("__app.commuting.on")
        await page.wait_for_timeout(850)
        out=Path(__file__).parent/"results"
        out.mkdir(exist_ok=True)
        await page.screenshot(path=str(out/"commuting-desktop.png"))
        await section.locator("ul").first.get_by_role("button",name="Oslo",exact=True).click()
        assert await page.evaluate("__app.state.selectedCity.id === 'NO-0301'")
        await page.evaluate("__app.ui.setMapToggle('commuting-connections',false)")
        assert not await page.evaluate("__app.commuting.on")
        await page.evaluate("__app.selectCity('SE-0180',{fly:false})")
        await expect(page.locator("#city-panel .commuting-section")).to_have_count(0)
        ok(label,True,"Lillestrøm↔Oslo counts, selected municipality navigation, toggle")
    except Exception as error:
        ok(label,False,str(error))
    finally:
        await ctx.close()
