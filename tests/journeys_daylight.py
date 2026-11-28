"""Daylight browser journeys. Run as part of smoke_browser.py."""

from datetime import datetime, timezone
import re
from urllib.parse import urlencode

from playwright.async_api import expect

CONTROLS = "#daylight-controls"
CITY = "#city-panel [data-daylight-city]"
CLOCK = CONTROLS + " .daylight-clock time"

# Count only paints of the Daylight image, not static map renders or cache blits.
COUNT_PAINTS = """(() => {
  window.daylightPaints = 0;
  const put = CanvasRenderingContext2D.prototype.putImageData;
  CanvasRenderingContext2D.prototype.putImageData = function (image, ...args) {
    if (image.data[0] === 20 && image.data[1] === 33 && image.data[2] === 58) window.daylightPaints++;
    return put.call(this, image, ...args);
  };
})()"""
SAMPLE_LIGHT = """() => {
  const app = window.__app, layer = app.staticLayers().find(l => l.id === "daylight");
  const canvas = document.createElement("canvas");
  canvas.width = canvas.height = 1;
  const ctx = canvas.getContext("2d", {willReadFrequently: true});
  return ["NO-5501", "DK-101"].map(id => {
    const {x, y} = app.cityById.get(id);
    ctx.resetTransform();
    ctx.clearRect(0, 0, 1, 1);
    ctx.translate(-x, -y);
    layer.draw(ctx, null, app.w, {lens: null});
    return ctx.getImageData(0, 0, 1, 1).data[3];
  });
}"""


async def open_map(page, url):
    await page.goto(url, wait_until="domcontentloaded")
    await expect(page.locator("#btn-daylight")).to_have_count(1, timeout=15000)
    await expect(page.locator("#opening")).to_have_count(0, timeout=15000)


async def select_place(page, name):
    await page.locator("#search-input").fill(name)
    await page.get_by_role("option").filter(has_text=name).first.click()
    await expect(page.locator(".cp-name")).to_contain_text(name, ignore_case=True)
    await page.get_by_role("tab", name="Daylight").click()


async def set_time(page, date, time):
    await page.locator(CONTROLS + ' input[name="date"]').fill(date)
    await page.locator(CONTROLS + ' input[name="time"]').fill(time)
    await page.get_by_role("button", name="Apply time").click()


async def desktop(page, url):
    await page.add_init_script(COUNT_PAINTS)
    await open_map(page, url)
    await expect(page.locator(CONTROLS)).to_be_hidden()
    assert await page.evaluate("window.daylightPaints") == 0, "Daylight painted while off"
    await page.get_by_role("button", name="Daylight", exact=True).click()
    await expect(page.locator(CONTROLS + " h2")).to_be_focused()
    await select_place(page, "Tromsø")
    await page.get_by_role("button", name="Choose date and time").click()
    await set_time(page, "2024-06-20", "23:55")
    await expect(page.locator(CLOCK)).to_have_attribute("datetime", "2024-06-20T21:55:00.000Z")
    await expect(page.locator(CITY)).to_contain_text("Midnight sun")
    await expect(page.locator(CITY)).to_contain_text("24 h")
    await expect(page.locator(CITY)).to_contain_text("No sunset today")
    summer = await page.evaluate(SAMPLE_LIGHT)
    assert summer[0] == 0 and summer[1] > 45, summer
    paints = await page.evaluate("window.daylightPaints")
    await page.evaluate("__app.cam.zoomBy(innerWidth / 2, innerHeight / 2, 1.25); __app.requestDraw()")
    await page.evaluate("new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))")
    assert await page.evaluate("window.daylightPaints") == paints, "Zoom repainted the Daylight raster"

    await set_time(page, "2024-12-21", "12:00")
    await expect(page.locator(CITY)).to_contain_text("Polar night")
    await expect(page.locator(CITY)).to_contain_text("Civil twilight")
    await expect(page.locator(CITY)).to_contain_text("No sunrise today")
    await expect(page.locator(CITY)).to_contain_text("0 h")
    winter = await page.evaluate(SAMPLE_LIGHT)
    assert winter[0] > 20 and winter[1] == 0, winter

    await select_place(page, "Copenhagen")
    await expect(page.locator(CONTROLS)).to_contain_text("Denmark local time")
    await expect(page.locator(CITY + " dd")).to_have_text(["08:37", "15:38", "7 h 1 min"])
    await page.evaluate("__app.setLens('income')")
    await page.get_by_role("button", name="Turn off").click()
    await expect(page.locator(CONTROLS)).to_be_hidden()
    await expect(page.locator(CITY)).to_contain_text("Turn on Daylight")
    await expect(page).to_have_url(re.compile(r"^(?!.*[#&]daylight=).*$"))
    assert await page.evaluate("""() => __app.state.selectedCity.id === "DK-101" &&
      __app.state.lens.id === "income" && !__app.staticLayers().find(l => l.id === "daylight").visible()"""), "Turning off changed the selection or lens"
    await page.locator("#btn-daylight").click()
    await select_place(page, "Tromsø")
    await expect(page.locator("[data-seasonal-city]")).to_contain_text("24 h daylight")
    await expect(page.locator("[data-seasonal-city]")).to_contain_text("0 h astronomical darkness")
    aurora = page.get_by_role("link", name="Aurora forecast (NOAA)")
    await expect(aurora).to_have_attribute("href", "https://www.spaceweather.gov/products/aurora-30-minute-forecast")
    await expect(aurora).to_have_attribute("target", "_blank")
    await page.locator(".daylight-seasons summary").click()
    await page.get_by_role("button", name="Winter", exact=True).click()
    await expect(page.locator(CITY)).to_contain_text("Polar night")
    await page.get_by_role("button", name="Summer", exact=True).click()
    await page.get_by_role("button", name="Midnight", exact=True).click()
    await expect(page.locator(CITY)).to_contain_text("Midnight sun")
    return {"summer_alpha_north_south": summer, "winter_alpha_north_south": winter, "raster_reused_on_zoom": True,
            "seasonal_comparison": True, "aurora_reference": True}


async def time_and_link(page, url):
    await page.clock.install(time=datetime(2024, 6, 21, 0, 0, 10, tzinfo=timezone.utc))
    async def flush_before_daylight_loads(route):
        await page.evaluate("window.__app.hash.flush()")
        await route.continue_()
    await page.route("**/js/ext/daylight/index.js", flush_before_daylight_loads, times=1)
    await open_map(page, url + "#" + urlencode({"daylight": "2024-06-20T21:55:00.000Z"}))
    await expect(page.locator(CLOCK)).to_have_attribute("datetime", "2024-06-20T21:55:00.000Z")
    await select_place(page, "Kiruna")
    await expect(page.locator(CONTROLS)).to_contain_text("Sweden local time")
    await expect(page.locator(CLOCK)).to_contain_text("23:55 UTC+2")
    await expect(page.locator(CITY)).to_contain_text("Midnight sun")

    await set_time(page, "2024-03-31", "02:30")
    await expect(page.get_by_role("status").filter(has_text="That time is skipped")).to_be_visible()
    await expect(page.locator(CLOCK)).to_have_attribute("datetime", "2024-06-20T21:55:00.000Z")
    await set_time(page, "2024-10-27", "02:30")
    await expect(page.get_by_label("Which time?")).to_be_focused()
    await page.get_by_label("Which time?").select_option("later")
    await page.get_by_role("button", name="Apply time").click()
    await expect(page.locator(CLOCK)).to_have_attribute("datetime", "2024-10-27T01:30:00.000Z")
    await expect(page.locator(CLOCK)).to_contain_text("02:30 UTC+1")
    await expect(page).to_have_url(re.compile(r"[#&]daylight=2024-10-27T01%3A30%3A00\.000Z(?:&|$)"))
    await page.get_by_role("button", name="Now", exact=True).click()
    await expect(page.locator(CLOCK)).to_have_attribute("datetime", "2024-06-21T00:00:00.000Z")
    await expect(page).to_have_url(re.compile(r"[#&]daylight=now(?:&|$)"))
    await page.clock.fast_forward(61_000)
    await expect(page.locator(CLOCK)).to_have_attribute("datetime", "2024-06-21T00:01:00.000Z")
    await page.go_back()
    await expect(page.locator(CLOCK)).to_have_attribute("datetime", "2024-10-27T01:30:00.000Z")
    await expect(page.get_by_role("button", name="Choose date and time")).to_have_attribute("aria-pressed", "true")
    return {"spring_gap": True, "fall_second_occurrence": True, "live_tick": True, "back_restores_time": True}


async def mobile(page, url):
    await open_map(page, url)
    assert await page.evaluate("matchMedia('(prefers-reduced-motion: reduce)').matches")
    await page.locator("#daylight-mobile").tap()
    await expect(page.locator(CONTROLS)).to_be_visible()
    await expect(page.get_by_role("list", name="Map lighting")).to_have_text("DaylightTwilightDarkness")
    await select_place(page, "Copenhagen")
    await page.get_by_role("button", name="Choose date and time").tap()
    await set_time(page, "2024-06-20", "12:00")
    await expect(page.locator(CITY)).to_contain_text("Daylight at 12:00")
    await expect(page.locator(CITY + " dd")).to_have_text(["04:25", "21:57", "17 h 32 min"])
    layout = await page.locator(CONTROLS).evaluate("""el => {
      const r = el.getBoundingClientRect(), city = document.querySelector('#city-panel');
      return r.x >= 0 && r.right <= innerWidth && r.bottom < city.getBoundingClientRect().top
        && el.scrollWidth <= el.clientWidth && city.scrollWidth <= city.clientWidth && city.scrollLeft === 0
        && getComputedStyle(el).transitionDuration === '0s';
    }""")
    assert layout, "Daylight controls or municipality tabs overflow on a narrow screen"
    await page.get_by_role("button", name="Turn off").tap()
    await expect(page.locator(CONTROLS)).to_be_hidden()
    await expect(page.get_by_role("button", name="Turn on Daylight")).to_be_focused()
    return {"touch": True, "reduced_motion": True, "controls_clear_of_municipality": layout}


async def run(browser, url, ok, errors):
    base = url.split("#")[0]
    for label, journey, options in [
        ("43 Daylight desktop: winter and summer, geographic lighting, local figures, raster cache, lens and return", desktop, {}),
        ("44 Daylight time: shared view, DST gap and overlap, live updates and Back", time_and_link, {}),
        ("45 Daylight phone: touch, reduced motion and municipality layout", mobile,
         {"viewport": {"width": 360, "height": 800}, "is_mobile": True, "has_touch": True,
          "device_scale_factor": 2, "reduced_motion": "reduce"}),
    ]:
        ctx = await browser.new_context(**{"viewport": {"width": 1440, "height": 900}, **options})
        await ctx.add_init_script("localStorage.setItem('nc-intro', '1')")
        page = await ctx.new_page()
        page.set_default_timeout(12000)
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.on("console", lambda message: errors.append(message.text) if message.type == "error" else None)
        try:
            ok(label, True, await journey(page, base))
        except Exception as error:
            ok(label, False, str(error))
        finally:
            await ctx.close()
