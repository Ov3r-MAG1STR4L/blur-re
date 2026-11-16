#!/usr/bin/env python3
"""Proof of concept: Blur 2 baked light -> Blur 1 vertex colours, on ONE piece of the south-west glass tower of
Dubai Marina (the b2proto area), for the test copy Blur_vcolor only.

Source (Blur2DubaiTest, read only): MeshRenderer `draws_d0154` (path PIECE, tower block 65 x 55 x 97 m), material with _HasDualLightmap,
_BaseMap tex_1904 whitepanel_square, lightmaps A = _Lightmap0Tex, B = _Lightmap1Tex read on UV1 (= m_UV1, the
lightmap UVs; UV0 = texture UVs).
Light per vertex (shader Blur2/InspectionSurface, docs/CONNAISSANCES.md):
    indirect = (A.rgb * B.z)^2 * lerp(_BakedColour, _EnvBakedColour, _EnvBlend)
    sun      = saturate(N.L) * B.y^2 * main light colour          (B.y ~ 0 on Dubai; SUN / SUN_COLOUR guessed)
    light    = (indirect + sun) * EXPOSURE                         (b2bake.EXPOSURE, as the Marina decor)
Blur 2 shows encode(base_linear * light) ; Blur 1 (2nd in-game test, material light 0) shows about
base_display * colour / 128 (product in the texture's space, gain 2). Same picture when
    colour = 128 * light ^ (1 / 2.2)        (clipped to 0..255: margin up to light 4.5)
rather than 128 * light: the "x 128" hypothesis would darken mid lights (light 0.25 -> 32 instead of 69).

usage: b2vcolor_poc.py report OUT_DIR            measurements + offline renders (nothing installed)
       b2vcolor_poc.py install GAME_COPY OUT_DIR   + the piece in Blur_vcolor (the panels kept)
"""
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import b2bake  # noqa: E402
import b2proto  # noqa: E402

PIECE = 12991
GAMMA = 2.2
TEX = 512
LAP = r"C:/Users/sanqu/Jeux_WII/blur2_aid/dubai/lap_route4_marina.csv"
MAUVE = np.array((0.86, 0.71, 1.0))          # empty padding of the lightmap pages
TOWER = (np.array([-1112, 0, -744]), np.array([-1043, 110, -685]))        # draws_d0154's box + 2 m (game axes)
_ENV = []


def load(path_id=PIECE, box=None):
    """the piece: P, N (game axes), uv0 (texture, _BaseMap tiling applied), uv1 (lightmap), triangles, images;
    box: only the triangles inside it (vertices renumbered)"""
    import UnityPy
    from UnityPy.helpers.MeshHelper import MeshHandler
    import b2collision
    if not _ENV:
        _ENV.append(UnityPy.load(b2proto.UNITY))
    env = _ENV[0]
    o = next(o for o in env.objects if o.path_id == path_id and o.type.name == "MeshRenderer")
    r = o.read()
    go = r.m_GameObject.read()
    comps = [p.read() for p in (x.component if hasattr(x, "component") else x for x in go.m_Component)
             if p.type.name in ("Transform", "MeshFilter")]
    tr = next(c for c in comps if c.object_reader.type.name == "Transform")
    mf = next(c for c in comps if c.object_reader.type.name == "MeshFilter")
    h = MeshHandler(mf.m_Mesh.read())
    h.process()
    m = b2collision.world_matrix(tr)
    P = (np.array(h.m_Vertices, float).reshape(-1, 3) @ m[:3, :3].T + m[:3, 3]) * [-1, 1, -1]
    N = np.array(h.m_Normals, float).reshape(-1, 3) @ np.linalg.inv(m[:3, :3]) * [-1, 1, -1]
    N /= np.maximum(np.linalg.norm(N, axis=1, keepdims=True), 1e-9)
    uv0 = np.array(h.m_UV0, float).reshape(-1, 2)
    uv1 = np.array(h.m_UV1, float).reshape(-1, 2)
    subs = [s for s, mp in zip(h.get_triangles(), r.m_Materials) if mp.path_id]
    assert len(subs) == 1 and len(r.m_Materials) == 1, "one material expected"
    mat = r.m_Materials[0].read()
    te = dict(mat.m_SavedProperties.m_TexEnvs)
    fl = dict(mat.m_SavedProperties.m_Floats)
    co = {k: np.array([v.r, v.g, v.b]) for k, v in dict(mat.m_SavedProperties.m_Colors).items()}
    base = te["_BaseMap"]
    st = (base.m_Scale.x, base.m_Scale.y, base.m_Offset.x, base.m_Offset.y)
    img = lambda k, mode: base_img(te[k].m_Texture.read(), mode)
    src = dict(name=go.m_Name, material=mat.m_Name, base=te["_BaseMap"].m_Texture.read().m_Name,
               a=te["_Lightmap0Tex"].m_Texture.read().m_Name, b=te["_Lightmap1Tex"].m_Texture.read().m_Name,
               dual=fl.get("_HasDualLightmap", 0), env_blend=fl.get("_EnvBlend", 0.0), st=st,
               baked=co.get("_BakedColour", np.ones(3)).tolist(), env_baked=co.get("_EnvBakedColour", np.ones(3)).tolist(),
               alpha_test=fl.get("_AlphaTest", 0), has_material=fl.get("_HasMaterial", 0))
    tris = np.array(subs[0], int).reshape(-1, 3)
    if box is not None:
        tris = tris[((P >= box[0]) & (P <= box[1])).all(1)[tris].all(1)]
        keep = np.unique(tris)
        new = np.full(len(P), -1)
        new[keep] = np.arange(len(keep))
        tris, P, N, uv0, uv1 = new[tris], P[keep], N[keep], uv0[keep], uv1[keep]
    checks = dict(verts=len(P), tris=len(tris), uv1_per_vertex=len(uv1) == len(P), uv0_per_vertex=len(uv0) == len(P),
                  normals=len(N) == len(P), uv1_range=[float(uv1.min()), float(uv1.max())],
                  dual=src["dual"] > 0.5)
    assert checks["uv1_per_vertex"] and checks["uv0_per_vertex"] and checks["normals"] and checks["dual"], checks
    assert 0 <= uv1.min() and uv1.max() <= 1, "UV1 outside the lightmap page"
    return dict(P=P, N=N, uv0=uv0 * st[:2] + st[2:], uv1=uv1, tris=tris, src=src, checks=checks,
                base=img("_BaseMap", "RGBA"), A=img("_Lightmap0Tex", "RGB"), B=img("_Lightmap1Tex", "RGB"))


def base_img(t, mode):
    return np.asarray(t.image.convert(mode), np.float32) / 255           # rows top-down (v = 1 at row 0)


def bilinear(I, uv):
    """clamped bilinear sample, Unity uv (v up)"""
    h, w = I.shape[:2]
    x = np.clip(uv[:, 0], 0, 1) * (w - 1)
    y = (1 - np.clip(uv[:, 1], 0, 1)) * (h - 1)
    x0, y0 = np.floor(x).astype(int), np.floor(y).astype(int)
    x1, y1 = np.minimum(x0 + 1, w - 1), np.minimum(y0 + 1, h - 1)
    fx, fy = (x - x0)[:, None], (y - y0)[:, None]
    return (I[y0, x0] * (1 - fx) * (1 - fy) + I[y0, x1] * fx * (1 - fy) + I[y1, x0] * (1 - fx) * fy
            + I[y1, x1] * fx * fy)


def light(pc, uv1, N):
    """Blur 2 baked light (linear, exposure applied) at lightmap coordinates uv1 with normals N"""
    A, B = bilinear(pc["A"], uv1), bilinear(pc["B"], uv1)
    s = pc["src"]
    amb = np.array(s["baked"]) * (1 - s["env_blend"]) + np.array(s["env_baked"]) * s["env_blend"]
    ind = (A * B[:, 2:3]) ** 2 * amb
    sun = np.clip(N @ b2bake.SUN, 0, 1)[:, None] * B[:, 1:2] ** 2 * b2bake.SUN_COLOUR
    return (ind + sun) * b2bake.EXPOSURE, ind, sun, A


def encode(L):
    """Blur 1 vertex colour (0..255) from the linear light"""
    return np.clip(np.round(128 * np.maximum(L, 0) ** (1 / GAMMA)), 0, 255).astype(int)


def vertex_light(pc):
    L, ind, sun, A = light(pc, pc["uv1"], pc["N"])
    empty = np.abs(A - MAUVE).sum(1) < 0.15                 # vertex on the mauve padding: mean of its triangles
    for v in np.flatnonzero(empty):
        nb = np.unique(pc["tris"][(pc["tris"] == v).any(1)])
        nb = nb[~empty[nb]]
        if len(nb):
            L[v] = L[nb].mean(0)
    return L, ind, sun, empty


def triangle_error(pc, Lv):
    """display-space error of interpolating the light from the vertices: per triangle, max over 7 inner points"""
    bc = np.array([[1/3, 1/3, 1/3], [.5, .5, 0], [0, .5, .5], [.5, 0, .5], [2/3, 1/6, 1/6], [1/6, 2/3, 1/6],
                   [1/6, 1/6, 2/3]])
    T = pc["tris"]
    err = np.zeros(len(T))
    col = encode(Lv).astype(float) / 128                     # what Blur 1 shows (display space, x 1 = texture)
    for b in bc:
        uv = (pc["uv1"][T] * b[None, :, None]).sum(1)
        n = (pc["N"][T] * b[None, :, None]).sum(1)
        n /= np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-9)
        true = np.clip(light(pc, uv, n)[0], 0, None) ** (1 / GAMMA)
        interp = (col[T] * b[None, :, None]).sum(1)
        err = np.maximum(err, np.abs(true - interp).max(1))
    P = pc["P"][T]
    area = 0.5 * np.linalg.norm(np.cross(P[:, 1] - P[:, 0], P[:, 2] - P[:, 0]), axis=1)
    return err, area


def subdivision_gain(pc, Lv, err, limit=0.10):
    """measured, not applied: split each triangle over `limit` in 4 (edge midpoints get their own light) and
    re-measure; cost = new vertices (shared midpoints), against the ~10 000 vertices Blur 1 model budget"""
    T = pc["tris"][err > limit]
    if not len(T):
        return dict(triangles=0)
    edges = {}
    for t in T:
        for a, b in ((t[0], t[1]), (t[1], t[2]), (t[2], t[0])):
            edges.setdefault((min(a, b), max(a, b)), len(edges))
    e = np.array(list(edges))
    uvm = (pc["uv1"][e[:, 0]] + pc["uv1"][e[:, 1]]) / 2
    nm = pc["N"][e[:, 0]] + pc["N"][e[:, 1]]
    nm /= np.maximum(np.linalg.norm(nm, axis=1, keepdims=True), 1e-9)
    sub = dict(P=None, N=np.vstack([pc["N"], nm]), uv1=np.vstack([pc["uv1"], uvm]), A=pc["A"], B=pc["B"], src=pc["src"])
    Lm = light(pc, uvm, nm)[0]
    L2 = np.vstack([Lv, Lm])
    n0 = len(Lv)
    m = lambda a, b: n0 + edges[(min(a, b), max(a, b))]
    T2 = np.array([q for a, b, c in T for q in ((a, m(a, b), m(c, a)), (m(a, b), b, m(b, c)), (m(c, a), m(b, c), c),
                                                 (m(a, b), m(b, c), m(c, a)))])
    sub["tris"] = T2
    sub["P"] = np.zeros((len(L2), 3))
    err2, _ = triangle_error(sub, L2)
    worst = err2.reshape(-1, 4).max(1)
    return dict(triangles=int(len(T)), new_vertices=len(edges), new_triangles=3 * len(T),
                err_before=float(err[err > limit].mean()), err_after=float(worst.mean()),
                still_over=int((worst > limit).sum()))


def subdivide(pc):
    """every triangle in 4 (shared edge midpoints: no crack); positions, normals, both UV sets interpolated"""
    T = pc["tris"]
    e = np.sort(np.vstack([T[:, [0, 1]], T[:, [1, 2]], T[:, [2, 0]]]), 1)
    e, inv = np.unique(e, axis=0, return_inverse=True)
    n0 = len(pc["P"])
    mid = n0 + inv.reshape(3, -1).T                         # per triangle: midpoint of (0,1), (1,2), (2,0)
    q = dict(pc)
    for k in ("P", "uv0", "uv1"):
        q[k] = np.vstack([pc[k], (pc[k][e[:, 0]] + pc[k][e[:, 1]]) / 2])
    nm = pc["N"][e[:, 0]] + pc["N"][e[:, 1]]
    q["N"] = np.vstack([pc["N"], nm / np.maximum(np.linalg.norm(nm, axis=1, keepdims=True), 1e-9)])
    a, b, c = T.T
    ab, bc, ca = mid.T
    q["tris"] = np.vstack([np.c_[a, ab, ca], np.c_[ab, b, bc], np.c_[ca, bc, c], np.c_[ab, bc, ca]])
    return q


def subdivision_levels(pid, levels=4, budget=7500):
    """uniform subdivision, measured: vertices, triangles, area-weighted interpolation error per level"""
    pc = load(pid, TOWER)
    out = []
    for lv in range(levels + 1):
        if lv:
            pc = subdivide(pc)
        if len(pc["P"]) > 4 * budget:
            break
        Lv = vertex_light(pc)[0]
        err, area = triangle_error(pc, Lv)
        out.append(dict(level=lv, verts=len(pc["P"]), tris=len(pc["tris"]), err=float((err * area).sum() / area.sum()),
                        area_over_0_10=float(area[err > .1].sum() / area.sum()), fits=len(pc["P"]) <= budget))
    return out


def ground_low():
    import csv
    return min(float(r["y"]) for r in csv.DictReader(open(LAP)))


def model_data(pc, Lv, matrix, low):
    """slot-local vertices, single-sided indices (front = cross(b - a, c - a) on the normal side, as the template;
    double-sided would pass 32 767 indices), colours, RGB texture (TEX x TEX) for blurmodel_write.build"""
    from PIL import Image
    M = np.array(matrix[:3]).T
    inv, o = np.linalg.inv(M), np.array(matrix[3])
    Pw = pc["P"] + (0, 1.0 - low, 0)                         # Map Builder ground: y = 1 (as the Marina decor)
    Pl = (Pw - o) @ inv.T
    Nl = pc["N"] @ inv.T
    Nl /= np.maximum(np.linalg.norm(Nl, axis=1, keepdims=True), 1e-9)
    V = [(*p, *n, u, 1 - v) for p, n, (u, v) in zip(Pl, Nl, pc["uv0"])]        # Blur stores v top-down
    T = pc["tris"]
    fn = np.cross(Pl[T[:, 1]] - Pl[T[:, 0]], Pl[T[:, 2]] - Pl[T[:, 0]])
    flip = (fn * Nl[T].sum(1)).sum(1) < 0
    I = [int(i) for t, f in zip(T, flip) for i in ((t[0], t[2], t[1]) if f else t)]
    C = [(*c, 255) for c in encode(Lv)]
    img = Image.fromarray((pc["base"][:, :, :3] * 255).astype(np.uint8)).resize((TEX, TEX), Image.LANCZOS)
    return V, I, C, img.tobytes()


def renders(pc, Lv, out_dir, cam=None, look=None, tag="poc", extra=None):
    """offline: Blur 2 formula per pixel (REF), Blur 1 expected (vertex colours), their difference;
    extra = (pc, Lv) of the same piece without subdivision: its expected render as one more panel"""
    from PIL import Image, ImageDraw
    info = dict(base=("b", 0), st=(1, 1, 0, 0), a=None, b=None, mat=None, alpha=False, cut=.5)
    T = [(pc["P"][t], pc["N"][t], pc["uv0"][t], pc["uv1"][t], info) for t in pc["tris"]]
    if cam is None:
        cam, look = np.array((-1215.0, 45, -600)), np.array((-1080.0, 50, -715))   # b2proto's camera on this area
    c = look
    tid, bary = b2proto.raster(T, cam, c)
    W, H = b2proto.W, b2proto.H
    sky = (0.72, 0.78, 0.86)
    ref, exp_ = np.zeros((H, W, 3)) + sky, np.zeros((H, W, 3)) + sky
    py, px = np.nonzero(tid >= 0)
    L = bary[py, px]
    tri = pc["tris"][tid[py, px]]
    uv0 = (pc["uv0"][tri] * L[:, :, None]).sum(1)
    uv1 = (pc["uv1"][tri] * L[:, :, None]).sum(1)
    n = (pc["N"][tri] * L[:, :, None]).sum(1)
    n /= np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-9)
    base = b2proto.tex({0: pc["base"]}, 0, uv0)[:, :3]
    ref[py, px] = np.clip(base ** GAMMA * light(pc, uv1, n)[0], 0, 1) ** (1 / GAMMA)
    col = (encode(Lv)[tri] * L[:, :, None]).sum(1) / 128
    exp_[py, px] = np.clip(base * col, 0, 1)
    panels = [("Blur 2 (formule, par pixel)", ref), ("Blur 1 attendu (couleurs de sommet)", exp_),
              ("ecart x4", np.clip(np.abs(ref - exp_) * 4, 0, 1))]
    m = tid >= 0
    Y = np.array((0.2126, 0.7152, 0.0722))
    lum = lambda im: (im[m] @ Y) * 255
    stats = dict(cam=np.asarray(cam).tolist(), look=np.asarray(c).tolist(), pixels=int(m.sum()),
                 ref_mean=float(lum(ref).mean()), exp_mean=float(lum(exp_).mean()),
                 mean_abs_err=float(np.abs(lum(ref) - lum(exp_)).mean()),
                 p95_abs_err=float(np.percentile(np.abs(lum(ref) - lum(exp_)), 95)),
                 ref_std=float(lum(ref).std()), exp_std=float(lum(exp_).std()))
    if extra is not None:                                   # same view, light from the unsubdivided vertices
        pc0, Lv0 = extra
        T0 = [(pc0["P"][t], pc0["N"][t], pc0["uv0"][t], pc0["uv1"][t], info) for t in pc0["tris"]]
        tid0, bary0 = b2proto.raster(T0, cam, c)
        e0 = np.zeros((H, W, 3)) + sky
        q = tid0 >= 0
        qy, qx = np.nonzero(q)
        L0 = bary0[qy, qx]
        tri0 = pc0["tris"][tid0[qy, qx]]
        b0 = b2proto.tex({0: pc0["base"]}, 0, (pc0["uv0"][tri0] * L0[:, :, None]).sum(1))[:, :3]
        e0[qy, qx] = np.clip(b0 * (encode(Lv0)[tri0] * L0[:, :, None]).sum(1) / 128, 0, 1)
        panels.insert(2, ("Blur 1 attendu sans subdivision", e0))
        both = m & q
        l0, lr = (e0[both] @ Y) * 255, (ref[both] @ Y) * 255
        stats.update(nosub_mean_abs_err=float(np.abs(lr - l0).mean()),
                     nosub_p95_abs_err=float(np.percentile(np.abs(lr - l0), 95)), nosub_std=float(l0.std()))
    os.makedirs(out_dir, exist_ok=True)
    sheet = Image.new("RGB", (W * len(panels), H), "white")
    for k, (name, im) in enumerate(panels):
        p = Image.fromarray((im * 255).astype(np.uint8))
        ImageDraw.Draw(p).text((8, 8), name, fill=(255, 0, 0))
        p.save(os.path.join(out_dir, "%s_%d.png" % (tag, k)))
        sheet.paste(p, (k * W, 0))
    sheet.save(os.path.join(out_dir, "%s_planche.png" % tag))
    return stats


def survey(ids, out):
    """candidate solid surfaces among the tower's lots (triangles inside TOWER): size, flatness, vertex density,
    light contrast and shadows (display light on 7 points per triangle), interpolation error, subdivision gain"""
    rows = []
    for pid in ids:
        try:
            pc = load(pid, TOWER)
        except (AssertionError, KeyError, StopIteration) as e:
            rows.append(dict(path=pid, error="%s %s" % (type(e).__name__, e)))
            continue
        if pc["src"]["alpha_test"] > .5 or len(pc["tris"]) < 40:
            continue
        T = pc["tris"]
        Pt = pc["P"][T]
        cr = np.cross(Pt[:, 1] - Pt[:, 0], Pt[:, 2] - Pt[:, 0])
        area = 0.5 * np.linalg.norm(cr, axis=1)
        Lv, ind, sun, empty = vertex_light(pc)
        err, _ = triangle_error(pc, Lv)
        bc = np.array([[1/3, 1/3, 1/3], [.5, .5, 0], [0, .5, .5], [.5, 0, .5], [2/3, 1/6, 1/6], [1/6, 2/3, 1/6], [1/6, 1/6, 2/3]])
        d = []
        for b in bc:
            uv = (pc["uv1"][T] * b[None, :, None]).sum(1)
            n = (pc["N"][T] * b[None, :, None]).sum(1)
            n /= np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-9)
            d.append(np.clip(light(pc, uv, n)[0], 0, None).mean(1) ** (1 / GAMMA))
        d = np.array(d).T                                          # triangles x 7, display light
        w = np.repeat(area[:, None], 7, 1).ravel() / 7
        med = np.median(d)
        sub = subdivision_gain(pc, Lv, err)
        rows.append(dict(path=pid, name=pc["src"]["name"], base=pc["src"]["base"], verts=len(pc["P"]), tris=len(T),
                         area_m2=float(area.sum()), flatness=float(np.linalg.norm(cr.sum(0)) / (2 * area.sum())),
                         verts_per_100m2=float(100 * len(pc["P"]) / area.sum()),
                         light_p5=float(np.percentile(d, 5)), light_p95=float(np.percentile(d, 95)),
                         shadow_share=float(w[(d < 0.6 * med).ravel()].sum() / w.sum()),
                         intra_tri_var=float((area * (d.max(1) - d.min(1))).sum() / area.sum()),
                         err_mean=float((area * err).sum() / area.sum()), area_err_over_0_10=float(area[err > .1].sum() / area.sum()),
                         subdiv_new_vertices=sub.get("new_vertices", 0), subdiv_err=(sub.get("err_before"), sub.get("err_after")),
                         mauve=int(empty.sum()), uv1=pc["checks"]["uv1_range"], lightmaps=(pc["src"]["a"], pc["src"]["b"])))
        print(json.dumps(rows[-1], default=float), flush=True)
    json.dump(rows, open(out, "w"), indent=1, default=float)
    return rows


def poc2(out_dir, game=None, pid=11220, level=2):
    """second proof of concept: a solid surface of the tower (lot `pid` inside TOWER), uniform subdivision `level`,
    same light formula, encoding, shader and material light 0 as the first one; game: install ONE model"""
    import csv
    pc0 = load(pid, TOWER)
    Lv0 = vertex_light(pc0)[0]
    pc = pc0
    for _ in range(level):
        pc = subdivide(pc)
    Lv, ind, sun, empty = vertex_light(pc)
    err0, area0 = triangle_error(pc0, Lv0)
    err, area = triangle_error(pc, Lv)
    col = encode(Lv)
    lap = np.array([(float(r["x"]), float(r["y"]), float(r["z"])) for r in csv.DictReader(open(LAP))])
    c = pc["P"].mean(0)
    info = dict(base=("b", 0), st=(1, 1, 0, 0), a=None, b=None, mat=None, alpha=False, cut=.5)
    T = [(pc["P"][t], pc["N"][t], pc["uv0"][t], pc["uv1"][t], info) for t in pc["tris"]]
    dist = np.hypot(lap[:, 0] - c[0], lap[:, 2] - c[2])
    best = None                                              # from the route (as in game), 25..150 m, most pixels
    for i in np.flatnonzero((dist > 25) & (dist < 150))[::3]:
        cam = lap[i] + (0, 2.5, 0)
        n = (b2proto.raster(T, cam, c)[0] >= 0).sum()
        if best is None or n > best[0]:
            best = (n, cam)
    w = lambda e, a: dict(err=float((e * a).sum() / a.sum()), area_over_0_10=float(a[e > .1].sum() / a.sum()))
    r = dict(source=pc0["src"], path=pid, level=level, checks=pc0["checks"], mauve_vertices=int(empty.sum()),
             verts=len(pc["P"]), tris=len(pc["tris"]), area_m2=float(area.sum()),
             light=dict(mean=Lv.mean(0).tolist(), p50=float(np.percentile(Lv.mean(1), 50)), max=float(Lv.max()),
                        sun_share=float(sun.sum() / max(1e-9, (ind + sun).sum()))),
             colour=dict(min=int(col.min()), max=int(col.max()), mean=col.mean(0).tolist(),
                         clipped=int((128 * np.maximum(Lv, 0) ** (1 / GAMMA) > 255).any(1).sum())),
             interpolation=dict(level0=w(err0, area0), chosen=w(err, area)))
    r["render"] = renders(pc, Lv, out_dir, cam=best[1], look=c, tag="poc2", extra=(pc0, Lv0))
    if game:
        r["installed"] = install_one(game, pc, Lv, c)
    json.dump(r, open(os.path.join(out_dir, "poc2_rapport.json"), "w"), indent=1, default=float)
    print(json.dumps(r, indent=1, default=float))
    return r


def install_one(game, pc, Lv, centre, keep=("nfs_101.model", "nfs_035.model", "nfs_048.model", "road_21_00.model",
                                              "nfs_042.model")):
    """write ONE slot model (a hidden slot near the piece) of the same size as the others; nothing else touched"""
    import blurmesh
    import blurmodel_write as W
    import make_nfs_map as J
    import config
    g = os.path.normcase(os.path.abspath(game))
    assert g != os.path.normcase(os.path.abspath(config.BLUR_TEST)) and "program files" not in g
    ap = os.path.join(game, "gamedata", "levels", "flat_earth", "actorpack.xt")
    flat = os.path.join(game, "models", "objects", "flat_earth")
    mats = {}
    for k in range(110):
        f = "nfs_%03d.model" % k
        if f in keep:
            continue
        try:
            mats[f] = J.slot_matrix(ap, J.NFS_UID + 2 * k + 1)
        except AssertionError:
            pass
    slot = min(mats, key=lambda f: np.linalg.norm(np.array(mats[f][3])[[0, 2]] - centre[[0, 2]]))
    V, I, C, tex = model_data(pc, Lv, mats[slot], ground_low())
    tpl = W.add_colour(open(J.TEMPLATE, "rb").read())
    d = W.build(tpl, V, I, tex, TEX, TEX, glow=0, salt=0x56430400, pad_verts=7500, pad_indices=25600, colours=C)
    size = {os.path.getsize(os.path.join(flat, f)) for f in os.listdir(flat) if f.startswith(("nfs_", "road_21_"))}
    assert size == {len(d)}, (size, len(d))
    s = blurmesh.read(d)["vertex_streams"][0]
    assert blurmesh.colours(d, s)[:len(C)] == [tuple(x) for x in C]
    open(os.path.join(flat, slot), "wb").write(d)
    return dict(slot=slot, bytes=len(d),
                slot_distance=float(np.linalg.norm(np.array(mats[slot][3])[[0, 2]] - centre[[0, 2]])))


def report(out_dir):
    pc = load()
    Lv, ind, sun, empty = vertex_light(pc)
    col = encode(Lv)
    err, area = triangle_error(pc, Lv)
    r = dict(source=pc["src"], checks=pc["checks"], mauve_vertices=int(empty.sum()),
             light=dict(mean=Lv.mean(0).tolist(), p50=np.percentile(Lv.mean(1), 50), p99=np.percentile(Lv.mean(1), 99),
                        max=float(Lv.max()), sun_share=float(sun.sum() / max(1e-9, (ind + sun).sum()))),
             colour=dict(mean=col.mean(0).tolist(), min=int(col.min()), max=int(col.max()),
                         clipped=int((128 * np.maximum(Lv, 0) ** (1 / GAMMA) > 255).any(1).sum()),
                         x128_hypothesis_mean=np.clip(128 * Lv, 0, 255).mean(0).tolist()),
             triangles=dict(n=len(err), err_mean=float(err.mean()), over_0_05=int((err > .05).sum()),
                            over_0_10=int((err > .10).sum()), over_0_20=int((err > .20).sum()),
                            area_over_0_10=float(area[err > .10].sum() / area.sum())))
    r["subdivision_0_10"] = subdivision_gain(pc, Lv, err)
    r["render"] = renders(pc, Lv, out_dir)
    os.makedirs(out_dir, exist_ok=True)
    json.dump(r, open(os.path.join(out_dir, "poc_rapport.json"), "w"), indent=1, default=float)
    print(json.dumps(r, indent=1, default=float))
    return pc, Lv


def install(game, out_dir):
    import blurmesh
    import blurmodel_write as W
    import make_nfs_map as J
    import vcolor_scene as S
    import config
    g = os.path.normcase(os.path.abspath(game))
    assert g != os.path.normcase(os.path.abspath(config.BLUR_TEST)) and "program files" not in g
    pc, Lv = report(out_dir)
    S.PAD = (7500, 25600)                                     # every slot model the same size
    S.TW = S.TH = TEX
    S.CELL = TEX // 16
    out, best, labels, p, start, groups = S.build_all(game)
    ap = os.path.join(game, "gamedata", "levels", "flat_earth", "actorpack.xt")
    used = set(groups) | {best}
    c = pc["P"].mean(0)
    cand = [f for f in out if f not in used and f.startswith("nfs_")]
    mats = {}
    for f in cand:
        try:
            mats[f] = J.slot_matrix(ap, J.NFS_UID + 2 * int(f[4:7]) + 1)
        except AssertionError:                             # slot without a visible actor
            pass
    slot = min(mats, key=lambda f: np.linalg.norm(np.array(mats[f][3])[[0, 2]] - c[[0, 2]]))
    V, I, C, tex = model_data(pc, Lv, mats[slot], ground_low())
    tpl = W.add_colour(open(J.TEMPLATE, "rb").read())
    piece = W.build(tpl, V, I, tex, TEX, TEX, glow=0, salt=0x56430300, pad_verts=S.PAD[0], pad_indices=S.PAD[1],
                    colours=C)
    assert len(piece) == len(out[best]), (len(piece), len(out[best]))
    s = blurmesh.read(piece)["vertex_streams"][0]
    assert blurmesh.colours(piece, s)[:len(C)] == [tuple(x) for x in C]
    out[slot] = piece
    flat = os.path.join(game, "models", "objects", "flat_earth")
    for f, d in out.items():
        assert os.path.exists(os.path.join(flat, f)), f
        open(os.path.join(flat, f), "wb").write(d)
    print("%d models of %d bytes; piece %s in %s (%.0f m from its slot actor), panels %s %s" % (
        len(out), len(piece), pc["src"]["name"], slot, np.linalg.norm(np.array(mats[slot][3])[[0, 2]] - c[[0, 2]]),
        best, groups))
    return slot


if __name__ == "__main__":
    if sys.argv[1] == "poc2":
        poc2(sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else None)
    elif sys.argv[1] == "survey":
        survey([int(x) for x in sys.argv[3:]], sys.argv[2])
    elif sys.argv[1] == "report":
        report(sys.argv[2])
    else:
        install(sys.argv[2], sys.argv[3])
