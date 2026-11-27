// NordicCiv camera-uplink page check. Paste into the console of a page on the provider's own origin (camstreamer.com,
// webcamcollections.com, www.skylinewebcams.com …) and call verifyUplinks([[key, url], …]). Each public viewing page
// is requested once from that origin (same-origin, so the status and title are readable), and the result records the
// HTTP status, the final URL after redirects and the page title. Nothing is downloaded beyond the page itself: no
// player, stream or image is requested. A page counts as verified when it answers 200 on the same host and its title
// is not an error page. Cross-origin pages (operators' own sites, Panomax instances) are checked by opening them in
// a browser tab instead and recording the same fields (see docs/METHODOLOGY.md, "Camera uplinks").
//
// The result goes to pipeline/catalogue/camera_uplinks_verification.json (merged by key) and is read by the build.
window.verifyUplinks = async function verifyUplinks(list, { concurrency = 4 } = {}) {
  const out = {};
  const queue = [...list];
  const day = new Date().toISOString().slice(0, 10);
  async function worker() {
    while (queue.length) {
      const [key, url] = queue.shift();
      try {
        const res = await fetch(url, { redirect: "follow", credentials: "omit" });
        const html = await res.text();
        const title = (new DOMParser().parseFromString(html, "text/html").title || "").replace(/\s+/g, " ").trim();
        const sameHost = new URL(res.url).host === new URL(url).host;
        const errorPage = /\b(404|not found|page not found|ikke funnet|hittades inte)\b/i.test(title);
        out[key] = { url, status: res.status, final_url: res.url, title: title.slice(0, 140), checked: day,
                     ok: res.status === 200 && sameHost && !errorPage, method: "same-origin fetch" };
      } catch (e) {
        out[key] = { url, status: 0, error: String(e), checked: day, ok: false, method: "same-origin fetch" };
      }
    }
  }
  await Promise.all(Array.from({ length: concurrency }, worker));
  return out;
};
