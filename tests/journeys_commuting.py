"""Domestic commuting in all three countries, desktop and phone."""
from pathlib import Path
from playwright.async_api import expect

async def run(browser,url,ok,errors):
    for mobile in (False, True):
        ctx=await browser.new_context(viewport={"width":390 if mobile else 1440,"height":900},is_mobile=mobile,has_touch=mobile,reduced_motion="reduce")
        await ctx.add_init_script("localStorage.setItem('nc-intro','1')")
        page=await ctx.new_page()
        page.on("pageerror",lambda e:errors.append(str(e)))
        label="52 Commuting: three national sources, directions and partner navigation" + (" phone" if mobile else " desktop")
        try:
            await page.goto(url.split("#")[0],wait_until="domcontentloaded")
            await expect(page.locator("#opening")).to_have_count(0,timeout=15000)
            await page.wait_for_function("() => window.__app?.commuting?.packets.size === 3")
            assert not await page.evaluate("__app.commuting.on")
            for city,partner,number,table in [("NO-3205","NO-0301","19,124","03321"),("SE-0180","SE-0184","40,783","TAB1830"),("DK-147","DK-101","30,649","PEND100")]:
                await page.evaluate("id => __app.selectCity(id,{fly:false})",city)
                section=page.locator("#city-panel .commuting-section")
                await expect(section).to_contain_text("Counts are people, not trips")
                await expect(section).to_contain_text(table)
                await expect(section.locator("ul").first).to_contain_text(number)
                if city=="DK-147":
                    await expect(section).to_contain_text("zero is also the suppression value")
                await section.get_by_role("button",name="Show connections").click()
                assert await page.evaluate("__app.commuting.on")
                await section.locator('[data-commuting-city="'+partner+'"]').first.click()
                assert await page.evaluate("__app.state.selectedCity.id")==partner
                await page.evaluate("__app.ui.setMapToggle('commuting-connections',false)")
                assert not await page.evaluate("__app.commuting.on")
            out=Path(__file__).parent/"results"
            out.mkdir(exist_ok=True)
            await page.screenshot(path=str(out/('commuting-phone.png' if mobile else 'commuting-desktop.png')))
            ok(label,True,"NO/SE/DK observed outgoing counts, source definitions, navigation and map toggle")
        except Exception as error:
            ok(label,False,str(error))
        finally:
            await ctx.close()
