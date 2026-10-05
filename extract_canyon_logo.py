"""Extract the CANYON down-tube wordmark from Canyon's product image (logo.avif) as an alpha mask.

Run: python3 extract_canyon_logo.py   (system python3 + Pillow)
Writes canyon_downtube.png (black letters, transparent background) and prints its size in mm.
"""
import math
import os
from collections import deque

from PIL import Image, ImageFilter

OUT = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(OUT, "logo.avif")
REGION = (1180, 420, 1680, 940)        # area around the down-tube lettering (source px)
PX_PER_MM = 944 / 686.0                # front tyre outer diameter (686 mm) spans 944 px in logo.avif


def components(img, thresh=80):
    w, h = img.size
    px = img.load()
    lab = [[0] * w for _ in range(h)]
    out = []
    for sy in range(h):
        for sx in range(w):
            if px[sx, sy] < thresh and not lab[sy][sx]:
                k = len(out) + 1
                lab[sy][sx] = k
                q, pts = deque([(sx, sy)]), []
                while q:
                    x, y = q.popleft()
                    pts.append((x, y))
                    for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                        if 0 <= nx < w and 0 <= ny < h and px[nx, ny] < thresh and not lab[ny][nx]:
                            lab[ny][nx] = k
                            q.append((nx, ny))
                out.append(pts)
    return out


def main():
    full = Image.open(SRC).convert("L")
    x0, y0, _, _ = REGION
    reg = full.crop(REGION)
    rw, rh = reg.size
    comps = [c for c in components(reg) if 15 <= len(c) < 5000             # drop tyre (huge) and specks
             and not any(x in (0, rw - 1) or y in (0, rh - 1) for x, y in c)]  # and the cut-off crank
    cents = [(sum(p[0] for p in c) / len(c), sum(p[1] for p in c) / len(c), len(c)) for c in comps]
    # baseline: weighted line fit through component centroids, then keep only components near it
    def fit(cs):
        W_ = sum(c[2] for c in cs)
        mx = sum(c[0] * c[2] for c in cs) / W_
        my = sum(c[1] * c[2] for c in cs) / W_
        sxx = sum(c[2] * (c[0] - mx) ** 2 for c in cs)
        sxy = sum(c[2] * (c[0] - mx) * (c[1] - my) for c in cs)
        syy = sum(c[2] * (c[1] - my) ** 2 for c in cs)
        return mx, my, 0.5 * math.atan2(2 * sxy, sxx - syy)
    mx, my, ang = fit(cents)
    def dist(c):
        return abs(-(c[0] - mx) * math.sin(ang) + (c[1] - my) * math.cos(ang))
    keep = [i for i, c in enumerate(cents) if dist(c) < 30]
    mx, my, ang = fit([cents[i] for i in keep])
    keep = [i for i, c in enumerate(cents) if dist(c) < 30]
    mask = Image.new("L", reg.size, 0)
    mp = mask.load()
    for i in keep:
        for x, y in comps[i]:
            mp[x, y] = 255
    mask = mask.filter(ImageFilter.MaxFilter(11))                          # generous: keep whole soft edges
    # darkness straight from the source greyscale (its anti-aliasing is the true sub-pixel outline)
    src, dark = reg.load(), Image.new("L", reg.size, 0)
    dp = dark.load()
    for y in range(reg.size[1]):
        for x in range(reg.size[0]):
            if mp[x, y]:
                dp[x, y] = max(0, min(255, int((232 - src[x, y]) * 255 / 200)))
    pad = 120                                                             # room so rotation clips nothing
    padded = Image.new("L", (dark.width + 2 * pad, dark.height + 2 * pad), 0)
    padded.paste(dark, (pad, pad))
    deg = math.degrees(ang)                                               # baseline angle (screen, y down)
    scale = 8
    big = padded.resize((padded.width * scale, padded.height * scale), Image.BICUBIC)
    rot = big.rotate(deg, resample=Image.BICUBIC, center=((mx + pad) * scale, (my + pad) * scale))
    rot = rot.filter(ImageFilter.GaussianBlur(scale * 1.3))               # removes source pixel stair-steps
    rot = rot.point(lambda a: max(0, min(255, (a - 112) * 255 // 32)))    # iso-contour at ~50% darkness
    bbox = rot.getbbox()
    rot = rot.crop(bbox)
    # reading direction: C must be on the left (C sits at the lower-left end in the source)
    if math.cos(ang) < 0:
        rot = rot.rotate(180)
    rgba = Image.new("RGBA", rot.size, (0, 0, 0, 0))
    rgba.putalpha(rot)
    path = os.path.join(OUT, "canyon_downtube.png")
    rgba.save(path)
    w_mm = rot.width / scale / PX_PER_MM
    h_mm = rot.height / scale / PX_PER_MM
    print(f"canyon_downtube.png {rot.width}x{rot.height}px, {len(keep)} parts, baseline {deg:.1f} deg, "
          f"{w_mm:.0f} x {h_mm:.1f} mm, aspect {rot.width / rot.height:.3f}")


if __name__ == "__main__":
    main()


# ---------------------------------------------------------------- vectorize -> canyon_glyphs.json
def upright_mask(path, tube_deg):
    """Undo the photo's shear: tube frame (x along tube, y up) -> upright text (u reading, v letter-up)."""
    alpha = Image.open(path).split()[3]
    a = math.radians(tube_deg)
    ca, sa = math.cos(a), math.sin(a)
    W, H = alpha.size
    v_max = H / sa
    Wout, Hout = int(W + v_max * ca) + 10, int(v_max) + 10
    out = alpha.transform((Wout, Hout), Image.AFFINE, (1, ca, -Hout * ca, 0, sa, H - Hout * sa),
                          resample=Image.BICUBIC)
    return out.crop(out.getbbox())


def boundary_loops(img, thresh=128):
    """Crack-following: closed loops along pixel edges, foreground on the left (outer CCW in y-up)."""
    w, h = img.size
    px = img.load()
    on = lambda x, y: 0 <= x < w and 0 <= y < h and px[x, y] >= thresh
    nxt = {}
    for y in range(h):
        for x in range(w):
            if not on(x, y):
                continue
            # image y down; corners (x, y) .. (x+1, y+1). Edges oriented with the pixel on the left (y up).
            if not on(x, y - 1):
                nxt[(x + 1, y)] = nxt.get((x + 1, y), []) + [(x, y)]
            if not on(x, y + 1):
                nxt[(x, y + 1)] = nxt.get((x, y + 1), []) + [(x + 1, y + 1)]
            if not on(x - 1, y):
                nxt[(x, y)] = nxt.get((x, y), []) + [(x, y + 1)]
            if not on(x + 1, y):
                nxt[(x + 1, y + 1)] = nxt.get((x + 1, y + 1), []) + [(x + 1, y)]
    loops = []
    while nxt:
        start = next(iter(nxt))
        loop, cur = [start], start
        while True:
            outs = nxt[cur]
            n_ = outs.pop()
            if not outs:
                del nxt[cur]
            if n_ == start:
                break
            loop.append(n_)
            cur = n_
            if cur not in nxt:
                break
        loops.append(loop)
    return loops


def area(loop):
    return 0.5 * sum(loop[i][0] * loop[i - 1][1] - loop[i - 1][0] * loop[i][1] for i in range(len(loop)))


def dp(points, tol):
    """Douglas-Peucker on an open polyline."""
    if len(points) < 3:
        return points
    (x0, y0), (x1, y1) = points[0], points[-1]
    dx, dy = x1 - x0, y1 - y0
    L = math.hypot(dx, dy) or 1e-9
    best, idx = -1, 0
    for i in range(1, len(points) - 1):
        d = abs(dy * (points[i][0] - x0) - dx * (points[i][1] - y0)) / L
        if d > best:
            best, idx = d, i
    if best <= tol:
        return [points[0], points[-1]]
    return dp(points[:idx + 1], tol)[:-1] + dp(points[idx:], tol)


def dp_closed(loop, tol):
    far = max(range(len(loop)), key=lambda i: (loop[i][0] - loop[0][0]) ** 2 + (loop[i][1] - loop[0][1]) ** 2)
    a_ = dp(loop[:far + 1], tol)
    b_ = dp(loop[far:] + [loop[0]], tol)
    return a_[:-1] + b_[:-1]


def smooth_curves(loop, sharp_deg=55, iters=3):
    """Chaikin smoothing that keeps sharp corners (turns > sharp_deg) exactly."""
    for _ in range(iters):
        n = len(loop)
        out = []
        for i in range(n):
            p0, p1, p2 = loop[i - 1], loop[i], loop[(i + 1) % n]
            a1 = math.atan2(p1[1] - p0[1], p1[0] - p0[0])
            a2 = math.atan2(p2[1] - p1[1], p2[0] - p1[0])
            turn = abs((a2 - a1 + math.pi) % (2 * math.pi) - math.pi)
            if math.degrees(turn) > sharp_deg:
                out.append(p1)
            else:
                out.append((0.75 * p1[0] + 0.25 * p0[0], 0.75 * p1[1] + 0.25 * p0[1]))
                out.append((0.75 * p1[0] + 0.25 * p2[0], 0.75 * p1[1] + 0.25 * p2[1]))
        loop = out
    return loop


def vectorize(tube_deg):
    import json
    up = upright_mask(os.path.join(OUT, "canyon_downtube.png"), tube_deg)
    ppm = 8 * PX_PER_MM                                                     # px per mm in the upright mask
    small = up.resize((int(up.width / ppm * 6), int(up.height / ppm * 6)), Image.LANCZOS)   # 6 px/mm
    k = 6.0
    loops = []
    for lp in boundary_loops(small):
        a_ = area(lp)
        if abs(a_) < 25 * k * k:                                           # specks < 25 mm^2 (stray paint/reflections)
            continue
        pts = [(x / k, (small.height - y) / k) for x, y in lp]             # mm, y up
        pts = dp_closed(pts, 0.9)                                          # straight stems stay straight
        pts = smooth_curves(pts, sharp_deg=50, iters=4)
        loops.append(pts)
    xs = [p[0] for lp in loops for p in lp]
    ys = [p[1] for lp in loops for p in lp]
    x0, y0 = min(xs), min(ys)
    loops = [[(round(x - x0, 3), round(y - y0, 3)) for x, y in lp] for lp in loops]
    data = {"source": "logo.avif (Canyon product image), traced + vectorized",
            "units": "mm", "frame": "upright text: u = reading direction, v = letter up",
            "width": round(max(xs) - x0, 2), "height": round(max(ys) - y0, 2),
            "loops": loops}
    with open(os.path.join(OUT, "canyon_glyphs.json"), "w") as f:
        json.dump(data, f)
    holes = sum(1 for lp in loops if area(lp) > 0)                         # y flipped: outer loops are CW
    print(f"canyon_glyphs.json: {len(loops)} loops ({holes} holes), {data['width']} x {data['height']} mm, "
          f"{sum(len(l) for l in loops)} vertices")


def trace_photo():
    """Vectorize the decal from the owner's photo (canyonlogo_ref_1.jpg = IMG_6968), which shows it at
    ~8 px/mm, nearly orthographic. Keeps the real letterform: blade-like tapered tips, diagonal end cuts,
    V-notches and the stencil cuts in C and O."""
    import json
    from PIL import ImageOps
    photo = ImageOps.exif_transpose(Image.open(os.path.join(OUT, "canyonlogo_ref_1.jpg"))).convert("L")
    cx, cy, nx, ny = 1403, 4582, 3056, 2847                     # C and last-N centroids (photo px)
    ang = math.degrees(math.atan2(cy - ny, nx - cx))            # tube axis on screen
    rot = photo.rotate(-ang, resample=Image.BICUBIC, center=(cx, cy))
    L = math.hypot(nx - cx, cy - ny)
    band = rot.crop((cx - 300, cy - 230, int(cx + L + 450), cy + 330))   # letters only (no cage plate)
    band = band.filter(ImageFilter.GaussianBlur(0.8))
    w, h = band.size
    px = band.load()
    dark = [(x, h - 1 - y) for y in range(h) for x in range(w) if px[x, y] < 50]       # y up (letters ~5, tube ~170, wall ~100)
    # shear angle: the one that makes letter stems vertical (sharpest column histogram)
    best = None
    for k in range(0, 101):
        phi = math.radians(40 + k * 0.2)
        hist = {}
        for x, y in dark[::7]:
            b = int((x + y / math.tan(phi)) / 3)
            hist[b] = hist.get(b, 0) + 1
        score = sum(c * c for c in hist.values())
        if best is None or score > best[0]:
            best = (score, phi)
    phi = best[1]
    mask = band.point(lambda g: 255 if g < 50 else 0)
    ys = [y for _, y in dark]
    v_px = (max(ys) - min(ys)) / math.sin(phi)                  # letter height in px (upright)
    ppm = v_px / 56.3                                           # px per mm, letter height 56.3 mm (product image)
    loops = []
    for lp in boundary_loops(mask):
        if abs(area(lp)) < 25 * ppm * ppm:
            continue
        pts = [(x, h - y) for x, y in lp]                       # tube frame, y up (px)
        # tube frame -> upright: v = y / sin(phi), u = x + v cos(phi)
        pts = [((x + (y / math.sin(phi)) * math.cos(phi)) / ppm, (y / math.sin(phi)) / ppm) for x, y in pts]
        pts = dp_closed(pts, 0.18)
        pts = smooth_curves(pts, sharp_deg=40, iters=3)
        loops.append(pts)
    xs = [p[0] for lp in loops for p in lp]
    ys_ = [p[1] for lp in loops for p in lp]
    x0, y0 = min(xs), min(ys_)
    loops = [[(round(x - x0, 3), round(y - y0, 3)) for x, y in lp] for lp in loops]
    data = {"source": "canyonlogo_ref_1.jpg (owner photo IMG_6968), traced + vectorized",
            "units": "mm", "frame": "upright text: u = reading direction, v = letter up",
            "photo_shear_deg": round(math.degrees(phi), 2),
            "width": round(max(xs) - x0, 2), "height": round(max(ys_) - y0, 2), "loops": loops}
    with open(os.path.join(OUT, "canyon_glyphs.json"), "w") as f:
        json.dump(data, f)
    print(f"canyon_glyphs.json from photo: shear {math.degrees(phi):.1f} deg, {ppm:.2f} px/mm, "
          f"{len(loops)} loops, {data['width']} x {data['height']} mm, {sum(len(l) for l in loops)} vertices")


def trace_endurace():
    """ENDURACE SLX top-tube decal, traced from the owner's photo slx_ref.jpg (IMG_6975) and kept in the
    tube frame (x along the tube toward the head tube, y up); same Canyon stencil face as the down tube."""
    import json
    from PIL import ImageOps
    photo = ImageOps.exif_transpose(Image.open(os.path.join(OUT, "slx_ref.jpg"))).convert("L")
    band = photo.crop((691, 2534, 2736, 2836))
    w, h = band.size
    px = band.load()
    pts = [(x, y) for y in range(h) for x in range(w) if px[x, y] < 60]
    # baseline tilt from the lowest letter pixels at the left and right ends
    def low(x0, x1):
        return max(y for x, y in pts if x0 <= x < x1)
    xs_ = [x for x, _ in pts]
    xl, xr = min(xs_), max(xs_)
    tilt = math.degrees(math.atan2(low(xr - 120, xr + 1) - low(xl, xl + 120), xr - xl))
    band = band.rotate(tilt, resample=Image.BICUBIC, center=(w / 2, h / 2), fillcolor=200)
    band = band.filter(ImageFilter.GaussianBlur(0.8))
    mask = band.point(lambda g: 255 if g < 60 else 0)
    loops = []
    for lp in boundary_loops(mask):
        if abs(area(lp)) < 40:                                   # specks (px^2)
            continue
        loops.append([(x, h - y) for x, y in lp])
    ys = [p[1] for lp in loops for p in lp]
    xs = [p[0] for lp in loops for p in lp]
    x0, y0, H = min(xs), min(ys), max(ys) - min(ys)
    out = []
    for lp in loops:
        q = [((x - x0) / H, (y - y0) / H) for x, y in lp]       # units: text height = 1
        q = dp_closed(q, 0.012)
        out.append([(round(x, 5), round(y, 5)) for x, y in smooth_curves(q, sharp_deg=40, iters=3)])
    data = {"source": "slx_ref.jpg (owner photo IMG_6975), traced + vectorized", "units": "text height = 1",
            "frame": "tube frame: x along the tube (reading direction), y up", "tilt_deg": round(tilt, 2),
            "width": round((max(xs) - x0) / H, 4), "height": 1.0, "loops": out}
    with open(os.path.join(OUT, "endurace_glyphs.json"), "w") as f:
        json.dump(data, f)
    print(f"endurace_glyphs.json: {len(out)} loops, aspect {data['width']:.2f}:1, tilt {tilt:.2f} deg, "
          f"{sum(len(l) for l in out)} vertices")


if __name__ == "__main__":
    import sys as _sys
    if "--endurace" in _sys.argv:
        trace_endurace()
    else:
        trace_photo()
