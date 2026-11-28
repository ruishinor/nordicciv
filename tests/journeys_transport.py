"""Transport observations and filters in desktop and phone municipality panels."""
from playwright.async_api import expect


async def run(browser, url, ok, errors):
    for mobile in (False, True):
        ctx = await browser.new_context(viewport={"width": 390 if mobile else 1440, "height": 900},
                                        is_mobile=mobile, has_touch=mobile, reduced_motion="reduce")
        await ctx.add_init_script("localStorage.setItem('nc-intro','1')")
        page = await ctx.new_page()
        page.on("pageerror", lambda e: errors.append(str(e)))
        label = f"{57 if mobile else 56} Transport: directions, units and category filters" + (" phone" if mobile else " desktop")
        try:
            await page.goto(url.split("#")[0], wait_until="domcontentloaded")
            await expect(page.locator("#opening")).to_have_count(0, timeout=15000)
            await page.wait_for_function("() => window.__app?.transport?.packet?.flows.length === 40")
            assert not await page.evaluate("__app.transport.on")
            await page.evaluate("() => __app.selectCity('DK-185',{fly:false})")
            section = page.locator("#city-panel .transport-section")
            await expect(section).to_contain_text("1,146,000")
            await expect(section).to_contain_text("1,127,000")
            await expect(section).to_contain_text("no map line")
            assert await page.evaluate("() => __app.transport.mapped().every(f => f.table !== 'FLYV34' && !f.id.startsWith('SKIB31:10205:'))")
            await section.locator("select").select_option("freight")
            await expect(section.locator("li:visible")).to_have_count(0)
            await expect(section.locator("[data-transport-empty]")).to_be_visible()
            await page.evaluate("() => __app.selectCity('DK-217',{fly:false})")
            await expect(section.locator("li:visible")).to_contain_text("4,890,000")
            await expect(section.locator("li:visible")).to_contain_text("tonnes")
            await section.locator("select").select_option("ferry")
            await expect(section.locator("li:visible")).to_contain_text("6,419,000")
            await expect(section.locator("li:visible")).to_contain_text("both directions")
            await section.get_by_role("button", name="Show transport connections").click()
            assert await page.evaluate("__app.transport.on")
            assert await page.evaluate("() => __app.transport.mapped().every(f => f.category === 'ferry')")
            await section.locator('li:visible [data-transport-city="SE-1283"]').click()
            assert await page.evaluate("__app.state.selectedCity.id") == "SE-1283"
            ok(label, True, "Published aviation and ferry values, no fabricated airport routes, category filtering and navigation")
        except Exception as error:
            ok(label, False, str(error))
        finally:
            await ctx.close()
