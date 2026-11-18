#!/usr/bin/env python3
"""3D viewer data for a Blur 2 city (Blur2DubaiTest's Unity collision) with its circuits, to choose what to build.

Reads every MeshCollider (b2collision.colliders, game axes), sorts the triangles into layers:
  road     drivable (collider suffix 17f / 8017f) with n.y >= 0.5
  steep    drivable with |n.y| < 0.5           -> wall-ride candidates
  over     drivable with n.y <= -0.5           -> facing down: bridge underside or loop top / ceiling
  walls    15d colliders
  route_N  physics_route_N_* barriers (the walls that close route N)
  other    anything else
lightens them by vertex clustering (GRID m, degenerate triangles dropped) and writes
  OUT/<city>.bin  : per layer Int16 x/y/z in decimetres around the centre, then Uint32 indices
  OUT/<city>.json : layer table (offsets, counts), circuits, official grids, gravity zones
Circuits: the rolled laps lap_routeN_*.csv (all 4 Dubai routes have one). A route without a lap would need a
supposed circuit (corridor between its physics_route_N barriers): not written, add it when a city lacks laps.

usage: b2viewer.py [--city dubai] [--grid 1.0] [--out viewer/dubai]
"""
import argparse, base64, csv, glob, json, os, re, sys
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import b2collision  # noqa: E402
import config  # noqa: E402

UNITY = os.path.join(config.JEUX, "Blur2DubaiTest", "Blur2DubaiTest_Data")
AID = os.path.join(config.JEUX, "blur2_aid")
GRAVITY_TXT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "natif", "b2gravity", "b2gravity.txt")
# official grids (CONNAISSANCES: "Les 4 routes de Dubaï"), game axes x, z
STARTS = {1: ("Business Bay", 90, -174), 2: ("Dubai Island", -540, 482), 3: ("Construction", 429, -1014),
          4: ("Marina", -435, 473)}


def layer_of(name):
    """names: physics_main_part_002_17f_collision, physics_route_4_part_000_5d_collision"""
    m = re.match(r"physics_route_(\d+)", name)
    if m:
        return "route_" + m.group(1), False
    suffix = name.replace("_collision", "").rsplit("_", 1)[-1]
    if suffix in ("17f", "8017f"):                # road and other drivable
        return "drivable", True
    if suffix == "15d":
        return "walls", False
    return "other", False


def cluster(v, t, grid):
    """vertex clustering: snap to grid, merge, drop degenerate and duplicate triangles"""
    key = np.round(v / grid).astype(np.int64)
    uniq, inv = np.unique(key, axis=0, return_inverse=True)
    inv = inv.reshape(-1)
    nv = np.zeros((len(uniq), 3))
    np.add.at(nv, inv, v)
    nv /= np.bincount(inv, minlength=len(uniq))[:, None]
    nt = inv[t]
    nt = nt[(nt[:, 0] != nt[:, 1]) & (nt[:, 1] != nt[:, 2]) & (nt[:, 0] != nt[:, 2])]
    _, first = np.unique(np.sort(nt, axis=1), axis=0, return_index=True)
    return nv, nt[np.sort(first)]


def normals_y(v, t):
    a, b, c = v[t[:, 0]], v[t[:, 1]], v[t[:, 2]]
    n = np.cross(b - a, c - a)
    ln = np.linalg.norm(n, axis=1)
    ln[ln == 0] = 1
    return n[:, 1] / ln


def gravity_zones(path):
    zs = []
    if os.path.exists(path):
        for line in open(path, encoding="utf-8", errors="replace"):
            p = line.split()
            if len(p) == 6 and not line.startswith("#"):
                try:
                    zs.append([float(x) for x in p])
                except ValueError:
                    pass
    return zs


def laps(city):
    out = {}
    for p in sorted(glob.glob(os.path.join(AID, city, "lap_route*.csv"))):
        m = re.match(r"lap_route(\d+)_(.+)\.csv", os.path.basename(p))
        rows = list(csv.DictReader(open(p)))
        pts = [[round(float(r["x"]), 1), round(float(r["y"]), 1), round(float(r["z"]), 1), round(float(r["kmh"]))]
               for r in rows]
        d = sum(np.hypot(a[0] - b[0], a[2] - b[2]) for a, b in zip(pts, pts[1:]))
        out[int(m.group(1))] = {"name": m.group(2).replace("_", " ").title(), "points": pts, "length_m": round(d),
                                "source": "rolled lap " + os.path.basename(p)}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--city", default="dubai")
    ap.add_argument("--grid", type=float, default=1.0)
    ap.add_argument("--out", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "viewer", "dubai"))
    a = ap.parse_args()

    groups = {}
    for name, (v, t) in b2collision.colliders(UNITY).items():
        lay, drivable = layer_of(name)
        if not len(t):
            continue
        if drivable:
            ny = normals_y(v, t)
            # Unity winding is not reliable (bridge undersides, flipped faces): steep = |n.y| < 0.5 either way,
            # "over" = facing down (n.y <= -0.5): bridge underside OR loop top, the viewer says so
            for sub, sel in (("road", ny >= 0.5), ("steep", np.abs(ny) < 0.5), ("over", ny <= -0.5)):
                if sel.any():
                    groups.setdefault(sub, []).append((v, t[sel]))
        else:
            groups.setdefault(lay, []).append((v, t))

    allv = np.vstack([v for g in groups.values() for v, _ in g])
    lo, hi = allv.min(0), allv.max(0)
    centre = np.round((lo + hi) / 2)
    os.makedirs(a.out, exist_ok=True)
    blob, table = bytearray(), []
    for lay in sorted(groups):
        vs, ts, base = [], [], 0
        for v, t in groups[lay]:
            used = np.unique(t)
            remap = np.full(len(v), -1, np.int64)
            remap[used] = np.arange(len(used))
            vs.append(v[used]); ts.append(remap[t] + base); base += len(used)
        v, t = cluster(np.vstack(vs), np.vstack(ts), a.grid)
        q = np.clip(np.round((v - centre) * 10), -32767, 32767).astype("<i2")
        while len(blob) % 4:
            blob.append(0)
        vo = len(blob); blob += q.tobytes()
        while len(blob) % 4:
            blob.append(0)
        io = len(blob); blob += t.astype("<u4").tobytes()
        table.append({"layer": lay, "vertices": int(len(v)), "triangles": int(len(t)), "v_offset": vo, "i_offset": io})
        print(f"{lay:10s} {len(t):8d} triangles, {len(v):7d} vertices")
    open(os.path.join(a.out, a.city + ".bin"), "wb").write(blob)
    with open(os.path.join(a.out, a.city + ".b64.txt"), "w") as f:      # what the web page loads (no raw binary served)
        f.write(base64.b64encode(bytes(blob)).decode())
    meta = {"city": a.city, "centre": centre.tolist(), "bounds": [lo.tolist(), hi.tolist()], "grid_m": a.grid,
            "layers": table, "circuits": laps(a.city),
            "starts": {k: {"name": n, "x": x, "z": z} for k, (n, x, z) in STARTS.items()},
            "gravity_zones": {"route": 4, "boxes": gravity_zones(GRAVITY_TXT)}}
    json.dump(meta, open(os.path.join(a.out, a.city + ".json"), "w"), separators=(",", ":"))
    print(f"{len(blob) / 1e6:.1f} MB -> {a.out}")


if __name__ == "__main__":
    main()
