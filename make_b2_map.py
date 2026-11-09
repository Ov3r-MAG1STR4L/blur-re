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
    loc["lighting"] = {"preset": "Amboy (desert day)",       # sunny desert sky (the base had Rio's Mount Haruna)
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
    mats = []
    for uid, fname in slots:
        try:
            mats.append((J.slot_matrix(ap, uid), fname))
        except AssertionError as e:                        # no single visible actor (with branches: road pieces)
            print("slot", fname, "skipped:", e)
    slots = mats
    for k, ((mat, fname), (img, tris)) in enumerate(zip(slots, models)):
        J.write_model(tris, "b2_%03d" % k, mat, os.path.join(flat, fname), 110,
                      salt=0x42324400 + k, pad=pad, image=img)
    from PIL import Image
    blank = Image.new("RGBA", models[0][0].size, (0, 0, 0, 255))
    hidden = [([(0, -50, 0), (0.01, -50, 0), (0, -50, 0.01)], [(0, 0)] * 3)]   # Map Builder's glowing road gone
    for k, (mat, fname) in enumerate(slots[len(models):], len(models)):
        J.write_model(hidden, "empty", mat, os.path.join(flat, fname), 110, salt=0x42324400 + k, pad=pad, image=blank)
    print(min(len(slots), len(models)), "scenery models in", len(slots), "slots (the others emptied)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("lap"), ap.add_argument("pickups"), ap.add_argument("out")
    ap.add_argument("--name", required=True), ap.add_argument("--city", required=True)
    ap.add_argument("--route", type=int, required=True)
    ap.add_argument("--grid", type=float, nargs=2, required=True, metavar=("X", "Z"))
    ap.add_argument("--decor", action="store_true")
    ap.add_argument("--official", metavar="ACTORPACK", help="X360 actorpack.xt of the city: official AI branches")
    a = ap.parse_args()
    lap = [(float(r["x"]), float(r["y"]), float(r["z"])) for r in csv.DictReader(open(a.lap))]
    pk = json.load(open(a.pickups))["pickups"]
    w, low, npk, res = world(lap, pk, a.name, a.city, a.grid)
    laps = [a.lap]
    if a.official:
        w["locations"][0]["maps"][0]["branches"], extra = branches(a.official, lap, res, low, a.out)
        laps += extra
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
