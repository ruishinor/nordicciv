"""Atlas controls and visual identity on desktop and phone."""
from playwright.async_api import expect

async def run(browser,url,ok,errors,out):
    for mobile in (False,True):
        label=f"{59 if mobile else 58} Atlas layout, map layers and copy"
        ctx=await browser.new_context(viewport={"width":390 if mobile else 1440,"height":900},
                                      is_mobile=mobile,has_touch=mobile,reduced_motion="reduce")
        page=await ctx.new_page()
        page.on("pageerror",lambda error: errors.append(str(error)))
        try:
            await ctx.add_init_script("localStorage.setItem('nc-intro','1')")
            await page.goto(url.split("#")[0],wait_until="domcontentloaded")
            await expect(page.locator("#opening")).to_have_count(0,timeout=15000)
            await page.wait_for_function("() => __app?.mapArt?.model?.wonders?.length > 0")
            mm=page.locator("#btn-minimap")
            await expect(mm).to_be_visible()
            if mobile:
                await mm.click()
            await expect(page.locator("#minimap-wrap")).to_be_visible()
            await mm.click()
            await expect(page.locator("#minimap-wrap")).to_be_hidden()
            await mm.click()
            await expect(page.locator("#minimap-wrap")).to_be_visible()
            await mm.click()
            layers=page.locator("#btn-maplayers-mobile" if mobile else "#btn-maplayers")
            await layers.click()
            wonder=page.locator('[data-toggle="wonders"]')
            await expect(wonder).to_have_attribute("aria-checked","false")
            await wonder.click()
            await expect(wonder).to_have_attribute("aria-checked","true")
            assert await page.evaluate("__app.mapArt.layers.find(l=>l.id==='wonders').visible()")
            await wonder.click()
            assert not await page.evaluate("__app.mapArt.layers.find(l=>l.id==='wonders').visible()")
            await layers.click()
            await page.evaluate("() => __app.selectCity('NO-3205',{fly:false})")
            panel=page.locator("#city-panel")
            await expect(panel).to_be_visible()
            await panel.locator('[data-cptab="Overview"]').click()
            await expect(panel.locator(".standout li b").first).to_be_visible()
            assert await panel.locator(".standout li b").evaluate_all("nodes=>nodes.every(n=>!/^\\p{Ll}/u.test(n.textContent))")
            assert await panel.locator(".ctype").evaluate("e=>getComputedStyle(e).boxShadow==='none' && getComputedStyle(e).backgroundImage==='none'")
            await panel.locator('[data-cptab="Society"]').click()
            await panel.locator(".cp-collapse").click()
            await expect(panel).to_be_hidden()
            restore=page.locator("#btn-inspector")
            await expect(restore).to_be_visible()
            assert await page.evaluate("__app.state.selectedCity.id")=="NO-3205"
            await page.screenshot(path=str(out / f"atlas-{'phone' if mobile else 'desktop'}-collapsed.png"))
            await restore.click()
            await expect(panel).to_be_visible()
            await expect(panel.locator('[data-cptab="Society"]')).to_have_attribute("aria-selected","true")
            await panel.locator('[data-cptab="Overview"]').click()
            await page.screenshot(path=str(out / f"atlas-{'phone' if mobile else 'desktop'}-expanded.png"))
            assert await page.locator('link[rel="icon"]').get_attribute("href")=="logo.svg"
            ok(label,True,"minimap, retained selection/tab, wonders off/on, sentence case, badge and logo")
        except Exception as error:
            ok(label,False,str(error))
        finally:
            await ctx.close()
