"""Canvas fallback and WebGL context-loss user journeys."""
from pathlib import Path

from playwright.async_api import expect


def _webgl_url(url):
    return url.split("#")[0].split("?")[0] + "?renderer=webgl&pitch=24"


async def run(browser, url, ok, errors, out):
    failed_ctx = await browser.new_context(viewport={"width": 1440, "height": 900}, bypass_csp=True)
    await failed_ctx.add_init_script("""(() => {
        localStorage.setItem('nc-intro', '1');
        const getContext = HTMLCanvasElement.prototype.getContext;
        HTMLCanvasElement.prototype.getContext = function(type, ...args) {
            return type === 'webgl2' ? null : getContext.call(this, type, ...args);
        };
    })()""")
    failed_page = await failed_ctx.new_page()
    failed_page.on("pageerror", lambda error: errors.append("WebGL init fallback: " + str(error)))
    try:
        await failed_page.goto(_webgl_url(url), wait_until="domcontentloaded")
        await expect(failed_page.locator("#opening")).to_have_count(0, timeout=15000)
        await failed_page.wait_for_function("() => window.__app?.terrain && window.__app.cityById.has('NO-4601')", timeout=30000)
        init_fallback = await failed_page.evaluate("""() => {
            const a = __app, city = a.cityById.get('NO-4601');
            a.selectCity(city.id, {fly: false});
            a.cam.centerOn(city.x, city.y);
            a.cam.scale = 4;
            a.invalidate();
            const x = a.w.grid.cx(city.cell), y = a.w.grid.cy(city.cell);
            const [sx, sy] = a.cam.toScreen(x, y);
            return {
                available: a.terrain.stats().available,
                pitch: a.cam.pitch,
                maxScale: a.cam.maxScale,
                elevationAt: a.cam.elevationAt,
                verticalExaggeration: a.cam.verticalExaggeration,
                selected: a.state.selectedCity?.id,
                cellAt: a.cellAt(sx, sy),
                cell: city.cell,
                status: document.getElementById('terrain-status')?.textContent,
            };
        }""")
        ok("60 WebGL initialization failure restores the standard Canvas camera and keeps selection and hit-testing",
           not init_fallback["available"] and init_fallback["pitch"] == 0 and init_fallback["maxScale"] == 12
           and init_fallback["elevationAt"] is None and init_fallback["verticalExaggeration"] == 1
           and init_fallback["selected"] == "NO-4601" and init_fallback["cellAt"] == init_fallback["cell"]
           and "standard map" in init_fallback["status"], init_fallback)
    except Exception as error:
        ok("60 WebGL initialization failure restores the standard Canvas camera and keeps selection and hit-testing", False, str(error))
    finally:
        await failed_ctx.close()

    ctx = await browser.new_context(viewport={"width": 1440, "height": 900}, bypass_csp=True)
    await ctx.add_init_script("""(() => {
        localStorage.setItem('nc-intro', '1');
        const getContext = HTMLCanvasElement.prototype.getContext;
        HTMLCanvasElement.prototype.getContext = function(type, ...args) {
            const context = getContext.call(this, type, ...args);
            if (type === 'webgl2' && context) window.__terrainGl = context;
            return context;
        };
    })()""")
    page = await ctx.new_page()
    page.on("pageerror", lambda error: errors.append("WebGL context loss: " + str(error)))
    page.on("console", lambda message: errors.append("WebGL context loss: " + message.text) if message.type == "error" else None)
    try:
        await page.goto(_webgl_url(url), wait_until="domcontentloaded")
        await expect(page.locator("#opening")).to_have_count(0, timeout=15000)
        await page.wait_for_function("() => window.__app?.terrain?.stats().available && window.__terrainGl", timeout=30000)
        await page.evaluate("""() => {
            const a = __app, city = a.cityById.get('NO-4601');
            a.selectCity(city.id, {fly: false});
            a.cam.stop();
            a.cam.centerOn(city.x, city.y);
            a.cam.scale = 28;
            a.invalidate();
        }""")
        await page.wait_for_timeout(500)
        await page.screenshot(path=str(Path(out) / "d01-terrain-current-main.png"))
        lens_projection = await page.evaluate("""() => {
            const a = __app, cam = a.cam;
            const lens = a.data.lenses.lenses[0];
            a.setLens(lens.id);
            const flat = !cam.elevationAt;
            const [x, y] = [cam.x + 1, cam.y + 1];
            const hit = cam.toWorld(...cam.toScreen(x, y));
            a.setLens(null);
            return { flat, aligned: Math.hypot(hit[0] - x, hit[1] - y) < 1e-7,
                restored: typeof cam.elevationAt === 'function' };
        }""")
        ok("62 Pitched statistical lens uses flat hit testing and restores terrain projection",
           lens_projection["flat"] and lens_projection["aligned"] and lens_projection["restored"], lens_projection)
        before = await page.evaluate("() => __perf().static_n")
        await page.evaluate("""() => {
            const extension = window.__terrainGl.getExtension('WEBGL_lose_context');
            if (!extension) throw new Error('WEBGL_lose_context is unavailable');
            extension.loseContext();
        }""")
        await page.wait_for_function("""() => {
            const a = window.__app;
            return a && !a.terrain.stats().available && a.cam.pitch === 0 && a.cam.maxScale === 12 &&
                a.cam.elevationAt === null && a.cam.verticalExaggeration === 1 && a.cam.scale <= 12;
        }""", timeout=15000)
        await page.evaluate("() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))")
        await page.evaluate("__app.invalidate()")
        await page.evaluate("() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))")
        fallback = await page.evaluate("""() => {
            const a = __app, city = a.cityById.get('NO-4601');
            const [sx, sy] = a.cam.toScreen(a.w.grid.cx(city.cell), a.w.grid.cy(city.cell));
            return {
                available: a.terrain.stats().available,
                pitch: a.cam.pitch,
                maxScale: a.cam.maxScale,
                scale: a.cam.scale,
                selected: a.state.selectedCity?.id,
                cellAt: a.cellAt(sx, sy),
                cell: city.cell,
                staticRenders: __perf().static_n,
                status: document.getElementById('terrain-status')?.textContent,
            };
        }""")
        await page.screenshot(path=str(Path(out) / "d01-canvas-context-loss-fallback.png"))
        ok("61 WebGL context loss returns to Canvas, redraws the cache and preserves selection and cell hit-testing",
           not fallback["available"] and fallback["pitch"] == 0 and fallback["maxScale"] == 12
           and fallback["scale"] <= 12 and fallback["selected"] == "NO-4601"
           and fallback["cellAt"] == fallback["cell"] and fallback["staticRenders"] > before
           and "standard map" in fallback["status"], fallback)
    except Exception as error:
        ok("61 WebGL context loss returns to Canvas, redraws the cache and preserves selection and cell hit-testing", False, str(error))
    finally:
        await ctx.close()
