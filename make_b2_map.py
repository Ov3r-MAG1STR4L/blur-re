#!/usr/bin/env python3
"""Blur 2 route -> playable Blur 1 map in the flat_earth slot (project J pipeline, Blur Map Builder copy bmb_game).

1. world.json for Map Builder from a driven lap (lap2aid CSV): one point / STEP m, width W, height above the map
   floor h = y - lowest y (Map Builder puts the lowest point 1 m above its floor, as make_nfs_map.set_heights),
   start_m = the official grid's slot 0, official pickups (Blur2DubaiTest <city>.json, within 40 m of the lap)
   as Map Builder rows; the previous world.json is kept as world.json.bak.
2. build.py of Map Builder (NFS_NO_WALLS, NFS_FLOOR_Y as project J), files collected with make_nfs_map.main.
3. collision: b2collision (Unity MeshColliders within 60 m of the lap), shifted by 1 - lowest y, inserted in the
   built level.levelphysics.
4. --decor: visible scenery (b2decor: Unity MeshRenderers within 300 m, zone models with a texture atlas) in
   project J's slots: NFS_COUNT tower_nfsKKK models (actor at its zone centre) + the Map Builder road pieces
   (road_21_KK.model replaced: its glowing road would cover the real one), all the same size, same shift as 3.
Output: OUT/files (to copy over Blur_test). Install separately, with a backup.

usage: make_b2_map.py LAP.csv PICKUPS.json OUT --name Marina --city Dubai --route 4 --grid X Z [--decor]
       [--official ACTORPACK] [--edges] [--drive LOG...] [--track TRACK_JSON]
"""
import argparse, csv, json, math, os, shutil, struct, subprocess, sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import config  # noqa: E402
# Map Builder's paths.py is read once, by the first module that imports it (b2lit -> cpmodel for --decor, before
# blurmodel_write sets these): installed layout, else ADDON = _mod_project\blender\addon (absent) and the decor
# step fails with "No module named 'BlurImportExport'" (2026-11-18, route 1 build)
os.environ.setdefault("BMB_GAME", config.BMB_GAME)
os.environ.setdefault("BMB_INSTALLED", "1")

STEP = 12.0
WIDTH = 30
TUBE = 50            # race tube (out of it -> reset), as project J's TRACK_WIDTH
UNITY = os.path.join(config.JEUX, "Blur2DubaiTest", "Blur2DubaiTest_Data")


def resample(pts, step):
    out, carry = [pts[0]], 0.0
    for a, b in zip(pts, pts[1:]):
        seg = math.hypot(b[0] - a[0], b[2] - a[2])
        d = step - carry
        while d <= seg:
            t = d / seg
            out.append(tuple(a[k] + (b[k] - a[k]) * t for k in range(3)))
            d += step
        carry = (carry + seg) % step
    return out


def wall_points(route, step=1.0):
    """2D+height points (x, y, z, game axes) every `step` m along the edges of the wall triangles (near vertical) of
    the city colliders ('_5d' / '_15d': main walls + this route's barriers; other routes' barriers out)"""
    import b2collision
    out = []
    for name, (v, t) in b2collision.colliders(UNITY).items():
        if not ("_5d_" in name or "_15d_" in name) or (
                name.startswith("physics_route_") and not name.startswith("physics_route_%d_" % route)):
            continue
        T = v[t]
        n = np.cross(T[:, 1] - T[:, 0], T[:, 2] - T[:, 0])
        T = T[np.abs(n[:, 1]) < 0.5 * np.linalg.norm(n, axis=1)]          # vertical faces only
        for a, b in ((0, 1), (1, 2), (2, 0)):
            L = np.linalg.norm(T[:, b] - T[:, a], axis=1)
            for k in range(T.shape[0]):
                m = max(2, int(L[k] / step) + 1)
                out.append(np.linspace(T[k, a], T[k, b], m))
    return np.concatenate(out)


def fit_edges(pts, walls, tree, closed, reach=30.0, along=2.5, wmin=12.0, wmax=60.0):
    """each centre point (dict x, z, w + y) moved to the middle of its two walls (searched along the lateral
    axis within `reach` m, `along` m either side of the section, wall height within -1..+5 m of the road), w = the
    distance between them (wmin..wmax); a side without a wall keeps the old half width. -> number of points fitted"""
    P = np.array([(p["x"], p["z"]) for p in pts])
    off, wid, lats, fitted = [], [], [], 0
    for i, p in enumerate(pts):
        t = P[(i + 1) % len(P)] - P[i - 1]
        t = t / (np.linalg.norm(t) or 1)
        lat = np.array([-t[1], t[0]])
        lats.append(lat)
        near = tree.query_ball_point(P[i], reach)
        W = walls[near] if near else np.zeros((0, 3))
        dv = W[:, [0, 2]] - P[i]
        ok = (np.abs(dv @ t) < along) & (W[:, 1] > p["_y"] - 1) & (W[:, 1] < p["_y"] + 5)
        s = dv[ok] @ lat
        left, right = s[s > 1.5], -s[s < -1.5]
        half = p["w"] / 2
        l = left.min() if len(left) else half
        r = right.min() if len(right) else half
        fitted += bool(len(left) or len(right))
        off.append((l - r) / 2)
        wid.append(min(max(l + r, wmin), wmax))
    k = 2                                             # running median over 5 points: posts, kerbs, pillar notches
    idx = lambda i: [(i + j) % len(pts) for j in range(-k, k + 1)] if closed else range(max(0, i - k), min(len(pts), i + k + 1))
    for i, p in enumerate(pts):
        o, w = float(np.median([off[j] for j in idx(i)])), float(np.median([wid[j] for j in idx(i)]))
        c = P[i] + lats[i] * o
        p.update(x=round(float(c[0]), 2), z=round(float(c[1]), 2), w=round(w, 1))
    return fitted


def drive_edges(mp, logs, margin=1.5, along=4.0, reach=40.0):
    """--drive: edges from wall-hugging drives in Blur2DubaiTest (brul2lap.read, game axes; falls into the void and
    stops dropped). Each driven position goes to its nearest line (main road or a branch); at each line point the
    leftmost / rightmost positions within `along` m of the section (+ margin) give the edges; the point is moved to
    their middle, w = their distance (median over 5 points). A side never driven keeps the wall fit (--edges)."""
    import brul2lap
    from scipy.spatial import cKDTree
    a = np.vstack([brul2lap.read(f) for f in logs])
    a = a[a[:, 4] > 5]
    G = a[:, [1, 3]]
    lines = [mp["points"]] + [b["points"] for b in mp.get("branches") or []]
    dense = [np.array([(q["x"], q["z"]) for q in pts]) for pts in lines]
    owner = np.argmin([cKDTree(D).query(G)[0] for D in dense], axis=0)
    for k, (pts, P) in enumerate(zip(lines, dense)):
        g = G[owner == k]
        tree = cKDTree(g) if len(g) else None
        off, wid = [], []
        for i, q in enumerate(pts):
            t = P[(i + 1) % len(P)] - P[i - 1] if k == 0 else P[min(i + 1, len(P) - 1)] - P[max(i - 1, 0)]
            t = t / (np.linalg.norm(t) or 1)
            lat = np.array([-t[1], t[0]])
            near = tree.query_ball_point(P[i], reach) if tree is not None else []
            dv = g[near] - P[i] if near else np.zeros((0, 2))
            dv = dv[np.abs(dv @ t) < along] if len(dv) else dv
            sl = dv @ lat
            half = q["w"] / 2
            l = sl.max() + margin if len(sl) and sl.max() > 0 else half
            r = -sl.min() + margin if len(sl) and sl.min() < 0 else half
            off.append((l - r) / 2)
            wid.append(min(max(l + r, 12.0), 60.0))
        for i, q in enumerate(pts):
            j = [(i + d) % len(pts) for d in range(-2, 3)] if k == 0 else range(max(0, i - 2), min(len(pts), i + 3))
            o, w = float(np.median([off[x] for x in j])), float(np.median([wid[x] for x in j]))
            t = P[(i + 1) % len(P)] - P[i - 1] if k == 0 else P[min(i + 1, len(P) - 1)] - P[max(i - 1, 0)]
            t = t / (np.linalg.norm(t) or 1)
            c = P[i] + np.array([-t[1], t[0]]) * o
            q.update(x=round(float(c[0]), 2), z=round(float(c[1]), 2), w=round(w, 1))
        print("drive: line %d, %d positions, width %.0f-%.0f m (median %.0f)" % (
            k, len(g), min(q["w"] for q in pts), max(q["w"] for q in pts), np.median([q["w"] for q in pts])))
    mp["width"] = max(TUBE, max(q["w"] for pts in lines for q in pts) + 10)
    return a


def edges(mp, low, route, png):
    """--edges: main road and branches fitted between the city walls (fit_edges) + a top view check image"""
    from scipy.spatial import cKDTree
    walls = wall_points(route)
    tree = cKDTree(walls[:, [0, 2]])
    lines = [mp["points"]] + [b["points"] for b in mp.get("branches") or []]
    for k, pts in enumerate(lines):
        for q in pts:
            q["_y"] = q["h"] + low
        n = fit_edges(pts, walls, tree, closed=k == 0)
        for q in pts:
            del q["_y"]
        print("edges: %d/%d points fitted, width %.0f-%.0f m (median %.0f)" % (
            n, len(pts), min(q["w"] for q in pts), max(q["w"] for q in pts), np.median([q["w"] for q in pts])))
    mp["width"] = max(TUBE, max(q["w"] for pts in lines for q in pts) + 10)
    edges_png(mp, route, png, walls)


def edges_png(mp, route, png, walls=None, drive=None):
    """top view: walls (grey), drives (green), main road (blue) and branches (red) with their edges"""
    lines = [mp["points"]] + [b["points"] for b in mp.get("branches") or []]
    walls = wall_points(route) if walls is None else walls
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    allp = np.array([(q["x"], q["z"]) for pts in lines for q in pts])
    lo, hi = allp.min(0) - 60, allp.max(0) + 60
    W = walls[(walls[:, 0] > lo[0]) & (walls[:, 0] < hi[0]) & (walls[:, 2] > lo[1]) & (walls[:, 2] < hi[1])][::3]
    fig = plt.figure(figsize=(14, 14))
    plt.scatter(W[:, 0], W[:, 2], s=0.05, c="grey")
    if drive is not None:
        plt.scatter(drive[:, 1], drive[:, 3], s=0.3, c="green")
    for k, pts in enumerate(lines):
        P = np.array([(q["x"], q["z"]) for q in pts])
        t = np.gradient(P, axis=0)
        t /= np.linalg.norm(t, axis=1, keepdims=True)
        lat = np.c_[-t[:, 1], t[:, 0]] * np.array([q["w"] for q in pts])[:, None] / 2
        col = "blue" if k == 0 else "red"
        plt.plot(*P.T, col, lw=0.6)
        plt.plot(*(P + lat).T, col, lw=1.2)
        plt.plot(*(P - lat).T, col, lw=1.2)
    plt.gca().set_aspect("equal")
    plt.title("murs (gris), route (bleu), chemins secondaires (rouge)")
    fig.savefig(png, dpi=110, bbox_inches="tight")
    plt.close(fig)


def branches(actorpack, lap, cum_pts, low, out_dir, far=30.0, min_len=120.0):
    """official AI branches (b2official: the non-closed AIDataActor of every race) that leave the race tube (> far m
    from the lap; the tube is TUBE m wide) -> Map Builder branches {from_m, to_m, points} (ends projected on the
    resampled lap) + one CSV per branch (x, y, z: extra laps for the collision and the scenery)"""
    import b2official
    races, _ = b2official.official(actorpack)
    pts, cum = cum_pts
    xz = np.array([(p[0], p[2]) for p in pts])
    total = cum[-1] + math.hypot(*(xz[0] - xz[-1]))
    out, csvs = [], []
    for race in races.values():
        for b in race["branches"]:
            d = [float(np.hypot(*(xz - p[[0, 2]]).T).min()) for p in b]
            length = float(np.sum(np.linalg.norm(np.diff(b, axis=0), axis=1)))
            if max(d) < far or length < min_len:
                continue
            i0, i1 = (int(np.argmin(np.hypot(*(xz - b[k][[0, 2]]).T))) for k in (0, -1))
            fm, tm = float(cum[i0]), float(cum[i1])
            if tm < fm:
                tm += total                                   # runs past the loop's end (network.py allows it)
            if tm - fm > total / 2 or any(fm < o["to_m"] and o["from_m"] < tm for o in out):
                continue                                      # backwards, or overlaps one kept (the 2 races' copies)
            out.append({"from_m": round(fm), "to_m": round(tm), "width": WIDTH,
                        "points": [{"x": round(p[0], 2), "z": round(p[2], 2), "w": WIDTH,
                                    "h": round(max(0.0, p[1] - low), 2)} for p in b]})
            f = os.path.join(out_dir, "branch_%02d.csv" % len(csvs))
            with open(f, "w", newline="") as fh:
                w = csv.writer(fh)
                w.writerow(["x", "y", "z"])
                w.writerows(np.round(b, 2).tolist())
            csvs.append(f)
    print(len(out), "official branches kept (out of the tube)")
    return out, csvs


def world(lap, pickups, name, city, grid):
    pts = resample(lap, STEP)
    if math.hypot(pts[-1][0] - pts[0][0], pts[-1][2] - pts[0][2]) < STEP:
        pts.pop()
    low = min(p[1] for p in pts)
    cum = np.r_[0, np.cumsum([math.hypot(b[0] - a[0], b[2] - a[2]) for a, b in zip(pts, pts[1:])])]
    i0 = int(np.argmin([math.hypot(p[0] - grid[0], p[2] - grid[1]) for p in pts]))
    xz = np.array([(p[0], p[2]) for p in pts])
    rows = []
    for pk in pickups:
        x, z = -pk["position"][0], -pk["position"][2]      # Unity axes (Dubai: 38 on the Marina lap, 4 unconverted)
        if np.hypot(*(xz - (x, z)).T).min() < 40:
            rows.append({"kind": "row", "x": round(x, 2), "z": round(z, 2), "n": 1})
    base = json.load(open(os.path.join(config.BMB_GAME, "Blur Map Builder", "maps", "world.json")))
    loc = base["locations"][0]
    loc.update(id="b2_" + city.lower(), name=city)
    loc["lighting"] = {"preset": "LA River (day)",           # Amboy (desert) came out overexposed (user, 2026-11-09)
                       "values": {"object_light": [1.0, 0.97, 0.92, 0.14], "object_light_up": [0.6]}}
    m = loc["maps"][0]
    m.update(id="b2_%s_1" % city.lower(), name=name, laps=3, width=TUBE, auto_bridges=False, branches=[],
             points=[{"x": round(x, 2), "z": round(z, 2), "w": WIDTH, "h": round(y - low, 2)} for x, y, z in pts],
             pickups=rows, pickup_per_row=1, start_m=int(cum[i0]), finish_m=int(cum[i0]))
    loc["maps"] = [m]
    base["locations"] = [loc]
    return base, low, len(rows), (pts, cum)


ROAD_SLOTS = 12      # Map Builder road pieces (one per 420 m: 9 for Marina's 3.5 km); extra models unused


def decor(files, models, nfs):
    import make_nfs_map as J
    ap = os.path.join(files, "gamedata", "levels", "flat_earth", "actorpack.xt")
    flat = os.path.join(files, "models", "objects", "flat_earth")
    slots = [(J.NFS_UID + 2 * k + 1, "nfs_%03d.model" % k) for k in range(nfs)]
    slots += [(u, "road_21_%02d.model" % k) for k, u in enumerate(J.road_slots(ap))]
    import b2lit
    mats, skipped = [], []
    for uid, fname in slots:
        try:
            mats.append((J.slot_matrix(ap, uid), fname))
        except AssertionError as e:                        # no single visible actor (with branches: road pieces)
            print("slot", fname, "skipped:", e)
            skipped.append(fname)
    slots = mats
    for k, ((mat, fname), (img, tris, mmap, cut)) in enumerate(zip(slots, models)):
        nv, ni = b2lit.write(tris, mat, os.path.join(flat, fname), img, 0x42324400 + k, J.HP_GROUND, mmap, cut)
        print(fname, nv, "vertices", ni, "indices")
    from PIL import Image
    blank = Image.new("RGBA", (4, 4), (0, 0, 0, 255))        # free sizes: 3-vertex hidden models (G3b)
    hidden = [([(0, -50, 0), (0.01, -50, 0), (0, -50, 0.01)], [(0, 0)] * 3)]   # Map Builder's glowing road gone
    eye = [[1, 0, 0], [0, 1, 0], [0, 0, 1], [0, 0, 0]]
    for k, (mat, fname) in enumerate(slots[len(models):] + [(eye, f) for f in skipped], len(models)):
        J.write_model(hidden, "empty", mat, os.path.join(flat, fname), 0, salt=0x42324400 + k, image=blank)
    print(min(len(slots), len(models)), "scenery models in", len(slots), "slots (the others emptied)")
    if len(models) > len(slots):
        extra_actors(files, models[len(slots):], nfs, len(slots))


DECOR_TOTAL = 400    # scenery models in all (ponytail: game memory never measured; lower it if the load fails)


def extra_actors(files, models, k0, salt0):
    """scenery beyond Map Builder's 144-actor list (2026-11-16): one new GameModel + DynamicObjDef per model in
    amax.bin (clones of Map Builder's tower_nfs000 records, other file name), one new DynamicObjActor per model in
    the list holding the tower_nfs actors (neon.add_actors: method seen working in game, Reverse Studio).
    The game creates its world with MAX_NUM_ACTORS = 10000 (source: GameWorld.cpp, RLDefinitions.h)."""
    import tempfile
    import make_nfs_map as J
    import b2lit
    import neon
    from blurxt import XT
    from kslfwrite import KSLF
    am = os.path.join(files, "gamedata", "xt", "amax.bin")
    ap = os.path.join(files, "gamedata", "levels", "flat_earth", "actorpack.xt")
    flat = os.path.join(files, "models", "objects", "flat_earth")
    tower = "@%08x" % (J.NFS_UID + 1)
    lst = [n for n, t, v, h in XT(ap).records() if any(a and a.get("DynamicObjType") == tower
                                                        for a in v.get("LevelActors", []))]
    assert len(lst) == 1, lst
    amax = open(am, "rb").read()
    tmp = os.path.join(tempfile.gettempdir(), "b2_extra_amax.bin")
    open(tmp, "wb").write(amax)
    A = neon.dump.File(tmp)
    have = {u for u, t, oi in A.refs}
    obj = {u: oi for u, t, oi in A.refs if oi != 0xFFFF}
    assert J.NFS_UID in obj and J.NFS_UID + 1 in obj, "no tower_nfs000 records to clone"
    taken = have | {h for h, _, _ in KSLF(ap).index}
    c = 0xB2DE0000                                        # any free uids: rows inserted at their sorted place
    items, defs = [], {}
    for j, (img, tris, mmap, cut) in enumerate(models):
        uids = []
        while len(uids) < 2:
            if c not in taken:
                uids.append(c)
            c += 1
        assert c < 0xB2DF0000
        gm, du = uids
        k = k0 + j
        fname = "nfs_%03d.model" % k
        centre = J.zone_centre([(t[0], None) for t in tris])
        mat = [[1, 0, 0], [0, 1, 0], [0, 0, 1], centre]

        def gm_patch(data, pool, blocks, fname=r"models\objects\flat_earth" + "\\" + fname):
            struct.pack_into("<I", data, blocks[0], len(pool))
            pool += fname.encode() + b"\0"
        _, amax = neon.kslf_write.clone_object_any(obj[J.NFS_UID], None, gm, gm_patch, data_in=amax)
        k4 = neon.kslf.Kslf(amax)
        o4, n4 = k4.sections[4]
        gm_ref = next(i for i in range(n4) if struct.unpack_from("<I", amax, o4 + 8 * i)[0] == gm)

        def def_patch(data, pool, blocks, gm_ref=gm_ref):
            struct.pack_into("<I", data, blocks[0], gm_ref)           # Model; the rest as tower_nfs000
        _, amax = neon.kslf_write.clone_object_any(obj[J.NFS_UID + 1], None, du, def_patch, data_in=amax)
        nv, ni = b2lit.write(tris, mat, os.path.join(flat, fname), img, 0x42324400 + salt0 + j, J.HP_GROUND, mmap, cut)
        print(fname, nv, "vertices", ni, "indices (new actor)")
        items.append((j, mat))
        defs[j] = du
    open(am, "wb").write(amax)
    data = open(ap, "rb").read()
    for du in defs.values():                              # external rows (defined in amax.bin), Map Builder's way
        data, _ = neon.kslf_write.insert_uid(data, du, "DynamicObjDef")   # (gen_actorpack.py)
    open(ap, "wb").write(data)
    neon.add_actors(ap, lst, items, template_list=lst[0], defs=defs, prefix="B2Decor")
    back = [a for n, t, v, h in XT(ap).records() if n == lst[0] for a in v["LevelActors"]
            if a and a.get("DynamicObjType") in {"@%08x" % u for u in defs.values()}]
    assert len(back) == len(models), (len(back), len(models))
    print(len(models), "scenery actors added to list", lst[0])


def mb_start_m(mp, grid):
    """start_m mesuré sur la route de Map Builder elle-même (lissée : ses distances ne sont pas celles de nos points ;
    avant le 2026-11-23 la 1re rangée tombait 8-20 m, voire 270 m, à côté). Map Builder pose la 1re rangée
    NFS_GRID_GAP m (8) derrière la ligne : ligne = point de sa route le plus proche de la case 0 officielle + 8 m."""
    sys.path.insert(0, os.path.join(config.MAP_BUILDER_DIR, "flat_earth"))
    import road as mb_road
    r = mb_road.for_map(dict(mp, laps=mp.get("laps") or 3))
    C = np.array(r.centre)
    i = int(np.argmin(np.hypot(*(C - np.asarray(grid)).T)))
    gap = float(os.environ.get("NFS_GRID_GAP", 8.0))
    return int(round((r.dist[i] + gap) % r.length))


def mb_branch_m(mp):
    """from_m / to_m des chemins secondaires remesurés sur la route de Map Builder (bouts projetés sur sa route)"""
    import road as mb_road                              # chemin posé par mb_start_m
    r = mb_road.for_map(dict(mp, laps=mp.get("laps") or 3))
    C = np.array(r.centre)
    for b in mp.get("branches") or []:
        i0, i1 = (int(np.argmin(np.hypot(*(C - (b["points"][k]["x"], b["points"][k]["z"])).T))) for k in (0, -1))
        fm, tm = r.dist[i0], r.dist[i1]
        b["from_m"], b["to_m"] = int(round(fm)), int(round(tm + r.length if tm < fm else tm))


def flatten_loops(pts, steep=1.0, reach=60, tol=3.0):
    """copy of the points with every loop / vertical wall-ride stretch flattened (Map Builder only): its road
    pieces collide (2026-11-23, Business Bay: the branch going down the loop became a 30 m wide invisible ramp
    across the wall-ride, from y 124 down to 0 -> the car hit it at 140 km/h and got stuck under it). Around each
    segment steeper than `steep` (dh / ds): from the last point within `tol` m of the lowest of the `reach` points
    before, to the first such point after, h goes linearly between those two.
    ponytail: anchors by local minimum, a loop starting on a slope may flatten a bit too far"""
    h = np.array([q["h"] for q in pts], float)
    xz = np.array([(q["x"], q["z"]) for q in pts], float)
    g = np.abs(np.diff(h)) / np.maximum(np.hypot(*np.diff(xz, axis=0).T), 0.1)
    out = h.copy()
    for s in np.where(g > steep)[0]:
        lo = max(0, s - reach)
        a = lo + int(np.where(h[lo:s + 1] <= h[lo:s + 1].min() + tol)[0].max())
        hi = min(len(h), s + 1 + reach)
        b = s + 1 + int(np.where(h[s + 1:hi] <= h[s + 1:hi].min() + tol)[0].min())
        out[a:b + 1] = np.minimum(out[a:b + 1], np.linspace(h[a], h[b], b - a + 1))
    return [dict(q, h=float(v)) for q, v in zip(pts, out)]


def track(mp, path, low, grid, route, out_dir):
    """--track: main road and branches from the editor (b2track.py), instead of --edges / --drive; start_m again
    from the grid (the points moved), one CSV per branch (x, y, z: collision and scenery) + a top view check image"""
    t = json.load(open(path, encoding="utf-8"))
    mp["points"], mp["branches"] = t["points"], t["branches"]
    P = np.array([(q["x"], q["z"]) for q in mp["points"]])
    mp["start_m"] = mp["finish_m"] = mb_start_m(mp, grid)
    mb_branch_m(mp)
    # Map Builder: 64 road models per map at most (road_mesh.uids, one uid block); each branch also adds raised-edge
    # models. Too many -> drop the shortest branch until it fits (2026-11-23: Business Bay v2 73, Marina v2 83).
    import build as mb_fe, road_mesh as mb_mesh
    every = list(mp["branches"])                       # the collision still faces ALL of them (a dropped branch's
    while mp["branches"] and mb_mesh.model_count(mb_fe, dict(mp, laps=mp.get("laps") or 3)) > 64:
        b = min(mp["branches"], key=lambda b: len(b["points"]))
        mp["branches"].remove(b)
        print("branch %d-%d m dropped (Map Builder: 64 road models at most)" % (b["from_m"], b["to_m"]))
    mp["points"] = flatten_loops(mp["points"])         # Map Builder's copy only (`every` keeps the real heights)
    mp["branches"] = [dict(b, points=flatten_loops(b["points"])) for b in mp["branches"]]
    lines =[mp["points"]] + [b["points"] for b in mp["branches"]]
    mp["width"] = max(TUBE, max(q["w"] for pts in lines for q in pts) + 10)
    os.makedirs(out_dir, exist_ok=True)
    csvs = []
    for k, b in enumerate(every):                      # loop / tube: no lap inside -> its faces turned away)
        f = os.path.join(out_dir, "branch_%02d.csv" % k)
        with open(f, "w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["x", "y", "z"])
            w.writerows([(q["x"], round(q["h"] + low, 2), q["z"]) for q in b["points"]])
        csvs.append(f)
    print("track: %s, %d points, %d branches, start_m %d" % (path, len(P), len(csvs), mp["start_m"]))
    edges_png(mp, route, os.path.join(out_dir, "bords_trace.png"))
    return csvs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("lap"), ap.add_argument("pickups"), ap.add_argument("out")
    ap.add_argument("--name", required=True), ap.add_argument("--city", required=True)
    ap.add_argument("--route", type=int, required=True)
    ap.add_argument("--grid", type=float, nargs=2, metavar=("X", "Z"),
                    help="grid slot 0; omitted: blur2_aid/dubai/grilles.json (poscapture.py grille) for --route")
    ap.add_argument("--decor", action="store_true")
    ap.add_argument("--edges", action="store_true", help="road centre and width fitted between the walls")
    ap.add_argument("--drive", nargs="+", metavar="PLAYER_LOG", help="wall-hugging drives: edges from them")
    ap.add_argument("--official", metavar="ACTORPACK", help="X360 actorpack.xt of the city: official AI branches")
    ap.add_argument("--track", metavar="TRACK_JSON", help="road and branches edited in b2track.py (replaces the above)")
    a = ap.parse_args()
    if a.grid is None:
        gf = os.path.join(os.path.dirname(HERE), "blur2_aid", "dubai", "grilles.json")
        g = json.load(open(gf, encoding="utf-8")).get(str(a.route)) if os.path.exists(gf) else None
        if not g:
            sys.exit("--grid X Z, or place it in game: poscapture.py grille (route %s)" % a.route)
        a.grid = [g["x"], g["z"]]
        print("grid from grilles.json: (%.1f ; %.1f), %s" % (g["x"], g["z"], g["date"]))
    lap = [(float(r["x"]), float(r["y"]), float(r["z"])) for r in csv.DictReader(open(a.lap))]
    pk = json.load(open(a.pickups))["pickups"]
    w, low, npk, res = world(lap, pk, a.name, a.city, a.grid)
    laps = [a.lap]
    mp = w["locations"][0]["maps"][0]
    if a.official:
        mp["branches"], extra = branches(a.official, lap, res, low, a.out)
        laps += extra
    if a.edges:
        edges(mp, low, a.route, os.path.join(a.out, "bords.png"))
    if a.drive:
        edges_png(mp, a.route, os.path.join(a.out, "bords_conduite.png"), drive=drive_edges(mp, a.drive))
    if a.track:
        laps = [a.lap] + track(mp, a.track, low, a.grid, a.route, a.out)
    wfile = os.path.join(config.BMB_GAME, "Blur Map Builder", "maps", "world.json")
    if not os.path.exists(wfile + ".bak"):
        shutil.copyfile(wfile, wfile + ".bak")
    json.dump(w, open(wfile, "w"), indent=1)
    print("world.json: %d points, lowest road y %.1f, %d pickups, start_m %d"
          % (len(w["locations"][0]["maps"][0]["points"]), low, npk, w["locations"][0]["maps"][0]["start_m"]))
    import make_nfs_map                                # its paths come from sys.argv at import: set them
    files = os.path.join(a.out, "files")
    make_nfs_map.BMB, make_nfs_map.OUT = config.BMB_GAME, files
    make_nfs_map.WORK = os.path.join(config.BMB_GAME, "Blur Map Builder", "work")
    make_nfs_map.HP_GROUND = low                       # write_model / zone_centre shift y by 1 - HP_GROUND
    models, spots = [], os.path.abspath(os.path.join(a.out, "nfs_spots.json"))
    if a.decor:
        import b2decor
        import b2bake
        import b2lit                                   # lot 1 (2026-11-16): sharp tiled atlases, Blur 2 light in
        data = b2bake.extract(UNITY, laps, a.route, radius=200)          # vertex colours (mixed mode replaced)
        models = b2lit.jobs(data, laps, DECOR_TOTAL)
        del data
        b2decor.sheet([m[:2] for m in models], os.path.join(a.out, "atlas.png"))
        json.dump([make_nfs_map.zone_centre([(t[0], None) for t in m[1]]) for m in models[:make_nfs_map.DECOR_MAX]],
                  open(spots, "w"))
    nfs = min(len(models), make_nfs_map.DECOR_MAX)
    env = dict(os.environ, BMB_GAME=config.BMB_GAME, BMB_INSTALLED="1", NFS_COUNT=str(nfs), NFS_SPOTS=spots,
               NFS_DRAW=str(make_nfs_map.DECOR_DRAW), NFS_NO_WALLS="1", NFS_FLOOR_Y="-5")
    subprocess.run([sys.executable, "build.py"], cwd=os.path.join(config.BMB_GAME, "map_builder", "flat_earth"),
                   env=env, check=True, stdout=subprocess.DEVNULL, timeout=1800)   # 30 min max (Map Builder)
    make_nfs_map.main()
    import b2pickups                                   # official power-ups at their 3D place, own types (2026-11-17)
    lines = [np.array([(float(r["x"]), float(r["y"]), float(r["z"])) for r in csv.DictReader(open(f))]) for f in laps]
    b2pickups.apply(os.path.join(files, "gamedata", "levels", "flat_earth", "actorpack.xt"),
                    b2pickups.spots(pk, lines, low))
    if models:
        decor(files, models, nfs)
    phys = os.path.join(files, "levels", "flat_earth", "level.levelphysics")
    subprocess.run([sys.executable, os.path.join(HERE, "b2collision.py"), UNITY, phys, phys, "--route", str(a.route),
                    *laps, "--radius", "150", "--dy", str(1.0 - low)], check=True)   # all the Unity collision near the route


if __name__ == "__main__":
    main()
