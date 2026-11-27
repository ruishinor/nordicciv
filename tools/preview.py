"""Quick raster preview of web/data/world.json (sanity check, not the app renderer)."""
import json, sys, math
from PIL import Image, ImageDraw
w = json.load(open('/home/claude/nordicciv/web/data/world.json'))
R = w['grid']['radius']; cols = w['grid']['cols']; rows = w['grid']['rows']
S = float(sys.argv[2]) if len(sys.argv) > 2 else 0.6  # px per km
img = Image.new('RGB', (int(w['width'] * S) + 20, int(w['height'] * S) + 20), (13, 42, 71))
d = ImageDraw.Draw(img)
cov = {t['id']: t['color'] for t in w['tables']['cover']}
wat = {1: '#1b4266', 2: '#2d6d97', 3: '#3a80b0'}
mode = sys.argv[1] if len(sys.argv) > 1 else 'cover'
pal = ['#c96', '#9c6', '#69c', '#c69', '#6c9', '#96c', '#cc6', '#6cc', '#c66', '#66c']
for i in range(cols * rows):
    c, r = i % cols, i // cols
    x = math.sqrt(3) * R * (c + 0.5 * (r & 1)); y = 1.5 * R * r
    o = w['owner'][i]
    if o == -1: col = wat.get(w['water'][i], '#123')
    elif o == -2: col = '#6b6658'
    elif mode == 'cover': col = cov.get(w['cover'][i], '#f0f')
    elif mode == 'relief': col = ['#7a9a5a', '#a89a5a', '#8a7a6a', '#eeeeee'][w['relief'][i]]
    elif mode == 'owner': col = pal[o % len(pal)]
    elif mode == 'pop':
        p = w['pop'][i]; v = min(1, math.log10(max(p, 1)) / 5.5); col = (int(255 * v), int(200 * v), int(80 * v))
    pts = [(x + R * math.cos(math.radians(60 * k - 30)), y + R * math.sin(math.radians(60 * k - 30))) for k in range(6)]
    d.polygon([(px * S + 10, py * S + 10) for px, py in pts], fill=col)
img.save(f'/tmp/preview_{mode}.png')
print(img.size)
