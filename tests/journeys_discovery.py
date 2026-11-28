"""Connected Discover journeys on desktop and phone."""
from playwright.async_api import expect


async def run(browser, url, ok, errors):
    for mobile in (False, True):
        ctx = await browser.new_context(viewport={"width": 360 if mobile else 1440, "height": 900},
                                        is_mobile=mobile, has_touch=mobile, reduced_motion="reduce")
        await ctx.add_init_script("localStorage.setItem('nc-intro', '1')")
        page = await ctx.new_page()
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.on("console", lambda message: errors.append(message.text) if message.type == "error" else None)
        label = f"{50 if mobile else 49} Connected discovery journeys, {'phone' if mobile else 'desktop'}"
        try:
            await page.goto(url.split("#")[0], wait_until="domcontentloaded")
            await expect(page.locator("#opening")).to_have_count(0, timeout=15000)
            await page.wait_for_function("window.__app?.explore?.journeys?.length >= 4")
            await page.locator('[data-mnav="discover"]' if mobile else "#btn-discover").click()
            card = page.locator("#discovery")
            await card.get_by_role("button", name="Journeys", exact=True).click()
            await card.get_by_role("button", name="Winter daylight from south to north", exact=False).click()
            await expect(card).to_contain_text("1 of 3")
            await expect(card.get_by_role("button", name="Previous")).to_be_disabled()
            first = await page.evaluate("__app.state.selectedCity.id")
            await card.get_by_role("button", name="Next stop").click()
            await expect(card).to_contain_text("2 of 3")
            second = await page.evaluate("__app.state.selectedCity.id")
            assert first != second
            await page.wait_for_function("new URLSearchParams(location.hash.slice(1)).get('journey') === 'daylight:1'")
            await page.reload(wait_until="domcontentloaded")
            await expect(card).to_contain_text("2 of 3", timeout=15000)
            assert await page.evaluate("__app.state.selectedCity.id") == second
            assert await card.evaluate("(el) => {const r=el.getBoundingClientRect(); return r.left>=0 && r.right<=innerWidth && r.bottom<=innerHeight && el.scrollWidth<=el.clientWidth}")
            await card.get_by_role("button", name="Close", exact=True).click()
            await expect(card).to_be_hidden()
            await page.wait_for_function("!new URLSearchParams(location.hash.slice(1)).has('journey')")
            await page.locator('#city-panel [data-cptab="Overview"]').click()
            link = page.get_by_role("link", name="Satellite imagery (Copernicus)")
            await expect(link).to_have_attribute("target", "_blank")
            assert "datasetId=S2_L2A_CDAS" in await link.get_attribute("href")
            await expect(page.get_by_role("link", name="Find forecast on Yr")).to_have_attribute("href", "https://www.yr.no/en")
            ok(label, True, "next/previous, reload, public links")
        except Exception as error:
            ok(label, False, str(error))
        finally:
            await ctx.close()
