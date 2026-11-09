#!/usr/bin/env python3
"""Blur 2 route -> playable Blur 1 map in the flat_earth slot (project J pipeline, Blur Map Builder copy bmb_game).

1. world.json for Map Builder from a driven lap (lap2aid CSV): one point / STEP m, width W, height above the map
   floor h = y - lowest y (Map Builder puts the lowest point 1 m above its floor, as make_nfs_map.set_heights),
   start_m = the official grid's slot 0, official pickups (Blur2DubaiTest <city>.json, within 40 m of the lap)
   as Map Builder rows; the previous world.json is kept as world.json.bak.
2. build.py of Map Builder (NFS_NO_WALLS, NFS_FLOOR_Y as project J), files collected with make_nfs_map.main.
3. collision: b2collision (Unity MeshColliders within 60 m of the lap), shifted by 1 - lowest y, inserted in the
   built level.levelphysics.
Output: OUT/files (to copy over Blur_test). Install separately, with a backup.

usage: make_b2_map.py LAP.csv PICKUPS.json OUT --name Marina --city Dubai --route 4 --grid X Z
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
    m = loc["maps"][0]
    m.update(id="b2_%s_1" % city.lower(), name=name, laps=3, width=TUBE, auto_bridges=False, branches=[],
             points=[{"x": round(x, 2), "z": round(z, 2), "w": WIDTH, "h": round(y - low, 2)} for x, y, z in pts],
             pickups=rows, pickup_per_row=1, start_m=int(cum[i0]), finish_m=int(cum[i0]))
    loc["maps"] = [m]
    base["locations"] = [loc]
    return base, low, len(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("lap"), ap.add_argument("pickups"), ap.add_argument("out")
    ap.add_argument("--name", required=True), ap.add_argument("--city", required=True)
    ap.add_argument("--route", type=int, required=True)
    ap.add_argument("--grid", type=float, nargs=2, required=True, metavar=("X", "Z"))
    a = ap.parse_args()
    lap = [(float(r["x"]), float(r["y"]), float(r["z"])) for r in csv.DictReader(open(a.lap))]
    pk = json.load(open(a.pickups))["pickups"]
    w, low, npk = world(lap, pk, a.name, a.city, a.grid)
    wfile = os.path.join(config.BMB_GAME, "Blur Map Builder", "maps", "world.json")
    if not os.path.exists(wfile + ".bak"):
        shutil.copyfile(wfile, wfile + ".bak")
    json.dump(w, open(wfile, "w"), indent=1)
    print("world.json: %d points, lowest road y %.1f, %d pickups, start_m %d"
          % (len(w["locations"][0]["maps"][0]["points"]), low, npk, w["locations"][0]["maps"][0]["start_m"]))
    env = dict(os.environ, BMB_GAME=config.BMB_GAME, BMB_INSTALLED="1", NFS_COUNT="0", NFS_NO_WALLS="1",
               NFS_FLOOR_Y="-5")
    subprocess.run([sys.executable, "build.py"], cwd=os.path.join(config.BMB_GAME, "map_builder", "flat_earth"),
                   env=env, check=True, stdout=subprocess.DEVNULL)
    files = os.path.join(a.out, "files")
    import make_nfs_map                                # its paths come from sys.argv at import: set them
    make_nfs_map.BMB, make_nfs_map.OUT = config.BMB_GAME, files
    make_nfs_map.WORK = os.path.join(config.BMB_GAME, "Blur Map Builder", "work")
    make_nfs_map.main()
    phys = os.path.join(files, "levels", "flat_earth", "level.levelphysics")
    subprocess.run([sys.executable, os.path.join(HERE, "b2collision.py"), UNITY, phys, phys, "--route", str(a.route),
                    a.lap, "--dy", str(1.0 - low)], check=True)


if __name__ == "__main__":
    main()
