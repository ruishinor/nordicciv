"""Environmental history in the Council and regional panel."""
from pathlib import Path
from playwright.async_api import expect


async def run(browser, url, ok, errors):
    ctx = await browser.new_context(viewport={"width": 1440, "height": 900}, reduced_motion="reduce")
    await ctx.add_init_script("localStorage.setItem('nc-intro', '1')")
    page = await ctx.new_page()
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.on("console", lambda message: errors.append(message.text) if message.type == "error" else None)
    label = "48 Environmental history: observed years, regional scope and official hazard links"
    try:
        await page.goto(url.split("#")[0], wait_until="domcontentloaded")
        await expect(page.locator("#opening")).to_have_count(0, timeout=15000)
        await page.locator("#council").click()
        await page.locator('[data-adv="environment"]').click()
        await expect(page.locator(".nc .environment-history")).to_contain_text("486 km²")
        await expect(page.locator(".nc .environment-hazards")).to_contain_text("not current warnings")
        await page.get_by_role("tab", name="Timeline").click()
        await page.locator('[data-y="scope"]').select_option("NO-56")
        history = page.locator(".nc .environment-history")
        await expect(history).to_contain_text("Nordmannsjøkelen")
        await expect(history).to_contain_text("1970: 4.8 km²")
        await expect(history).not_to_contain_text("Jostedalsbreen")
        await page.locator('[data-y="scope"]').select_option("SE")
        await expect(history).to_have_count(0)
        await page.get_by_role("button", name="Show new built-up land").click()
        assert await page.evaluate("__app.state.lens?.id === 'urban_growth' || __app.state.lens === 'urban_growth'")
        await page.get_by_role("button", name="Forest cover change 1990–2018").click()
        assert await page.evaluate("__app.state.lens?.id === 'forest_change'")
        await page.get_by_role("button", name="Agricultural land change 1990–2018").click()
        assert await page.evaluate("__app.state.lens?.id === 'agriculture_change'")
        await page.get_by_role("tab", name="Advisors").click()
        await page.locator('[data-adv="environment"]').click()
        await expect(page.locator(".nc")).to_contain_text("one-kilometre cells across")
        await expect(page.locator(".nc")).to_contain_text("km² gained")
        out = Path(__file__).parent / "results"
        out.mkdir(exist_ok=True)
        await page.screenshot(path=str(out / "corine-environment-desktop.png"))
        await page.get_by_role("button", name="Close the council").click()
        await page.evaluate("__app.selectState('NO-46', {fly: false})")
        await expect(page.locator("#city-panel .environment-history")).to_contain_text("Jostedalsbreen")
        ok(label, True, "NVE observations and CORINE lens")
    except Exception as error:
        ok(label, False, str(error))
    finally:
        await ctx.close()
