"""Close-range terrain artwork and camera regression, desktop and high-DPI phone."""
from playwright.async_api import expect


async def run(browser, url, ok, errors, out):
    for mobile in (False, True):
        label = f"{52 if mobile else 51} Close terrain zoom, {'phone' if mobile else 'desktop'}"
        ctx = await browser.new_context(
            viewport={"width": 390 if mobile else 1440, "height": 844 if mobile else 900},
            device_scale_factor=2 if mobile else 1, is_mobile=mobile, has_touch=mobile,
            reduced_motion="reduce")
        await ctx.add_init_script("localStorage.setItem('nc-intro', '1')")
        page = await ctx.new_page()
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.on("console", lambda message: errors.append(message.text) if message.type == "error" else None)
        try:
            await page.goto(url.split("#")[0].split("?")[0] + "?detail=full", wait_until="domcontentloaded")
            await expect(page.locator("#opening")).to_have_count(0, timeout=15000)
            await page.wait_for_function("() => window.__app?.cam && window.__app.cityById.has('NO-4601')")
            await page.evaluate("""() => {
                const a = __app, c = a.cityById.get('NO-4601');
                a.clearSelection(); a.setLens(null); a.cam.stop();
                a.cam.zoomAt(a.cam.w / 2, a.cam.h / 2, 6 / a.cam.scale);
                a.cam.centerOn(c.x, c.y); a.invalidate();
            }""")
            stats = """async (zoom) => {
                const m = await import('/js/render/art/illustrate.js');
                const s = m.illustrationState()?.last;
                return s && Math.abs(s.zoom - zoom) < 0.001 && s.classes > 0 ? s : false;
            }"""
            before = await (await page.wait_for_function(stats, arg=6, timeout=30000)).json_value()
            centre = await page.evaluate("() => [__app.cam.x, __app.cam.y]")
            await page.evaluate("() => {const a = __app; a.cam.zoomBy(a.cam.w/2, a.cam.h/2, 10); a.requestDraw();}")
            await page.wait_for_function("() => !__app.cam.moving && __app.cam.scale === 12", timeout=15000)
            after = await (await page.wait_for_function(stats, arg=12, timeout=30000)).json_value()
            assert before["kmPerPx"] == after["kmPerPx"] == 0.125, (before, after)
            assert after["raster"] > before["raster"], (before, after)
            assert after["cachedPixels"] <= 12000000, after
            assert await page.evaluate("() => [__app.cam.x, __app.cam.y]") == centre
            await page.screenshot(path=str(out / f"close-zoom-{'phone' if mobile else 'desktop'}-bergen.png"))
            # Lenses remain available at the deeper zoom; turning one on does not reset the camera.
            await page.evaluate("__app.setLens('farmland')")
            assert await page.evaluate("() => __app.state.lens?.id === 'farmland' && __app.cam.scale === 12")
            await page.evaluate("__app.setLens(null)")
            if not mobile:
                await page.evaluate("""() => {
                    const a = __app, c = a.cityById.get('DK-751');
                    a.cam.centerOn(c.x - 20, c.y); a.invalidate();
                }""")
                await page.wait_for_function("""async (at) => {
                    const m = await import('/js/render/art/illustrate.js');
                    const s = m.illustrationState()?.last;
                    return s && s.at > at && s.classes > 0;
                }""", arg=after["at"], timeout=30000)
                await page.screenshot(path=str(out / "close-zoom-desktop-danish-farmland.png"))
            ok(label, True, {"before": before, "after": after, "lens": True})
        except Exception as error:
            ok(label, False, str(error))
        finally:
            await ctx.close()
