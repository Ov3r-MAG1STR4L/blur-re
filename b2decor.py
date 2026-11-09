#!/usr/bin/env python3
"""Blur 2 city scenery (Blur2DubaiTest's Unity data) -> triangles near a lap, for make_b2_map's scenery mode.

Every MeshRenderer (shader Blur2/InspectionSurface, texture _BaseMap with its tiling) with its world matrix from the
Transform chain (as b2collision.colliders); game = (-x, y, -z). Kept: triangles within RADIUS m of the lap.
extract() -> {"tex": {path_id: PIL image}, "tris": [(texture path_id, 3x3 game positions, 3x2 uv)]}
"""
import os, sys
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from b2collision import lap_points  # noqa: E402


def keep(go, tr, route):
    """city scenery only: active hierarchy under dubai/Authored Layout Content, in 'Shared Render' or this route's
    'Route N ...' groups (other routes' actor lists, SpecialFx and the 239 inactive pickup / effect objects out)"""
    path, act, t = [], go.m_IsActive, tr
    while t.m_Father and t.m_Father.path_id:
        t = t.m_Father.read()
        g = t.m_GameObject.read()
        act, path = act and g.m_IsActive, [g.m_Name] + path
    if not act or len(path) < 3 or path[1] != "Authored Layout Content":
        return False
    return path[2].startswith("Shared Render") or path[2].startswith("Route %d " % route)


def extract(data_dir, laps, route, radius=300.0):
    import UnityPy
    from UnityPy.helpers.MeshHelper import MeshHandler
    from scipy.spatial import cKDTree
    import b2collision
    tree = cKDTree(lap_points(laps))
    env = UnityPy.load(data_dir)
    world = b2collision.world_matrix
    tex, tris = {}, []
    for o in env.objects:
        if o.type.name != "MeshRenderer":
            continue
        r = o.read()
        go = r.m_GameObject.read()
        if go.m_Name.startswith("physics") or not getattr(r, "m_Enabled", 1):
            continue
        comps = [p.read() for p in (x.component if hasattr(x, "component") else x for x in go.m_Component)
                 if p.type.name in ("Transform", "MeshFilter")]
        tr = next(c for c in comps if c.object_reader.type.name == "Transform")
        if not keep(go, tr, route):
            continue
        mf = next((c for c in comps if c.object_reader.type.name == "MeshFilter"), None)
        if mf is None or not mf.m_Mesh.path_id:
            continue
        h = MeshHandler(mf.m_Mesh.read())
        h.process()
        if not h.m_UV0:
            continue
        m = world(tr)
        P = (np.array(h.m_Vertices, float).reshape(-1, 3) @ m[:3, :3].T + m[:3, 3]) * [-1, 1, -1]
        d = tree.query(P[:, [0, 2]])[0]
        if d.min() > radius:
            continue
        uv = np.array(h.m_UV0, float).reshape(-1, 2)
        for sub, mp in zip(h.get_triangles(), r.m_Materials):
            if not mp.path_id:
                continue
            mat = mp.read()
            envs = dict(mat.m_SavedProperties.m_TexEnvs)
            te = envs.get("_BaseMap")
            if te is None or not te.m_Texture.path_id:
                continue
            k = te.m_Texture.path_id
            if k not in tex and te.m_Texture.read().m_Name.startswith("mdl_"):
                tex[k] = None                                 # pickup icons, lightning, mine pulses (effects)
            if tex.get(k, 0) is None:
                continue
            if k not in tex:
                tex[k] = te.m_Texture.read().image.convert("RGBA")
                ec = envs.get("_EnvironmentCube")
                if ec is not None and ec.m_Texture.path_id:    # alpha = reflection mask, not cutout (as HP
                    tex[k].putalpha(255)                       # glass): Blur 1 drew the windows black
            sc, of = (te.m_Scale.x, te.m_Scale.y), (te.m_Offset.x, te.m_Offset.y)
            for t in np.array(sub, int).reshape(-1, 3):
                if d[t].min() <= radius:
                    tris.append((k, P[t], uv[t] * sc + of))
    return {"tex": {k: v for k, v in tex.items() if v is not None}, "tris": tris}


ZONE = 150.0       # zone side (m): tight actor boxes (project J: whole-city boxes made the game crawl)
CELL = 128         # atlas cell (px); ATLAS / CELL = 4 -> at most 16 textures per model
ATLAS = 512        # every model the same size (project J crash fix): one atlas size for all


def jobs(data, laps, count, max_verts=10000, detail=0.005):
    """-> [(atlas image, [(3 positions, 3 uv)])], at most `count` models, nearest to the lap first.
    Zone (ZONE m square) -> models of <= max_verts shared vertices and <= 16 textures, each texture shrunk to a
    CELL x CELL atlas cell. Tiling is lost: uv moved into [0, 1] (shift by floor) and squeezed if the triangle
    spans more than one repeat. Small far triangles dropped (area < detail * distance m2: 1.76 M -> 0.62 M
    triangles within 300 m of Marina; 800 k lie within 50 m: lamps, barriers, props) (ponytail: 10 % of triangles stretched; splitting them would keep the tiling)."""
    import collections
    from PIL import Image
    from scipy.spatial import cKDTree
    tri = data["tris"]
    C = np.array([P.mean(0) for _, P, _ in tri])
    dist = cKDTree(lap_points(laps)).query(C[:, [0, 2]])[0]
    inset = 0.5 / CELL
    zones = collections.defaultdict(list)
    for (k, P, uv), c, dd in zip(tri, C, dist):
        if np.linalg.norm(np.cross(P[1] - P[0], P[2] - P[0])) / 2 < detail * dd:
            continue
        u = uv - np.floor(uv.min(0))
        u = u / np.maximum(u.max(0), 1)                       # squeeze tiled triangles into one repeat
        u = np.round(inset + u * (1 - 2 * inset), 4)
        zones[int(c[0] // ZONE), int(c[2] // ZONE)].append((float(dd), k, P, u))
    per = ATLAS // CELL
    out = []
    for tris in zones.values():
        tris.sort(key=lambda t: (t[1], t[0]))                 # by texture: few textures per model
        cur, keys, texs = [], set(), {}
        for t in tris:
            kk = {(tuple(np.round(p, 3)), t[1], tuple(q)) for p, q in zip(t[2], t[3])}
            if len(keys) + len(kk - keys) > max_verts or (t[1] not in texs and len(texs) == per * per):
                out.append((min(x[0] for x in cur), texs, cur))
                cur, keys, texs = [], set(), {}
            texs.setdefault(t[1], len(texs))
            cur.append(t)
            keys |= kk
        if cur:
            out.append((min(x[0] for x in cur), texs, cur))
    out.sort(key=lambda j: j[0])
    print(len(out), "models possible,", min(count, len(out)), "kept, nearest beyond:",
          round(out[count][0]) if len(out) > count else None, "m")
    res = []
    for _, texs, tris in out[:count]:
        img = Image.new("RGBA", (ATLAS, ATLAS))
        for k, i in texs.items():
            img.paste(data["tex"][k].resize((CELL, CELL)), ((i % per) * CELL, (i // per) * CELL))
        mt = []
        for _, k, P, u in tris:
            i = texs[k]
            v = 1 - u[:, 1]                                   # Unity v up; atlas rows top-down
            cu = ((i % per) + u[:, 0]) / per
            cv = 1 - ((i // per) + v) / per                    # write_model stores 1 - v
            mt.append(([tuple(p) for p in P], list(zip(cu, cv))))
        res.append((img, mt))
    return res


def sheet(models, path, n=24):
    """contact sheet of the first n atlases (visual check)"""
    from PIL import Image
    im = Image.new("RGB", (6 * 256, -(-min(n, len(models)) // 6) * 256), "magenta")
    for i, (img, _) in enumerate(models[:n]):
        im.paste(img.convert("RGB").resize((256, 256)), ((i % 6) * 256, (i // 6) * 256))
    im.save(path)


if __name__ == "__main__":
    import pickle
    r = extract(sys.argv[1], sys.argv[4:], int(sys.argv[3]))
    pickle.dump(r, open(sys.argv[2], "wb"))
    span = np.array([np.ptp(u, 0).max() for _, _, u in r["tris"]])
    print(len(r["tris"]), "triangles,", len(r["tex"]), "textures ; UV span >1 :", round(float((span > 1).mean()), 3),
          "> 4 :", round(float((span > 4).mean()), 3))
