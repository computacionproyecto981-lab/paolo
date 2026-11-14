#!/usr/bin/env python3
"""Genera todo el arte WebP de Arcade 12.
Uso:  python tools/generar_arte.py
Requiere Pillow con soporte WebP. Todo el arte es procedural (dibujado por código)."""
import os, math, random
from PIL import Image, ImageDraw, ImageFilter, ImageChops

LZ = Image.Resampling.LANCZOS
S = 3  # supermuestreo para bordes suaves
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS = os.path.join(ROOT, 'assets')
HI = {}


# ------------------------------------------------------------------ utilidades
def save(img, *path, q=88):
    p = os.path.join(ASSETS, *path)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    img.save(p, 'WEBP', quality=q, method=6)
    return img


def rgba(c, a=None):
    if c is None:
        return None
    if isinstance(c, str):
        h = c.lstrip('#')
        if len(h) == 3:
            h = ''.join(ch * 2 for ch in h)
        v = (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), int(h[6:8], 16) if len(h) >= 8 else 255)
    else:
        v = tuple(c) if len(c) == 4 else (*c, 255)
    if a is not None:
        v = (*v[:3], int(a))
    return v


def mix(a, b, t):
    a, b = rgba(a), rgba(b)
    return tuple(int(round(a[i] + (b[i] - a[i]) * t)) for i in range(4))


def lit(c, t):
    x = rgba(c); return mix(x, (255, 255, 255, x[3]), t)


def dk(c, t):
    x = rgba(c); return mix(x, (0, 0, 0, x[3]), t)


def al(c, a):
    return rgba(c, a)


def comp(base, img, x, y):
    x, y = int(round(x)), int(round(y))
    sx, sy = max(0, -x), max(0, -y)
    dx, dy = max(0, x), max(0, y)
    w = min(img.width - sx, base.width - dx)
    h = min(img.height - sy, base.height - dy)
    if w <= 0 or h <= 0:
        return
    base.alpha_composite(img.crop((sx, sy, sx + w, sy + h)), (dx, dy))


class C:
    def __init__(s, w, h, bg=None, sc=S):
        s.w, s.h, s.s = w, h, sc
        s.im = Image.new('RGBA', (int(w * sc), int(h * sc)), rgba(bg) if bg else (0, 0, 0, 0))
        s.d = ImageDraw.Draw(s.im)

    def _b(s, b): return [v * s.s for v in b]
    def _p(s, pts): return [(x * s.s, y * s.s) for x, y in pts]
    def _w(s, w): return max(1, int(round(w * s.s)))

    def ell(s, box, fill=None, ol=None, w=1):
        s.d.ellipse(s._b(box), fill=rgba(fill), outline=rgba(ol), width=s._w(w)); return s

    def circ(s, x, y, r, fill=None, ol=None, w=1):
        return s.ell((x - r, y - r, x + r, y + r), fill, ol, w)

    def rect(s, box, fill=None, ol=None, w=1, r=0):
        x0, y0, x1, y1 = box
        s.d.rounded_rectangle(s._b((min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))), radius=r * s.s,
                              fill=rgba(fill), outline=rgba(ol), width=s._w(w)); return s

    def poly(s, pts, fill=None, ol=None, w=1):
        s.d.polygon(s._p(pts), fill=rgba(fill), outline=rgba(ol), width=s._w(w)); return s

    def line(s, pts, fill, w=1):
        s.d.line(s._p(pts), fill=rgba(fill), width=s._w(w), joint='curve'); return s

    def arc(s, box, a0, a1, fill, w=1):
        s.d.arc(s._b(box), a0, a1, fill=rgba(fill), width=s._w(w)); return s

    def chord(s, box, a0, a1, fill):
        s.d.chord(s._b(box), a0, a1, fill=rgba(fill)); return s

    def pie(s, box, a0, a1, fill):
        s.d.pieslice(s._b(box), a0, a1, fill=rgba(fill)); return s

    def new(s): return C(s.w, s.h, sc=s.s)

    def put(s, o, x=0, y=0):
        comp(s.im, o.im if isinstance(o, C) else o, x * s.s, y * s.s); return s

    def blur(s, r):
        s.im = s.im.filter(ImageFilter.GaussianBlur(r * s.s)); s.d = ImageDraw.Draw(s.im); return s

    def out(s, w=None, h=None):
        return s.im.resize((w or int(s.w), h or int(s.h)), LZ)


def grad(w, h, stops, angle='v'):
    n = 256
    strip = Image.new('RGBA', (n, 1))
    px = strip.load()
    st = [(t, rgba(c)) for t, c in stops]
    for i in range(n):
        t = i / (n - 1)
        col = st[-1][1] if t > st[-1][0] else st[0][1]
        for j in range(len(st) - 1):
            a, ca = st[j]; b, cb = st[j + 1]
            if a <= t <= b:
                col = mix(ca, cb, (t - a) / (b - a) if b > a else 0); break
        px[i, 0] = col
    if angle == 'v':
        strip = strip.transpose(Image.Transpose.ROTATE_270)
    return strip.resize((max(1, int(w)), max(1, int(h))), Image.BILINEAR)


def gfill(c, draw, stops, box, angle='v'):
    m = c.new(); draw(m)
    g = Image.new('RGBA', c.im.size, (0, 0, 0, 0))
    x0, y0, x1, y1 = box
    comp(g, grad((x1 - x0) * c.s + 2, (y1 - y0) * c.s + 2, stops, angle), x0 * c.s - 1, y0 * c.s - 1)
    g.putalpha(ImageChops.multiply(g.getchannel('A'), m.im.getchannel('A')))
    c.im.alpha_composite(g); return c


def radial(r, color, alpha=255, power=2.0, sc=1):
    size = max(2, int(2 * r * sc))
    g = Image.radial_gradient('L').resize((size, size), Image.BILINEAR)
    a = g.point([int(alpha * max(0.0, 1 - v / 255.0) ** power) for v in range(256)])
    im = Image.new('RGBA', (size, size), rgba(color)); im.putalpha(a); return im


def glow(c, x, y, r, color, alpha=255, power=2.0):
    comp(c.im, radial(r, color, alpha, power, c.s), (x - r) * c.s, (y - r) * c.s); return c


def noise(w, h, base, amt=.12, grain=1, blur=0, seed=None):
    if seed is not None:
        random.seed(seed)
    n = Image.effect_noise((max(1, int(w // grain)), max(1, int(h // grain))), 48)
    if grain > 1:
        n = n.resize((int(w), int(h)), Image.BICUBIC)
    if blur:
        n = n.filter(ImageFilter.GaussianBlur(blur))
    return Image.composite(Image.new('RGBA', (int(w), int(h)), lit(base, amt)),
                           Image.new('RGBA', (int(w), int(h)), dk(base, amt)), n)


def tex_fill(c, draw, tex):
    m = c.new(); draw(m)
    t = tex.copy(); t.putalpha(ImageChops.multiply(t.getchannel('A'), m.im.getchannel('A')))
    c.im.alpha_composite(t)


def shadow(c, draw, blur=3, dx=0, dy=3, a=130):
    m = c.new(); draw(m)
    sh = Image.new('RGBA', c.im.size, (0, 0, 0, 255)); sh.putalpha(m.im.getchannel('A').point(lambda v: v * a // 255))
    sh = sh.filter(ImageFilter.GaussianBlur(blur * c.s))
    comp(c.im, sh, dx * c.s, dy * c.s)


def vignette(c, strength=190, p=2.2, reach=.9):
    g = Image.radial_gradient('L').resize(c.im.size, Image.BILINEAR)
    a = g.point([int(strength * min(1, (v / 255) / reach) ** p) for v in range(256)])
    l = Image.new('RGBA', c.im.size, (0, 0, 0, 255)); l.putalpha(a); c.im.alpha_composite(l)


def bb(pts):
    xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
    return (min(xs), min(ys), max(xs), max(ys))


def star_pts(cx, cy, R, r, n=5, rot=-math.pi / 2):
    return [(cx + (R if i % 2 == 0 else r) * math.cos(rot + i * math.pi / n),
             cy + (R if i % 2 == 0 else r) * math.sin(rot + i * math.pi / n)) for i in range(2 * n)]


def stars(c, n, area=None, maxr=1.6, color='#ffffff', seed=1):
    rnd = random.Random(seed)
    x0, y0, x1, y1 = area or (0, 0, c.w, c.h)
    for _ in range(n):
        x, y = rnd.uniform(x0, x1), rnd.uniform(y0, y1)
        r = rnd.random() ** 3 * maxr + .35
        c.circ(x, y, r, fill=al(color, int(rnd.uniform(90, 255))))
        if r > 1.1:
            glow(c, x, y, r * 6, color, 70)


def bg_base(w, h, stops, sc=2):
    c = C(w, h, sc=sc)
    c.im = grad(w * sc, h * sc, stops); c.d = ImageDraw.Draw(c.im); return c


def blobs(c, items, blur):
    l = c.new()
    for x, y, rx, ry, col, a in items:
        l.ell((x - rx, y - ry, x + rx, y + ry), fill=al(col, a))
    l.blur(blur); c.put(l)


def fin(key, c, *path, q=90):
    HI[key] = c.im
    img = c.out(); save(img, *path, q=q); return img


def leaf_pts(cx, cy, L, W, ang):
    pts = []
    for i in range(13):
        t = i / 12; pts.append((t * L, W * math.sin(math.pi * t) * (1 - .3 * t)))
    for i in range(12, -1, -1):
        t = i / 12; pts.append((t * L, -W * math.sin(math.pi * t) * (1 - .3 * t)))
    ca, sa = math.cos(ang), math.sin(ang)
    return [(cx + x * ca - y * sa, cy + x * sa + y * ca) for x, y in pts]


def tree(size, cols, seed=1):
    c = C(size, size); s = size; rnd = random.Random(seed)
    shadow(c, lambda m: m.circ(s * .5, s * .5, s * .4, fill='#000'), blur=s * .05, dx=s * .06, dy=s * .08, a=140)
    for (dx, dy, r) in [(0, 0, .40), (-.13, -.12, .26), (.15, -.08, .24), (-.06, .15, .25), (.14, .14, .22)]:
        x, y, R = s * (.5 + dx), s * (.5 + dy), s * r
        gfill(c, lambda m, x=x, y=y, R=R: m.circ(x, y, R, fill='#fff'), [(0, cols[0]), (1, cols[1])], (x - R, y - R, x + R, y + R))
    for _ in range(14):
        a = rnd.uniform(0, 6.28); d = rnd.uniform(0, s * .3)
        c.circ(s * .5 + math.cos(a) * d - s * .04, s * .5 + math.sin(a) * d - s * .04, s * rnd.uniform(.03, .06), fill=al(lit(cols[0], .25), 140))
    glow(c, s * .4, s * .38, s * .2, '#ffffff', 50)
    return c


# ------------------------------------------------------------ 1 · CRIPTA
def g_cripta():
    base = '#3b4050'
    for k in range(2):
        c = C(64, 64)
        c.im.paste(noise(64 * S, 64 * S, mix(base, '#4a4038', k * .45), .07, grain=3, blur=2), (0, 0))
        rnd = random.Random(10 + k)
        c.rect((0, 0, 64, 64), ol=dk(base, .45), w=1.5)
        c.line([(1.5, 1.5), (62.5, 1.5)], lit(base, .14), 1)
        c.line([(1.5, 1.5), (1.5, 62.5)], lit(base, .08), 1)
        for _ in range(2):
            x, y = rnd.uniform(10, 54), rnd.uniform(10, 54); pts = [(x, y)]
            for _ in range(3):
                x += rnd.uniform(-9, 9); y += rnd.uniform(-9, 9); pts.append((x, y))
            c.line(pts, al(dk(base, .5), 150), .8)
        fin(f'cr_floor{k}', c, 'cripta', f'floor{k}.webp')

    c = C(64, 64, bg='#1f1816'); rnd = random.Random(3)
    for i, (y0, y1) in enumerate([(0, 16), (16, 32), (32, 48), (48, 64)]):
        off = 0 if i % 2 == 0 else -16
        for x in range(off, 64, 32):
            col = mix('#6b5446', '#8c7460', rnd.random())
            c.rect((x + 1, y0 + 1, x + 31, y1 - 1), fill=col, r=2)
            c.line([(x + 3, y0 + 2), (x + 29, y0 + 2)], lit(col, .2), 1)
            c.line([(x + 3, y1 - 2), (x + 29, y1 - 2)], dk(col, .3), 1)
    ov = noise(64 * S, 64 * S, '#808080', .35, grain=2); ov.putalpha(45); c.im.alpha_composite(ov)
    fin('cr_wall', c, 'cripta', 'wall.webp')

    for on in (False, True):
        c = C(64, 64)
        if on:
            glow(c, 32, 32, 34, '#57ffb0', 150)
        shadow(c, lambda m: m.rect((6, 8, 60, 62), fill='#000', r=8), blur=2.5, dy=2)
        c.rect((5, 5, 59, 59), fill='#5a3414', r=7)
        wa, wb = ('#c98a4a', '#93561f') if not on else ('#b9c96a', '#6f8a2c')
        gfill(c, lambda m: m.rect((8, 8, 56, 56), fill='#fff', r=5), [(0, wa), (1, wb)], (8, 8, 56, 56))
        for y in (24, 40):
            c.line([(9, y), (55, y)], '#5d3313', 2)
        c.poly([(10, 15), (15, 10), (54, 49), (49, 54)], fill=lit(wb, .15), ol='#5d3313', w=1.5)
        c.rect((8, 8, 56, 56), ol='#5d3313', w=2, r=5)
        for (x, y) in [(5, 5), (49, 5), (5, 49), (49, 49)]:
            gfill(c, lambda m, x=x, y=y: m.rect((x, y, x + 10, y + 10), fill='#fff', r=2), [(0, '#eef0f5'), (1, '#7d828f')], (x, y, x + 10, y + 10))
            c.circ(x + 5, y + 5, 1.6, fill='#41454e')
        c.line([(12, 9), (52, 9)], al('#ffe8c4', 130), 1)
        if on:
            glow(c, 32, 32, 14, '#c8ffe4', 230)
            c.poly(star_pts(32, 32, 7, 3, 4, 0), fill='#f4fff9')
        fin('cr_boxon' if on else 'cr_box', c, 'cripta', 'boxon.webp' if on else 'box.webp')

    c = C(64, 64)
    glow(c, 32, 32, 30, '#ffc23d', 120)
    c.circ(32, 32, 16, ol='#ffd56b', w=2.5)
    c.circ(32, 32, 10, ol=al('#ffd56b', 170), w=1.2)
    c.poly([(32, 25), (39, 32), (32, 39), (25, 32)], fill='#fff1b8')
    for a in range(0, 360, 45):
        r = math.radians(a)
        c.line([(32 + math.cos(r) * 19, 32 + math.sin(r) * 19), (32 + math.cos(r) * 24, 32 + math.sin(r) * 24)], al('#ffd56b', 200), 1.5)
    fin('cr_target', c, 'cripta', 'target.webp')

    c = C(64, 64)
    shadow(c, lambda m: m.ell((14, 52, 50, 62), fill='#000'), blur=2, dy=0, a=120)
    for x in (22, 34):
        c.rect((x, 44, x + 8, 56), fill='#3a2a4f', r=3)
        c.rect((x - 2, 53, x + 9, 60), fill='#2a1d14', r=3)
    gfill(c, lambda m: m.rect((17, 30, 47, 52), fill='#fff', r=9), [(0, '#45e0d0'), (1, '#1a7f7a')], (17, 30, 47, 52))
    c.rect((17, 44, 47, 48), fill='#5b3a1f'); c.rect((29, 43.5, 35, 48.5), fill='#ffd56b', r=1)
    for x in (11, 46):
        c.rect((x, 32, x + 7, 46), fill='#2fb5a8', r=3.5); c.circ(x + 3.5, 47, 3.5, fill='#f0c49a')
    gfill(c, lambda m: m.circ(32, 22, 13, fill='#fff'), [(0, '#ffe2c2'), (1, '#e5ab80')], (19, 9, 45, 35))
    for x in (27, 37):
        c.ell((x - 2.2, 20, x + 2.2, 26.5), fill='#2b1a10'); c.circ(x - .6, 21.6, .9, fill='#fff')
    c.circ(23, 27, 2.6, fill=al('#ff8a8a', 90)); c.circ(41, 27, 2.6, fill=al('#ff8a8a', 90))
    c.arc((28, 25, 36, 31), 20, 160, '#7a3b22', 1.3)
    gfill(c, lambda m: m.chord((17, 5, 47, 35), 180, 360, fill='#fff'), [(0, '#ffd84d'), (1, '#e3920f')], (17, 5, 47, 20))
    c.rect((15, 18, 49, 22), fill='#c97f0c', r=2)
    glow(c, 32, 11, 11, '#fff6b0', 210)
    c.circ(32, 11, 4, fill='#fffbe6', ol='#b87309', w=1)
    fin('cr_player', c, 'cripta', 'player.webp')

    c = bg_base(1280, 720, [(0, '#1d1724'), (1, '#09080c')])
    glow(c, 640, 360, 640, '#4a3326', 130, 1.4)
    for x in (90, 1190):
        glow(c, x, 150, 260, '#ff8c2a', 90, 1.6); glow(c, x, 150, 40, '#ffd27a', 200)
    l = c.new(); rnd = random.Random(5)
    for _ in range(26):
        x, y, w, h = rnd.uniform(0, 1280), rnd.uniform(0, 720), rnd.uniform(80, 220), rnd.uniform(40, 120)
        l.rect((x, y, x + w, y + h), fill=al('#2a2230', 90), r=8)
    l.blur(18); c.put(l)
    stars(c, 120, color='#ffcf8a', maxr=1.2, seed=8)
    vignette(c, 220)
    return fin('cr_bg', c, 'cripta', 'bg.webp', q=82)


# ------------------------------------------------------------ 2 · SALTO LUNAR
def g_lunar():
    c = bg_base(1280, 720, [(0, '#080420'), (.55, '#2b1460'), (1, '#7a3a9c')])
    stars(c, 280, (0, 0, 1280, 480), seed=2)
    glow(c, 980, 190, 300, '#c9b6ff', 90, 1.6)
    gfill(c, lambda m: m.circ(980, 190, 95, fill='#fff'), [(0, '#fbf7ff'), (1, '#cbbcf0')], (885, 95, 1075, 285))
    for (x, y, r) in [(950, 160, 18), (1010, 220, 24), (1015, 150, 10), (945, 230, 9), (990, 255, 7)]:
        c.circ(x, y, r, fill=al('#b9a8e6', 55)); c.circ(x + 1.5, y + 1.5, r * .8, fill=al('#e4dbff', 45))
    for li, (by, amp, col) in enumerate([(430, 130, '#3a2170'), (505, 95, '#2a1755'), (575, 70, '#1b0f3b')]):
        rnd = random.Random(li + 4); pts = [(0, 720)]; x = 0
        while x <= 1280:
            pts.append((x, by - rnd.uniform(0, amp))); x += rnd.uniform(40, 110)
        pts += [(1280, by - rnd.uniform(0, amp)), (1280, 720)]
        c.poly(pts, fill=col)
        haze = c.new(); haze.rect((0, by - 20, 1280, by + 60), fill=al('#b47cff', 40)); haze.blur(30); c.put(haze)
    lunar_bg = fin('lu_bg', c, 'lunar', 'bg.webp', q=82)

    for top in (True, False):
        c = C(48, 48)
        c.im.paste(noise(48 * S, 48 * S, '#3d2b6b', .1, grain=4, blur=1), (0, 0))
        rnd = random.Random(7 if top else 9)
        for _ in range(5):
            x, y, r = rnd.uniform(4, 44), rnd.uniform(14 if top else 4, 44), rnd.uniform(2, 4)
            c.circ(x, y, r, fill='#2e2054'); c.circ(x - .6, y - .6, r * .6, fill='#53408a')
        if top:
            gfill(c, lambda m: m.rect((0, 0, 48, 12), fill='#fff'), [(0, '#a8fff6'), (1, '#24b0a8')], (0, 0, 48, 12))
            for x in range(2, 48, 9):
                c.poly([(x, 11), (x + 6, 11), (x + 3, 17)], fill='#24b0a8')
            c.line([(0, .8), (48, .8)], al('#ffffff', 200), 1.2)
            for x in range(4, 48, 12):
                c.poly([(x, 1), (x + 2, -2), (x + 4, 1)], fill='#d6fffb')
        fin('lu_top' if top else 'lu_dirt', c, 'lunar', 'ground.webp' if top else 'dirt.webp')

    c = C(48, 48)
    shadow(c, lambda m: m.ell((12, 42, 36, 48), fill='#000'), blur=1.5, dy=0, a=110)
    c.rect((9, 18, 18, 34), fill='#8b95ad', r=3); c.rect((10, 20, 13, 32), fill='#b3bcd2', r=1.5)
    gfill(c, lambda m: m.rect((14, 19, 34, 38), fill='#fff', r=7), [(0, '#ffffff'), (1, '#b9c4dc')], (14, 19, 34, 38))
    for x in (16, 26):
        c.rect((x, 35, x + 6, 45), fill='#dfe5f2', r=3); c.rect((x - 1, 42, x + 7, 47), fill='#56607a', r=2.5)
    c.rect((27, 24, 37, 30), fill='#e6ebf6', r=3); c.circ(38, 27, 3, fill='#b9c4dc')
    c.circ(20, 28, 2.4, fill='#ff8a3d')
    gfill(c, lambda m: m.circ(25, 14, 12, fill='#fff'), [(0, '#ffffff'), (1, '#c9d2e6')], (13, 2, 37, 26))
    gfill(c, lambda m: m.ell((21, 8, 36, 21), fill='#fff'), [(0, '#7ff9ff'), (1, '#1a5fb0')], (21, 8, 36, 21))
    c.ell((24, 9.5, 31, 13.5), fill=al('#ffffff', 170))
    c.line([(18, 4), (15, -1)], '#c9d2e6', 1.2); glow(c, 15, 0, 4, '#ff5fd2', 255); c.circ(15, 0, 1.5, fill='#ffd0f4')
    fin('lu_player', c, 'lunar', 'player.webp')

    c = C(32, 32)
    glow(c, 16, 16, 16, '#ffd84d', 170)
    gfill(c, lambda m: m.poly(star_pts(16, 16.5, 12, 5.2), fill='#fff'), [(0, '#fff6b0'), (1, '#ffaa00')], (4, 4, 28, 28))
    c.poly(star_pts(16, 16.5, 12, 5.2), ol='#c97a00', w=.8)
    c.poly(star_pts(14.5, 14, 4, 1.8), fill=al('#ffffff', 200))
    fin('lu_gem', c, 'lunar', 'gem.webp')

    c = C(48, 48)
    for i in range(3):
        x = 2 + i * 15
        gfill(c, lambda m, x=x: m.poly([(x, 48), (x + 7, 20), (x + 14, 48)], fill='#fff'), [(0, '#ffffff'), (1, '#7a7f96')], (x, 20, x + 14, 48), 'h')
        c.poly([(x, 48), (x + 7, 20), (x + 14, 48)], ol='#4a4e63', w=.8)
    fin('lu_spike', c, 'lunar', 'spike.webp')

    c = C(48, 48)
    shadow(c, lambda m: m.ell((8, 42, 40, 48), fill='#000'), blur=1.5, dy=0, a=110)
    gfill(c, lambda m: (m.ell((5, 14, 43, 46), fill='#fff'), m.rect((5, 32, 43, 45), fill='#fff', r=6)), [(0, '#ff8ab0'), (1, '#c01c5a')], (5, 14, 43, 46))
    c.ell((12, 18, 22, 24), fill=al('#ffffff', 120))
    for x in (17, 31):
        c.ell((x - 5, 25, x + 5, 35), fill='#fff'); c.circ(x + 1, 31, 2.8, fill='#2a0a1a')
    c.line([(11, 22), (21, 26)], '#5a0a2a', 2); c.line([(37, 22), (27, 26)], '#5a0a2a', 2)
    c.arc((18, 35, 30, 42), 200, 340, '#5a0a2a', 1.5)
    fin('lu_enemy', c, 'lunar', 'enemy.webp')

    c = C(64, 96)
    glow(c, 32, 50, 46, '#ff4fd8', 170, 1.5)
    gfill(c, lambda m: m.ell((14, 14, 50, 86), fill='#fff'), [(0, '#1c0638'), (.5, '#7a24d6'), (1, '#1c0638')], (14, 14, 50, 86))
    for i, a in enumerate((0, 60, 120, 180, 240, 300)):
        c.arc((18 + i, 20 + i * 2, 46 - i, 80 - i * 2), a, a + 90, al('#ffb3f2', 200 - i * 25), 1.5)
    c.ell((10, 8, 54, 92), ol='#ffb3f2', w=3.5); c.ell((12, 10, 52, 90), ol=al('#ffffff', 160), w=1)
    glow(c, 32, 50, 12, '#ffffff', 160)
    fin('lu_portal', c, 'lunar', 'portal.webp')
    return lunar_bg


# ------------------------------------------------------------ 3 · NÉBULA
def g_nebula():
    c = bg_base(720, 640, [(0, '#04050d'), (1, '#0a0b24')], sc=1)
    rnd = random.Random(11)
    blobs(c, [(rnd.uniform(0, 720), rnd.uniform(0, 640), rnd.uniform(120, 260), rnd.uniform(80, 200),
               rnd.choice(['#5a2bd6', '#1f6fd1', '#c2257a', '#13a39a', '#3b1a8a']), rnd.randint(60, 120)) for _ in range(14)], 55)
    stars(c, 320, seed=12, maxr=1.8)
    top = c.out()
    full = Image.new('RGBA', (720, 1280)); full.paste(top, (0, 0)); full.paste(top.transpose(Image.Transpose.FLIP_TOP_BOTTOM), (0, 640))
    save(full, 'nebula', 'bg.webp', q=82)

    c = C(64, 64)
    glow(c, 25, 58, 10, '#33e1ff', 230); glow(c, 39, 58, 10, '#33e1ff', 230)
    wing = [(32, 16), (60, 46), (57, 53), (38, 46), (26, 46), (7, 53), (4, 46)]
    gfill(c, lambda m: m.poly(wing, fill='#fff'), [(0, '#6b7da3'), (1, '#262f4d')], bb(wing))
    c.poly([(48, 38), (58, 47), (55, 51), (46, 45)], fill='#ff3d6e'); c.poly([(16, 38), (6, 47), (9, 51), (18, 45)], fill='#ff3d6e')
    body = [(32, 2), (40, 24), (40, 50), (32, 57), (24, 50), (24, 24)]
    gfill(c, lambda m: m.poly(body, fill='#fff'), [(0, '#5c6a8a'), (.5, '#f4f7ff'), (1, '#5c6a8a')], bb(body), 'h')
    c.poly(body, ol='#1b2238', w=.8)
    gfill(c, lambda m: m.ell((28, 15, 36, 33), fill='#fff'), [(0, '#b5fbff'), (1, '#1592d1')], (28, 15, 36, 33))
    c.ell((29.5, 17, 32, 23), fill=al('#ffffff', 190))
    c.circ(5, 46, 1.6, fill='#ff3d6e'); c.circ(59, 46, 1.6, fill='#3dffb0')
    fin('ne_ship', c, 'nebula', 'ship.webp')

    c = C(48, 48)
    glow(c, 24, 28, 22, '#ff3d55', 80)
    gfill(c, lambda m: m.ell((14, 8, 34, 30), fill='#fff'), [(0, '#ffe0e0'), (1, '#ff6b6b')], (14, 8, 34, 30))
    gfill(c, lambda m: m.ell((3, 19, 45, 35), fill='#fff'), [(0, '#ff6b6b'), (1, '#7a1028')], (3, 19, 45, 35))
    c.ell((3, 19, 45, 35), ol='#4a0818', w=1)
    for x in (10, 18, 24, 30, 38):
        glow(c, x, 28, 4, '#ffe14d', 200); c.circ(x, 28, 1.6, fill='#fff7c2')
    c.ell((18, 11, 24, 16), fill=al('#ffffff', 170))
    fin('ne_a', c, 'nebula', 'enemy_a.webp')

    c = C(48, 48)
    for side in (-1, 1):
        w = [(24, 18), (24 + side * 22, 6), (24 + side * 20, 22), (24 + side * 10, 28)]
        c.poly(w, fill=al('#8cffc9', 120), ol=al('#d8fff0', 200), w=.8)
        c.line([(24 + side * 6, 34), (24 + side * 12, 46)], '#2a8a4f', 2.2)
    gfill(c, lambda m: m.ell((15, 6, 33, 40), fill='#fff'), [(0, '#6dff9d'), (1, '#0f6b3a')], (15, 6, 33, 40))
    for y in (15, 22, 29):
        c.arc((15, y - 4, 33, y + 4), 20, 160, al('#0a4527', 200), 1)
    glow(c, 20, 36, 4, '#ff2d2d', 230); glow(c, 28, 36, 4, '#ff2d2d', 230)
    c.circ(20, 36, 1.8, fill='#ffd0d0'); c.circ(28, 36, 1.8, fill='#ffd0d0')
    fin('ne_b', c, 'nebula', 'enemy_b.webp')

    c = C(64, 64)
    glow(c, 32, 34, 28, '#b04dff', 90)
    hull = [(32, 60), (54, 44), (60, 18), (46, 6), (18, 6), (4, 18), (10, 44)]
    gfill(c, lambda m: m.poly(hull, fill='#fff'), [(0, '#5a2a8a'), (1, '#1d0b33')], bb(hull))
    c.poly(hull, ol='#c78bff', w=1.2)
    for pts in ([(10, 18), (22, 12), (24, 30), (12, 34)], [(54, 18), (42, 12), (40, 30), (52, 34)]):
        gfill(c, lambda m, p=pts: m.poly(p, fill='#fff'), [(0, '#8d5ad0'), (1, '#40206a')], bb(pts))
    glow(c, 32, 36, 12, '#ff4fd8', 255); c.circ(32, 36, 5, fill='#ffe0fa')
    c.rect((29, 46, 35, 62), fill='#2a1240', r=2)
    fin('ne_c', c, 'nebula', 'enemy_c.webp')

    c = C(220, 160)
    glow(c, 110, 80, 110, '#ff2d55', 70, 1.5)
    hull = [(110, 150), (170, 120), (214, 70), (196, 30), (150, 14), (70, 14), (24, 30), (6, 70), (50, 120)]
    gfill(c, lambda m: m.poly(hull, fill='#fff'), [(0, '#7a1630'), (1, '#1a050c')], bb(hull))
    c.poly(hull, ol='#ff7a95', w=1.5)
    for x in (40, 180):
        gfill(c, lambda m, x=x: m.ell((x - 22, 48, x + 22, 98), fill='#fff'), [(0, '#a83355'), (1, '#3a0a18')], (x - 22, 48, x + 22, 98))
        c.rect((x - 5, 90, x + 5, 118), fill='#2a0a14', r=2); c.circ(x, 118, 4, fill='#ff4f6d')
    for x in range(60, 170, 14):
        c.circ(x, 30, 2.4, fill='#ffd84d')
    glow(c, 110, 78, 38, '#ffb347', 255); c.circ(110, 78, 18, fill='#fff2c8', ol='#ff7a2a', w=3)
    c.circ(110, 78, 8, fill='#ffffff')
    fin('ne_boss', c, 'nebula', 'boss.webp')

    for name, col, icon in (('p_weapon', '#ff9f1c', 'bolt'), ('p_shield', '#36c5ff', 'ring'), ('p_heal', '#3dff9a', 'plus')):
        c = C(32, 32)
        glow(c, 16, 16, 16, col, 200)
        gfill(c, lambda m: m.circ(16, 16, 11, fill='#fff'), [(0, lit(col, .5)), (1, dk(col, .35))], (5, 5, 27, 27))
        c.circ(16, 16, 11, ol='#ffffff', w=1.2)
        if icon == 'bolt':
            c.poly([(17, 8), (11, 17), (15.5, 17), (14, 24), (21, 14), (16.5, 14)], fill='#fff')
        elif icon == 'ring':
            c.circ(16, 16, 5.5, ol='#fff', w=2.2)
        else:
            c.rect((14, 9.5, 18, 22.5), fill='#fff', r=1); c.rect((9.5, 14, 22.5, 18), fill='#fff', r=1)
        c.ell((10, 8, 16, 12), fill=al('#ffffff', 140))
        fin('ne_' + name, c, 'nebula', name + '.webp')
    return top


# ------------------------------------------------------------ 4 · GEMAS
def gem_img(color, n, rot, sx=1, sy=1, cy_off=0, size=80):
    c = C(size, size); cx, cy = size / 2, size / 2 + cy_off; R = size * .43
    outer = [(cx + R * sx * math.cos(rot + 2 * math.pi * i / n), cy + R * sy * math.sin(rot + 2 * math.pi * i / n)) for i in range(n)]
    inner = [(cx + (x - cx) * .52, cy + (y - cy) * .52) for x, y in outer]
    shadow(c, lambda m: m.poly(outer, fill='#000'), blur=2.5, dy=3, a=150)
    c.poly(outer, fill=dk(color, .3))
    lx, ly = -.55, -.83
    for i in range(n):
        a, b = outer[i], outer[(i + 1) % n]; ia, ib = inner[i], inner[(i + 1) % n]
        mx, my = (a[0] + b[0]) / 2 - cx, (a[1] + b[1]) / 2 - cy; L = math.hypot(mx, my) or 1
        d = (mx * lx + my * ly) / L
        col = lit(color, .5 * d) if d > 0 else dk(color, -.45 * d)
        c.poly([a, b, ib, ia], fill=col)
    gfill(c, lambda m: m.poly(inner, fill='#fff'), [(0, lit(color, .45)), (1, color)], bb(inner))
    for i in range(n):
        c.line([outer[i], inner[i]], al(lit(color, .55), 130), .8)
    c.poly(outer, ol=dk(color, .55), w=1.3); c.poly(inner, ol=al(lit(color, .7), 170), w=.8)
    hx, hy = cx - R * .3, cy - R * .32
    c.ell((hx - 7, hy - 4, hx + 5, hy + 3), fill=al('#ffffff', 160))
    glow(c, hx + 14, hy - 4, 7, '#ffffff', 220)
    c.poly(star_pts(hx + 14, hy - 4, 5, 1, 4, 0), fill='#ffffff')
    return c


def g_gemas():
    specs = [('#ff2d55', 8, math.pi / 8, 1, 1, 0), ('#2e8bff', 4, -math.pi / 2, .85, 1.08, 0),
             ('#22d67a', 6, 0, 1, 1, 0), ('#ffc21a', 3, -math.pi / 2, 1.12, 1.12, 5),
             ('#b04dff', 5, -math.pi / 2, 1.04, 1.04, 2), ('#ff8a1f', 12, 0, 1, 1, 0)]
    for i, sp in enumerate(specs):
        fin(f'ge_{i}', gem_img(*sp), 'gemas', f'gem{i}.webp')
    c = bg_base(1280, 720, [(0, '#071a24'), (.5, '#140f33'), (1, '#05060f')])
    rnd = random.Random(21)
    blobs(c, [(rnd.uniform(0, 1280), rnd.uniform(0, 720), rnd.uniform(120, 300), rnd.uniform(100, 240),
               rnd.choice(['#13a39a', '#5a2bd6', '#c2257a', '#1f6fd1']), 90) for _ in range(10)], 70)
    for r in range(80, 900, 70):
        c.circ(640, 360, r, ol=al('#7ff7ff', 18), w=1)
    stars(c, 160, color='#bff9ff', seed=22)
    vignette(c, 200)
    return fin('ge_bg', c, 'gemas', 'bg.webp', q=82)


# ------------------------------------------------------------ 5 · LADRILLO NEÓN
def g_neon():
    c = bg_base(960, 640, [(0, '#0b0120'), (.45, '#3a0a5e'), (.64, '#ff3d8b'), (.645, '#0a0216'), (1, '#0a0216')])
    stars(c, 180, (0, 0, 960, 330), seed=31)
    sun = C(960, 640, sc=2)
    gfill(sun, lambda m: m.circ(480, 410, 160, fill='#fff'), [(0, '#ffe14d'), (.6, '#ff6b3d'), (1, '#ff2d95')], (320, 250, 640, 570))
    for i, y in enumerate(range(340, 420, 12)):
        sun.rect((300, y, 660, y + 2 + i * 1.3), fill=(0, 0, 0, 0))
    sun.rect((300, 412, 660, 600), fill=(0, 0, 0, 0))
    glow(c, 480, 380, 300, '#ff3d8b', 110, 1.4)
    c.put(sun)
    for li, (col, by, amp) in enumerate([('#2a0845', 412, 70), ('#1a0430', 412, 40)]):
        rnd = random.Random(40 + li); pts = [(0, 412)]; x = 0
        while x < 960:
            x += rnd.uniform(30, 80); pts.append((x, by - rnd.uniform(5, amp) * (1 - abs(x - 480) / 700)))
        pts += [(960, 412)]
        c.poly(pts, fill=col, ol=al('#ff4fd8', 160), w=1.2)
    g = C(960, 640, sc=2)
    for k in range(1, 18):
        y = 412 + (k ** 2) * 0.8
        if y > 640: break
        g.line([(0, y), (960, y)], al('#ff3df0', 200), 1.4)
    for k in range(-24, 25):
        g.line([(480 + k * 12, 412), (480 + k * 110, 640)], al('#ff3df0', 170), 1.2)
    gb = C(960, 640, sc=2); gb.im = g.im.filter(ImageFilter.GaussianBlur(6)); c.put(gb); c.put(g)
    vignette(c, 160)
    bgimg = fin('nb_bg', c, 'neon', 'bg.webp', q=84)

    cols = ['#ff3d6e', '#ff9f1c', '#ffe14d', '#3dff9a', '#2ee6ff', '#9b5cff']
    for i, col in enumerate(cols):
        c = C(80, 30)
        gfill(c, lambda m: m.rect((1, 1, 79, 29), fill='#fff', r=6), [(0, lit(col, .35)), (1, dk(col, .3))], (1, 1, 79, 29))
        c.rect((3, 3, 77, 27), ol=al(lit(col, .7), 220), w=1, r=4.5)
        c.rect((6, 4, 74, 11), fill=al('#ffffff', 75), r=3)
        c.line([(8, 25), (72, 25)], al(dk(col, .5), 120), 1)
        fin(f'nb_b{i}', c, 'neon', f'brick{i}.webp')
    c = C(80, 30)
    gfill(c, lambda m: m.rect((1, 1, 79, 29), fill='#fff', r=5), [(0, '#e7ebf2'), (.5, '#8a93a6'), (1, '#4c5466')], (1, 1, 79, 29))
    for x in range(-30, 90, 10):
        c.line([(x, 29), (x + 28, 1)], al('#ffffff', 30), 2)
    c.rect((3, 3, 77, 27), ol=al('#ffffff', 140), w=1, r=4)
    for (x, y) in [(7, 7), (73, 7), (7, 23), (73, 23)]:
        c.circ(x, y, 2, fill='#3a404d'); c.circ(x - .4, y - .4, 1, fill='#d9dee8')
    fin('nb_steel', c, 'neon', 'steel.webp')
    c = C(80, 30)
    for pts in ([(40, 15), (30, 8), (24, 2)], [(40, 15), (52, 20), (60, 28)], [(40, 15), (46, 6)], [(30, 8), (20, 12)], [(52, 20), (56, 12)]):
        c.line(pts, al('#ffffff', 220), 1.4)
    fin('nb_crack', c, 'neon', 'crack.webp')
    c = C(32, 32)
    glow(c, 16, 16, 16, '#7ff7ff', 220); c.circ(16, 16, 8, fill='#ffffff'); c.circ(14, 14, 3, fill=al('#ffffff', 255))
    fin('nb_ball', c, 'neon', 'ball.webp')
    c = C(140, 24)
    gfill(c, lambda m: m.rect((2, 3, 138, 21), fill='#fff', r=9), [(0, '#a8fbff'), (.5, '#1fb8ff'), (1, '#0b4a9a')], (2, 3, 138, 21))
    gfill(c, lambda m: m.rect((2, 3, 24, 21), fill='#fff', r=9), [(0, '#ffb3f2'), (1, '#c4157e')], (2, 3, 24, 21))
    gfill(c, lambda m: m.rect((116, 3, 138, 21), fill='#fff', r=9), [(0, '#ffb3f2'), (1, '#c4157e')], (116, 3, 138, 21))
    c.rect((26, 6, 114, 9), fill=al('#ffffff', 150), r=1.5)
    c.rect((2, 3, 138, 21), ol=al('#ffffff', 200), w=1, r=9)
    fin('nb_paddle', c, 'neon', 'paddle.webp')
    return bgimg


# ------------------------------------------------------------ 6 · BASTIÓN
def g_bastion():
    for k in range(3):
        c = C(64, 64)
        c.im.paste(noise(64 * S, 64 * S, mix('#4f8a3a', '#5a9440', k / 2), .08, grain=4, blur=2), (0, 0))
        rnd = random.Random(50 + k)
        for _ in range(26):
            x, y = rnd.uniform(0, 64), rnd.uniform(0, 64)
            col = rnd.choice(['#3d7330', '#6aa84f', '#77b85a'])
            c.line([(x, y), (x + rnd.uniform(-2, 2), y - rnd.uniform(3, 6))], col, 1)
        if k == 2:
            for _ in range(3):
                x, y = rnd.uniform(8, 56), rnd.uniform(8, 56)
                for a in range(5):
                    r = a * 1.256; c.circ(x + math.cos(r) * 2, y + math.sin(r) * 2, 1.5, fill='#fff6fb')
                c.circ(x, y, 1.2, fill='#ffd23d')
        fin(f'ba_grass{k}', c, 'bastion', f'grass{k}.webp')
    c = C(64, 64)
    c.im.paste(noise(64 * S, 64 * S, '#b88d5a', .09, grain=3, blur=1), (0, 0))
    rnd = random.Random(55)
    for _ in range(9):
        x, y, r = rnd.uniform(4, 60), rnd.uniform(4, 60), rnd.uniform(1.2, 2.8)
        c.circ(x, y, r, fill='#8f6a42'); c.circ(x - .4, y - .4, r * .55, fill='#d3ae7c')
    fin('ba_path', c, 'bastion', 'path.webp')
    fin('ba_tree', tree(64, ['#5fbf4a', '#1f5e2a'], 3), 'bastion', 'tree.webp')
    c = C(48, 48)
    shadow(c, lambda m: m.poly([(8, 34), (14, 14), (30, 8), (42, 20), (40, 38), (22, 42)], fill='#000'), blur=2, dx=2, dy=3)
    pts = [(8, 34), (14, 14), (30, 8), (42, 20), (40, 38), (22, 42)]
    gfill(c, lambda m: m.poly(pts, fill='#fff'), [(0, '#c3c8d2'), (1, '#5e6470')], bb(pts))
    c.poly([(14, 14), (30, 8), (28, 22), (18, 24)], fill=al('#ffffff', 60))
    fin('ba_rock', c, 'bastion', 'rock.webp')
    c = C(64, 64)
    shadow(c, lambda m: m.circ(32, 32, 27, fill='#000'), blur=2.5, dy=3)
    gfill(c, lambda m: m.circ(32, 32, 27, fill='#fff'), [(0, '#b9bfca'), (1, '#5d6370')], (5, 5, 59, 59))
    for a in range(0, 360, 30):
        r = math.radians(a)
        c.line([(32 + math.cos(r) * 18, 32 + math.sin(r) * 18), (32 + math.cos(r) * 27, 32 + math.sin(r) * 27)], '#4a4f5a', 1.2)
    c.circ(32, 32, 27, ol='#3c414b', w=1.5); c.circ(32, 32, 18, fill='#555b67', ol='#3c414b', w=1.2)
    fin('ba_base', c, 'bastion', 'base.webp')
    c = C(64, 64)
    c.rect((18, 29, 52, 35), fill='#7a4a22', r=2)
    c.arc((36, 12, 52, 52), 300, 60, '#5b3416', 3.2)
    c.line([(47, 14.5), (40, 32), (47, 49.5)], '#e8e2d0', .8)
    c.line([(26, 32), (58, 32)], '#d9d9d9', 1.6); c.poly([(58, 29), (63, 32), (58, 35)], fill='#e6e9ef')
    gfill(c, lambda m: m.circ(28, 32, 10, fill='#fff'), [(0, '#7fb2ff'), (1, '#1f4fbf')], (18, 22, 38, 42))
    c.circ(28, 32, 10, ol='#13307a', w=1.2); c.circ(26, 29.5, 3, fill=al('#ffffff', 150))
    fin('ba_t0', c, 'bastion', 'tower_arrow.webp')
    c = C(64, 64)
    gfill(c, lambda m: m.rect((28, 25, 60, 39), fill='#fff', r=3), [(0, '#7e8696'), (.5, '#2a2f3a'), (1, '#111318')], (28, 25, 60, 39))
    c.rect((54, 23, 61, 41), fill='#1a1d24', r=2); c.circ(61, 32, 4, fill='#050608')
    gfill(c, lambda m: m.circ(28, 32, 13, fill='#fff'), [(0, '#6b7280'), (1, '#1d2028')], (15, 19, 41, 45))
    c.circ(28, 32, 13, ol='#0e1014', w=1.3); c.circ(24, 28, 3.5, fill=al('#ffffff', 90))
    for a in range(0, 360, 60):
        r = math.radians(a); c.circ(28 + math.cos(r) * 9.5, 32 + math.sin(r) * 9.5, 1.3, fill='#a1a8b5')
    fin('ba_t1', c, 'bastion', 'tower_cannon.webp')
    c = C(64, 64)
    glow(c, 32, 32, 30, '#7ff7ff', 150)
    for a in (0, 120, 240):
        r = math.radians(a); cx, cy = 32 + math.cos(r) * 4, 32 + math.sin(r) * 4
        pts = [(cx, cy), (32 + math.cos(r - .35) * 16, 32 + math.sin(r - .35) * 16), (32 + math.cos(r) * 27, 32 + math.sin(r) * 27), (32 + math.cos(r + .35) * 16, 32 + math.sin(r + .35) * 16)]
        gfill(c, lambda m, p=pts: m.poly(p, fill='#fff'), [(0, '#e6ffff'), (1, '#2bb8e0')], bb(pts))
        c.poly(pts, ol='#127aa0', w=1)
    gfill(c, lambda m: m.circ(32, 32, 9, fill='#fff'), [(0, '#ffffff'), (1, '#59d9ff')], (23, 23, 41, 41))
    c.circ(32, 32, 9, ol='#127aa0', w=1)
    fin('ba_t2', c, 'bastion', 'tower_frost.webp')

    def creature(name, body, r, extra):
        c = C(40, 40)
        shadow(c, lambda m: m.circ(20, 20, r, fill='#000'), blur=1.5, dx=1.5, dy=2.5)
        extra(c, 'under')
        gfill(c, lambda m: m.circ(20, 20, r, fill='#fff'), [(0, lit(body, .3)), (1, dk(body, .35))], (20 - r, 20 - r, 20 + r, 20 + r))
        c.circ(20, 20, r, ol=dk(body, .55), w=1)
        extra(c, 'over')
        fin(name, c, 'bastion', name.split('_')[1] + '.webp')

    def goblin(c, layer):
        if layer == 'under':
            c.poly([(14, 10), (8, 2), (19, 9)], fill='#3fae3a'); c.poly([(14, 30), (8, 38), (19, 31)], fill='#3fae3a')
        else:
            c.circ(26, 16, 2.4, fill='#ffe14d'); c.circ(26, 24, 2.4, fill='#ffe14d')
            c.circ(26.8, 16, 1, fill='#000'); c.circ(26.8, 24, 1, fill='#000')
            c.line([(30, 28), (36, 33)], '#c9ced8', 1.6)
    creature('ba_goblin', '#55c94a', 10, goblin)

    def orc(c, layer):
        if layer == 'under':
            c.circ(17, 6, 7, fill='#5a4632'); c.circ(17, 34, 7, fill='#5a4632')
        else:
            c.poly([(30, 15), (35, 13), (31, 18)], fill='#fff8e0'); c.poly([(30, 25), (35, 27), (31, 22)], fill='#fff8e0')
            c.circ(27, 16, 2, fill='#ff3d3d'); c.circ(27, 24, 2, fill='#ff3d3d')
    creature('ba_orc', '#6f8a3a', 13, orc)

    def knight(c, layer):
        if layer == 'under':
            c.ell((14, 27, 30, 39), fill='#2e5bd6', ol='#ffd84d', w=1.2)
            c.poly([(8, 20), (2, 16), (2, 24)], fill='#e0233d')
        else:
            c.rect((24, 17, 31, 23), fill='#1a1d24', r=1); c.line([(10, 20), (30, 20)], al('#ffffff', 90), 1)
    creature('ba_knight', '#c9ced8', 11, knight)

    def bat(c, layer):
        if layer == 'under':
            for s in (-1, 1):
                c.poly([(20, 20), (14, 20 + s * 18), (20, 20 + s * 12), (26, 20 + s * 17), (24, 20)], fill='#5a2a8a', ol='#2a0f45', w=.8)
        else:
            c.circ(24, 17.5, 1.6, fill='#ff3d6e'); c.circ(24, 22.5, 1.6, fill='#ff3d6e')
    creature('ba_bat', '#7a3fb0', 7, bat)

    c = C(96, 96)
    shadow(c, lambda m: m.rect((10, 22, 86, 90), fill='#000', r=4), blur=3, dx=2, dy=4)
    gfill(c, lambda m: m.rect((10, 30, 86, 90), fill='#fff', r=3), [(0, '#cfd3db'), (1, '#7c8290')], (10, 30, 86, 90))
    for x in range(10, 86, 14):
        c.rect((x, 22, x + 9, 32), fill='#b5bac5', ol='#6a707c', w=1)
    for y in range(40, 90, 10):
        for x in range(10 + (y // 10 % 2) * 7, 86, 14):
            c.rect((x, y, x + 13, y + 9), ol=al('#6a707c', 150), w=.8)
    c.chord((36, 56, 60, 100), 180, 360, '#3a2416'); c.rect((36, 78, 60, 90), fill='#3a2416')
    c.line([(48, 4), (48, 24)], '#5b3416', 2); c.poly([(48, 4), (66, 9), (48, 14)], fill='#e0233d')
    fin('ba_castle', c, 'bastion', 'castle.webp')
    c = C(64, 64)
    glow(c, 32, 32, 32, '#b04dff', 200, 1.3)
    for i in range(6):
        c.arc((8 + i * 3, 8 + i * 3, 56 - i * 3, 56 - i * 3), i * 60, i * 60 + 200, al('#ffd0ff', 200 - i * 25), 2)
    c.circ(32, 32, 8, fill='#1a0530')
    fin('ba_portal', c, 'bastion', 'portal.webp')


# ------------------------------------------------------------ 7 · MEMORIA
def g_memoria():
    c = C(200, 260, sc=2)
    gfill(c, lambda m: m.rect((0, 0, 200, 260), fill='#fff', r=18), [(0, '#33227a'), (1, '#110a2e')], (0, 0, 200, 260))
    for x in range(-260, 260, 22):
        c.line([(x, 0), (x + 260, 260)], al('#e6c36a', 22), 1); c.line([(x + 260, 0), (x, 260)], al('#e6c36a', 22), 1)
    c.rect((10, 10, 190, 250), ol='#e6c36a', w=3, r=12); c.rect((18, 18, 182, 242), ol=al('#e6c36a', 120), w=1, r=8)
    glow(c, 100, 130, 70, '#ffd27a', 120)
    c.circ(100, 130, 44, fill='#1b1145', ol='#e6c36a', w=3)
    gfill(c, lambda m: m.poly(star_pts(100, 130, 34, 12, 8, -math.pi / 2), fill='#fff'), [(0, '#fff3c4'), (1, '#c9922a')], (66, 96, 134, 164))
    c.circ(100, 130, 8, fill='#fff6d8')
    for (x, y) in [(30, 30), (170, 30), (30, 230), (170, 230)]:
        c.poly(star_pts(x, y, 8, 3, 4, 0), fill='#e6c36a')
    fin('me_back', c, 'memoria', 'back.webp')

    # Cada icono se dibuja con una función propia
    def sun(c):
        glow(c, 80, 80, 78, '#ffb347', 150)
        for i in range(12):
            a = i * math.pi / 6
            pts = [(80 + math.cos(a - .14) * 44, 80 + math.sin(a - .14) * 44), (80 + math.cos(a) * 70, 80 + math.sin(a) * 70), (80 + math.cos(a + .14) * 44, 80 + math.sin(a + .14) * 44)]
            c.poly(pts, fill='#ffb020')
        gfill(c, lambda m: m.circ(80, 80, 42, fill='#fff'), [(0, '#fff4a8'), (1, '#ff8a00')], (38, 38, 122, 122))
        c.circ(66, 66, 12, fill=al('#ffffff', 120))

    def moon(c):
        glow(c, 80, 80, 74, '#9bb6ff', 120)
        m = c.new(); m.circ(80, 80, 50, fill='#fff'); m.circ(104, 66, 44, fill=(0, 0, 0, 0))
        g = C(160, 160, sc=2); gfill(g, lambda q: q.rect((0, 0, 160, 160), fill='#fff'), [(0, '#f2f6ff'), (1, '#7f98e6')], (0, 0, 160, 160))
        g.im.putalpha(m.im.getchannel('A')); c.put(g)
        c.circ(60, 98, 6, fill=al('#7f98e6', 140)); c.circ(52, 74, 4, fill=al('#7f98e6', 140))
        c.poly(star_pts(118, 112, 10, 4), fill='#fff6c4')

    def star(c):
        glow(c, 80, 82, 74, '#ffd84d', 140)
        pts = star_pts(80, 84, 62, 26)
        gfill(c, lambda m: m.poly(pts, fill='#fff'), [(0, '#fff6b0'), (1, '#ff9d00')], bb(pts))
        c.poly(pts, ol='#c76f00', w=2)
        c.poly(star_pts(72, 74, 16, 7), fill=al('#ffffff', 170))

    def heart(c):
        glow(c, 80, 84, 72, '#ff4f7b', 140)
        def h(m):
            m.circ(56, 64, 28, fill='#fff'); m.circ(104, 64, 28, fill='#fff')
            m.poly([(30, 74), (130, 74), (80, 132)], fill='#fff')
        gfill(c, h, [(0, '#ff9ab5'), (1, '#d1123f')], (28, 36, 132, 132))
        c.ell((44, 46, 64, 62), fill=al('#ffffff', 160))

    def leaf(c):
        glow(c, 80, 80, 72, '#3dff9a', 110)
        pts = leaf_pts(30, 120, 120, 34, -math.pi / 4)
        gfill(c, lambda m: m.poly(pts, fill='#fff'), [(0, '#a6ff8a'), (1, '#169a4a')], bb(pts))
        c.line([(30, 120), (112, 40)], '#0f6b34', 3)
        for t in (.3, .5, .7):
            x, y = 30 + 82 * t, 120 - 80 * t
            c.line([(x, y), (x + 18, y + 2)], '#0f6b34', 2); c.line([(x, y), (x - 2, y - 18)], '#0f6b34', 2)

    def drop(c):
        glow(c, 80, 90, 70, '#36c5ff', 140)
        def d(m):
            m.circ(80, 100, 38, fill='#fff'); m.poly([(46, 84), (80, 22), (114, 84)], fill='#fff')
        gfill(c, d, [(0, '#b5f0ff'), (1, '#0a6fd6')], (42, 22, 118, 138))
        c.ell((60, 84, 74, 112), fill=al('#ffffff', 150))

    def flame(c):
        glow(c, 80, 90, 76, '#ff6b1f', 150)
        def f(m, s):
            m.circ(80, 104, 36 * s, fill='#fff'); m.poly([(80 - 34 * s, 98), (80 + 6 * s, 104 - 92 * s), (80 + 34 * s, 98)], fill='#fff')
        gfill(c, lambda m: f(m, 1), [(0, '#ff3d1f'), (1, '#b3120a')], (40, 10, 120, 142))
        gfill(c, lambda m: f(m, .7), [(0, '#ff9f1c'), (1, '#ff5a1f')], (50, 40, 110, 132))
        gfill(c, lambda m: f(m, .4), [(0, '#fff6b0'), (1, '#ffd23d')], (62, 70, 98, 120))

    def bolt(c):
        glow(c, 80, 80, 74, '#ffe14d', 150)
        pts = [(92, 14), (40, 88), (74, 88), (62, 146), (122, 64), (86, 64), (104, 14)]
        gfill(c, lambda m: m.poly(pts, fill='#fff'), [(0, '#fffbd0'), (1, '#ffb800')], bb(pts))
        c.poly(pts, ol='#b37800', w=2)

    def crown(c):
        glow(c, 80, 86, 72, '#ffd84d', 120)
        pts = [(28, 118), (22, 50), (52, 78), (80, 36), (108, 78), (138, 50), (132, 118)]
        gfill(c, lambda m: m.poly(pts, fill='#fff'), [(0, '#fff3b0'), (1, '#d38a00')], bb(pts))
        c.rect((26, 110, 134, 128), fill='#c27c00', r=4)
        for x, col in ((52, '#ff2d55'), (80, '#2e8bff'), (108, '#22d67a')):
            c.circ(x, 119, 6, fill=col, ol='#fff3b0', w=1.2)
        for x, y in ((22, 50), (80, 36), (138, 50)):
            c.circ(x, y, 7, fill='#fff6d0')

    def gem(c):
        glow(c, 80, 80, 70, '#2ee6ff', 120)
        c.put(gem_img('#2ee6ff', 8, math.pi / 8, size=160).im.resize(c.im.size, LZ))

    def key(c):
        glow(c, 80, 80, 72, '#ffc23d', 110)
        gfill(c, lambda m: (m.circ(54, 58, 30, fill='#fff'), m.rect((70, 52, 140, 66), fill='#fff', r=3), m.rect((112, 64, 122, 88), fill='#fff', r=2), m.rect((128, 64, 138, 80), fill='#fff', r=2)),
              [(0, '#fff3b0'), (1, '#c98a00')], (24, 28, 140, 88))
        c.circ(54, 58, 13, fill=(0, 0, 0, 0)); c.circ(54, 58, 13, ol='#a06a00', w=3)
        c.ell((34, 36, 50, 48), fill=al('#ffffff', 150))

    def mushroom(c):
        glow(c, 80, 80, 72, '#ff4f6d', 110)
        gfill(c, lambda m: m.rect((62, 78, 98, 136), fill='#fff', r=14), [(0, '#fff8ec'), (1, '#e3cfae')], (62, 78, 98, 136))
        gfill(c, lambda m: m.chord((22, 26, 138, 126), 180, 360, fill='#fff'), [(0, '#ff6b6b'), (1, '#b3122a')], (22, 26, 138, 80))
        c.rect((22, 74, 138, 82), fill='#9c0f22', r=4)
        for x, y, r in ((52, 52, 9), (82, 40, 10), (112, 56, 8), (70, 64, 6)):
            c.circ(x, y, r, fill='#fff6ee')

    for name, fn in (('sun', sun), ('moon', moon), ('star', star), ('heart', heart), ('leaf', leaf), ('drop', drop),
                     ('flame', flame), ('bolt', bolt), ('crown', crown), ('gem', gem), ('key', key), ('mushroom', mushroom)):
        c = C(160, 160, sc=2)
        sh = C(160, 160, sc=2); fn(sh)
        s2 = Image.new('RGBA', sh.im.size, (0, 0, 0, 255))
        s2.putalpha(sh.im.getchannel('A').point(lambda v: min(v, 200) * 70 // 255))
        comp(c.im, s2.filter(ImageFilter.GaussianBlur(10)), 0, 12)
        fn(c)
        fin('me_' + name, c, 'memoria', name + '.webp')

    c = bg_base(1280, 720, [(0, '#1a0f3d'), (.6, '#2a1650'), (1, '#0c0720')])
    rnd = random.Random(70)
    blobs(c, [(rnd.uniform(0, 1280), rnd.uniform(0, 720), rnd.uniform(140, 300), rnd.uniform(120, 260),
               rnd.choice(['#7a3fd6', '#c2257a', '#ffb347', '#1f6fd1']), 80) for _ in range(9)], 80)
    for _ in range(40):
        x, y, s = rnd.uniform(0, 1280), rnd.uniform(0, 720), rnd.uniform(3, 9)
        c.poly(star_pts(x, y, s, s * .35, 4, 0), fill=al('#ffe7b0', rnd.randint(60, 180)))
    vignette(c, 190)
    return fin('me_bg', c, 'memoria', 'bg.webp', q=82)


# ------------------------------------------------------------ 8 · SERPIENTE
def g_serpiente():
    for k, col in enumerate(('#2f6b3a', '#356f3f')):
        c = C(32, 32)
        c.im.paste(noise(32 * S, 32 * S, col, .05, grain=3, blur=1), (0, 0))
        fin(f'se_cell{k}', c, 'serpiente', f'cell{k}.webp')
    c = C(32, 32)
    gfill(c, lambda m: m.ell((1, 3, 31, 29), fill='#fff'), [(0, '#9dff6a'), (1, '#1a8a34')], (1, 3, 31, 29))
    c.ell((1, 3, 31, 29), ol='#0f5a22', w=1)
    for y in (9, 23):
        c.circ(21, y, 4.4, fill='#ffffff'); c.circ(22.5, y, 2.4, fill='#111')
        c.circ(23.2, y - 1, .8, fill='#fff')
    c.circ(29, 13.5, .9, fill='#0f5a22'); c.circ(29, 18.5, .9, fill='#0f5a22')
    c.ell((6, 6, 14, 11), fill=al('#ffffff', 110))
    fin('se_head', c, 'serpiente', 'head.webp')
    c = C(32, 32)
    gfill(c, lambda m: m.circ(16, 16, 14, fill='#fff'), [(0, '#7dff5a'), (1, '#1a8a34')], (2, 2, 30, 30))
    c.circ(16, 16, 14, ol='#0f5a22', w=1)
    c.circ(16, 16, 6, fill=al('#d8ff6a', 160))
    c.ell((8, 6, 16, 11), fill=al('#ffffff', 110))
    fin('se_body', c, 'serpiente', 'body.webp')
    for name, a, b in (('apple', '#ff6b6b', '#b3122a'), ('gold', '#fff3a0', '#d38a00')):
        c = C(32, 32)
        if name == 'gold':
            glow(c, 16, 17, 16, '#ffd84d', 200)
        gfill(c, lambda m: (m.circ(11.5, 18, 10, fill='#fff'), m.circ(20.5, 18, 10, fill='#fff')), [(0, a), (1, b)], (1, 8, 31, 28))
        c.line([(16, 9), (17, 3)], '#5b3416', 1.6)
        c.poly(leaf_pts(17, 6, 9, 3.5, -.5), fill='#3fbf4a')
        c.ell((7, 11, 12, 16), fill=al('#ffffff', 170))
        fin('se_' + name, c, 'serpiente', name + '.webp')
    c = C(32, 32)
    pts = [(3, 24), (6, 9), (16, 3), (28, 8), (30, 22), (20, 30), (8, 30)]
    shadow(c, lambda m: m.poly(pts, fill='#000'), blur=1.5, dy=2)
    gfill(c, lambda m: m.poly(pts, fill='#fff'), [(0, '#b9bfca'), (1, '#4e5461')], bb(pts))
    c.poly([(6, 9), (16, 3), (18, 14), (9, 17)], fill=al('#ffffff', 55))
    c.line([(16, 14), (22, 22)], al('#2a2e36', 150), 1)
    fin('se_rock', c, 'serpiente', 'rock.webp')
    c = bg_base(1280, 720, [(0, '#0d2a18'), (1, '#04120a')])
    rnd = random.Random(80)
    for layer in range(3):
        l = c.new()
        for _ in range(70):
            x, y = rnd.uniform(-50, 1330), rnd.uniform(-50, 770)
            L = rnd.uniform(90, 220) * (1 + layer * .3)
            col = mix('#0f4a22', '#2f8a3f', rnd.random() * (.4 + layer * .3))
            l.poly(leaf_pts(x, y, L, L * .28, rnd.uniform(0, 6.28)), fill=al(col, 230))
        if layer < 2:
            l.blur(8 - layer * 4)
        c.put(l)
        if layer == 1:
            ov = c.new(); ov.rect((0, 0, 1280, 720), fill=al('#04120a', 110)); c.put(ov)
    for _ in range(40):
        glow(c, rnd.uniform(0, 1280), rnd.uniform(0, 720), rnd.uniform(4, 10), '#d8ff6a', 200)
    vignette(c, 210)
    return fin('se_bg', c, 'serpiente', 'bg.webp', q=80)


# ------------------------------------------------------------ 9 · TECLADO
def g_teclado():
    c = bg_base(1280, 720, [(0, '#02040f'), (.5, '#0f1a44'), (1, '#2a1650')])
    stars(c, 260, (0, 0, 1280, 420), seed=90)
    l = c.new()
    for i, col in enumerate(('#3dff9a', '#2ee6ff', '#b04dff')):
        pts = []
        for x in range(-40, 1330, 20):
            pts.append((x, 150 + i * 40 + math.sin(x / 140 + i) * 40 + math.sin(x / 57) * 12))
        l.line(pts, al(col, 120), 36)
    l.blur(26); c.put(l)
    rnd = random.Random(91)
    for layer, (col, hmin, hmax, wc) in enumerate((('#141a3a', 120, 300, '#4a5aa0'), ('#0a0d20', 80, 220, '#ffd27a'))):
        x = -20
        while x < 1300:
            w = rnd.uniform(50, 110); h = rnd.uniform(hmin, hmax); top = 660 - h
            c.rect((x, top, x + w, 720), fill=col)
            if layer == 1 and rnd.random() < .4:
                c.line([(x + w / 2, top), (x + w / 2, top - 30)], col, 2); glow(c, x + w / 2, top - 30, 6, '#ff3d55', 255)
            for wy in range(int(top) + 10, 650, 14):
                for wx in range(int(x) + 8, int(x + w) - 8, 12):
                    if rnd.random() < (.25 if layer == 0 else .35):
                        c.rect((wx, wy, wx + 5, wy + 7), fill=al(wc, rnd.randint(90, 230)))
            x += w + rnd.uniform(2, 14)
    c.rect((0, 655, 1280, 720), fill='#05060f')
    glow(c, 640, 690, 600, '#2ee6ff', 40, 2)
    vignette(c, 170)
    bgimg = fin('te_bg', c, 'teclado', 'bg.webp', q=82)

    c = C(96, 96)
    trail = C(96, 96)
    for i in range(10):
        y = 60 - i * 6; r = 20 - i * 1.6
        trail.circ(48 + math.sin(i) * 2, y, max(2, r), fill=al(mix('#ffe14d', '#ff3d1f', i / 9), 220 - i * 18))
    trail.blur(3); c.put(trail)
    glow(c, 48, 62, 34, '#ff7a2a', 170)
    pts = [(48 + math.cos(a) * (20 + random.Random(int(a * 10)).uniform(-3, 3)), 64 + math.sin(a) * (20 + random.Random(int(a * 10) + 1).uniform(-3, 3))) for a in [i * math.pi / 7 for i in range(14)]]
    gfill(c, lambda m: m.poly(pts, fill='#fff'), [(0, '#a07a6a'), (1, '#3a2620')], bb(pts))
    for (x, y, r) in ((42, 58, 5), (55, 70, 4), (40, 72, 3), (56, 56, 3)):
        c.circ(x, y, r, fill='#2a1a16'); c.arc((x - r, y - r, x + r, y + r), 200, 340, '#c99a86', 1)
    c.poly(pts, ol='#ffb347', w=1.2)
    fin('te_meteor', c, 'teclado', 'meteor.webp')
    c = C(96, 96)
    glow(c, 48, 56, 40, '#2ee6ff', 110)
    gfill(c, lambda m: m.rect((42, 10, 54, 56), fill='#fff', r=3), [(0, '#5c6a8a'), (.5, '#e9eef8'), (1, '#5c6a8a')], (42, 10, 54, 56), 'h')
    c.rect((40, 8, 56, 16), fill='#2ee6ff', r=2)
    gfill(c, lambda m: m.chord((18, 44, 78, 104), 180, 360, fill='#fff'), [(0, '#8794b0'), (1, '#262f4d')], (18, 44, 78, 74))
    c.arc((18, 44, 78, 104), 180, 360, '#9fb4e0', 1.5)
    c.rect((10, 72, 86, 80), fill='#1b2238', r=3)
    glow(c, 48, 60, 8, '#7ff7ff', 255); c.circ(48, 60, 4, fill='#e0ffff')
    fin('te_cannon', c, 'teclado', 'cannon.webp')
    return bgimg


# ------------------------------------------------------------ 10 · GOLF
def g_golf():
    c = C(128, 128, sc=1)
    for i in range(4):
        c.rect((i * 32, 0, i * 32 + 32, 128), fill='#4caf50' if i % 2 == 0 else '#43a047')
    ov = noise(128, 128, '#808080', .25, grain=1); ov.putalpha(28); c.im.alpha_composite(ov)
    grass = c.out(); save(grass, 'golf', 'grass.webp'); HI['go_grass'] = grass
    c = C(128, 128, sc=1); c.im.paste(noise(128, 128, '#e6cb8e', .08, grain=1, blur=.6), (0, 0))
    save(c.out(), 'golf', 'sand.webp')
    c = C(128, 128, sc=2); c.im.paste(noise(256, 256, '#2a8bd6', .06, grain=6, blur=3), (0, 0))
    rnd = random.Random(100)
    for _ in range(10):
        x, y = rnd.uniform(0, 128), rnd.uniform(0, 128)
        c.arc((x - 12, y - 4, x + 12, y + 4), 200, 340, al('#bfe9ff', 150), 1.2)
    save(c.out(), 'golf', 'water.webp')
    c = C(32, 32, sc=4)
    c.rect((0, 0, 32, 32), fill='#8a5a32')
    rnd = random.Random(101)
    for y in range(2, 32, 4):
        c.line([(0, y + rnd.uniform(-.5, .5)), (32, y + rnd.uniform(-.5, .5))], al('#5b3416', 120), .7)
    ov = noise(128, 128, '#808080', .3, grain=2); ov.putalpha(40); c.im.alpha_composite(ov)
    save(c.out(), 'golf', 'wood.webp')
    c = C(24, 24)
    shadow(c, lambda m: m.circ(12, 12, 8, fill='#000'), blur=1.2, dx=1.5, dy=2)
    gfill(c, lambda m: m.circ(12, 12, 8, fill='#fff'), [(0, '#ffffff'), (1, '#c9cfdb')], (4, 4, 20, 20))
    for (x, y) in ((10, 9), (14, 10), (12, 14), (9, 13), (15, 14)):
        c.circ(x, y, .7, fill=al('#9aa3b5', 160))
    c.circ(9.5, 8.5, 2.2, fill=al('#ffffff', 220))
    fin('go_ball', c, 'golf', 'ball.webp')
    c = C(32, 32)
    c.circ(16, 16, 13, fill='#2b5f2e')
    gfill(c, lambda m: m.circ(16, 16, 11, fill='#fff'), [(0, '#000000'), (1, '#1a2b1c')], (5, 5, 27, 27))
    c.arc((5, 5, 27, 27), 200, 340, al('#ffffff', 120), 1)
    fin('go_hole', c, 'golf', 'hole.webp')
    c = C(48, 80)
    c.line([(10, 78), (10, 4)], '#f2f2f2', 2.2)
    pts = [(11, 5), (40, 9), (34, 14), (42, 22), (11, 24)]
    gfill(c, lambda m: m.poly(pts, fill='#fff'), [(0, '#ff6b6b'), (1, '#c0122a')], bb(pts))
    c.circ(10, 4, 2.5, fill='#ffd84d')
    fin('go_flag', c, 'golf', 'flag.webp')
    fin('go_tree', tree(72, ['#4fbf5a', '#155a2a'], 7), 'golf', 'tree.webp')
    c = C(48, 48)
    glow(c, 24, 24, 24, '#ff4fd8', 140)
    gfill(c, lambda m: m.circ(24, 24, 16, fill='#fff'), [(0, '#ffb3f2'), (1, '#b0157a')], (8, 8, 40, 40))
    c.circ(24, 24, 16, ol='#ffffff', w=2); c.circ(24, 24, 8, ol=al('#ffffff', 160), w=1.5)
    c.ell((14, 12, 24, 18), fill=al('#ffffff', 150))
    fin('go_bumper', c, 'golf', 'bumper.webp')


# ------------------------------------------------------------ 11 · PULSO
def g_pulso():
    c = bg_base(1280, 720, [(0, '#07030f'), (.7, '#1a0630'), (1, '#2a0a3a')])
    l = c.new()
    for x0, col in ((150, '#ff3df0'), (430, '#2ee6ff'), (850, '#ffe14d'), (1130, '#3dff9a')):
        for sgn in (-1, 1):
            l.poly([(x0, -10), (x0 + 14, -10), (640 + sgn * 120 + (x0 - 640) * .3 + 180, 720), (640 + sgn * 120 + (x0 - 640) * .3 - 60, 720)], fill=al(col, 50))
    l.blur(16); c.put(l)
    for x0, col in ((150, '#ff3df0'), (430, '#2ee6ff'), (850, '#ffe14d'), (1130, '#3dff9a')):
        glow(c, x0 + 7, 0, 80, col, 200)
    glow(c, 640, 720, 600, '#ff3df0', 70, 1.5)
    rnd = random.Random(110)
    for row in range(3):
        y = 640 + row * 28
        x = -20
        while x < 1300:
            r = rnd.uniform(14, 20)
            col = mix('#05020a', '#120621', row / 3)
            c.circ(x, y - r, r * .8, fill=col); c.ell((x - r * 1.5, y - r * .3, x + r * 1.5, y + r * 3), fill=col)
            if rnd.random() < .08:
                c.line([(x + r, y - r), (x + r * 1.6, y - r * 3.5)], col, 6)
            x += r * 2.2
    vignette(c, 180)
    bgimg = fin('pu_bg', c, 'pulso', 'bg.webp', q=82)
    cols = ['#ff4f8b', '#ffb82e', '#3dff9a', '#36c5ff']
    for i, col in enumerate(cols):
        c = C(80, 80)
        glow(c, 40, 40, 40, col, 190)
        gfill(c, lambda m: m.circ(40, 40, 26, fill='#fff'), [(0, lit(col, .55)), (1, dk(col, .35))], (14, 14, 66, 66))
        c.circ(40, 40, 26, ol='#ffffff', w=2.5)
        c.circ(40, 40, 16, ol=al('#ffffff', 140), w=1.5)
        c.ell((26, 20, 46, 32), fill=al('#ffffff', 150))
        fin(f'pu_note{i}', c, 'pulso', f'note{i}.webp')
    c = C(80, 80)
    c.circ(40, 40, 30, fill=al('#000000', 120), ol=al('#ffffff', 200), w=3)
    c.circ(40, 40, 20, ol=al('#ffffff', 80), w=1.5)
    fin('pu_receptor', c, 'pulso', 'receptor.webp')
    return bgimg


# ------------------------------------------------------------ 12 · FLUJO
def g_flujo():
    c = C(96, 96)
    gfill(c, lambda m: m.rect((2, 2, 94, 94), fill='#fff', r=12), [(0, '#323b4a'), (1, '#1a2029')], (2, 2, 94, 94))
    ov = noise(96 * S, 96 * S, '#808080', .3, grain=2); ov.putalpha(18)
    tex_fill(c, lambda m: m.rect((2, 2, 94, 94), fill='#fff', r=12), ov)
    c.rect((2, 2, 94, 94), ol='#465265', w=1.5, r=12); c.rect((6, 6, 90, 90), ol=al('#000000', 120), w=1, r=9)
    for (x, y) in ((11, 11), (85, 11), (11, 85), (85, 85)):
        c.circ(x, y, 2.6, fill='#11151c'); c.circ(x - .5, y - .5, 1.4, fill='#7d8aa0')
    fin('fl_plate', c, 'flujo', 'plate.webp')

    steel = [(0, '#3f4856'), (.3, '#b8c2cf'), (.5, '#f2f5f9'), (.7, '#b8c2cf'), (1, '#3f4856')]

    def arm(wet):
        a = C(96, 96)
        gfill(a, lambda m: m.rect((34, 0, 62, 48), fill='#fff'), steel, (34, 0, 62, 48), 'h')
        gfill(a, lambda m: m.rect((30, 1, 66, 9), fill='#fff', r=2), steel, (30, 1, 66, 9), 'h')
        a.rect((30, 1, 66, 9), ol='#2a313c', w=1, r=2)
        a.line([(34, 0), (34, 48)], '#2a313c', 1); a.line([(62, 0), (62, 48)], '#2a313c', 1)
        if wet:
            gfill(a, lambda m: m.rect((41, 0, 55, 48), fill='#fff'), [(0, '#0a7fd6'), (.5, '#9ffcff'), (1, '#0a7fd6')], (41, 0, 55, 48), 'h')
        return a.im

    types = {'end': (0,), 'straight': (0, 2), 'corner': (0, 1), 'tee': (0, 1, 2), 'cross': (0, 1, 2, 3)}
    for wet in (False, True):
        A = arm(wet)
        rots = [A, A.rotate(-90), A.rotate(180), A.rotate(90)]
        for name, dirs in types.items():
            c = C(96, 96)
            sh = Image.new('RGBA', c.im.size, (0, 0, 0, 0))
            for d in dirs:
                sh.alpha_composite(rots[d])
            s2 = Image.new('RGBA', sh.size, (0, 0, 0, 255)); s2.putalpha(sh.getchannel('A').point(lambda v: v * 120 // 255))
            comp(c.im, s2.filter(ImageFilter.GaussianBlur(4 * S)), 2 * S, 4 * S)
            if wet:
                gl = Image.new('RGBA', sh.size, rgba('#2ee6ff')); gl.putalpha(sh.getchannel('A').point(lambda v: v * 90 // 255))
                comp(c.im, gl.filter(ImageFilter.GaussianBlur(6 * S)), 0, 0)
            c.im.alpha_composite(sh)
            gfill(c, lambda m: m.circ(48, 48, 21, fill='#fff'), [(0, '#e9eef4'), (1, '#4a5463')], (27, 27, 69, 69))
            c.circ(48, 48, 21, ol='#2a313c', w=1.2)
            for a in range(45, 360, 90):
                r = math.radians(a); c.circ(48 + math.cos(r) * 15, 48 + math.sin(r) * 15, 2, fill='#2a313c')
            if wet:
                glow(c, 48, 48, 18, '#7ff7ff', 230)
                c.circ(48, 48, 9, fill='#c8ffff', ol='#0a7fd6', w=1.5)
            else:
                c.circ(48, 48, 9, fill='#1a2029', ol='#2a313c', w=1.5)
            fin(f'fl_{name}{int(wet)}', c, 'flujo', f'{name}{"_wet" if wet else ""}.webp')

    c = C(96, 96)
    glow(c, 48, 48, 34, '#3dff9a', 200)
    gfill(c, lambda m: m.circ(48, 48, 22, fill='#fff'), [(0, '#a8ffcf'), (1, '#0f9a4f')], (26, 26, 70, 70))
    c.circ(48, 48, 22, ol='#ffffff', w=2)
    c.poly([(42, 37), (60, 48), (42, 59)], fill='#ffffff')
    fin('fl_source', c, 'flujo', 'source.webp')
    for on in (False, True):
        c = C(96, 96)
        if on:
            glow(c, 48, 48, 30, '#ffd84d', 220)
        gfill(c, lambda m: m.circ(48, 48, 19, fill='#fff'), [(0, '#fff3b0' if on else '#9aa3b5'), (1, '#c98a00' if on else '#3a414d')], (29, 29, 67, 67))
        c.circ(48, 48, 19, ol='#ffffff' if on else '#1a2029', w=2)
        for dx in (-8, 0, 8):
            c.rect((48 + dx - 2, 38, 48 + dx + 2, 58), fill='#1a2029' if not on else '#7a5200', r=2)
        fin(f'fl_sink{int(on)}', c, 'flujo', f'sink{"_on" if on else ""}.webp')

    c = bg_base(1280, 720, [(0, '#0b1220'), (1, '#05070d')])
    for row in range(-1, 26):
        for col in range(-1, 46):
            x = col * 30 + (row % 2) * 15; y = row * 26
            pts = [(x + 14 * math.cos(math.pi / 6 + k * math.pi / 3), y + 14 * math.sin(math.pi / 6 + k * math.pi / 3)) for k in range(6)]
            c.poly(pts, ol=al('#2ee6ff', 16), w=1)
    rnd = random.Random(120)
    blobs(c, [(rnd.uniform(0, 1280), rnd.uniform(0, 720), rnd.uniform(150, 300), rnd.uniform(100, 220),
               rnd.choice(['#0a7fd6', '#13a39a', '#3a1a8a']), 70) for _ in range(8)], 80)
    vignette(c, 200)
    return fin('fl_bg', c, 'flujo', 'bg.webp', q=82)


# ------------------------------------------------------------ PORTADAS + HUB
def cover(name, bg, items, extra=None):
    W, H = 640, 400
    c = Image.new('RGBA', (W, H), (8, 8, 16, 255))
    if bg is not None:
        b = bg.copy()
        s = max(W / b.width, H / b.height)
        b = b.resize((int(b.width * s) + 1, int(b.height * s) + 1), LZ)
        x, y = (b.width - W) // 2, (b.height - H) // 2
        c.alpha_composite(b.crop((x, y, x + W, y + H)))
    if extra:
        extra(c)
    for it in items:
        key, cx, cy, w = it[:4]
        rot = it[4] if len(it) > 4 else 0
        src = HI[key]
        h = int(src.height * w / src.width)
        im = src.resize((int(w), max(1, h)), LZ)
        if rot:
            im = im.rotate(rot, resample=Image.BICUBIC, expand=True)
        comp(c, im, cx - im.width / 2, cy - im.height / 2)
    c.alpha_composite(grad(W, H, [(0, (0, 0, 0, 0)), (.5, (0, 0, 0, 0)), (1, (0, 0, 0, 175))]))
    save(c.convert('RGB'), 'covers', name + '.webp', q=86)


def tiles(c, keys, size, cols, rows, ox=0, oy=0, pick=None):
    for y in range(rows):
        for x in range(cols):
            k = pick(x, y) if pick else keys[(x + y) % len(keys)]
            if k:
                im = HI[k].resize((size, size), LZ); comp(c, im, ox + x * size, oy + y * size)


def hub_bg():
    c = bg_base(1920, 1080, [(0, '#0a0818'), (1, '#05050b')], sc=1)
    blobs(c, [(300, 200, 420, 300, '#5a2bd6', 120), (1600, 260, 380, 280, '#c2257a', 100), (1000, 900, 520, 300, '#1f6fd1', 100), (200, 950, 300, 220, '#13a39a', 80)], 120)
    for x in range(0, 1920, 64):
        c.line([(x, 0), (x, 1080)], al('#ffffff', 8), 1)
    for y in range(0, 1080, 64):
        c.line([(0, y), (1920, y)], al('#ffffff', 8), 1)
    stars(c, 220, seed=200)
    vignette(c, 160)
    save(c.out(), 'hub', 'bg.webp', q=80)


def main():
    cr = g_cripta(); lu = g_lunar(); ne = g_nebula(); ge = g_gemas(); nb = g_neon(); g_bastion()
    me = g_memoria(); se = g_serpiente(); te = g_teclado(); g_golf(); pu = g_pulso(); fl = g_flujo()
    hub_bg()

    def cripta_x(c):
        lay = ['#######', '#  .  #', '# $@$ #', '#  .  #', '#######']
        tiles(c, [], 64, 7, 5, 96, 40, lambda x, y: 'cr_wall' if lay[y][x] == '#' else 'cr_floor%d' % ((x + y) % 2))
    cover('cripta', cr, [('cr_target', 320, 104, 64), ('cr_target', 320, 232, 64), ('cr_box', 256, 168, 64), ('cr_boxon', 384, 168, 64), ('cr_player', 320, 168, 64)], cripta_x)

    def lunar_x(c):
        for x in range(0, 640, 48):
            if 240 <= x < 336: continue
            comp(c, HI['lu_top'].resize((48, 48), LZ), x, 304); comp(c, HI['lu_dirt'].resize((48, 48), LZ), x, 352)
        for x in (384, 432):
            comp(c, HI['lu_top'].resize((48, 48), LZ), x, 208)
    cover('lunar', lu, [('lu_player', 150, 230, 96), ('lu_gem', 290, 190, 40), ('lu_gem', 340, 170, 40), ('lu_gem', 408, 150, 40), ('lu_enemy', 520, 280, 64), ('lu_portal', 590, 240, 72), ('lu_spike', 120, 280, 48)], lunar_x)
    cover('nebula', ne, [('ne_boss', 320, 110, 230), ('ne_a', 150, 150, 64), ('ne_a', 490, 150, 64), ('ne_b', 230, 230, 56), ('ne_b', 410, 230, 56), ('ne_ship', 320, 320, 100), ('ne_p_weapon', 520, 300, 36)],
          lambda c: [comp(c, Image.new('RGBA', (4, 26), rgba('#7ff7ff')), x, y) for x, y in ((310, 230), (326, 200))])

    def gem_x(c):
        lay = [[0, 1, 2, 3, 4, 5, 0], [2, 3, 4, 5, 0, 1, 2], [4, 5, 0, 1, 2, 3, 4], [1, 0, 3, 2, 5, 4, 1]]
        panel = Image.new('RGBA', (7 * 72 + 16, 4 * 72 + 16), (10, 16, 32, 170)); comp(c, panel, 60, 40)
        for y, row in enumerate(lay):
            for x, g in enumerate(row):
                comp(c, HI[f'ge_{g}'].resize((68, 68), LZ), 70 + x * 72, 50 + y * 72)
    cover('gemas', ge, [], gem_x)

    def neon_x(c):
        for r in range(4):
            for k in range(7):
                comp(c, HI[f'nb_b{(r + k) % 6}'].resize((80, 30), LZ), 36 + k * 82, 40 + r * 34)
    cover('neon', nb, [('nb_ball', 360, 260, 40), ('nb_paddle', 320, 340, 180)], neon_x)

    def ba_x(c):
        lay = ['gggggggggg', 'gtgggggggg', 'pppppgggtg', 'ggggpggggg', 'gtggpppppp', 'gggggggtgg', 'gggggggggg']
        for y, row in enumerate(lay):
            for x, ch in enumerate(row):
                comp(c, HI['ba_path' if ch == 'p' else 'ba_grass%d' % ((x * 7 + y * 3) % 3)].resize((64, 64), LZ), x * 64, y * 64 - 24)
                if ch == 't':
                    comp(c, HI['ba_tree'].resize((64, 64), LZ), x * 64, y * 64 - 24)
        for (tx, ty, t) in ((2, 1, 0), (6, 3, 1), (3, 4, 2)):
            comp(c, HI['ba_base'].resize((64, 64), LZ), tx * 64, ty * 64 - 24); comp(c, HI[f'ba_t{t}'].resize((64, 64), LZ), tx * 64, ty * 64 - 24)
    cover('bastion', None, [('ba_goblin', 120, 136, 48), ('ba_orc', 200, 136, 52), ('ba_knight', 288, 200, 48), ('ba_bat', 400, 264, 48), ('ba_castle', 590, 250, 100)], ba_x)

    def mem_x(c):
        for i, (k, rot) in enumerate((('me_back', -10), ('me_star', 0), ('me_back', 8))):
            x = 110 + i * 170
            if k == 'me_back':
                im = HI[k].resize((150, 195), LZ).rotate(rot, resample=Image.BICUBIC, expand=True)
            else:
                im = Image.new('RGBA', (150, 195), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
                d.rounded_rectangle((0, 0, 149, 194), 14, fill=(250, 244, 230, 255), outline=(230, 195, 106, 255), width=3)
                comp(im, HI['me_crown'].resize((120, 120), LZ), 15, 38)
            comp(c, im, x, 100 + abs(rot) * 2)
    cover('memoria', me, [], mem_x)

    def se_x(c):
        tiles(c, ['se_cell0', 'se_cell1'], 40, 16, 10)
        body = [(5, 5), (4, 5), (3, 5), (3, 4), (3, 3), (4, 3), (5, 3), (6, 3)]
        for x, y in body[1:]:
            comp(c, HI['se_body'].resize((40, 40), LZ), 80 + x * 40, 40 + y * 40)
        comp(c, HI['se_head'].resize((40, 40), LZ), 80 + 5 * 40 + 4, 40 + 5 * 40)
        comp(c, HI['se_apple'].resize((40, 40), LZ), 80 + 9 * 40, 40 + 5 * 40)
        comp(c, HI['se_gold'].resize((40, 40), LZ), 80 + 10 * 40, 40 + 2 * 40)
        for x, y in ((12, 1), (12, 2), (1, 7), (2, 7)):
            comp(c, HI['se_rock'].resize((40, 40), LZ), x * 40, y * 40)
    cover('serpiente', None, [], se_x)
    cover('teclado', te, [('te_meteor', 160, 120, 110), ('te_meteor', 460, 90, 90), ('te_meteor', 330, 200, 100), ('te_cannon', 320, 330, 110)])

    def golf_x(c):
        g = HI['go_grass']
        for x in range(0, 640, 128):
            for y in range(0, 400, 128):
                c.alpha_composite(g, (x, y))
        d = ImageDraw.Draw(c)
        d.rounded_rectangle((330, 170, 460, 250), 30, fill=(230, 203, 142, 255))
        d.rounded_rectangle((150, 40, 260, 130), 40, fill=(42, 139, 214, 255))
        d.rectangle((0, 0, 640, 14), fill=(138, 90, 50, 255)); d.rectangle((0, 386, 640, 400), fill=(138, 90, 50, 255))
    cover('golf', None, [('go_hole', 520, 200, 36), ('go_flag', 534, 160, 56), ('go_ball', 140, 290, 30), ('go_tree', 590, 60, 90), ('go_tree', 60, 70, 80), ('go_bumper', 330, 300, 52)], golf_x)

    def pu_x(c):
        lane = Image.new('RGBA', (360, 400), (10, 6, 20, 150)); comp(c, lane, 140, 0)
        d = ImageDraw.Draw(c)
        for i in range(5):
            d.line((140 + i * 90, 0, 140 + i * 90, 400), fill=(255, 255, 255, 40), width=2)
        for i in range(4):
            comp(c, HI['pu_receptor'].resize((80, 80), LZ), 145 + i * 90, 290)
    cover('pulso', pu, [('pu_note0', 185, 90, 80), ('pu_note1', 275, 180, 80), ('pu_note2', 365, 60, 80), ('pu_note3', 455, 230, 80), ('pu_note2', 365, 330, 80)], pu_x)

    def fl_x(c):
        lay = [('corner', 1, 0), ('straight', 1, 1), ('tee', 1, 2), ('end', 1, 3), ('straight', 0, 1), ('cross', 1, 0), ('corner', 0, 2), ('end', 0, 3)]
        for i, (t, wet, r) in enumerate(lay):
            x, y = 80 + (i % 4) * 120, 70 + (i // 4) * 120
            comp(c, HI['fl_plate'].resize((116, 116), LZ), x, y)
            im = HI[f'fl_{t}{wet}'].resize((116, 116), LZ).rotate(-90 * r)
            comp(c, im, x, y)
        comp(c, HI['fl_source'].resize((116, 116), LZ), 80 + 120, 70)
    cover('flujo', fl, [], fl_x)
    print('Arte generado en', ASSETS)


if __name__ == '__main__':
    main()
