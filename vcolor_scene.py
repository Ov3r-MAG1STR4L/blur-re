#!/usr/bin/env python3
"""In-game vertex colour test (Blur 1, shader default_NB_NL): a panel of grey bands in front of the start line of
the flat_earth map, written into the decor slots of a COPY of the game (never Blur_test nor the original).

Panel, seen from the start (left to right), top to bottom:
  row G  continuous gradient, vertex colour 0 -> 255 over 32 columns, texture white
  row V  9 bands, vertex colour grey 0, 32, ..., 224, 255, texture white          (vertex colour response)
  row T  9 bands, texture grey 0, 32, ..., 224, 255, vertex colour white          (texture response, reference)
  row C  controls: white ref (tex 255, vc 255) | black ref (tex 255, vc 0) | tex 128 x vc 128 |
         tex red x vc green | tex white x vc red | tex red x vc white | tex 128 x vc 255 | tex 255 x vc 128 | tex 64 x vc 64
Every band has one constant texel (uv at the centre of a 16 x 16 cell of the texture) and one constant colour.
If the shader multiplies: red x green = black ; if it adds: yellow.

usage: vcolor_scene.py [GAME_COPY]          (default C:/Users/sanqu/Jeux_WII/Blur_vcolor)
"""
import json
import os
import sys

import numpy as np

import blurmesh
import blurmodel_write as W
import config
import make_nfs_map as J

GREYS = (0, 32, 64, 96, 128, 160, 192, 224, 255)
CELL, TW, TH = 16, 256, 16                    # texture: 16 vertical stripes (v does not matter)
CELLS = [(g, g, g) for g in GREYS] + [(255, 0, 0)]      # cell k: stripe k
CONTROLS = [(255, (255, 255, 255)), (255, (0, 0, 0)), (128, (128, 128, 128)), ("red", (0, 255, 0)),
            (255, (255, 0, 0)), ("red", (255, 255, 255)), (128, (255, 255, 255)), (255, (128, 128, 128)),
            (64, (64, 64, 64))]
NAMES = ["blanc", "noir", "128x128", "rougeXvert", "blancXrouge", "rougeXblanc", "tex128", "vc128", "64x64"]
AHEAD, WIDTH, BAND_H, GAP = 40.0, 18.0, 1.6, 0.25        # metres
GLOW = 110                                                # material texture green, as the Marina decor
# second test: the same panel at NEAR m, scaled, 3 copies side by side (left to right as seen from the start)
# whose only difference is the material light (green of the material texture)
NEAR, SCALE, GROUPS = 15.0, 0.45, (0, 30, 110)
PAD = (600, 1800)


def texture():
    img = np.full((TH, TW, 3), 255, np.uint8)
    for k, c in enumerate(CELLS):
        img[:, k * CELL:(k + 1) * CELL] = c
    return img


def cell_uv(tex):
    k = CELLS.index((255, 0, 0) if tex == "red" else (tex,) * 3)
    return (k + 0.5) * CELL / TW, 0.5


def panel():
    """[(quad corners in panel space (s across, t up), uv, colours of the 4 corners, label)]"""
    quads, w = [], WIDTH / 9
    top, n = 4 * (BAND_H + GAP), 32
    for i in range(n):                                        # row G
        a, b = i / n, (i + 1) / n
        quads.append(([(a * WIDTH, top), (b * WIDTH, top), (b * WIDTH, top + BAND_H), (a * WIDTH, top + BAND_H)],
                      cell_uv(255), [(round(255 * x),) * 3 for x in (a, b, b, a)], "G%d" % i))
    rows = [(3, "V", [(255, (g,) * 3) for g in GREYS], [str(g) for g in GREYS]),
            (2, "T", [(g, (255,) * 3) for g in GREYS], [str(g) for g in GREYS]),
            (1, "C:", CONTROLS, NAMES)]
    for t, prefix, items, names in rows:
        y = t * (BAND_H + GAP)
        for i, ((tex, vc), name) in enumerate(zip(items, names)):
            quads.append(([(i * w, y), ((i + 1) * w - GAP, y), ((i + 1) * w - GAP, y + BAND_H), (i * w, y + BAND_H)],
                          cell_uv(tex), [vc] * 4, prefix + name))
    return quads


def start_frame(ahead=AHEAD):
    """world point `ahead` m after the start line, route direction there, start point (Map Builder: y = h + 1)"""
    w = json.load(open(os.path.join(config.BMB_GAME, "Blur Map Builder", "maps", "world.json")))
    m = w["locations"][0]["maps"][0]
    P = np.array([(q["x"], q["h"] + 1.0, q["z"]) for q in m["points"]])
    cum = np.r_[0, np.cumsum(np.linalg.norm(np.diff(P[:, [0, 2]], axis=0), axis=1))]
    at = m["start_m"] + ahead
    i = int(np.searchsorted(cum, at))
    f = (at - cum[i - 1]) / (cum[i] - cum[i - 1])
    p = P[i - 1] + f * (P[i] - P[i - 1])
    d = P[i] - P[i - 1]
    d[1] = 0
    return p, d / np.linalg.norm(d), P[int(np.searchsorted(cum, m["start_m"]))]


def scene(slot_matrix):
    """vertices (slot-local), indices, colours of two panels across the road, AHEAD m before and after the start,
    both facing the start (the race direction is not checked)"""
    inv, o = np.linalg.inv(np.array(slot_matrix[:3]).T), np.array(slot_matrix[3])
    V, I, C, labels = [], [], [], []
    for sign in (1, -1):
        p, fwd, start = start_frame(sign * AHEAD)
        fwd = fwd * sign                           # looking from the start towards the panel
        _panel(V, I, C, labels, p, fwd, inv, o)
    return V, I, C, labels, start_frame()[0], start


def scene_near(slot_matrix, k):
    """group k of GROUPS: the panel scaled by SCALE, NEAR m after the start, shifted across the road"""
    inv, o = np.linalg.inv(np.array(slot_matrix[:3]).T), np.array(slot_matrix[3])
    V, I, C, labels = [], [], [], []
    p, fwd, _ = start_frame(NEAR)
    step = WIDTH * SCALE + 1.0
    _panel(V, I, C, labels, p, fwd, inv, o, scale=SCALE, shift=(k - (len(GROUPS) - 1) / 2) * step)
    return V, I, C, labels


def _panel(V, I, C, labels, p, fwd, inv, o, scale=1.0, shift=0.0):
    right = np.cross((0, 1, 0), fwd)           # seen from the start (looking along fwd), s grows to the right
    right /= np.linalg.norm(right)
    n = inv @ -fwd
    n /= np.linalg.norm(n)
    for corners, uv, cols, label in panel():
        base = len(V)
        for (s, t), c in zip(corners, cols):
            q = p + right * (shift + scale * (s - WIDTH / 2)) + np.array((0, 0.3 + scale * t, 0))
            V.append((*(inv @ (q - o)), *n, *uv))
            C.append((*c, 255))
        I += [base, base + 1, base + 2, base, base + 2, base + 3]           # both faces: visible whatever the
        I += [base, base + 2, base + 1, base, base + 3, base + 2]           # winding the shader culls
        labels.append(label)


def build_all(game):
    ap = os.path.join(game, "gamedata", "levels", "flat_earth", "actorpack.xt")
    slots = [(J.NFS_UID + 2 * k + 1, "nfs_%03d.model" % k) for k in range(110)]
    slots += [(u, "road_21_%02d.model" % k) for k, u in enumerate(J.road_slots(ap))]
    mats = {}
    for uid, fname in slots:
        try:
            mats[fname] = J.slot_matrix(ap, uid)
        except AssertionError:
            mats[fname] = None
    p, _, _ = start_frame()
    best = min((f for f in mats if mats[f]), key=lambda f: np.linalg.norm(np.array(mats[f][3]) - p))
    tpl = W.add_colour(open(J.TEMPLATE, "rb").read())
    tex = texture().tobytes()
    V, I, C, labels, p, start = scene(mats[best])
    test = W.build(tpl, V, I, tex, TW, TH, glow=GLOW, salt=0x56430000, pad_verts=PAD[0], pad_indices=PAD[1],
                   colours=C)
    hidden = [(0, -50, 0, 0, 1, 0, 0.5, 0.5), (0.01, -50, 0, 0, 1, 0, 0.5, 0.5), (0, -50, 0.01, 0, 1, 0, 0.5, 0.5)]
    out = {best: test}
    near = sorted((f for f in mats if mats[f] and f != best), key=lambda f: np.linalg.norm(np.array(mats[f][3]) - p))
    groups = {}
    for k, (glow, f) in enumerate(zip(GROUPS, near)):
        Vk, Ik, Ck, _ = scene_near(mats[f], k)
        out[f] = W.build(tpl, Vk, Ik, tex, TW, TH, glow=glow, salt=0x56430200 + k, pad_verts=PAD[0],
                         pad_indices=PAD[1], colours=Ck)
        got = blurmesh.colours(out[f], blurmesh.read(out[f])["vertex_streams"][0])
        assert got[:len(Ck)] == [tuple(c) for c in Ck] and Ck == C[:len(C) // 2]     # same bands as the reference
        groups[f] = glow
    for k, f in enumerate(f for f in mats if f not in out):
        out[f] = W.build(tpl, hidden, [0, 1, 2], tex, TW, TH, glow=GLOW, salt=0x56430100 + k,
                         pad_verts=PAD[0], pad_indices=PAD[1], colours=[(0, 0, 0, 255)] * 3)
    sizes = {len(d) for d in out.values()}
    assert len(sizes) == 1, sizes                  # every slot model the same size (mixed sizes crash at load)
    for d in out.values():                         # integrity: re-read, colour stream, padded vertex count
        s = blurmesh.read(d)["vertex_streams"][0]
        assert s["stride"] == 24 and s["count"] == PAD[0] and blurmesh.colour_offset(s) == 20
    got = blurmesh.colours(test, blurmesh.read(test)["vertex_streams"][0])
    assert got[:len(C)] == [tuple(c) for c in C]
    return out, best, labels, p, start, groups


def main():
    game = sys.argv[1] if len(sys.argv) > 1 else r"C:/Users/sanqu/Jeux_WII/Blur_vcolor"
    g, t = os.path.normcase(os.path.abspath(game)), os.path.normcase(os.path.abspath(config.BLUR_TEST))
    assert g != t and "program files" not in g, "only a separate copy of the game"
    out, best, labels, p, start, groups = build_all(game)
    flat = os.path.join(game, "models", "objects", "flat_earth")
    for f, d in out.items():
        assert os.path.exists(os.path.join(flat, f)), f
        open(os.path.join(flat, f), "wb").write(d)
    print("%d slot models written (%d bytes each); panel in %s at x %.1f y %.1f z %.1f, %.0f m after the start "
          "(%.1f, %.1f, %.1f)" % (len(out), len(next(iter(out.values()))), best, *p, AHEAD, *start))
    print("second test, %.0f m after the start, left to right: %s" % (NEAR, ", ".join(
        "%s glow %d" % (f, g) for f, g in groups.items())))


if __name__ == "__main__":
    main()
