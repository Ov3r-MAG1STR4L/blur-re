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
"""
import argparse, csv, json, math, os, shutil, subprocess, sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import config  # noqa: E402

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
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    allp = np.array([(q["x"], q["z"]) for pts in lines for q in pts])
    lo, hi = allp.min(0) - 60, allp.max(0) + 60
    W = walls[(walls[:, 0] > lo[0]) & (walls[:, 0] < hi[0]) & (walls[:, 2] > lo[1]) & (walls[:, 2] < hi[1])][::3]
    fig = plt.figure(figsize=(14, 14))
    plt.scatter(W[:, 0], W[:, 2], s=0.05, c="grey")
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
    pad = (J.DECOR_VERTS, 6 * max(len(t) for _, t in models))      # faces doubled: 6 indices per triangle
    mats, skipped = [], []
    for uid, fname in slots:
        try:
            mats.append((J.slot_matrix(ap, uid), fname))
        except AssertionError as e:                        # no single visible actor (with branches: road pieces)
            print("slot", fname, "skipped:", e)
            skipped.append(fname)
    slots = mats
    for k, ((mat, fname), (img, tris)) in enumerate(zip(slots, models)):
        J.write_model(tris, "b2_%03d" % k, mat, os.path.join(flat, fname), 110,
                      salt=0x42324400 + k, pad=pad, image=img)
    from PIL import Image
    blank = Image.new("RGBA", models[0][0].size, (0, 0, 0, 255))
    hidden = [([(0, -50, 0), (0.01, -50, 0), (0, -50, 0.01)], [(0, 0)] * 3)]   # Map Builder's glowing road gone
    eye = [[1, 0, 0], [0, 1, 0], [0, 0, 1], [0, 0, 0]]
    for k, (mat, fname) in enumerate(slots[len(models):] + [(eye, f) for f in skipped], len(models)):
        J.write_model(hidden, "empty", mat, os.path.join(flat, fname), 110, salt=0x42324400 + k, pad=pad, image=blank)
    print(min(len(slots), len(models)), "scenery models in", len(slots), "slots (the others emptied)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("lap"), ap.add_argument("pickups"), ap.add_argument("out")
    ap.add_argument("--name", required=True), ap.add_argument("--city", required=True)
    ap.add_argument("--route", type=int, required=True)
    ap.add_argument("--grid", type=float, nargs=2, required=True, metavar=("X", "Z"))
    ap.add_argument("--decor", action="store_true")
    ap.add_argument("--edges", action="store_true", help="road centre and width fitted between the walls")
    ap.add_argument("--official", metavar="ACTORPACK", help="X360 actorpack.xt of the city: official AI branches")
    a = ap.parse_args()
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
        models = b2decor.jobs(b2decor.extract(UNITY, laps, a.route), laps, make_nfs_map.DECOR_MAX + ROAD_SLOTS)
        b2decor.sheet(models, os.path.join(a.out, "atlas.png"))
        json.dump([make_nfs_map.zone_centre(t) for _, t in models[:make_nfs_map.DECOR_MAX]], open(spots, "w"))
    nfs = min(len(models), make_nfs_map.DECOR_MAX)
    env = dict(os.environ, BMB_GAME=config.BMB_GAME, BMB_INSTALLED="1", NFS_COUNT=str(nfs), NFS_SPOTS=spots,
               NFS_DRAW=str(make_nfs_map.DECOR_DRAW), NFS_NO_WALLS="1", NFS_FLOOR_Y="-5")
    subprocess.run([sys.executable, "build.py"], cwd=os.path.join(config.BMB_GAME, "map_builder", "flat_earth"),
                   env=env, check=True, stdout=subprocess.DEVNULL)
    make_nfs_map.main()
    if models:
        decor(files, models, nfs)
    phys = os.path.join(files, "levels", "flat_earth", "level.levelphysics")
    subprocess.run([sys.executable, os.path.join(HERE, "b2collision.py"), UNITY, phys, phys, "--route", str(a.route),
                    *laps, "--dy", str(1.0 - low)], check=True)


if __name__ == "__main__":
    main()
