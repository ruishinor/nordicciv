"""Browser journeys 33–42 (v0.5): the opening screen and "Open in Maps". Called from tests/smoke_browser.py.

Opening (33–39): cold start under a slow network and a slow CPU (real progress, real steps, app inert until the first
frame, optional layers not waited for), cached start, reduced motion, essential and optional failures (with retry),
a slow start's "taking longer" note, a shared URL with state, and the phone layout.
Maps (40–42): links built from each feature's own position (checked independently with pyproj), the right behaviour
and zoom per kind of place, explicit outbound navigation only (no request before the click, the app's state kept,
no geolocation), and the phone.
"""
from urllib.parse import parse_qs, urlsplit

STEPS_ORDER = ["Opening Scandinavia…", "Loading resources and regions…", "Loading population and economy…",
               "Loading cities and settlements…", "Loading the landscape…", "Preparing the map…", "Ready to explore."]
READY = "window.__opening && (__opening.phase === 'ready' || __opening.phase === 'failed')"


def _q(url):
    u = urlsplit(url)
    return u, {k: v[0] for k, v in parse_qs(u.query).items()}


def _latlon(url):
    u, q = _q(url)
    lat, lon = map(float, (q.get("center") or q.get("query")).split(","))
    return lat, lon, int(q["zoom"]) if "zoom" in q else None, u.path


async def _open(b, url, ok_errors, *, viewport=None, mobile=False, reduced=False, routes=(), net=None, cpu=None, init=None):
    kw = {"viewport": viewport or {"width": 1440, "height": 900}, "bypass_csp": True}
    if mobile:
        kw.update(is_mobile=True, has_touch=True, device_scale_factor=2)
    if reduced:
        kw["reduced_motion"] = "reduce"
    ctx = await b.new_context(**kw)
    await ctx.add_init_script("try { localStorage.setItem('nc-intro', '1') } catch (e) {}")
    if init:
        await ctx.add_init_script(init)
    for pattern, handler in routes:
        await ctx.route(pattern, handler)
    pg = await ctx.new_page()
    reqs = []
    pg.on("request", lambda r: reqs.append((r.url, r.resource_type)))
    if net or cpu:
        cdp = await ctx.new_cdp_session(pg)
        if net:
            await cdp.send("Network.enable")
            await cdp.send("Network.setCacheDisabled", {"cacheDisabled": True})
            await cdp.send("Network.emulateNetworkConditions", {"offline": False, **net})
        if cpu:
            await cdp.send("Emulation.setCPUThrottlingRate", {"rate": cpu})
    await pg.goto(url, wait_until="commit")
    return ctx, pg, reqs


async def run(b, URL, ok, errors, timings, geo_of, out):
    base = URL.split("#")[0]

    # 33–34. cold start, slow network (≈ 4 Mbit/s, 150 ms) and 4× slower CPU
    ctx, pg, reqs = await _open(b, URL, errors, net={"latency": 150, "downloadThroughput": 500 * 1024, "uploadThroughput": 200 * 1024}, cpu=4)
    # the first paint: the browser shows nothing until the stylesheet has arrived
    await pg.wait_for_function("(() => { const o = document.getElementById('opening'); return o && getComputedStyle(o).position === 'fixed'; })()", timeout=30000)
    samples, inert_seen, tab_escaped = [], [], False
    first = await pg.evaluate("""(() => { const o = document.getElementById('opening'), r = o.getBoundingClientRect();
        return { covers: r.width >= innerWidth && r.height >= innerHeight, title: o.querySelector('.op-title').innerText, sub: o.querySelector('.op-sub').innerText,
                 busy: o.getAttribute('aria-busy'), role: o.querySelector('.op-progress').getAttribute('role'),
                 live: o.querySelector('.op-live').getAttribute('aria-live'), statusHidden: o.querySelector('.op-status').getAttribute('aria-hidden') }; })()""")
    for i in range(400):
        s = await pg.evaluate("""(() => { const o = document.getElementById('opening'); if (!o) return null;
            const f = o.querySelector('.op-fill'); const m = getComputedStyle(f).transform; const k = m.startsWith('matrix(') ? +m.slice(7).split(',')[0] : 0;
            return { k, msg: o.querySelector('.op-status').textContent, phase: window.__opening?.phase || 'script', text: o.innerText,
                     inert: ['topbar', 'map', 'lens-area', 'mobile-nav'].every((id) => document.getElementById(id)?.inert),
                     ind: o.classList.contains('op-indeterminate') }; })()""")
        if not s or s["phase"] in ("ready", "failed"):
            break
        samples.append(s)
        inert_seen.append(s["inert"])
        if i == 3:
            await pg.keyboard.press("Tab")
            await pg.keyboard.press("Tab")
            tab_escaped = await pg.evaluate("!!document.activeElement && !!document.activeElement.closest('#topbar, #lens-area, #mobile-nav, #minimap-wrap')")
        await pg.wait_for_timeout(120)
    await pg.wait_for_function(READY, timeout=120000)
    await pg.wait_for_timeout(1200)
    st = await pg.evaluate("""(async () => { const rel = await import('./js/render/art/relief.js');
        const res = performance.getEntriesByType('resource'); const at = (n) => res.find((e) => e.name.includes('/data/' + n));
        const o = window.__opening;
        return { phase: o.phase, ready: o.readyMs, readyAbs: o.t0 + o.readyMs, log: o.log, gone: !document.getElementById('opening'), inert: document.querySelectorAll('[inert]').length,
                 version: (await (await fetch('data/version.json')).json()).version,
                 world: at('world.json')?.responseEnd, munisEnd: at('munis.json')?.responseEnd, uplinksStart: at('uplinks.json')?.startTime,
                 t0: performance.timeOrigin, navStart: 0, reliefReadyNow: rel.reliefReady() }; })()""")
    shown_version = next((x["text"] for x in samples if "v0." in x["text"]), "")
    ks = [x["k"] for x in samples]
    steps = [e["step"] for e in st["log"]]
    order_ok = [s_ for s_ in STEPS_ORDER if s_ in steps] == steps
    ready_abs = st["readyAbs"]  # ms since navigation start, like the resource timings
    timings["opening_slow"] = {"ready_ms": st["ready"], "steps": st["log"], "samples": len(samples)}
    await pg.close()
    await ctx.close()
    c33 = {
        "screen": first["covers"] and first["title"].upper() == "NORDICCIV" and "Explore Scandinavia" in first["sub"],
        "version": f"v{st['version']}" in shown_version,
        "a11y": first["busy"] == "true" and first["role"] == "progressbar" and first["live"] == "polite" and first["statusHidden"] == "true",
        "grows": len(samples) > 10 and all(b2 >= a2 - 1e-6 for a2, b2 in zip(ks, ks[1:])) and ks[-1] > 0.5,
        "indeterminate_first": bool(samples) and samples[0]["ind"],
        "steps": len(set(x["msg"] for x in samples)) >= 4 and order_ok and steps[-1] == "Ready to explore." and "Preparing the map…" in steps,
        "no_percent": not any("%" in x["text"] for x in samples),
        "inert": all(inert_seen) and not tab_escaped,
        "released": st["phase"] == "ready" and st["gone"] and st["inert"] == 0,
    }
    ok("33 opening, cold and slow: a full-screen NordicCiv opening (title, 'Explore Scandinavia', the version from VERSION) shows real progress — "
       "the bar only grows and starts indeterminate, the status lines follow the files actually arriving, then 'Preparing the map…' and 'Ready to explore.'; "
       "no percentage is shown; the app behind is inert (keyboard cannot reach it) until the first map frame, then fully released",
       all(c33.values()), {**c33, "log": steps, "k_last": ks[-1:], "n": len(samples), "v": st["version"]})
    ok("34 opening does not wait for what the first map does not need: it is gone before the municipal outlines and relief have arrived and "
       "before the optional map layers (camera uplinks) are even requested; progressive loading carries on behind the open map",
       st["phase"] == "ready" and (st["munisEnd"] is None or st["munisEnd"] > ready_abs) and (st["uplinksStart"] is None or st["uplinksStart"] > ready_abs)
       and st["world"] is not None and st["world"] < ready_abs,
       {k: st[k] for k in ("readyAbs", "world", "munisEnd", "uplinksStart")})

    # 35. cached start: the same browser profile a second time — quick, with a short fade
    ctx = await b.new_context(viewport={"width": 1440, "height": 900}, bypass_csp=True)
    await ctx.add_init_script("try { localStorage.setItem('nc-intro', '1') } catch (e) {}")
    pg = await ctx.new_page()
    await pg.goto(URL, wait_until="load")
    await pg.wait_for_function(READY, timeout=60000)
    cold = await pg.evaluate("window.__opening.readyMs")
    await pg.goto("about:blank")
    await pg.goto(URL, wait_until="commit")
    await pg.wait_for_function(READY, timeout=60000)
    warm = await pg.evaluate("""(() => ({ ready: __opening.readyMs, fade: document.getElementById('opening')?.style.getPropertyValue('--op-fade') || 'gone',
        cached: performance.getEntriesByType('resource').filter((e) => e.name.includes('/data/') && (e.transferSize === 0 || e.transferSize < 1000)).length }))()""")
    await pg.wait_for_timeout(900)
    gone = await pg.evaluate("!document.getElementById('opening')")
    timings["opening_cached"] = {"cold_ms": cold, **warm}
    await ctx.close()
    ok("35 cached start: data come from the browser cache, the map opens without a hold and the screen fades out quickly (short fade under 0.7 s)",
       warm["cached"] >= 3 and warm["ready"] < 4000 and gone and (warm["fade"] in ("180ms", "gone") if warm["ready"] < 700 else warm["fade"] in ("420ms", "gone")),
       {"cold": cold, **warm, "gone": gone})

    # 36. reduced motion: nothing moves (needle, glint, fade), the map still opens
    async def hold(route):  # keep the opening on screen for a moment so its styles can be read
        await pg_hold.wait_for_timeout(5000)
        await route.continue_()
    ctx, pg_hold, _ = await _open(b, URL, errors, reduced=True, routes=[("**/data/world.json", hold)])
    await pg_hold.wait_for_function("document.querySelector('#opening .op-needle')", timeout=20000)
    await pg_hold.locator("#opening").screenshot(path=str(out / "opening-desktop.png"), animations="disabled")
    rm = await pg_hold.evaluate("""(() => { const g = (sel, p) => getComputedStyle(document.querySelector('#opening ' + sel))[p];
        return { compass: !!document.querySelector("#opening .op-bezel") && !document.querySelector("#opening .op-cross"), needle: g('.op-needle', 'animationName'),
                 bar: g('.op-progress', 'animationName'), fade: getComputedStyle(document.getElementById('opening')).transitionDuration,
                 fill: g('.op-fill', 'transitionDuration') }; })()""")
    await pg_hold.wait_for_function(READY, timeout=60000)
    rm["phase"] = await pg_hold.evaluate("__opening.phase")
    await ctx.close()
    ok("36 reduced motion: the compass needle, progress glint and fade do not animate; the map opens as usual",
       rm["compass"] and rm["needle"] == rm["bar"] == "none" and rm["fade"].startswith("0s") and rm["fill"] == "0s" and rm["phase"] == "ready", rm)

    # 37. failures: an essential file missing (404), an essential download cut off, a code file that does not load;
    # each stops the progress with a plain explanation and "Try again" (focused); the retry works once the cause is gone.
    async def r404(route):
        await route.fulfill(status=404, body="not found")

    async def rabort(route):
        await route.abort()
    fails = {}
    for key, pattern, handler in (("missing", "**/data/world.json", r404), ("network", "**/data/cities.json", rabort), ("code", "**/js/ui/minimap.js", rabort)):
        ctx, pf, _ = await _open(b, URL, errors, routes=[(pattern, handler)])
        await pf.wait_for_function(READY, timeout=60000)
        fails[key] = await pf.evaluate("""(() => { const o = document.getElementById('opening'), e = o?.querySelector('.op-error');
            return { phase: __opening.phase, title: e?.querySelector('.op-err-title')?.textContent, role: e?.getAttribute('role'),
                     barHidden: o?.querySelector('.op-progress')?.hidden, focused: document.activeElement?.classList.contains('op-retry'),
                     detail: e?.querySelector('.op-err-detail code')?.textContent || '', stillInert: !!document.getElementById('topbar').inert }; })()""")
        if key == "missing":  # the retry after the file is back
            await ctx.unroute(pattern, handler)
            await pf.click("#opening .op-retry")
            await pf.wait_for_function(READY, timeout=60000)
            fails[key]["retry"] = await pf.evaluate("__opening.phase")
        await ctx.close()
    ok("37 failures: a missing essential file, a broken download and a code file that does not load each stop the progress and say what happened "
       "in plain words with 'Try again' (focused, announced as an alert, details kept for developers, app still locked); retrying works once the cause is gone",
       fails["missing"]["phase"] == "failed" and fails["missing"]["title"] == "The map data is missing" and fails["missing"]["retry"] == "ready"
       and fails["network"]["title"] == "The map didn't arrive" and fails["code"]["title"] == "NordicCiv didn't start"
       and all(f["role"] == "alert" and f["barHidden"] and f["focused"] and f["detail"] and f["stillInert"] for f in fails.values()),
       {k: {kk: (vv[:60] if isinstance(vv, str) else vv) for kk, vv in v.items()} for k, v in fails.items()})

    # 38. optional failures and a slow essential file: the map opens anyway; a long wait gets a gentle note, not an error
    async def slow(route):
        await pg_slow.wait_for_timeout(20000)
        await route.continue_()
    routes = [("**/data/lenses.json", r404), ("**/data/uplinks.json", rabort), ("**/data/munis.json", rabort), ("**/data/world.json", slow)]
    ctx, pg_slow, _ = await _open(b, URL, errors, routes=routes)
    await pg_slow.wait_for_timeout(18500)
    note = await pg_slow.evaluate("""(() => { const o = document.getElementById('opening'); return { slow: !!o?.classList.contains('op-slow'),
        failed: !!o?.classList.contains('op-failed'), text: o ? getComputedStyle(o.querySelector('.op-status'), '::after').content : '' }; })()""")
    await pg_slow.wait_for_function(READY, timeout=60000)
    await pg_slow.wait_for_timeout(1500)
    opt = await pg_slow.evaluate("""(() => ({ phase: __opening.phase, lenses: __app.data.lenses.lenses.length, uplinks: __app.data.uplinks ?? null,
        cities: __app.data.cities.length, gone: !document.getElementById('opening') }))()""")
    await ctx.close()
    ok("38 optional failures do not block: with the lenses, camera-uplink and outline files unavailable the map still opens (a slow essential file "
       "first shows 'This is taking longer than usual.' instead of an error)",
       note["slow"] and not note["failed"] and "longer than usual" in note["text"] and opt["phase"] == "ready" and opt["gone"] and opt["cities"] == 745
       and opt["lenses"] == 0 and opt["uplinks"] is None, {**note, **opt})

    # 39. a shared link with state opens on that state (after the opening screen); the phone layout fits
    ctx = await b.new_context(viewport={"width": 1440, "height": 900}, bypass_csp=True)
    await ctx.add_init_script("try { localStorage.setItem('nc-intro', '1') } catch (e) {}")
    pa = await ctx.new_page()
    await pa.goto(URL, wait_until="load")
    await pa.wait_for_function(READY, timeout=60000)
    await pa.evaluate("__app.setLens('density'); __app.selectCity('NO-1525', {fly: false}); __app.hash.flush?.()")
    await pa.wait_for_timeout(600)
    shared = await pa.evaluate("location.href")
    pb = await ctx.new_page()
    await pb.goto(shared, wait_until="commit")
    await pb.wait_for_function(READY, timeout=60000)
    await pb.wait_for_timeout(1200)
    sh = await pb.evaluate("({ city: __app.state.selectedCity?.id, lens: __app.state.lens?.id, phase: __opening.phase, panel: !document.getElementById('city-panel').hidden })")
    await ctx.close()

    async def hold_m(route):
        await pm_.wait_for_timeout(5000)
        await route.continue_()
    ctx, pm_, _ = await _open(b, URL, errors, viewport={"width": 390, "height": 844}, mobile=True, routes=[("**/data/world.json", hold_m)])
    await pm_.wait_for_function("document.querySelector('#opening .op-version')?.textContent", timeout=20000)
    await pm_.locator("#opening").screenshot(path=str(out / "opening-phone.png"), animations="disabled")
    ph = await pm_.evaluate("""(() => { const r = (s) => document.querySelector('#opening ' + s).getBoundingClientRect(); const inV = (x) => x.left >= 0 && x.right <= innerWidth && x.top >= 0 && x.bottom <= innerHeight;
        return { emblem: inV(r('.op-emblem')), title: inV(r('.op-title')), bar: inV(r('.op-progress')), status: inV(r('.op-status')), version: inV(r('.op-version')),
                 overflow: document.documentElement.scrollWidth > innerWidth }; })()""")
    await pm_.wait_for_function(READY, timeout=60000)
    ph["phase"] = await pm_.evaluate("__opening.phase")
    await ctx.close()
    ok("39 a shared link with a selected municipality and lens opens on exactly that state behind the opening screen; on a phone the opening fits the screen",
       sh["city"] == "NO-1525" and sh["lens"] == "density" and sh["panel"] and sh["phase"] == "ready"
       and all(ph[k] for k in ("emblem", "title", "bar", "status", "version")) and not ph["overflow"] and ph["phase"] == "ready", {"shared": sh, "phone": ph, "url": shared[-60:]})

    # 40. Open in Maps across Norway, Sweden and Denmark: positions checked independently (pyproj), behaviour and zoom per kind
    geo_spy = "window.__geoCalls = 0; try { for (const k of ['getCurrentPosition', 'watchPosition']) { const f = navigator.geolocation[k].bind(navigator.geolocation); navigator.geolocation[k] = (...a) => { window.__geoCalls++; return f(...a); }; } } catch (e) {}"
    ctx = await b.new_context(viewport={"width": 1440, "height": 900}, bypass_csp=True)
    await ctx.add_init_script("try { localStorage.setItem('nc-intro', '1') } catch (e) {}")
    await ctx.add_init_script(geo_spy)
    pm = await ctx.new_page()
    reqs = []
    pm.on("request", lambda r: reqs.append(r.url))
    pm.on("pageerror", lambda e: errors.append("maps: " + str(e)))
    await pm.goto(URL, wait_until="networkidle")
    await pm.wait_for_function("window.__app && __app.uplinks && __app.uplinks.data && __app.data.infrastructure && __app.data.wonders", timeout=60000)
    await pm.wait_for_function("import('./js/render/art/relief.js').then(m => m.munisReady())", timeout=30000)
    links = await pm.evaluate("""(async () => { const a = __app, out = {}; const rel = await import('./js/render/art/relief.js');
        const wait = (ms) => new Promise((r) => setTimeout(r, ms));
        const grab = (sel) => [...document.querySelectorAll(sel)].map((l) => ({ text: l.textContent.trim(), label: l.getAttribute('aria-label'), title: l.title, icon: !!l.querySelector('svg[aria-hidden=true]'), href: l.href, target: l.target, rel: l.rel,
            ref: l.referrerPolicy, kind: l.dataset.mapsOut, tab: l.closest('[data-tab]')?.dataset.tab || '' }));
        for (const id of ['NO-1525', 'SE-2584', 'DK-101', 'NO-4601', 'SE-0180']) {
          a.selectCity(id, { fly: false }); await wait(300);
          out[id] = { links: grab('#city-panel a.maps-open'), bbox: rel.muniFeature(id).bbox, city: (({ lat, lon, place, anchor }) => ({ lat, lon, place, anchor }))(a.cityById.get(id)) };
        }
        for (const st of ['NO-15', 'SE-25', 'DK-083']) { a.selectState(st, { fly: false }); await wait(300); out[st] = { links: grab('#city-panel a.maps-open') }; }
        a.clearSelection();
        const ap = a.data.infrastructure.airports.filter((x) => ['EKCH', 'ESSA', 'ENBR'].includes(x.id)).map(({ id, name, x, y }) => ({ id, name, x, y }));
        const cams = {};
        for (const id of ['ln-gaustabanen', 'cs-425493061']) { a.uplinks.open(id, { fly: false }); await wait(300);
          const c = a.uplinks.data.byId.get(id); cams[id] = { links: grab('#uplink-card a.maps-open'), uplink: grab('#uplink-card a.uplink-open'), lat: c.lat, lon: c.lon, pos: c.pos }; }
        a.uplinks.closeCard();
        return { out, ap, cams }; })()""")
    probs = []
    o = links["out"]
    for cid in ("NO-1525", "SE-2584", "DK-101"):
        L = o[cid]["links"]
        muni = next((x for x in L if x["kind"] == "municipality"), None)
        if not muni or muni["tab"] != "Overview" or muni["text"] or not muni["icon"]:
            probs.append(f"{cid}: municipality link {muni}")
            continue
        lat, lon, z, path = _latlon(muni["href"])
        b0 = o[cid]["bbox"]
        elon, elat = geo_of((b0[0] + b0[2]) / 2, (b0[1] + b0[3]) / 2)
        if path != "/maps/@" or abs(lat - elat) > 2e-5 or abs(lon - elon) > 2e-5:
            probs.append(f"{cid}: centre {lat},{lon} vs {elat:.5f},{elon:.5f}")
        town = next((x for x in L if x["kind"] == "settlement"), None)
        if o[cid]["city"]["anchor"].startswith("euronym"):
            tl = _latlon(town["href"]) if town else None
            if not tl or (tl[0], tl[1]) != (o[cid]["city"]["lat"], o[cid]["city"]["lon"]) or tl[2] not in (12, 13):
                probs.append(f"{cid}: settlement {tl}")
    zm = {cid: _latlon(next(x for x in o[cid]["links"] if x["kind"] == "municipality")["href"])[2] for cid in ("NO-1525", "SE-2584", "DK-101")}
    if not zm["SE-2584"] < zm["NO-1525"] < zm["DK-101"]:
        probs.append(f"municipality zoom does not follow size: {zm}")
    if not any((x["label"] or "").startswith("Open København in Maps:") for x in o["DK-101"]["links"]):
        probs.append("Copenhagen: no 'Open København in Maps'")
    for st in ("NO-15", "SE-25", "DK-083"):
        L = o[st]["links"]
        if len(L) != 1 or _latlon(L[0]["href"])[2] > 8:
            probs.append(f"region {st}: {L}")
    sites = [x for x in o["NO-4601"]["links"] + o["SE-0180"]["links"] if x["tab"] == "Economy"]
    ap_links = [x for x in o["NO-4601"]["links"] + o["SE-0180"]["links"] + o["DK-101"]["links"] if "search" in x["href"]]
    ap_ok = 0
    for a in links["ap"]:
        elon, elat = geo_of(a["x"], a["y"])
        if any(abs(_latlon(x["href"])[0] - elat) < 2e-5 and abs(_latlon(x["href"])[1] - elon) < 2e-5 for x in ap_links):
            ap_ok += 1
    if ap_ok < 2:
        probs.append(f"airports marked at their own position: {ap_ok}/3 found")
    if not any("/maps/@" in x["href"] and _latlon(x["href"])[2] == 15 for x in sites):
        probs.append("no landmark close-up among Bergen/Stockholm sites")
    cams = links["cams"]
    for cid, c in cams.items():
        if len(c["links"]) != 1 or len(c["uplink"]) != 1 or c["uplink"][0]["text"] != "Open uplink ↗":
            probs.append(f"{cid}: card actions {c}")
            continue
        lat, lon, z, path = _latlon(c["links"][0]["href"])
        if (lat, lon) != (round(c["lat"], 5), round(c["lon"], 5)) or z != (14 if c["pos"] == "place" else 16):
            probs.append(f"{cid}: {lat},{lon} z{z} vs {c['lat']},{c['lon']} {c['pos']}")
    every = [x for v in o.values() for x in v["links"]] + [x for c in cams.values() for x in c["links"]]
    bad_attr = [x["href"][:40] for x in every if x["target"] != "_blank" or "noopener" not in x["rel"] or "noreferrer" not in x["rel"] or x["ref"] != "no-referrer"
                or not x["href"].startswith("https://www.google.com/maps/") or x["text"] or not x["icon"] or not x["title"] or not x["label"]]
    ok("40 Open in Maps (Norway, Sweden, Denmark): municipalities open on their whole extent (centre checked with pyproj, zoom by size), the main settlement "
       "separately at town/city scale, regions as a landscape overview, landmarks close up, airports marked at their own position, camera uplinks next to "
       "'Open uplink' (close where the position is published, wider where it is only a place); every link a new-tab https Google Maps link without opener or referrer",
       not probs and not bad_attr and len(every) >= 20, {"problems": probs[:4], "bad": bad_attr[:3], "n": len(every)})

    # 41. explicit and private: no request to any map service before the click; clicking the map never leaves; following the
    # link opens Google Maps in a new tab (blocked here) and NordicCiv keeps its view, selection and lens; no geolocation
    await pm.evaluate("__app.setLens('density'); __app.selectCity('SE-2584', {fly: false})")
    await pm.wait_for_timeout(500)
    before = await pm.evaluate("({ city: __app.state.selectedCity?.id, lens: __app.state.lens?.id, x: __app.cam.x, y: __app.cam.y, s: __app.cam.scale, hash: location.hash })")
    href = await pm.evaluate("document.querySelector('#city-panel a[data-maps-out=municipality]').href")
    await pm.hover("#city-panel a[data-maps-out=municipality]")
    await pm.wait_for_timeout(400)
    foreign_before = [u for u in reqs if not u.startswith(base) and not u.startswith(("data:", "blob:"))]
    popups = []
    pm.on("popup", lambda p_: popups.append(p_))
    await pm.mouse.click(700, 450)  # a click on the map selects inside NordicCiv only
    await pm.wait_for_timeout(900)
    map_click_popups = len(popups)
    await pm.evaluate("__app.selectCity('SE-2584', {fly: false}); __app.cam.stop?.()")
    await pm.evaluate(f"(() => {{ __app.cam.x = {before['x']}; __app.cam.y = {before['y']}; __app.cam.scale = {before['s']}; __app.invalidate(); }})()")
    await pm.wait_for_timeout(500)
    out_req = []

    def foreign(u):
        return not u.startswith(base)

    async def block(route):
        out_req.append(route.request.url)
        await route.abort()
    await ctx.route(foreign, block)
    opened = None
    try:
        async with ctx.expect_page(timeout=5000) as pop:
            await pm.click("#city-panel a[data-maps-out=municipality]")
        p2 = await pop.value
        await p2.wait_for_timeout(400)
        opened = p2.url
        await p2.close()
    except Exception as e:  # noqa: BLE001
        opened = f"no popup: {e}"
    await ctx.unroute(foreign, block)
    await pm.wait_for_timeout(300)
    after = await pm.evaluate("({ city: __app.state.selectedCity?.id, lens: __app.state.lens?.id, x: __app.cam.x, y: __app.cam.y, s: __app.cam.scale, hash: location.hash, geo: window.__geoCalls, url: location.href })")
    probes = await pm.evaluate("""(async () => { const m = await import('./js/app/maps.js');
        return [m.mapsUrl({ lat: NaN, lon: 1 }), m.mapsUrl({ lat: 95, lon: 10 }), m.mapsUrl({ lat: 60, lon: 200 }), m.mapsUrl({}), m.mapsLink(null)]; })()""")
    await ctx.close()
    same = all(abs(before[k] - after[k]) < 1e-6 for k in ("x", "y", "s")) and before["city"] == after["city"] and before["lens"] == after["lens"]
    ok("41 explicit and private: nothing from a map service is requested while links are shown or hovered; a click on the map only selects inside NordicCiv; "
       "the link opens Google Maps in a new tab with exactly its URL; NordicCiv keeps its view, selection and lens; no location is asked for; invalid coordinates give no link",
       not foreign_before and map_click_popups == 0 and isinstance(opened, str) and not opened.startswith("no popup") and out_req and out_req[0] == href
       and href.startswith("https://www.google.com/maps/")
       and same and after["geo"] == 0 and after["url"].startswith(base) and all(p_ in (None, "") for p_ in probes),
       {"foreign": foreign_before[:2], "popup": (opened or "")[:60], "outbound": out_req[:1], "same": same, "geo": after["geo"], "probes": probes})

    # 42. phone: the municipality panel and the camera card offer Open in Maps as a full-size, visible tap target
    ctx = await b.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True, device_scale_factor=2)
    await ctx.add_init_script("try { localStorage.setItem('nc-intro', '1') } catch (e) {}")
    mq = await ctx.new_page()
    mq.on("pageerror", lambda e: errors.append("maps mobile: " + str(e)))
    await mq.goto(URL, wait_until="networkidle")
    await mq.wait_for_function("window.__app && __app.uplinks && __app.uplinks.data", timeout=30000)
    await mq.evaluate("__app.selectCity('NO-1525', {fly: true})")
    await mq.wait_for_timeout(1400)
    mob = await mq.evaluate("""(async () => { const l = document.querySelector('#city-panel a[data-maps-out=municipality]'); l?.scrollIntoView({ block: 'center' });
        await new Promise((r) => setTimeout(r, 300)); const r = l?.getBoundingClientRect();
        const panel = r && r.height >= 44 && r.width >= 44 && r.top >= 0 && r.bottom <= innerHeight && document.elementFromPoint(r.x + r.width / 2, r.y + r.height / 2)?.closest('a') === l;
        __app.clearSelection(); __app.uplinks.open('ln-gaustabanen'); await new Promise((r2) => setTimeout(r2, 1200));
        const as = [...document.querySelectorAll('#uplink-card a')].map((a) => a.getBoundingClientRect());
        return { panel, card: as.length === 2 && as.every((x) => x.height >= 22 && x.bottom <= innerHeight && x.right <= innerWidth && x.left >= 0) }; })()""")
    await ctx.close()
    ok("42 phone: 'Open in Maps' is a visible, full-size tap target in the municipality panel, and the camera card shows both actions on screen",
       mob["panel"] and mob["card"], mob)
