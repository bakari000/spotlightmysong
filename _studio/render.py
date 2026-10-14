"""Builds a Spotlight My Song campaign delivery from a campaign JSON file.

Usage: python3 _studio/render.py path/to/campaign.json
Writes everything into d/<slug>/ : index.html, campaign.pdf and the graphics.
"""
import json, sys, os, html, pathlib
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import numpy as np

ROOT = pathlib.Path(__file__).resolve().parent.parent
FONT_DIR = '/usr/share/fonts/opentype/inter/'
LORA = '/usr/share/fonts/truetype/google-fonts/Lora-Italic-Variable.ttf'
MONO = '/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf'
RED = (226, 48, 30); ORANGE = (255, 140, 40)

def inter(w, s): return ImageFont.truetype(FONT_DIR + f'InterDisplay-{w}.otf', s)
def lora(s):
    f = ImageFont.truetype(LORA, s)
    try: f.set_variation_by_name('Medium')
    except Exception: pass
    return f
def tsize(d, t, f): b = d.textbbox((0, 0), t, font=f); return b[2]-b[0], b[3]-b[1], b[0], b[1]
def cx(d, t, f, W): tw, _, ox, _ = tsize(d, t, f); return (W - tw) / 2 - ox
def fit(d, t, weight, start, maxw, minsize=40):
    s = start
    while s > minsize and tsize(d, t, inter(weight, s))[0] > maxw: s -= 4
    return inter(weight, s)
def fit_lines(d, t, weight, start, maxw, minsize=40):
    """fit to one line, or split into two lines if that keeps it bigger"""
    one = fit(d, t, weight, start, maxw, minsize)
    words = t.split()
    if one.size >= start * 0.6 or len(words) < 2: return [t], one
    best = None
    for i in range(1, len(words)):
        a, b = ' '.join(words[:i]), ' '.join(words[i:])
        f = fit(d, max(a, b, key=len), weight, start, maxw, minsize)
        if not best or f.size > best[1].size: best = ([a, b], f)
    return best if best[1].size > one.size else ([t], one)

def load_cover(path, spots=()):
    if path and os.path.exists(path):
        im = Image.open(path).convert('L')
        w, h = im.size; m = min(w, h)
        im = im.crop(((w-m)//2, (h-m)//2, (w-m)//2+m, (h-m)//2+m)).copy()
        px = im.load()
        for (sx, sy, r) in spots:  # clone out small smudges, coordinates in the square crop
            for y in range(max(0, sy-r), min(m, sy+r)):
                for x in range(max(0, sx-r), min(m-2*r, sx+r)): px[x, y] = px[x+2*r, y]
        a = np.asarray(im).astype(np.float32) / 255
        a = np.where(a < 0.5, 0.05 + (a/0.5)**0.8 * 0.45, a)  # lift crushed shadows
        return Image.fromarray((np.clip(a, 0, 1)*255).astype('uint8')).copy()
    # no cover: soft spotlight gradient
    yy, xx = np.mgrid[0:1200, 0:1200]
    d = np.sqrt(((xx-600)/600)**2 + ((yy-380)/700)**2)
    return Image.fromarray((np.clip(1-d, 0, 1)**1.6*150+12).astype('uint8'))

def finish(im, grain=16, seed=1, vignette=True, scan=True):
    arr = np.asarray(im.convert('RGB')).astype(np.float32); H, W = arr.shape[:2]
    if vignette:
        yy, xx = np.mgrid[0:H, 0:W]; dd = np.sqrt(((xx-W/2)/(W/2))**2 + ((yy-H/2)/(H/2))**2)
        arr *= (1 - 0.38*np.clip(dd-0.55, 0, 1))[..., None]
    if scan: arr[::3] *= 0.93
    arr += np.random.default_rng(seed).normal(0, grain, (H, W))[..., None]
    return Image.fromarray(np.clip(arr, 0, 255).astype('uint8'))

def split_text(im, xy, t, f, off=7):
    W, H = im.size
    for col, dx in [((255, 40, 40), -off), ((40, 220, 255), off)]:
        L = Image.new('L', (W, H), 0); ImageDraw.Draw(L).text((xy[0]+dx, xy[1]), t, font=f, fill=255)
        im.paste(Image.new('RGB', (W, H), col), (0, 0), L.point(lambda v: int(v*0.55)))
    ImageDraw.Draw(im).text(xy, t, font=f, fill=(255, 255, 255))

def datestamp(im, xy, t):
    W, H = im.size; f = ImageFont.truetype(MONO, 38)
    L = Image.new('L', (W, H), 0); ImageDraw.Draw(L).text(xy, t, font=f, fill=255)
    im.paste(Image.new('RGB', (W, H), ORANGE), (0, 0), L.filter(ImageFilter.GaussianBlur(6)).point(lambda v: int(v*0.8)))
    im.paste(Image.new('RGB', (W, H), (255, 170, 80)), (0, 0), L)

def graphics(c, base, out):
    low = (lambda s: s.lower()) if c.get('lowercase', True) else (lambda s: s)
    artist, title = low(c['artist']), low(c['title'])
    platform = c.get('platform', 'Spotify')
    released = c.get('released', True)
    tagtxt = 'OUT NOW' if released else 'COMING SOON'
    cover = lambda n: base.resize((n, n), Image.LANCZOS).filter(ImageFilter.UnsharpMask(2, 60, 2))

    # 1 feed post 1080x1350
    W, H = 1080, 1350
    im = cover(1500).crop((210, 120, 210+W, 120+H)).convert('RGB')
    im.paste((8, 8, 8), (0, H-560, W, H), Image.linear_gradient('L').resize((W, 560)).point(lambda v: int(v*0.96)))
    im.paste((8, 8, 8), (0, 0, W, 220), Image.linear_gradient('L').rotate(180).resize((W, 220)).point(lambda v: int(v*0.7)))
    d = ImageDraw.Draw(im)
    d.text((60, 56), artist, font=fit(d, artist, 'Bold', 42, 560), fill=(255, 255, 255))
    ft = inter('Bold', 28); tw, th, ox, oy = tsize(d, tagtxt, ft)
    d.rounded_rectangle((W-60-tw-36, 58, W-60, 58+th+24), radius=8, fill=RED)
    d.text((W-60-tw-18-ox, 58+12-oy), tagtxt, font=ft, fill=(255, 255, 255))
    lines, fb = fit_lines(d, title, 'Black', 300, W-140, 90)
    lh = int(fb.size*0.95); y0 = 1220 - lh*len(lines)
    for i, ln in enumerate(lines): split_text(im, (cx(d, ln, fb, W), y0 + i*lh), ln, fb)
    d = ImageDraw.Draw(im)
    s = f'stream on {platform.lower()}  ·  link in bio' if released else f'out {c.get("release_label","soon")}  ·  link in bio'
    fs = inter('Medium', 34); d.text((cx(d, s, fs, W), 1262), s, font=fs, fill=(205, 205, 205))
    finish(im, 15, 1).save(out/'1_feed_post.jpg', quality=92)

    # 2 story 1080x1920, now-playing card
    W, H = 1080, 1920
    im = cover(1920).crop((420, 0, 1500, 1920)).filter(ImageFilter.GaussianBlur(46)).point(lambda v: int(v*0.32)).convert('RGB')
    d = ImageDraw.Draw(im)
    s = c.get('story_hook', 'if you slept on this' if released else 'save the date'); f = lora(60)
    d.text((cx(d, s, f, W), 210), s, font=f, fill=(235, 235, 235))
    card = Image.new('RGB', (900, 1200), (18, 18, 18)); m = Image.new('L', card.size, 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, 900, 1200), radius=36, fill=255); im.paste(card, (90, 360), m)
    art = cover(820).convert('RGB'); am = Image.new('L', art.size, 0)
    ImageDraw.Draw(am).rounded_rectangle((0, 0, 820, 820), radius=18, fill=255); im.paste(art, (130, 400), am)
    if c.get('date_stamp'): datestamp(im, (130+820-250, 400+820-62), c['date_stamp'])
    d = ImageDraw.Draw(im)
    d.text((130, 1262), title, font=fit(d, title, 'Black', 92, 820, 44), fill=(255, 255, 255))
    d.text((130, 1372), artist, font=fit(d, artist, 'Medium', 44, 820), fill=(170, 170, 170))
    d.rounded_rectangle((130, 1460, 950, 1470), radius=5, fill=(70, 70, 70))
    p = 130 + int(820*0.36)
    d.rounded_rectangle((130, 1460, p, 1470), radius=5, fill=(255, 255, 255)); d.ellipse((p-14, 1451, p+14, 1479), fill=(255, 255, 255))
    d.ellipse((470, 1610, 610, 1750), fill=(255, 255, 255)); d.polygon([(520, 1645), (520, 1715), (578, 1680)], fill=(18, 18, 18))
    s = 'tap the link to listen'; f = inter('Bold', 40); d.text((cx(d, s, f, W), 1790), s, font=f, fill=(255, 255, 255))
    finish(im, 13, 2, scan=False).save(out/'2_story.jpg', quality=92)

    # 3 fans-of post 1080x1080
    W, H = 1080, 1080
    im = cover(1080).point(lambda v: int(v*0.38)).convert('RGB'); d = ImageDraw.Draw(im)
    names = [low(n) for n in c.get('sounds_like', [])][:2]
    if names:
        s = 'if you rock with'; f = lora(66); d.text((cx(d, s, f, W), 232), s, font=f, fill=(240, 240, 240))
        fn = fit(d, max(names, key=len), 'Black', 104, W-120, 50)
        ys = [350] if len(names) == 1 else [350, 550]
        for t, y in zip(names, ys):
            E = Image.new('L', (W, H), 0); ImageDraw.Draw(E).text((cx(d, t, fn, W), y+10), t, font=fn, fill=255)
            im.paste(RED, (0, 0), E.filter(ImageFilter.GaussianBlur(1)).point(lambda v: int(v*0.85)))
            d = ImageDraw.Draw(im); d.text((cx(d, t, fn, W), y), t, font=fn, fill=(255, 255, 255))
        if len(names) == 2:
            s = 'or'; f = lora(46); d.text((cx(d, s, f, W), 488), s, font=f, fill=(220, 220, 220))
        y_need = 710 if len(names) == 2 else 520
    else:
        y_need = 420
        s = c.get('genre', '').lower() or 'new music'; f = lora(66); d.text((cx(d, s, f, W), 300), s, font=f, fill=(240, 240, 240))
    s = 'you need to hear this'; f = lora(56); d.text((cx(d, s, f, W), y_need), s, font=f, fill=(235, 235, 235))
    s = f'{artist}  —  {title}'; f = fit(d, s, 'Bold', 62, W-140); d.text((cx(d, s, f, W), y_need+120), s, font=f, fill=(255, 255, 255))
    s = f'on {platform.lower()} now' if released else 'link in bio'; f = inter('Medium', 34)
    d.text((cx(d, s, f, W), y_need+202), s, font=f, fill=(190, 190, 190))
    finish(im, 17, 3).save(out/'3_fans_of_post.jpg', quality=92)

E = lambda s: html.escape(str(s))

# Interactive plan tracker: each plan row is a checkbox the artist ticks off,
# with a progress bar. Progress is kept in the viewer's browser per page.
def sched_row(day, title, text):
    return (f'<tr><td class="d"><label class="tick"><input type="checkbox" aria-label="Mark done: {E(title)}">'
            f'<span>{E(day)}</span></label></td><td><b>{E(title)}</b>{E(text)}</td></tr>')

PLAN_PROGRESS = ('<div class="prog"><div class="ptext"><span id="pcount">0 done</span><span id="pmsg">Tick each step off as you post it</span></div>'
                 '<div class="bar"><i id="pbar"></i></div></div>')

PLAN_CSS = """
:root{color-scheme:dark}
.pill,.dl,.big{-webkit-text-fill-color:#1B0F05}
.prog{position:sticky;top:0;z-index:5;background:rgba(14,10,18,.95);backdrop-filter:blur(8px);padding:12px 0;margin-bottom:6px;border-bottom:1px solid var(--line)}
.ptext{display:flex;justify-content:space-between;gap:12px;font-size:14px;font-weight:600;color:var(--smoke)}
.bar{height:8px;border-radius:99px;background:#2A2030;overflow:hidden;margin-top:6px}
.bar i{display:block;height:100%;width:0;background:linear-gradient(90deg,var(--gold),var(--amber));transition:width .25s}
.tick{display:flex;gap:10px;align-items:flex-start;cursor:pointer}
.tick input{appearance:none;flex:none;width:22px;height:22px;margin-top:2px;border-radius:6px;border:2px solid #6B5A73;display:grid;place-content:center;cursor:pointer}
.tick input:checked{background:var(--amber);border-color:var(--amber)}
.tick input:checked::after{content:"";width:5px;height:10px;border:solid #1B0F05;border-width:0 3px 3px 0;transform:rotate(45deg) translate(-1px,-1px)}
.tick input:focus-visible{outline:2px solid var(--gold);outline-offset:2px}
tr:has(.tick input:checked) td b{text-decoration:line-through;text-decoration-color:rgba(255,196,107,.7)}
tr:has(.tick input:checked) td{opacity:.75}
.cycle{background:var(--card);border-radius:14px;padding:18px 20px;box-shadow:0 0 0 1px var(--line) inset}
.cycle li{margin:10px 0}.cycle li b{color:#fff}
"""

PLAN_JS = """<script>(function(){var K='sms-plan-'+location.pathname;var bx=[].slice.call(document.querySelectorAll('.tick input'));if(!bx.length)return;var sv=[];try{sv=JSON.parse(localStorage.getItem(K)||'[]')}catch(e){}
bx.forEach(function(b,i){if(sv[i])b.checked=true;b.addEventListener('change',up)});
function up(){var d=bx.filter(function(b){return b.checked}).length,n=bx.length;document.getElementById('pcount').textContent=d+' of '+n+' done';document.getElementById('pbar').style.width=(d/n*100)+'%';
document.getElementById('pmsg').textContent=d===0?'Tick each step off as you post it':d===n?'Campaign complete. Send us your numbers':d>n/2?'Past halfway. Stay on it':'You are rolling';
try{localStorage.setItem(K,JSON.stringify(bx.map(function(b){return b.checked})))}catch(e){}}up()})();</script>"""

# What a label does after the first two weeks. Same for every plan.
NEXT_CYCLE = """<section><h2>After the two weeks</h2><p style="margin-bottom:14px">This is how labels keep an artist moving between drops. Do the same and every release starts stronger than the last.</p>
<ol class="cycle">
<li><b>Day 14: check your numbers.</b> In Spotify for Artists, look at listeners, saves and where they came from. Note which post brought people in.</li>
<li><b>Weeks 3 to 6: keep the song alive.</b> Post two or three times a week using what worked. A song does not stop being new just because release week ended.</li>
<li><b>Week 4: lock in the next drop.</b> Pick your next song and a Friday release date six to eight weeks out.</li>
<li><b>Week 5: upload early.</b> Get the next song to your distributor three to four weeks before release so you can pitch it to Spotify's editors.</li>
<li><b>Every drop: same playbook, better each time.</b> Releasing on a steady schedule is what builds a fanbase. One song rarely does it alone.</li>
</ol></section>"""

def page(c, cover_rel):
    plan = c['plan'].capitalize()
    rv = c.get('review', {})
    sched = ''.join(sched_row(r["day"], r["title"], r["text"]) for r in c['schedule'])
    caps = ''.join(f'<div class="cap"><span>{E(x["label"])}</span><p>{E(x["text"])}</p><button class="copy" type="button">Copy</button></div>' for x in c['captions'])
    better = ''.join(f'<li>{E(b)}</li>' for b in rv.get('better', []))
    extras = ''
    for x in c.get('extras', []):
        body = ''
        if x.get('text'): body += ''.join(f'<p>{E(p)}</p>' for p in x['text'].split('\n\n'))
        if x.get('items'): body += '<ol>' + ''.join(f'<li>{E(i)}</li>' for i in x['items']) + '</ol>'
        extras += f'<section><h2>{E(x["heading"])}</h2>{body}</section>'
    readiness = f'<section><h2>Streaming readiness check</h2><p>{E(c["readiness"])}</p></section>' if c.get('readiness') else ''
    cover_img = f'<img class="covimg" src="{cover_rel}" alt="">' if cover_rel else ''
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="color-scheme" content="dark"><meta name="darkreader-lock">
<meta name="viewport" content="width=device-width, initial-scale=1"><meta name="robots" content="noindex, nofollow">
<title>{E(c["artist"])} – {E(c["title"])} | Spotlight My Song</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Big+Shoulders+Display:wght@800;900&family=Figtree:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
:root{{--night:#0E0A12;--card:#1B1420;--line:#33283B;--cream:#FFF3DF;--smoke:#D9CFDC;--gold:#FFC46B;--amber:#FF9A2E}}
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:var(--night);color:var(--cream);font-family:Figtree,system-ui,sans-serif;font-size:17px;line-height:1.6}}
.wrap{{max-width:860px;margin:0 auto;padding:0 20px}}
.top{{padding:22px 20px;font-family:"Big Shoulders Display",Impact,sans-serif;font-weight:800;font-size:20px;text-transform:uppercase;letter-spacing:.02em}}
.top a{{color:inherit;text-decoration:none}}
header{{padding:30px 0 10px;background:radial-gradient(70% 90% at 50% 0%,rgba(255,196,107,.22),transparent 70%)}}
.pill{{display:inline-block;font-weight:700;font-size:14px;padding:6px 14px;border-radius:99px;background:var(--gold);color:#1B0F05}}
h1{{font-family:"Big Shoulders Display",Impact,sans-serif;font-weight:900;text-transform:uppercase;font-size:clamp(56px,13vw,110px);line-height:.9;margin:16px 0 10px;color:#fff}}
.meta{{color:var(--smoke)}}
.summary{{margin-top:14px;max-width:62ch}}
section{{padding:44px 0 6px}}
h2{{font-family:"Big Shoulders Display",Impact,sans-serif;font-weight:900;text-transform:uppercase;font-size:clamp(34px,7vw,52px);line-height:1;color:#fff;margin-bottom:16px}}
h3{{font-size:17px;color:var(--gold);margin:18px 0 4px}}
p,li{{color:var(--smoke)}} p+p{{margin-top:10px}}
ul,ol{{padding-left:22px}} li{{margin:6px 0}}
.rev{{display:grid;grid-template-columns:220px 1fr;gap:26px;align-items:start}}
.covimg{{width:100%;border-radius:12px}}
.gfx{{display:grid;grid-template-columns:repeat(3,1fr);gap:14px}}
.gfx figure{{background:var(--card);border-radius:14px;padding:10px;box-shadow:0 0 0 1px var(--line) inset}}
.gfx img{{width:100%;border-radius:8px;display:block}}
.gfx figcaption{{font-size:14px;color:var(--smoke);margin:8px 2px 6px}}
.dl{{display:inline-block;font-weight:700;font-size:14px;color:#1B0F05;background:var(--gold);padding:8px 14px;border-radius:99px;text-decoration:none}}
.big{{display:inline-block;margin-top:18px;font-weight:700;color:#1B0F05;background:linear-gradient(135deg,#FFE0A3,var(--gold) 40%,var(--amber));padding:14px 24px;border-radius:99px;text-decoration:none}}
table{{width:100%;border-collapse:collapse}}
td{{vertical-align:top;padding:14px 8px;border-top:1px solid var(--line);color:var(--smoke)}}
td b{{display:block;color:#fff}}
td.d{{width:150px;font-weight:800;color:var(--gold);white-space:nowrap}}
.cap{{background:var(--card);border-radius:12px;padding:14px 16px;margin-bottom:12px;box-shadow:0 0 0 1px var(--line) inset}}
.cap span{{font-size:13px;font-weight:700;color:var(--gold)}}
.cap p{{color:#fff;margin:4px 0}}
.copy{{font:inherit;font-size:13px;font-weight:700;color:var(--gold);background:none;border:0;cursor:pointer;padding:2px 0}}
footer{{margin-top:50px;border-top:1px solid var(--line);padding:26px 0 40px;color:var(--smoke);font-size:15px}}
footer a{{color:var(--gold)}}
{PLAN_CSS}
@media(max-width:640px){{.rev{{grid-template-columns:1fr}}.rev .covimg{{max-width:240px}}.gfx{{grid-template-columns:1fr}}td.d{{width:112px;white-space:normal}}}}
</style></head><body>
<div class="wrap top"><a href="/">Spotlight My Song</a></div>
<header><div class="wrap">
<span class="pill">{E(plan)} campaign</span>
<h1>{E(c["artist"])}<br>{E(c["title"])}</h1>
<p class="meta">{E(c.get("meta",""))}</p>
<p class="summary">{E(c.get("summary",""))}</p>
<a class="big" href="campaign.pdf" download>Download the full plan (PDF)</a>
</div></header>
<div class="wrap">
<section><h2>Cover art review</h2><div class="rev">{cover_img}<div>
<h3>What works</h3><p>{E(rv.get("works",""))}</p>
<h3>What could be better</h3><ul>{better}</ul>
<h3>What we did</h3><p>{E(rv.get("what_we_did",""))}</p>
<h3>Next time</h3><p>{E(rv.get("next_time",""))}</p></div></div></section>
<section><h2>Your promo graphics</h2><p style="margin-bottom:16px">Tap download to save each one to your phone.</p><div class="gfx">
<figure><img src="1_feed_post.jpg" alt=""><figcaption>Feed post, 4 by 5</figcaption><a class="dl" href="1_feed_post.jpg" download>Download</a></figure>
<figure><img src="3_fans_of_post.jpg" alt=""><figcaption>Fans-of post, square</figcaption><a class="dl" href="3_fans_of_post.jpg" download>Download</a></figure>
<figure><img src="2_story.jpg" alt=""><figcaption>Story. Put your link sticker over the play button.</figcaption><a class="dl" href="2_story.jpg" download>Download</a></figure>
</div></section>
<section><h2>{E(c.get("schedule_title","Your two week plan"))}</h2><p style="margin-bottom:12px">{E(c.get("schedule_intro",""))}</p>{PLAN_PROGRESS}<table>{sched}</table></section>
<section><h2>Captions</h2>{caps}<h3>Hashtags</h3><p>{E(c.get("hashtags",""))}</p></section>
{extras}{readiness}
{NEXT_CYCLE}
<footer>Questions? Just reply to the email this link came in.<br><a href="https://spotlightmysong.com">spotlightmysong.com</a></footer>
</div>
<script>document.addEventListener('click',function(e){{if(!e.target.classList.contains('copy'))return;var t=e.target.previousElementSibling.textContent;try{{navigator.clipboard.writeText(t);e.target.textContent='Copied';setTimeout(function(){{e.target.textContent='Copy'}},1500)}}catch(x){{}}}});</script>
{PLAN_JS}
</body></html>'''

def pdf_from(html_path, pdf_path):
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch(); pg = b.new_page(viewport={'width': 900, 'height': 1200})
        pg.goto('file://' + str(html_path)); pg.wait_for_timeout(800)
        pg.add_style_tag(content='.big,.dl,.copy,.prog{display:none!important} section{break-inside:auto} tr,.cap,figure{break-inside:avoid}')
        pg.pdf(path=str(pdf_path), format='Letter', print_background=True, margin={'top': '0.4in', 'bottom': '0.4in'})
        b.close()

def main(cfg_path):
    c = json.load(open(cfg_path))
    out = ROOT / 'd' / c['slug']; out.mkdir(parents=True, exist_ok=True)
    base = load_cover(c.get('cover'), c.get('clean_spots', []))
    graphics(c, base, out)
    cover_rel = None
    if c.get('cover') and os.path.exists(c['cover']):
        Image.open(c['cover']).convert('RGB').save(out/'cover.jpg', quality=88); cover_rel = 'cover.jpg'
    (out/'index.html').write_text(page(c, cover_rel))
    pdf_from(out/'index.html', out/'campaign.pdf')
    print('built', out)

if __name__ == '__main__':
    main(sys.argv[1])
