"""Climate stations in the existing municipality, region, council and map views."""
from playwright.async_api import expect


async def journey(page, url, mobile=False):
    await page.goto(url + "#city=DK-101", wait_until="domcontentloaded")
    panel = page.locator("#city-panel")
    profile = panel.locator(".climate-local")
    await expect(profile).to_be_visible(timeout=15000)
    await expect(profile).to_contain_text("Sjælsmark · 24 km from København")
    await expect(profile).to_contain_text("Landbohøjskolen · 2 km from København")
    await expect(profile).to_contain_text("661.9 mm")
    precipitation = profile.locator(".climate-profile").filter(has_text="Landbohøjskolen")
    await precipitation.get_by_text("Month by month").click()
    await expect(precipitation.get_by_role("row", name="Jan 54.1")).to_be_visible()
    await expect(precipitation.get_by_role("link", name="Station data from DMI")).to_have_attribute(
        "href", "https://www.ncei.noaa.gov/data/oceans/archive/arc0216/0253808/6.6/data/0-data/Region-6-WMO-Normals-9120/Denmark/CSV/LANDBOHYJSKOLEN_06186.csv")
    await profile.get_by_role("button", name="Show Landbohøjskolen on map").click()
    card = page.get_by_role("region", name="Climate station", exact=True)
    await expect(card).to_be_visible()
    await expect(card.get_by_role("row", name="Year 661.9")).to_be_visible()
    assert await card.evaluate("(c) => {const r=c.getBoundingClientRect(); return r.left>=0 && r.right<=innerWidth && r.bottom<=innerHeight && c.scrollWidth<=c.clientWidth}")
    await card.get_by_role("button", name="Close climate station").click()
    await expect(card).to_be_hidden()
    if mobile:
        return {"width": 360, "separate_stations": True}

    await panel.locator("button[data-state]").click()
    await expect(profile).to_contain_text("the largest municipality in")
    await expect(profile).to_contain_text("Landbohøjskolen")
    await page.locator("#council").click()
    await page.locator('[data-adv="environment"]').click()
    await expect(page.locator(".nc .climate-local")).to_contain_text("Landbohøjskolen")
    await page.get_by_role("button", name="Close the council").click()
    await page.evaluate("__app.selectCity('SE-0180', { fly: false })")
    await profile.get_by_text("Month by month").click()
    await expect(profile.get_by_role("row", name="Jul 18.7 30 yr 61.5 30 yr")).to_be_visible()
    await page.evaluate("__app.selectCity('DK-751', { fly: false })")
    await expect(profile).to_contain_text("No station in this sample within 100 km supplies precipitation")
    await panel.get_by_role("button", name="Close panel").click()
    await page.evaluate("__app.home()")
    await page.wait_for_function("() => !window.__app.cam.moving")
    marker = await page.evaluate("""async () => {
      const {projectionFrom, lonLatToMap} = await import('/js/util/geo.js');
      const a = window.__app, p = projectionFrom(a.w);
      for (const station of a.data.climate.stations) {
        const {x, y} = lonLatToMap(p, station.lon, station.lat);
        const [sx, sy] = a.cam.toScreen(x, y);
        const hit = a.hitLayer(sx, sy);
        if (sx > 200 && sx < 1200 && sy > 140 && sy < 750 && !a.hitCity(sx, sy) && hit?.layer === 'climate-stations')
          return { sx, sy, name: hit.item.stations[0].name };
      }
      return null;
    }""")
    assert marker, "No accessible marker in the map view"
    await page.mouse.click(marker["sx"], marker["sy"])
    await expect(card).to_contain_text(marker["name"])
    await page.keyboard.press("Escape")
    await expect(card).to_be_hidden()
    await page.locator("#btn-maplayers").click()
    toggle = page.get_by_role("menuitemcheckbox", name="Climate stations")
    await expect(toggle).to_have_attribute("aria-checked", "true")
    await toggle.click()
    await expect(toggle).to_have_attribute("aria-checked", "false")
    return {"region_advisor": True, "published_counts": True, "missing_coverage": True}


async def run(browser, url, ok, errors):
    for mobile in (False, True):
        detail = "phone" if mobile else "desktop"
        ctx = await browser.new_context(viewport={"width": 360 if mobile else 1440, "height": 900},
                                        is_mobile=mobile, has_touch=mobile, reduced_motion="reduce")
        await ctx.add_init_script("localStorage.setItem('nc-intro', '1')")
        page = await ctx.new_page()
        page.set_default_timeout(10000)
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.on("console", lambda message: errors.append(message.text) if message.type == "error" else None)
        label = f"{47 if mobile else 46} Climate station profiles and map, {detail}"
        try:
            ok(label, True, await journey(page, url.split("#")[0], mobile))
        except Exception as error:
            ok(label, False, str(error))
        finally:
            await ctx.close()
