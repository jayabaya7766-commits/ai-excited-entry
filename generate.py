#!/usr/bin/env python3
"""
generate.py -- draw "Beanstalk to the Stars": a magic bean at the bottom
cracks open and a sprout of starlight climbs into a spiral-galaxy flower whose
heart is a newborn star.

Crisp, bold, readable at 300px. Deterministic (fixed seeds). Pure PIL.

Technique: supersample 2x for clean edges; opaque vector-like shapes are
alpha-composited (never additively blown to white); glow is reserved for the
core and a few accents only.
"""
import math
import random
from PIL import Image, ImageDraw, ImageFilter, ImageEnhance, ImageChops

S = 1024            # final square size
SS = 2              # supersample factor
M = 48              # margin (final px) so edge glows don't clip
SF = S + 2 * M      # final-space field
W = SF * SS         # raster buffer size


def lerp(a, b, t):
    return a + (b - a) * t


def lerp3(a, b, t):
    return (lerp(a[0], b[0], t), lerp(a[1], b[1], t), lerp(a[2], b[2], t))


# --- gaussian glow sprite (additive only, used sparingly) ---------------------
_CANON = None


def _canon():
    global _CANON
    if _CANON is None:
        size = 129
        half = (size - 1) / 2.0
        sigma = size / 6.0
        img = Image.new("L", (size, size), 0)
        px = img.load()
        for y in range(size):
            dy = (y - half) / sigma
            for x in range(size):
                dx = (x - half) / sigma
                px[x, y] = int(round(math.exp(-(dx * dx + dy * dy) / 2.0) * 255))
        _CANON = img
    return _CANON


def glow(canvas, x, y, radius, color, strength=1.0):
    """Additive soft glow stamp (RGB canvas)."""
    d = int(radius * 2) | 1
    if d < 1:
        d = 1
    k = _canon().resize((d, d), Image.BILINEAR)
    r, g, b = color
    sprite = Image.merge("RGB", (
        k.point(lambda v, c=r: v * c // 255),
        k.point(lambda v, c=g: v * c // 255),
        k.point(lambda v, c=b: v * c // 255),
    ))
    if strength < 0.999:
        sprite = Image.eval(sprite, lambda v: int(v * strength))
    x0 = int(x) - d // 2
    y0 = int(y) - d // 2
    region = canvas.crop((x0, y0, x0 + d, y0 + d))
    canvas.paste(ImageChops.add(region, sprite), (x0, y0))
    return canvas


def X(v):
    """final-space coordinate -> raster coordinate"""
    return int(round((v + M) * SS))


def bezier(p0, p1, p2, n):
    pts = []
    for i in range(n + 1):
        t = i / n
        mt = 1 - t
        pts.append((
            mt * mt * p0[0] + 2 * mt * t * p1[0] + t * t * p2[0],
            mt * mt * p0[1] + 2 * mt * t * p1[1] + t * t * p2[1],
        ))
    return pts


def cubic(p0, p1, p2, p3, n):
    pts = []
    for i in range(n + 1):
        t = i / n
        mt = 1 - t
        pts.append((
            mt ** 3 * p0[0] + 3 * mt * mt * t * p1[0] + 3 * mt * t * t * p2[0] + t ** 3 * p3[0],
            mt ** 3 * p0[1] + 3 * mt * mt * t * p1[1] + 3 * mt * t * t * p2[1] + t ** 3 * p3[1],
        ))
    return pts


# --- spiral arm ribbon --------------------------------------------------------
def spiral_ribbon(cx, cy, phi, r0, growth, theta_max, squash, n, w0, w1):
    rmax = r0 * math.exp(growth * theta_max)
    pts = []
    for i in range(n + 1):
        t = i / n
        theta = t * theta_max
        r = r0 * math.exp(growth * theta)
        pts.append((cx + r * math.cos(theta + phi),
                    cy + r * math.sin(theta + phi) * squash, r))
    left, right = [], []
    for i in range(n + 1):
        x, y, r = pts[i]
        xp, yp, _ = pts[max(0, i - 1)]
        xn, yn, _ = pts[min(n, i + 1)]
        tx, ty = xn - xp, yn - yp
        L = math.hypot(tx, ty) or 1.0
        nx, ny = -ty / L, tx / L
        w = w0 + (w1 - w0) * (r - r0) / (rmax - r0)
        left.append((x + nx * w, y + ny * w))
        right.append((x - nx * w, y - ny * w))
    return left + right[::-1]


def draw_ribbon(draw, ribbon, color):
    draw.polygon([(X(x), X(y)) for x, y in ribbon], fill=color)


# ---------------------------------------------------------------------------
def render():
    cx, cy = 512.0, 470.0          # galaxy flower centre
    field = Image.new("RGB", (W, W), (6, 4, 15))

    # ---- 1. deep-space nebula (subtle, kept dark) -----------------------------
    rng = random.Random(7)
    nebula = [
        (cx - 240, cy - 40, 400, (44, 22, 84), 0.30),
        (cx + 260, cy + 60, 360, (16, 28, 88), 0.28),
        (cx - 40, cy + 300, 300, (38, 12, 64), 0.24),
        (cx + 100, cy - 280, 280, (18, 40, 80), 0.24),
    ]
    for nx, ny, nr, nc, ns in nebula:
        glow(field, X(nx), X(ny), nr * SS, nc, ns)

    # ---- 2. star field --------------------------------------------------------
    star_rng = random.Random(20261117)
    sd = ImageDraw.Draw(field)
    for _ in range(1600):
        sx = star_rng.uniform(0, SF)
        sy = star_rng.uniform(0, SF)
        b = star_rng.random() ** 2.7
        g = int(b * 210)
        c = (g, g, min(255, g + 10))
        if star_rng.random() < 0.16:
            c = star_rng.choice([(200, 214, 255), (255, 236, 200), (255, 224, 235)])
        if b > 0.5:
            sd.ellipse([X(sx) - 1, X(sy) - 1, X(sx) + 1, X(sy) + 1], fill=c)
        else:
            sd.point((X(sx), X(sy)), fill=c)

    # ---- 3. spiral arms (opaque, alpha-composited -> crisp, no white blowout) --
    overlay = Image.new("RGBA", (W, W), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)

    arms = [
        (0.0,         (255, 92, 160)),   # magenta
        (math.pi / 2, (78, 198, 255)),   # cyan
        (math.pi,     (255, 200, 86)),   # gold
        (3 * math.pi / 2, (168, 122, 255)),  # violet
    ]
    r0, growth, theta_max, squash = 52.0, 0.0, 2.75, 0.82
    rmax = 392.0
    growth = math.log(rmax / r0) / theta_max

    for phi, base in arms:
        ribbon = spiral_ribbon(cx, cy, phi, r0, growth, theta_max, squash, 160, 30.0, 62.0)
        draw_ribbon(od, ribbon, base + (255,))
        # brighter inner half for depth
        inner = spiral_ribbon(cx, cy, phi, r0, growth, theta_max * 0.55, squash, 90, 22.0, 40.0)
        light = tuple(min(255, int(v * 0.72 + 84)) for v in base)
        draw_ribbon(od, inner, light + (255,))

    # soft halo *under* the arms, so the flower reads as one luminous bloom
    halo = Image.new("RGB", (W, W), (0, 0, 0))
    glow(halo, X(cx), X(cy), 330 * SS, (110, 60, 170), 0.20)
    glow(halo, X(cx), X(cy), 210 * SS, (150, 90, 160), 0.16)
    halo = halo.filter(ImageFilter.GaussianBlur(24))
    field = ImageChops.add(field, halo)

    # composite the crisp arms
    field = Image.alpha_composite(field.convert("RGBA"), overlay).convert("RGB")

    # ---- 4. core star (small, not blown out) ----------------------------------
    glow(field, X(cx), X(cy), 86 * SS, (255, 214, 150), 0.85)
    glow(field, X(cx), X(cy), 46 * SS, (255, 244, 224), 0.95)
    cd = ImageDraw.Draw(field)
    cd.ellipse([X(cx) - X(15), X(cy) - X(15), X(cx) + X(15), X(cy) + X(15)],
               fill=(255, 255, 250))
    # thin diffraction spikes (opaque, low alpha)
    spikes = Image.new("RGBA", (W, W), (0, 0, 0, 0))
    spd = ImageDraw.Draw(spikes)
    for ang in (0.0, math.pi / 2, math.pi / 4, -math.pi / 4):
        dx, dy = math.cos(ang), math.sin(ang)
        ln = 210 if ang in (0.0, math.pi / 2) else 150
        spd.line([(X(cx) - dx * ln * SS, X(cy) - dy * ln * SS),
                  (X(cx) + dx * ln * SS, X(cy) + dy * ln * SS)],
                 fill=(255, 250, 240, 150), width=3 * SS)
    spikes = spikes.filter(ImageFilter.GaussianBlur(1.2))
    field = Image.alpha_composite(field.convert("RGBA"), spikes).convert("RGB")

    # ---- 5. vine / sprout -----------------------------------------------------
    pod_x, pod_y = 512.0, 892.0
    vine = Image.new("RGBA", (W, W), (0, 0, 0, 0))
    vd = ImageDraw.Draw(vine)
    p0 = (pod_x, pod_y - 74)
    p1 = (pod_x - 120, cy + 170)
    p2 = (cx, cy + 44)
    vpts = bezier(p0, p1, p2, 120)
    # soft green underglow
    glow(field, X(p0[0]), X(p0[1]), 30 * SS, (120, 230, 170), 0.5)
    vd.line([(X(x), X(y)) for x, y in vpts], fill=(150, 235, 180, 255), width=7 * SS)
    vd.line([(X(x), X(y)) for x, y in vpts], fill=(210, 255, 225, 255), width=3 * SS)

    # leaves along the vine
    leaf_rng = random.Random(505)
    for i in range(7):
        t = 0.10 + i * 0.13
        idx = int(t * 120)
        bx, by = vpts[idx]
        side = 1 if i % 2 == 0 else -1
        a = leaf_rng.uniform(0.5, 1.2) * side
        tip = (bx + a * 46, by - 30)
        base_l = (bx + a * 14, by + 10)
        base_r = (bx - a * 4, by + 12)
        vd.polygon([(X(x), X(y)) for x, y in (tip, base_l, base_r)],
                   fill=(120, 230, 170, 255))
    field = Image.alpha_composite(field.convert("RGBA"), vine).convert("RGB")

    # ---- 6. magic bean (clear almond seed, cracked open) -----------------------
    bean = Image.new("RGBA", (W, W), (0, 0, 0, 0))
    bd = ImageDraw.Draw(bean)
    bw, bh = 300.0, 118.0
    # pointed-ends almond outline
    top = cubic((pod_x - bw, pod_y), (pod_x - bw * 0.55, pod_y - bh),
                (pod_x + bw * 0.55, pod_y - bh), (pod_x + bw, pod_y), 70)
    bottom = cubic((pod_x + bw, pod_y), (pod_x + bw * 0.55, pod_y + bh),
                   (pod_x - bw * 0.55, pod_y + bh), (pod_x - bw, pod_y), 70)
    outline = top + bottom[1:-1]
    bd.polygon([(X(x), X(y)) for x, y in outline], fill=(26, 16, 46, 255))
    bd.polygon([(X(x), X(y)) for x, y in outline], outline=(86, 54, 130, 255), width=2 * SS)
    # inner shade / highlight
    inner = cubic((pod_x - bw * 0.8, pod_y), (pod_x - bw * 0.4, pod_y - bh * 0.62),
                  (pod_x + bw * 0.4, pod_y - bh * 0.62), (pod_x + bw * 0.8, pod_y), 50)
    bd.line([(X(x), X(y)) for x, y in inner], fill=(56, 34, 92, 255), width=2 * SS)
    # glowing crack at the top (light spills upward)
    glow(field, X(pod_x), X(pod_y - 26), 46 * SS, (255, 208, 150), 0.9)
    glow(field, X(pod_x), X(pod_y - 16), 24 * SS, (255, 150, 190), 0.9)
    bd.ellipse([X(pod_x) - X(20), X(pod_y - 40) - X(14), X(pod_x) + X(20), X(pod_y) - X(6)],
               fill=(255, 226, 176, 255))
    field = Image.alpha_composite(field.convert("RGBA"), bean).convert("RGB")

    # ---- 7. falling sparks / petals --------------------------------------------
    petal_rng = random.Random(321)
    spd = ImageDraw.Draw(field)
    for _ in range(60):
        ang = petal_rng.uniform(0, math.tau)
        rad = petal_rng.uniform(120, 470)
        px = cx + rad * math.cos(ang)
        py = cy + rad * math.sin(ang) * 0.82
        drift = petal_rng.uniform(40, 150)
        wob = petal_rng.uniform(-1, 1) * 0.4
        col = petal_rng.choice([(255, 214, 138), (255, 150, 190),
                                (160, 190, 255), (196, 150, 255)])
        pts = []
        for i in range(6):
            t = i / 5
            pts.append((X(px + wob * t * 40 - t * 10), X(py + t * drift)))
        spd.line(pts, fill=col, width=2 * SS)
        spd.ellipse([pts[-1][0] - 2 * SS, pts[-1][1] - 2 * SS,
                     pts[-1][0] + 2 * SS, pts[-1][1] + 2 * SS], fill=col)

    # ---- 8. post-process -------------------------------------------------------
    # single gentle bloom (kept low so shapes stay crisp)
    bloom = field.filter(ImageFilter.GaussianBlur(7))
    field = ImageChops.add(field, Image.eval(bloom, lambda v: int(v * 0.10)))
    # downscale + crop
    field = field.resize((SF, SF), Image.LANCZOS)
    img = field.crop((M, M, M + S, M + S))
    img = ImageEnhance.Color(img).enhance(1.30)
    img = ImageEnhance.Contrast(img).enhance(1.06)
    img = ImageEnhance.Brightness(img).enhance(1.02)
    # vignette
    vg = Image.radial_gradient("L").resize((S, S), Image.BILINEAR)
    vg = Image.eval(vg, lambda v: 255 - int(v * 0.26))
    vg = Image.merge("RGB", (vg, vg, vg))
    img = ImageChops.multiply(img, vg)
    img = img.filter(ImageFilter.UnsharpMask(radius=1.4, percent=80, threshold=2))
    return img


if __name__ == "__main__":
    img = render()
    img.save("entry.png", optimize=True)
    print("saved entry.png", img.size)
