#!/usr/bin/env python3
"""Blur 2 scenery baked like Blur2DubaiTest's shader (Blur2/InspectionSurface, disassembled 2026-11-10), one texture
per Blur 2 lightmap page.

Dual lightmap branch of the pixel shader (A = _Lightmap0Tex t7, B = _Lightmap1Tex t8, both on mesh UV1 = v5.zw):
    indirect = (A.rgb * B.z)^2
    sun      = saturate(N . L) * B.y^2 * _MainLightColor
    ambient  = lerp(_BakedColour, _Blur2EnvBakedColour, _Blur2EnvBlend)
    colour   = albedo * (indirect * ambient + sun)
A page's UV1 layout is a non-overlapping unwrap of all its meshes: each texel of the page is baked with the
triangle covering it (albedo sampled with its own tiling, normal of the triangle), and the meshes use UV1.
"""
import os, sys
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import b2decor  # noqa: E402

SUN = np.array([0.45, 0.8, 0.4]) / np.linalg.norm([0.45, 0.8, 0.4])   # game axes; still a guess
SUN_COLOUR = np.array([1.0, 0.95, 0.85])
AMBIENT = np.array([1.0, 1.0, 1.0])                                     # _BakedColour of the materials seen: white
EXPOSURE = 2.2      # 4.0 washed light facades to white in game (2026-11-10). Unity adapts exposure at run time (Blur2SceneExposure); (A * B.z)^2 over Dubai's lightmaps:
                    # median 0.25 (10 % 0.016, 90 % 0.55) -> the median lit surface shows its albedo
# B.y (sun visibility) is ~0 on the used texels of the pages measured: the sun term hardly counts


def extract(data_dir, laps, route, radius=300.0):
    """-> {"tex": {id: RGBA}, "lm": {id: (A RGB uint8, B RGB uint8)}, "tris": [(tex id, lm id or None, P 3x3 game,
    uv0 3x2 tiled, uv1 3x2)]}"""
    import UnityPy
    from UnityPy.helpers.MeshHelper import MeshHandler
    from scipy.spatial import cKDTree
    import b2collision
    tree = cKDTree(b2decor.lap_points(laps))
    env = UnityPy.load(data_dir)
    tex, lm, tris, mat = {}, {}, [], {}
    for o in env.objects:
        if o.type.name != "MeshRenderer":
            continue
        r = o.read()
        go = r.m_GameObject.read()
        if go.m_Name.startswith("physics"):
            continue
        comps = [p.read() for p in (x.component if hasattr(x, "component") else x for x in go.m_Component)
                 if p.type.name in ("Transform", "MeshFilter")]
        tr = next(c for c in comps if c.object_reader.type.name == "Transform")
        mf = next((c for c in comps if c.object_reader.type.name == "MeshFilter"), None)
        if mf is None or not mf.m_Mesh.path_id or not b2decor.keep(go, tr, route):
            continue
        h = MeshHandler(mf.m_Mesh.read())
        h.process()
        if not h.m_UV0:
            continue
        m = b2collision.world_matrix(tr)
        P = (np.array(h.m_Vertices, float).reshape(-1, 3) @ m[:3, :3].T + m[:3, 3]) * [-1, 1, -1]
        d = tree.query(P[:, [0, 2]])[0]
        if d.min() > radius:
            continue
        uv = np.array(h.m_UV0, float).reshape(-1, 2)
        uv1 = np.array(h.m_UV1, float).reshape(-1, 2) if h.m_UV1 else None
        for sub, mp in zip(h.get_triangles(), r.m_Materials):
            if not mp.path_id:
                continue
            envs = dict(mp.read().m_SavedProperties.m_TexEnvs)
            fl = dict(getattr(mp.read().m_SavedProperties, "m_Floats", []))
            if fl.get("_MeshEffectMode", 0) != 0:   # 2026-11-24: glows / power-up effects (193 materials, queue
                continue                            # 3004-3005): drawn opaque they came out as black shapes
            te = envs.get("_BaseMap")
            if te is None or not te.m_Texture.path_id:
                continue
            k = te.m_Texture.path_id
            if k not in tex:
                t = te.m_Texture.read()
                tex[k] = None if t.m_Name.startswith("mdl_") else t.image.convert("RGBA")
                ec = envs.get("_EnvironmentCube")
                env = ec is not None and ec.m_Texture.path_id
                props = mp.read().m_SavedProperties
                floats = dict(props.m_Floats) if hasattr(props, "m_Floats") else {}
                if tex[k] is not None and (env or floats.get("_AlphaTest", 0) < 0.5) and floats.get("_ZWrite", 1) > 0.5:
                    # (_ZWrite 0 = blended glass / decals / veils, 627 materials: their alpha kept -> cut-out models,
                    # fully transparent parts become holes instead of black; ponytail: no real blending, cut at 50 %)
                    tex[k].putalpha(255)        # alpha = reflection mask or unused: only _AlphaTest cuts (2026-11-16)
                mt = envs.get("_MaterialTex")   # Blur 2 material map: R reflection mask, G gloss, B Fresnel base
                mat[k] = (mt.m_Texture.read().image.convert("RGB") if mt is not None and mt.m_Texture.path_id
                          else True) if env and tex[k] is not None else None
            if tex[k] is None:
                continue
            a, b = envs.get("_Lightmap0Tex"), envs.get("_Lightmap1Tex")
            page = None
            if uv1 is not None and a is not None and b is not None and a.m_Texture.path_id and b.m_Texture.path_id:
                page = a.m_Texture.path_id
                if page not in lm:
                    lm[page] = tuple(np.asarray(x.m_Texture.read().image.convert("RGB"))
                                     for x in (a, b))         # uint8: 479 pages near Marina
            sc, of = np.array([te.m_Scale.x, te.m_Scale.y]), np.array([te.m_Offset.x, te.m_Offset.y])
            for t in np.array(sub, int).reshape(-1, 3):
                if d[t].min() <= radius:
                    tris.append((k, page, P[t], uv[t] * sc + of, uv1[t] if page else None))
    return {"tex": tex, "lm": lm, "tris": tris, "mat": mat}


def bake_page(data, page, size=1024):
    """the baked texture (RGB uint8, size x size) of one lightmap page: every texel covered by one of its triangles"""
    A, B = (np.asarray(x, np.float32) / 255 for x in data["lm"][page])   # lightmaps = linear data
    tex = {}
    out = np.zeros((size, size, 3), np.float32)
    hit = np.zeros((size, size), bool)
    for k, pg, P, uv0, uv1 in data["tris"]:
        if pg != page:
            continue
        if k not in tex:
            tex[k] = (np.asarray(data["tex"][k].convert("RGB"), np.float32) / 255) ** 2.2
        T = tex[k]
        q = uv1 * size                                   # pixel space (v up -> rows from the bottom)
        q[:, 1] = size - q[:, 1]
        x0, y0 = np.floor(q.min(0)).astype(int)
        x1, y1 = np.ceil(q.max(0)).astype(int)
        x0, y0, x1, y1 = max(x0, 0), max(y0, 0), min(x1, size - 1), min(y1, size - 1)
        if x1 < x0 or y1 < y0:
            continue
        gx, gy = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
        (ax, ay), (bx, by), (cx, cy) = q
        den = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
        if abs(den) < 1e-12:
            continue
        l1 = ((by - cy) * (gx - cx) + (cx - bx) * (gy - cy)) / den
        l2 = ((cy - ay) * (gx - cx) + (ax - cx) * (gy - cy)) / den
        l3 = 1 - l1 - l2
        e = -0.5 / max(abs(den) ** 0.5, 1)              # half a texel of slack: no seams
        ins = (l1 >= e) & (l2 >= e) & (l3 >= e)
        if not ins.any():
            continue
        L = np.stack([l1[ins], l2[ins], l3[ins]], 1)
        u0 = L @ uv0                                     # albedo with its own tiling (wrap)
        th, tw = T.shape[:2]
        alb = T[((1 - u0[:, 1] % 1) * (th - 1)).astype(int), ((u0[:, 0] % 1) * (tw - 1)).astype(int)]
        u1 = L @ uv1
        lh, lw = A.shape[:2]
        iy, ix = ((1 - u1[:, 1] % 1) * (lh - 1)).astype(int), ((u1[:, 0] % 1) * (lw - 1)).astype(int)
        a, b = A[iy, ix], B[iy, ix]
        n = np.cross(P[1] - P[0], P[2] - P[0])
        n = n / (np.linalg.norm(n) or 1)
        light = (a * b[:, 2:3]) ** 2 * AMBIENT + max(float(n @ SUN), 0.0) * b[:, 1:2] ** 2 * SUN_COLOUR
        ys, xs = np.nonzero(ins)
        out[ys + y0, xs + x0] = alb * light * EXPOSURE
        hit[ys + y0, xs + x0] = True
    return (np.clip(out, 0, 1) ** (1 / 2.2) * 255).astype(np.uint8), hit          # back to sRGB (display)


def baked(n_y):
    """mixed mode: walls, facades and props are baked; flat ground / road (|normal y| > 0.8) keep their sharp tiled
    textures (b2decor atlas): the page only has the lightmap's resolution"""
    return abs(n_y) <= 0.8


def split(data, laps):
    """-> (page triangles {page: [(P, uv1)]} to bake, b2decor data {"tex", "tris": [(k, P, uv0, 1.0)]} for the rest)"""
    import collections
    pages, rest = collections.defaultdict(list), []
    for k, pg, P, uv0, uv1 in data["tris"]:
        n = np.cross(P[1] - P[0], P[2] - P[0])
        ny = n[1] / (np.linalg.norm(n) or 1)
        if pg is not None and baked(ny):
            pages[pg].append((P, uv1))
        else:
            rest.append((k, P, uv0, 1.0))
    return pages, {"tex": {k: v for k, v in data["tex"].items() if v is not None}, "tris": rest}


def page_models(data, pages, laps, count, size=1024, max_verts=10000):
    """-> [(distance to the lap, baked page image, [(3 positions, 3 uv)])], nearest first, at most `count`; a page
    with more than max_verts shared vertices is split (its parts share the image)"""
    from PIL import Image
    from scipy.spatial import cKDTree
    tree = cKDTree(b2decor.lap_points(laps))
    cand = []
    for pg, tris in pages.items():
        C = np.array([P.mean(0) for P, _ in tris])
        dist = tree.query(C[:, [0, 2]])[0]
        order = np.argsort(dist)
        cur, keys = [], set()
        for i in order:
            P, uv = tris[i]
            kk = {(tuple(np.round(p, 3)), tuple(np.round(q, 5))) for p, q in zip(P, uv)}
            if len(keys) + len(kk - keys) > max_verts:
                cand.append((float(dist[cur[0][0]]), pg, cur))
                cur, keys = [], set()
            cur.append((i, P, uv))
            keys |= kk
        if cur:
            cand.append((float(dist[cur[0][0]]), pg, cur))
    cand.sort(key=lambda c: c[0])
    cand = cand[:count]
    imgs, out = {}, []
    for dd, pg, cur in cand:
        if pg not in imgs:
            # only this page's baked triangles: bake_page reads data["tris"] for the page, so give it just those
            sub = {"tex": data["tex"], "lm": data["lm"],
                   "tris": [t for t in data["tris"] if t[1] == pg and baked(_ny(t[2]))]}
            img, hit = bake_page(sub, pg, size)
            from scipy import ndimage                    # empty texels take the nearest baked one: no black seams
            iy, ix = ndimage.distance_transform_edt(~hit, return_distances=False, return_indices=True)
            imgs[pg] = Image.fromarray(img[iy, ix] if hit.any() else img).convert("RGBA")
        out.append((dd, imgs[pg], [([tuple(p) for p in P], [tuple(q) for q in uv]) for _, P, uv in cur]))
    print(len(cand), "baked models from", len(imgs), "pages")
    return out


def _ny(P):
    n = np.cross(P[1] - P[0], P[2] - P[0])
    return n[1] / (np.linalg.norm(n) or 1)
