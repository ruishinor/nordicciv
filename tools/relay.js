// NordicCiv browser relay. Paste into the console of any page (CORS-enabled APIs: SSB, SCB, DST, Eurostat,
// UNESCO...) to run the requests that `python -m pipeline relay-plan` lists when your network blocks them.
// relay(plan) fetches every request, gzips the answers and stores them in window.__relayOut as base64 chunks;
// save them (e.g. copy(__relayOut.join(''))) to a file and run `python -m pipeline relay-ingest <file>`
// after decoding (tools/bridge.py does this).
window.relay = async function relay(plan, { chunk = 190000, concurrency = 4 } = {}) {
  const results = {};
  const queue = plan.map((p) => (Array.isArray(p) ? { key: p[0], url: p[1], method: p[2] || "GET", body: p[3] } : p));
  async function worker() {
    while (queue.length) {
      const r = queue.shift();
      try {
        const res = await fetch(r.url, { method: r.method || "GET", body: r.body, headers: r.headers });
        const buf = new Uint8Array(await res.arrayBuffer());
        let bin = "";
        for (let i = 0; i < buf.length; i += 8192) bin += String.fromCharCode.apply(null, buf.subarray(i, i + 8192));
        results[r.key] = { status: res.status, b64: btoa(bin), bytes: buf.length };
      } catch (e) {
        results[r.key] = { status: 0, error: String(e) };
      }
    }
  }
  await Promise.all(Array.from({ length: concurrency }, worker));
  const bytes = new TextEncoder().encode(JSON.stringify(results));
  const gz = new Uint8Array(await new Response(new Blob([bytes]).stream().pipeThrough(new CompressionStream("gzip"))).arrayBuffer());
  let bin = "";
  for (let i = 0; i < gz.length; i += 8192) bin += String.fromCharCode.apply(null, gz.subarray(i, i + 8192));
  const b64 = btoa(bin);
  window.__relayOut = [];
  for (let i = 0; i < b64.length; i += chunk) window.__relayOut.push(b64.slice(i, i + chunk));
  const sha = Array.from(new Uint8Array(await crypto.subtle.digest("SHA-256", gz))).map((b) => b.toString(16).padStart(2, "0")).join("");
  return {
    n: plan.length, chunks: window.__relayOut.length, gz: gz.length, sha,
    status: Object.fromEntries(Object.entries(results).map(([k, v]) => [k, v.status + (v.bytes ? ":" + v.bytes : "") + (v.error ? ":" + v.error : "")])),
  };
};
