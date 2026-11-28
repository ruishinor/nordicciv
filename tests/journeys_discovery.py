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
            await page.wait_for_function("() => window.__app?.explore?.journeys?.length >= 4")
            initial = await page.evaluate("__app.state.selectedCity?.id ?? null")
            discover = page.locator('[data-mnav="discover"]' if mobile else "#btn-discover")
            await discover.click()
            card = page.locator("#discovery")
            await expect(card.get_by_role("heading", name="Discover Scandinavia")).to_be_visible()
            assert await page.evaluate("__app.state.selectedCity?.id ?? null") == initial
            preview = card.get_by_role("button", name="Winter daylight from south to north", exact=False)
            names = await page.evaluate("""__app.explore.journeys.find(j => j.id === 'daylight').stops.map(s => __app.cityById.get(s.city).name)""")
            for name in names:
                await expect(preview).to_contain_text(name)
            for jid in ("commuting-no", "commuting-se", "commuting-dk", "transport-aviation", "transport-ferry", "oresund-commuting"):
                await expect(card.locator(f'[data-journey="{jid}"]')).to_be_visible()
            await page.wait_for_function("() => __app.transport?.packet && __app.commuting?.packets.size === 3")
            for jid, category, commuting in (
                    ("commuting-no", None, True),
                    ("commuting-se", None, True),
                    ("commuting-dk", None, True),
                    ("transport-aviation", "aviation", False),
                    ("transport-ferry", "ferry", False),
                    ("oresund-commuting", None, False)):
                await card.locator(f'[data-journey="{jid}"]').click()
                await expect(card).to_contain_text("1 of 2")
                assert await page.evaluate("__app.commuting.on") == commuting
                assert await page.evaluate("__app.transport.on") == bool(category)
                if category:
                    assert await page.evaluate("__app.transport.category") == category
                    assert await page.evaluate("c => __app.transport.mapped().every(f => f.category === c)", category)
                expected = await page.evaluate("id => __app.explore.journeys.find(j=>j.id===id).stops[1].city", jid)
                await card.get_by_role("button", name="Next stop").click()
                await expect(card).to_contain_text("2 of 2")
                assert await page.evaluate("__app.state.selectedCity.id") == expected
                if jid == "transport-ferry":
                    await page.wait_for_function("() => new URLSearchParams(location.hash.slice(1)).get('journey') === 'transport-ferry:1' && new URLSearchParams(location.hash.slice(1)).get('transport-category') === 'ferry'")
                    await page.reload(wait_until="domcontentloaded")
                    await expect(card).to_contain_text("2 of 2", timeout=15000)
                    await page.wait_for_function("() => __app.transport?.on && __app.transport.category === 'ferry'")
                await card.get_by_role("button", name="Journeys", exact=True).click()
            await preview.click()
            await expect(card).to_contain_text("1 of 3")
            await expect(card.get_by_role("button", name="Previous")).to_be_disabled()
            first = await page.evaluate("__app.state.selectedCity.id")
            await card.get_by_role("button", name="Next stop").click()
            await expect(card).to_contain_text("2 of 3")
            second = await page.evaluate("__app.state.selectedCity.id")
            assert first != second
            await page.wait_for_function("() => new URLSearchParams(location.hash.slice(1)).get('journey') === 'daylight:1'")
            await page.reload(wait_until="domcontentloaded")
            await expect(card).to_contain_text("2 of 3", timeout=15000)
            assert await page.evaluate("__app.state.selectedCity.id") == second
            await expect(card.locator('[data-journey-stop="1"]')).to_have_attribute("aria-current", "step")
            await card.locator('[data-journey-stop="2"]').click()
            await expect(card).to_contain_text("3 of 3")
            await expect(card.locator('[data-journey-stop="2"]')).to_be_disabled()
            await card.get_by_role("button", name="Previous").click()
            await expect(card).to_contain_text("2 of 3")
            assert await page.evaluate("__app.state.selectedCity.id") == second
            assert await card.evaluate("(el) => {const r=el.getBoundingClientRect(); return r.left>=0 && r.right<=innerWidth && r.bottom<=innerHeight && el.scrollWidth<=el.clientWidth}")
            await card.get_by_role("button", name="Close", exact=True).click()
            await expect(card).to_be_hidden()
            await page.wait_for_function("() => !new URLSearchParams(location.hash.slice(1)).has('journey')")
            await page.locator('#city-panel [data-cptab="Overview"]').click()
            related = page.locator('#city-panel [data-discover-journey="daylight:1"]')
            await expect(related).to_be_visible()
            await related.click()
            await expect(card).to_contain_text("2 of 3")
            assert await page.evaluate("__app.state.selectedCity.id") == second
            await card.get_by_role("button", name="Journeys", exact=True).click()
            await card.get_by_role("button", name="Surprise me").click()
            await expect(card.get_by_role("button", name="Another ›")).to_be_visible()
            await card.get_by_role("button", name="Close", exact=True).click()
            await page.evaluate("(id) => __app.selectCity(__app.cityById.get(id), {fly:false})", second)
            await page.locator('#city-panel [data-cptab="Overview"]').click()
            link = page.get_by_role("link", name="Satellite imagery (Copernicus)")
            await expect(link).to_have_attribute("target", "_blank")
            assert "datasetId=S2_L2A_CDAS" in await link.get_attribute("href")
            await expect(page.get_by_role("link", name="Find forecast on Yr")).to_have_attribute("href", "https://www.yr.no/en")
            save = page.locator("#city-panel [data-save-city]")
            await save.click()
            await expect(save).to_have_attribute("aria-pressed", "true")
            await page.reload(wait_until="domcontentloaded")
            await expect(page.locator("#opening")).to_have_count(0, timeout=15000)
            await page.wait_for_function("() => !!window.__app?.explore")
            await page.evaluate("__app.clearSelection()")
            await discover.click()
            await card.get_by_role("button", name="Saved places (1)").click()
            saved = card.locator("[data-place-open]")
            await expect(saved).to_have_attribute("data-place-open", second)
            await saved.click()
            assert await page.evaluate("__app.state.selectedCity.id") == second
            if mobile:
                await page.locator("#city-panel .cp-close").click()
            await discover.click()
            await card.get_by_role("button", name="Recent places", exact=False).click()
            await expect(card.locator("[data-place-open]").first).to_have_attribute("data-place-open", second)
            await card.get_by_role("button", name="Clear recent places").click()
            await expect(card).to_contain_text("No places yet.")
            await card.get_by_role("button", name="Back", exact=True).click()
            await card.get_by_role("button", name="Saved places (1)").click()
            await card.locator("[data-place-remove]").click()
            await expect(card).to_contain_text("No places yet.")
            await card.get_by_role("button", name="Close", exact=True).click()
            await page.evaluate("id => __app.selectCity(id, {fly:false})", second)
            await expect(page.locator("#city-panel [data-save-city]")).to_have_attribute("aria-pressed", "false")
            ok(label, True, "journeys, public links, saved places across reload, recent places and removal")
        except Exception as error:
            ok(label, False, str(error))
        finally:
            await ctx.close()
