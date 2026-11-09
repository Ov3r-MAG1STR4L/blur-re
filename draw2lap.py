#!/usr/bin/env python3
"""Route drawn on a physmap_x360 top-down image -> lap CSV for lap2aid.py.

Drawing rules (Paint is enough): one GREEN line (pure 0,255,0) along the middle of the road, closed for a lap
circuit; a RED dot (255,0,0) on the start line; a BLUE dot (0,0,255) a little after it, to give the direction.
The image must keep the size of the one physmap_x360 wrote (its <city>_map.npz gives pixel <-> game metres).

Each drawn point gets the road height from the collision points under it (the low quartile within HEIGHT_R m, so a
roof or a bridge above does not lift it). Width: --width for the whole route (the drawing has no edges).

usage: draw2lap.py DRAWN.png CITY_map.npz OUT_lap.csv [--width 20]        then: lap2aid.py OUT_lap.csv OUT.aid
       draw2lap.py --self-test CITY_map.npz
"""
import argparse, csv, math, sys
import numpy as np
from PIL import Image

STEP = 5.0          # m between lap points
HEIGHT_R = 8.0


def load_map(path):
    m = np.load(path)
    return m["points"].astype(np.float64), m["lo"], float(m["k"]), int(m["size"])


def to_game(px, py, lo, k, size):
    return (px - 10) / k + lo[0], (size - 1 - py - 10) / k + lo[1]


def to_px(x, z, lo, k, size):
    return (x - lo[0]) * k + 10, size - 1 - ((z - lo[1]) * k + 10)


def mask(img, rgb):
    a = img.astype(int)
    return (np.abs(a - np.array(rgb)).sum(-1) < 90) & (a.max(-1) > 150)


def chain(pts, start):
    """greedy walk over the pixel cloud, thinned to one point every ~3 px; stops when nothing is near"""
    left = pts.copy()
    cur = start
    out = [cur]
    while len(left):
        d = np.hypot(left[:, 0] - cur[0], left[:, 1] - cur[1])
        left = left[d > 2.5]                                   # eat the pixels around the current point
        if not len(left):
            break
        d = np.hypot(left[:, 0] - cur[0], left[:, 1] - cur[1])
        i = int(d.argmin())
        if d[i] > 25:                                          # gap in the line: end of the drawing
            break
        cur = left[i]
        out.append(cur)
    return np.array(out)


def drawn_route(png, lo, k, size):
    img = np.asarray(Image.open(png).convert("RGB"))
    assert img.shape[0] == size and img.shape[1] == size, "image resized: keep %d x %d px" % (size, size)
    g, r, b = (np.argwhere(mask(img, c))[:, ::-1].astype(float) for c in ((0, 255, 0), (255, 0, 0), (0, 0, 255)))
    assert len(g) > 50, "no green line found"
    assert len(r) and len(b), "red (start) and blue (direction) dots needed"
    red, blue = r.mean(0), b.mean(0)
    start = g[np.hypot(g[:, 0] - red[0], g[:, 1] - red[1]).argmin()]
    line = chain(g, start)
    # chain went one way round; the blue dot must be near its beginning, else reverse (keep the start first)
    nb = np.hypot(line[:, 0] - blue[0], line[:, 1] - blue[1]).argmin()
    if nb > len(line) / 2:
        line = np.vstack([line[:1], line[1:][::-1]])
    return np.array([to_game(px, py, lo, k, size) for px, py in line])


def resample(xz, step):
    out, carry = [xz[0]], 0.0
    for a, b in zip(xz, xz[1:]):
        seg = math.hypot(*(b - a))
        d = step - carry
        while d <= seg:
            out.append(a + (b - a) * d / seg)
            d += step
        carry = (carry + seg) % step
    return np.array(out)


def heights(xz, pts):
    out = []
    for x, z in xz:
        near = pts[np.hypot(pts[:, 0] - x, pts[:, 2] - z) < HEIGHT_R]
        out.append(np.percentile(near[:, 1], 25) if len(near) else np.nan)
    h = np.array(out)
    if np.isnan(h).all():
        return np.zeros(len(h))
    idx = np.arange(len(h))
    return np.interp(idx, idx[~np.isnan(h)], h[~np.isnan(h)])          # fill gaps from the neighbours


def write_lap(path, xz, y, width):
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["t", "x", "y", "z", "kmh", "w"])
        for i, ((x, z), h) in enumerate(zip(xz, y)):
            w.writerow([i, round(x, 2), round(h, 2), round(z, 2), 0, width])


def self_test(npz):
    """draw a synthetic loop (circle) with start/direction dots, read it back: game coords must round-trip"""
    import os, tempfile
    pts, lo, k, size = load_map(npz)
    cx, cz = np.median(pts[:, 0]), np.median(pts[:, 2]); R = 300.0
    img = Image.new("RGB", (size, size), (245, 245, 245))
    from PIL import ImageDraw
    d = ImageDraw.Draw(img)
    ring = [to_px(cx + R * math.cos(a), cz + R * math.sin(a), lo, k, size) for a in np.linspace(0, 2 * math.pi, 400)]
    d.line(ring, fill=(0, 255, 0), width=3)
    sx, sy = to_px(cx + R, cz, lo, k, size); bx, by = to_px(cx + R * math.cos(.1), cz + R * math.sin(.1), lo, k, size)
    d.ellipse((sx - 6, sy - 6, sx + 6, sy + 6), fill=(255, 0, 0)); d.ellipse((bx - 6, by - 6, bx + 6, by + 6), fill=(0, 0, 255))
    png = os.path.join(tempfile.mkdtemp(), "t.png"); img.save(png)
    xz = drawn_route(png, lo, k, size)
    err = np.abs(np.hypot(xz[:, 0] - cx, xz[:, 1] - cz) - R)
    ang = math.atan2(xz[5, 1] - cz, xz[5, 0] - cx)
    print("self-test: %d points, radius error max %.1f m, start (%.0f, %.0f) expected (%.0f, %.0f), direction %s"
          % (len(xz), err.max(), xz[0, 0], xz[0, 1], cx + R, cz, "ok" if 0 < ang < 1 else "WRONG"))
    px = 1 / k                                  # metres per pixel; the red dot hides ~6 px of the green line
    assert err.max() < 3 * px and math.hypot(xz[0, 0] - cx - R, xz[0, 1] - cz) < 10 * px and 0 < ang < 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("args", nargs="*")
    ap.add_argument("--width", type=float, default=20.0)
    ap.add_argument("--self-test", metavar="CITY_map.npz")
    a = ap.parse_args()
    if a.self_test:
        return self_test(a.self_test)
    png, npz, out = a.args
    pts, lo, k, size = load_map(npz)
    xz = resample(drawn_route(png, lo, k, size), STEP)
    y = heights(xz, pts)
    write_lap(out, xz, y, a.width)
    L = sum(math.hypot(*(b - a_)) for a_, b in zip(xz, xz[1:]))
    print("written %s: %d points, %.0f m, height %.1f..%.1f m" % (out, len(xz), L, y.min(), y.max()))


if __name__ == "__main__":
    main()
