"""Collect payloads that the browser bridge saved under /tmp/claude-tool-results.

A payload is a JS string result of the form  TAG<seq>:<base64>  (optionally padded with spaces).
Chunks for one TAG are concatenated in seq order, base64-decoded and (if gzip) decompressed.
"""
import base64, glob, gzip, hashlib, json, re, sys

def collect(tag):
    parts = {}
    for f in glob.glob('/tmp/claude-tool-results/*/*javascript_tool*.txt'):
        try:
            a = json.load(open(f))
        except Exception:
            continue
        t = a[0]['text']
        m = re.match(r'"' + re.escape(tag) + r'(\d+):([A-Za-z0-9+/=]+)\s*"', t)
        if m:
            parts[int(m.group(1))] = m.group(2)
    if not parts:
        raise SystemExit(f'no chunks for {tag}')
    seqs = sorted(parts)
    assert seqs == list(range(len(seqs))), f'missing chunks for {tag}: {seqs}'
    raw = base64.b64decode(''.join(parts[k] for k in seqs))
    sha = hashlib.sha256(raw).hexdigest()
    if raw[:2] == b'\x1f\x8b':
        raw = gzip.decompress(raw)
    return raw, sha, len(seqs)

if __name__ == '__main__':
    tag, out = sys.argv[1], sys.argv[2]
    raw, sha, n = collect(tag)
    open(out, 'wb').write(raw)
    print(f'{tag}: {n} chunks, sha256(gz)={sha}, {len(raw)} bytes -> {out}')
