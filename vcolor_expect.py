#!/usr/bin/env python3
"""Control image of the vertex colour test panel (vcolor_scene.py): its layout with labels, as it should look
under each hypothesis, to compare with the in-game capture.

  H1 same space   : shown = texture x colour (both read as sRGB values, or both linear: identical on screen)
  H2 colour linear: texture decoded from sRGB, colour used as linear, result encoded back to sRGB
  H3 colour added : shown = texture + colour (clamped)
Row V against row T decides: H1 -> V(g) = T(g) ; H2 -> V(g) = srgb(g / 255) brighter in the mid greys.

usage: vcolor_expect.py OUT.png
"""
import sys

import numpy as np
from PIL import Image, ImageDraw

import vcolor_scene as S


def srgb_dec(x):
    return np.where(x <= 0.04045, x / 12.92, ((x + 0.055) / 1.055) ** 2.4)


def srgb_enc(x):
    return np.where(x <= 0.0031308, x * 12.92, 1.055 * np.power(np.maximum(x, 0), 1 / 2.4) - 0.055)


def dxt1(c):
    """the texel the DXT1 encoder stores for a flat colour (565 endpoints)"""
    r, g, b = c
    q = lambda v, bits: round(round(v * (2 ** bits - 1) / 255) * 255 / (2 ** bits - 1))
    return q(r, 5), q(g, 6), q(b, 5)


def shown(tex, vc, hyp):
    t = np.array(dxt1((255, 0, 0) if tex == "red" else (tex,) * 3)) / 255
    v = np.array(vc[:3]) / 255
    if hyp == "H1":
        out = t * v
    elif hyp == "H2":
        out = srgb_enc(srgb_dec(t) * v)
    else:
        out = np.minimum(t + v, 1)
    return tuple(int(round(255 * x)) for x in out)


def panel_items():
    """[(label, tex, colour of each corner, (s0, t0, s1, t1))] from vcolor_scene.panel()"""
    for corners, (u, _), cols, label in S.panel():
        k = int(u * S.TW / S.CELL)
        c = S.CELLS[k]
        tex = "red" if c == (255, 0, 0) else c[0]
        (s0, t0), (s1, t1) = corners[0], corners[2]
        yield label, tex, cols, (s0, t0, s1, t1)


def draw(hyp, scale=40):
    W, H = int(S.WIDTH * scale), int(5 * (S.BAND_H + S.GAP) * scale)
    img = Image.new("RGB", (W, H + 30), (60, 90, 120))
    d = ImageDraw.Draw(img)
    for label, tex, cols, (s0, t0, s1, t1) in panel_items():
        x0, x1 = int(s0 * scale), int(s1 * scale)
        y0, y1 = H - int(t1 * scale), H - int(t0 * scale)
        if label.startswith("G"):                              # gradient: colours of the left and right corners
            for x in range(x0, x1):
                f = (x - x0) / max(1, x1 - x0)
                g = cols[0][0] + f * (cols[1][0] - cols[0][0])
                d.line([(x, y0), (x, y1)], fill=shown(tex, (g, g, g), hyp))
        else:
            d.rectangle([x0, y0, x1 - 1, y1], fill=shown(tex, cols[0], hyp))
            d.text((x0 + 3, y0 + 3), label, fill=(255, 128, 0))
    d.text((5, H + 8), {"H1": "H1 meme espace : tex x couleur", "H2": "H2 couleur lineaire, texture sRGB",
                        "H3": "H3 addition"}[hyp], fill=(255, 255, 255))
    return img


def main():
    imgs = [draw(h) for h in ("H1", "H2", "H3")]
    out = Image.new("RGB", (imgs[0].width, sum(i.height for i in imgs) + 20), (0, 0, 0))
    y = 0
    for i in imgs:
        out.paste(i, (0, y))
        y += i.height + 10
    out.save(sys.argv[1])
    print("rows V vs T (g: V under H1 / H2, T):")
    for g in S.GREYS:
        print("  %3d  %3d / %3d  %3d" % (g, shown(255, (g,) * 3, "H1")[0], shown(255, (g,) * 3, "H2")[0],
                                         shown(g, (255,) * 3, "H1")[0]))


if __name__ == "__main__":
    main()
