#!/usr/bin/env python3
"""Wall-ride zones for natif/b2gravity.dll: where the user drove in Blur2DubaiTest on steep surfaces (2026-11-16).

Positions = every journal of blur2_aid/journaux on the route (b2track.drives) + the driven lap. A position is "on a
wall" when the nearest collision surface (Unity MeshColliders, other routes' barriers out) within REACH m has
|normal y| < STEEP. Those positions are grouped (cells of CELL m, touching cells merged) and each group becomes a
box, MARGIN m wider; y shifted by DY like the whole map (Map Builder: lowest lap point at y = 1).
Output: lines "minx miny minz maxx maxy maxz" (+ "speed 13.9") for b2gravity.txt.

usage: b2gravity_zones.py OUT.txt [--route 4]
"""
import argparse, csv, os, sys
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import b2collision, b2track, make_b2_map  # noqa: E402

REACH, STEEP, CELL, MARGIN, MIN_POINTS = 3.0, 0.6, 10.0, 12.0, 3
NEAR_TRACK = 40.0   # m (top view) from a point of marina_trace.json (main road + branches): zone kept
FLOOR = 3.0      # no flat surface (|ny| >= STEEP) closer: on the wall (the wall-hugging edge drives stay out)


def surface_samples(route):
    S, N = [], []
    for name, (v, t) in b2collision.colliders(make_b2_map.UNITY).items():
        if name.startswith("physics_route_") and not name.startswith("physics_route_%d_" % route):
            continue
        T = v[t]
        n = np.cross(T[:, 1] - T[:, 0], T[:, 2] - T[:, 0])
        ny = np.abs(n[:, 1]) / np.maximum(np.linalg.norm(n, axis=1), 1e-9)
        for w in ((1/3, 1/3, 1/3), (.6, .2, .2), (.2, .6, .2), (.2, .2, .6), (.5, .5, 0), (0, .5, .5), (.5, 0, .5)):
            S.append((T * np.array(w)[None, :, None]).sum(1))
            N.append(ny)
    return np.concatenate(S), np.concatenate(N)


def boxes(P):
    """groups of touching CELL-m cells -> [min xyz, max xyz] + MARGIN"""
    from scipy import ndimage
    lo = P.min(0)
    c = ((P - lo) // CELL).astype(int)
    grid = np.zeros(c.max(0) + 1, bool)
    grid[tuple(c.T)] = True
    lab, n = ndimage.label(grid, structure=np.ones((3, 3, 3)))
    k = lab[tuple(c.T)]
    out = []
    for i in range(1, n + 1):
        Q = P[k == i]
        if len(Q) >= MIN_POINTS:
            out.append(np.r_[Q.min(0) - MARGIN, Q.max(0) + MARGIN])
    return out


def main():
    from scipy.spatial import cKDTree
    ap = argparse.ArgumentParser()
    ap.add_argument("out"), ap.add_argument("--route", type=int, default=4)
    a = ap.parse_args()
    lap = os.path.join(b2track.DUBAI, "lap_route4_marina.csv")
    L = np.array([(float(r["x"]), float(r["y"]), float(r["z"])) for r in csv.DictReader(open(lap))])
    D = [np.array(d["pts"]).reshape(-1, 3) for d in b2track.drives(a.route)]
    P = np.vstack([L] + D)
    S, N = surface_samples(a.route)
    d, i = cKDTree(S).query(P)
    fd = cKDTree(S[N >= STEEP]).query(P)[0]           # nearest flat surface: beside a wall, not on it
    wall = P[(d < REACH) & (N[i] < STEEP) & (fd > FLOOR)]
    print(len(P), "positions,", len(wall), "on steep surfaces (|ny| < %.1f)" % STEEP)
    import json
    t = json.load(open(os.path.join(b2track.DUBAI, "marina_trace.json")))
    T = np.array([(q["x"], q["z"]) for pts in [t["points"]] + [b["points"] for b in t["branches"]] for q in pts])
    near = lambda b: (np.hypot(np.clip(T[:, 0], b[0], b[3]) - T[:, 0], np.clip(T[:, 1], b[2], b[5]) - T[:, 1])
                      < NEAR_TRACK).any()
    B = [b for b in boxes(wall) if near(b)]                 # zones on the drivable lines only (others: city parts)
    wall = wall[np.any([(b[:3] <= wall).all(1) & (wall <= b[3:]).all(1) for b in B], 0)] if B else wall[:0]
    dy = 1.0 - L[:, 1].min()
    with open(a.out, "w") as f:
        f.write("# b2gravity zones, Dubai route %d (b2gravity_zones.py), game axes, y shifted by %.2f\nspeed 13.9\n"
                % (a.route, dy))
        for b in B:
            b = b + [0, dy, 0, 0, dy, 0]
            f.write("%.1f %.1f %.1f %.1f %.1f %.1f\n" % tuple(b))
            print("zone x %.0f..%.0f  y %.0f..%.0f  z %.0f..%.0f" % (b[0], b[3], b[1], b[4], b[2], b[5]))
    inside = [(b[:3] <= wall).all(1) & (wall <= b[3:]).all(1) for b in B]
    print(len(B), "zones; steep positions covered: %.0f %%" % (100 * np.any(inside, 0).mean() if B else 0))


if __name__ == "__main__":
    main()
