#!/usr/bin/env python3
"""Blur 2 scenery -> Blur 1 zone models lit by Blur 2's baked light in VERTEX COLOURS (Marina, lot 1, 2026-11-16).

Replaces the mixed mode (b2bake pages + flat b2decor atlases). Only pieces already seen working in game:
- one material per model: template sign_wetfloor + blurmodel_write.add_colour (shader default_NB_NL, POC2);
- material texture (ipr0) black: no specular (R), no self light (G = emissive, the flat look of the old models);
- light = Blur 2 shader on the lightmap pages (b2bake formula), sampled at each vertex (UV1, bilinear);
  triangles without lightmap: Blur 2's fallback 1.25 N.L + 0.32;
- colour = 128 * sqrt(light): Blur 1 squares the colour (DefaultLighting.h, SHNODE_IN_VERTEX_CONSTANT) and the
  in-game tests gave colour 128 = light 1 (exposure);
- tiling kept: a triangle spanning several repeats of its texture is cut on the integer UV lines (up to
  MAX_CELLS pieces), each piece maps into one atlas cell; also gives the ground vertices to carry the light;
- lit triangles longer than MAX_EDGE are cut in 4 (up to 3 times): shadows need vertices (POC2: error 0.21 -> 0.04);
- models of free size (G3b), single-sided with Unity's winding kept (G5: game = (-x, y, -z) is a rotation);
  textures with cut-out alpha stay double-sided.
"""
import collections, os, sys
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import b2bake  # noqa: E402
from b2collision import lap_points  # noqa: E402

ZONE = 150.0          # zone side (m), as b2decor
CELL = 256            # atlas cell (px): 128 before (blurry)
ATLAS = 1024          # 16 textures per model (ponytail: 2048 = 64 textures, 4x the memory; try if slots run out)
MAX_VERTS = 60000     # per model (G2: 65 504 shown in game)
MAX_INDICES = 96000   # per model (G2: 98 256 shown in game)
MAX_CELLS = 16        # tiling repeats kept per triangle; beyond: squeezed into one repeat (as before)
MAX_EDGE = 12.0       # m: lit triangles longer than this cut once in 4 (4 m x 3 levels: 6.4 M triangles, 291 models
                      # for 122 slots; 12 m x 1: 1.85 M, measured on a 5 % sample 2026-11-16)
NOLM = (1.25, 0.32)   # Blur 2 fallback without lightmap: 1.25 N.L + 0.32 (calibration knob)
MAUVE = np.array((0.86, 0.71, 1.0))   # empty texels of the lightmap pages
DETAIL = 0.005        # small far triangles dropped: area < DETAIL * distance (as b2decor)


def encode(L):
    """Blur 1 vertex colour 0..255 from Blur 2 light (linear, exposure applied): shown = colour^2 x 4"""
    return np.clip(np.round(128 * np.sqrt(np.maximum(L, 0))), 0, 255).astype(np.uint8)


def _bilinear(I, uv):
    h, w = I.shape[:2]
    x = (uv[:, 0] % 1) * (w - 1)
    y = (1 - uv[:, 1] % 1) * (h - 1)
    x0, y0 = np.floor(x).astype(int), np.floor(y).astype(int)
    x1, y1 = np.minimum(x0 + 1, w - 1), np.minimum(y0 + 1, h - 1)
    fx, fy = (x - x0)[:, None], (y - y0)[:, None]
    return I[y0, x0] * (1 - fx) * (1 - fy) + I[y0, x1] * fx * (1 - fy) + I[y1, x0] * (1 - fx) * fy + I[y1, x1] * fx * fy


def _clip(poly, axis, k, keep_above):
    """Sutherland-Hodgman on uv0[axis] = k; poly = list of attribute rows (P 3, uv0 2, uv1 2)"""
    out = []
    for a, b in zip(poly, poly[1:] + poly[:1]):
        ia, ib = (a[3 + axis] >= k) == keep_above, (b[3 + axis] >= k) == keep_above
        if ia:
            out.append(a)
        if ia != ib:
            t = (k - a[3 + axis]) / (b[3 + axis] - a[3 + axis])
            out.append(a + t * (b - a))
    return out


def tile_split(P, uv0, uv1):
    """-> [(P 3x3, uv0 3x2 in [0, 1], uv1 3x2)]: the triangle cut on integer uv0 lines"""
    u1 = uv1 if uv1 is not None else np.zeros((3, 2))
    lo, hi = np.floor(uv0.min(0)), np.ceil(uv0.max(0))
    hi = np.maximum(hi, lo + 1)
    n = (hi - lo).astype(int)
    if n.prod() > MAX_CELLS:                                   # squeezed into one repeat (rare: big tiled ground)
        u = uv0 - lo
        return [(P, u / np.maximum(u.max(0), 1), uv1)]
    if n.prod() == 1:
        return [(P, uv0 - lo, uv1)]
    rows = [np.r_[p, q, r] for p, q, r in zip(P, uv0, u1)]
    out = []
    for i in range(n[0]):
        for j in range(n[1]):
            poly = rows
            for ax, k, above in ((0, lo[0] + i, True), (0, lo[0] + i + 1, False),
                                 (1, lo[1] + j, True), (1, lo[1] + j + 1, False)):
                poly = _clip(poly, ax, k, above) if poly else poly
            if len(poly) < 3:
                continue
            V = np.array(poly)
            V[:, 3:5] = np.clip(V[:, 3:5] - (lo[0] + i, lo[1] + j), 0, 1)
            for a in range(1, len(V) - 1):                    # fan (convex)
                T = V[[0, a, a + 1]]
                if np.linalg.norm(np.cross(T[1, :3] - T[0, :3], T[2, :3] - T[0, :3])) > 1e-6:
                    out.append((T[:, :3], T[:, 3:5], T[:, 5:7] if uv1 is not None else None))
    return out


def light_split(P, uv0, uv1, depth=1):
    """lit triangle cut in 4 (edge midpoints) until its edges are <= MAX_EDGE"""
    if depth == 0 or max(np.linalg.norm(P[[1, 2, 0]] - P, axis=1)) <= MAX_EDGE:
        return [(P, uv0, uv1)]
    out = []
    for c in ((0, 3, 5), (3, 1, 4), (5, 4, 2), (3, 4, 5)):   # corners 0..2, midpoints 3 (0,1), 4 (1,2), 5 (2,0)
        sub = [np.vstack([X, (X + X[[1, 2, 0]]) / 2])[list(c)] for X in (P, uv0, uv1)]
        out += light_split(*sub, depth - 1)
    return out


def triangles(data, laps):
    """-> list of (texture id, page or None, P 3x3, uv0 3x2 in [0,1], uv1 3x2 or None, distance to the lap)"""
    from scipy.spatial import cKDTree
    tree = cKDTree(lap_points(laps))
    src = [t for t in data["tris"] if data["tex"].get(t[0]) is not None]
    dist = tree.query(np.array([t[2].mean(0)[[0, 2]] for t in src]))[0]
    out = []
    for (k, pg, P, uv0, uv1), dd in zip(src, dist):
        if np.linalg.norm(np.cross(P[1] - P[0], P[2] - P[0])) / 2 < DETAIL * dd:
            continue
        for p, u, v in tile_split(P, uv0, uv1 if pg else None):
            for q in (light_split(p, u, v) if pg else [(p, u, None)]):
                out.append((k, pg, q[0], q[1], q[2], float(dd)))
    return out


def colours(data, tris):
    """vertex colours (n, 3, 3) uint8 for the triangles of triangles()"""
    N = np.array([np.cross(t[2][1] - t[2][0], t[2][2] - t[2][0]) for t in tris])
    N /= np.maximum(np.linalg.norm(N, axis=1, keepdims=True), 1e-9)
    sun = np.clip(N @ b2bake.SUN, 0, 1)
    L = np.repeat(np.repeat((NOLM[0] * sun + NOLM[1])[:, None, None], 3, 1), 3, 2)
    bypage = collections.defaultdict(list)
    for i, t in enumerate(tris):
        if t[1] is not None:
            bypage[t[1]].append(i)
    for pg, ids in bypage.items():
        A, B = (np.asarray(x, np.float32) / 255 for x in data["lm"][pg])
        uv = np.concatenate([tris[i][4] for i in ids])
        a, b = _bilinear(A, uv), _bilinear(B, uv)
        s = np.repeat(sun[ids], 3)[:, None]
        lit = ((a * b[:, 2:3]) ** 2 * b2bake.AMBIENT + s * b[:, 1:2] ** 2 * b2bake.SUN_COLOUR) * b2bake.EXPOSURE
        empty = ((np.abs(a - MAUVE).sum(1) < 0.15) | (a.sum(1) < 0.01)).reshape(-1, 3)   # mauve or black: no data
        lit = lit.reshape(-1, 3, 3)
        for j, i in enumerate(ids):                            # empty corner: mean of the triangle's others
            e = empty[j]
            if e.all():
                continue                                       # all empty: fallback light kept
            lit[j][e] = lit[j][~e].mean(0)
            L[i] = lit[j]
    return encode(L)


def jobs(data, laps, count):
    """-> [(atlas RGBA, [(3 positions, 3 atlas uv, 3 rgb, double_sided)])] nearest to the lap first, at most count"""
    from PIL import Image
    tris = triangles(data, laps)
    C = colours(data, tris)
    print(len(data["tris"]), "Blur 2 triangles ->", len(tris), "after tiling / light cuts")
    per = ATLAS // CELL
    inset = 0.5 / CELL
    cut = {k: bool((np.asarray(im)[:, :, 3] < 128).any()) for k, im in data["tex"].items() if im is not None}
    zones = collections.defaultdict(list)
    for t, c in zip(tris, C):
        m = t[2].mean(0)
        zones[int(m[0] // ZONE), int(m[2] // ZONE)].append((t, c))
    out = []
    for zt in zones.values():
        zt.sort(key=lambda x: (x[0][0], x[0][5]))             # by texture: few cells per model
        cur, keys, texs, nidx = [], set(), {}, 0
        for t, c in zt:
            u = np.round(inset + t[3] * (1 - 2 * inset), 4)
            kk = {(tuple(np.round(p, 3)), tuple(q), tuple(cc)) for p, q, cc in zip(t[2], u, c)}
            ni = 6 if cut[t[0]] else 3
            if cur and (len(keys) + len(kk - keys) > MAX_VERTS or nidx + ni > MAX_INDICES
                        or (t[0] not in texs and len(texs) == per * per)):
                out.append((min(x[0][5] for x in cur), texs, cur))
                cur, keys, texs, nidx = [], set(), {}, 0
            texs.setdefault(t[0], len(texs))
            cur.append((t, c, u))
            keys |= kk
            nidx += ni
        if cur:
            out.append((min(x[0][5] for x in cur), texs, cur))
    out.sort(key=lambda j: j[0])
    print(len(out), "models possible,", min(count, len(out)), "kept, nearest left out:",
          round(out[count][0]) if len(out) > count else None, "m")
    res = []
    for _, texs, cur in out[:count]:
        img = Image.new("RGBA", (ATLAS, ATLAS))
        for k, i in texs.items():
            img.paste(data["tex"][k].resize((CELL, CELL), Image.LANCZOS), ((i % per) * CELL, (i // per) * CELL))
        mt = []
        for t, c, u in cur:
            i = texs[t[0]]
            cu = ((i % per) + u[:, 0]) / per
            cv = 1 - ((i // per) + (1 - u[:, 1])) / per          # Unity v up; atlas rows top-down; writer stores 1 - v
            mt.append(([tuple(p) for p in t[2]], list(zip(cu, cv)), [tuple(int(x) for x in cc) for cc in c],
                       cut[t[0]]))
        res.append((img, mt))
    return res


def write(tris, matrix, path, img, salt, ground):
    """zone triangles -> .model in the slot's local axes (world = x ax + y ay + z az + aw), y shifted by 1 - ground
    (Map Builder floor). Returns (vertices, indices)."""
    import blurmodel_write as W
    M = np.array(matrix[:3]).T
    inv, o = np.linalg.inv(M), np.array(matrix[3])
    verts, cols, idx, seen = [], [], [], {}
    for ps, us, cs, two in tris:
        P = [inv @ (np.array(p) + (0, 1.0 - ground, 0) - o) for p in ps]
        n = np.cross(P[1] - P[0], P[2] - P[0])
        n = n / (np.linalg.norm(n) or 1)
        ids = []
        for p, (u, v), c in zip(P, us, cs):
            key = (tuple(np.round(p, 3)), u, v, c)
            if key not in seen:
                seen[key] = len(verts)
                verts.append((*p, *n, u, 1 - v))
                cols.append((*c, 255))
            ids.append(seen[key])
        idx += ids + ids[::-1] if two else ids
    assert len(verts) <= 0xFFFF
    d = W.build(_template(), verts, idx, img.tobytes(), *img.size, glow=0, salt=salt, colours=cols)
    open(path, "wb").write(d)
    return len(verts), len(idx)


_TPL = []


def _template():
    if not _TPL:
        import blurmodel_write as W
        import make_nfs_map as J
        _TPL.append(W.add_colour(open(J.TEMPLATE, "rb").read()))
    return _TPL[0]


def _selftest():
    """tiling cut: a triangle over 2 x 1 repeats -> pieces covering the same area, uv in [0, 1]; light cut: 4^k"""
    P = np.array([[0, 0, 0], [10, 0, 0], [0, 0, 5]], float)
    uv = np.array([[0, 0], [2, 0], [0, 1]], float)
    parts = tile_split(P, uv, uv.copy())
    area = lambda Q: np.linalg.norm(np.cross(Q[1] - Q[0], Q[2] - Q[0])) / 2
    assert len(parts) >= 2 and abs(sum(area(p) for p, _, _ in parts) - area(P)) < 1e-6, parts
    assert all(u.min() >= 0 and u.max() <= 1 for _, u, _ in parts)
    sub = light_split(3 * P, uv, uv)                           # edges 30-34 m > MAX_EDGE: one cut
    assert len(sub) == 4 and abs(sum(area(p) for p, _, _ in sub) - area(3 * P)) < 1e-6
    assert encode(np.array([0, 1, 4, 9]).astype(float)).tolist() == [0, 128, 255, 255]
    print("b2lit selftest OK:", len(parts), "tiling pieces,", len(sub), "light pieces")


if __name__ == "__main__":
    _selftest()
