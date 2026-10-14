"""Renders a week of Spotlight My Song Instagram posts from a pack JSON.

Usage: python3 _studio/brand.py path/to/pack.json
Pack JSON: {"slug": "...", "week_of": "Oct 19", "posts": [
  {"day": "Mon", "caption": "...", "slides": [
     {"kind": "cover", "kicker": "release tip", "headline": "...", "body": "..."},
     {"kind": "point", "num": "1", "headline": "...", "body": "..."},
     {"kind": "cta", "headline": "...", "body": "..."}]}]}
Writes p/<slug>/ : one JPG per slide, index.html with captions and downloads.
"""
import json, sys, html, pathlib
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import numpy as np

ROOT = pathlib.Path(__file__).resolve().parent.parent
FD = '/usr/share/fonts/opentype/inter/'
LORA = '/usr/share/fonts/truetype/google-fonts/Lora-Italic-Variable.ttf'
W, H = 1080, 1350
NIGHT = (14, 10, 18); CREAM = (255, 243, 223); SMOKE = (205, 196, 210); GOLD = (255, 196, 107); AMBER = (255, 154, 46)

def F(w, s): return ImageFont.truetype(FD + f'InterDisplay-{w}.otf', s)
def L(s):
    f = ImageFont.truetype(LORA, s)
    try: f.set_variation_by_name('Medium')
    except Exception: pass
    return f

def wrap(d, text, font, maxw):
    lines, cur = [], ''
    for word in text.split():
        t = (cur + ' ' + word).strip()
        if d.textlength(t, font=font) <= maxw: cur = t
        else:
            if cur: lines.append(cur)
            cur = word
    if cur: lines.append(cur)
    return lines

def fit_block(d, text, weight, start, maxw, maxh, lead=0.98, minsize=44):
    s = start
    while True:
        f = F(weight, s); ls = wrap(d, text, f, maxw)
        if (len(ls) * s * lead <= maxh and all(d.textlength(x, font=f) <= maxw for x in ls)) or s <= minsize:
            return f, ls, int(s * lead)
        s -= 4

def backdrop(seed):
    rng = np.random.default_rng(seed)
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    cx = W * (0.25 + 0.5 * rng.random())
    beam = np.clip(1 - np.abs(xx - cx - (yy * (rng.random() - 0.5) * 0.6)) / (180 + yy * 0.55), 0, 1) ** 1.6
    beam *= np.clip(1 - yy / (H * 1.1), 0, 1)
    glow = np.exp(-(((xx - cx) / 520) ** 2 + ((yy - H * 1.05) / 420) ** 2))
    arr = np.zeros((H, W, 3), np.float32) + np.array(NIGHT, np.float32)
    arr += beam[..., None] * np.array([120, 90, 50], np.float32) * 0.55
    arr += glow[..., None] * np.array([150, 80, 20], np.float32) * 0.5
    arr += rng.normal(0, 7, (H, W))[..., None]
    return Image.fromarray(np.clip(arr, 0, 255).astype('uint8'))

def frame(im, idx, total):
    d = ImageDraw.Draw(im)
    d.ellipse((64, 64, 84, 84), fill=GOLD)
    d.text((98, 58), 'SPOTLIGHT MY SONG', font=F('Bold', 26), fill=CREAM)
    if total > 1:
        t = f'{idx}/{total}'; f = F('Medium', 26)
        d.text((W - 64 - d.textlength(t, font=f), 60), t, font=f, fill=SMOKE)
    d.line((64, H - 110, W - 64, H - 110), fill=(60, 48, 66), width=2)
    d.text((64, H - 86), 'spotlightmysong.com', font=F('Medium', 28), fill=SMOKE)
    if total > 1 and idx < total:
        t = 'swipe'; f = L(34)
        d.text((W - 64 - d.textlength(t, font=f) - 40, H - 92), t, font=f, fill=GOLD)
        d.polygon([(W - 82, H - 82), (W - 64, H - 72), (W - 82, H - 62)], fill=GOLD)

def slide(s, idx, total, seed):
    im = backdrop(seed); d = ImageDraw.Draw(im); X = 64; MW = W - 2 * X
    kind = s.get('kind', 'point')
    if kind == 'cover':
        if s.get('kicker'):
            k = s['kicker'].lower(); f = L(48); d.text((X, 300), k, font=f, fill=GOLD)
        f, ls, lh = fit_block(d, s['headline'].upper(), 'Black', 132, MW, 620)
        y = 380
        for ln in ls: d.text((X, y), ln, font=f, fill=(255, 255, 255)); y += lh
        if s.get('body'):
            bf = F('Medium', 38); y += 30
            for ln in wrap(d, s['body'], bf, MW)[:4]: d.text((X, y), ln, font=bf, fill=SMOKE); y += 52
    elif kind == 'cta':
        f, ls, lh = fit_block(d, s['headline'].upper(), 'Black', 112, MW, 460)
        y = 360
        for ln in ls: d.text((X, y), ln, font=f, fill=(255, 255, 255)); y += lh
        bf = F('Medium', 38); y += 30
        for ln in wrap(d, s.get('body', ''), bf, MW)[:4]: d.text((X, y), ln, font=bf, fill=SMOKE); y += 52
        y += 40; t = s.get('button', 'Link in bio'); bf2 = F('Bold', 40); tw = d.textlength(t, font=bf2)
        d.rounded_rectangle((X, y, X + tw + 80, y + 92), radius=46, fill=GOLD); d.text((X + 40, y + 20), t, font=bf2, fill=(27, 15, 5))
    else:
        f, ls, lh = fit_block(d, s['headline'], 'Black', 96, MW, 360)
        bf = F('Medium', 46); bl = wrap(d, s.get('body', ''), bf, MW)[:9]
        nh = 250 if s.get('num') else 0
        total_h = nh + lh * len(ls) + 40 + 64 * len(bl)
        y = max(170, (H - total_h) // 2 - 20)
        if s.get('num'): d.text((X - 6, y - 30), s['num'], font=F('Black', 230), fill=GOLD); y += nh
        for ln in ls: d.text((X, y), ln, font=f, fill=(255, 255, 255)); y += lh
        y += 40
        for ln in bl: d.text((X, y), ln, font=bf, fill=SMOKE); y += 64
    frame(im, idx, total)
    return im

E = lambda x: html.escape(str(x))

def main(p):
    pk = json.load(open(p)); out = ROOT / 'p' / pk['slug']; out.mkdir(parents=True, exist_ok=True)
    cards = ''
    for i, post in enumerate(pk['posts'], 1):
        imgs = ''
        n = len(post['slides'])
        for j, s in enumerate(post['slides'], 1):
            name = f'post{i}_{j}.jpg'
            slide(s, j, n, i * 31 + j).save(out / name, quality=92)
            imgs += f'<figure><img src="{name}" alt=""><a href="{name}" download>Download</a></figure>'
        cards += (f'<section><h2>{E(post.get("day", f"Post {i}"))}</h2><div class="row">{imgs}</div>'
                  f'<div class="cap"><p>{E(post["caption"])}</p><button class="copy">Copy caption</button></div></section>')
    (out / 'index.html').write_text(f'''<!doctype html><html><head><meta charset="utf-8"><meta name="color-scheme" content="dark"><meta name="darkreader-lock"><meta name="viewport" content="width=device-width, initial-scale=1"><meta name="robots" content="noindex, nofollow">
<title>Content pack {E(pk.get("week_of",""))}</title><style>
body{{margin:0;background:#0E0A12;color:#FFF3DF;font-family:system-ui,sans-serif;font-size:16px;line-height:1.5}}
.w{{max-width:900px;margin:0 auto;padding:24px 16px 60px}} h1{{font-size:30px;margin:0 0 6px}} .sub{{color:#CDC4D2;margin:0 0 10px}}
section{{border-top:1px solid #33283B;padding:22px 0}} h2{{color:#FFC46B;font-size:20px;margin:0 0 12px}}
.row{{display:flex;gap:10px;overflow-x:auto;padding-bottom:6px}} figure{{margin:0;flex:0 0 220px}} figure img{{width:100%;border-radius:8px;display:block}}
figure a{{display:inline-block;margin-top:6px;font-size:13px;font-weight:700;color:#1B0F05;background:#FFC46B;padding:5px 12px;border-radius:99px;text-decoration:none;-webkit-text-fill-color:#1B0F05}}
.cap{{background:#1B1420;border-radius:10px;padding:12px 14px;margin-top:12px}} .cap p{{margin:0 0 6px;white-space:pre-wrap}}
.copy{{font:inherit;font-size:13px;font-weight:700;color:#FFC46B;background:none;border:0;padding:0;cursor:pointer}}
</style></head><body><div class="w"><h1>Content pack, week of {E(pk.get("week_of",""))}</h1>
<p class="sub">Schedule these in Meta Business Suite. Post order and days are suggestions. For carousels, upload the slides in order.</p>{cards}</div>
<script>document.addEventListener('click',e=>{{if(!e.target.classList.contains('copy'))return;navigator.clipboard.writeText(e.target.previousElementSibling.textContent);e.target.textContent='Copied';setTimeout(()=>e.target.textContent='Copy caption',1500)}});</script>
</body></html>''')
    print('built', out)

if __name__ == '__main__':
    main(sys.argv[1])
