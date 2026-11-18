#!/usr/bin/env python3
"""Race trace (b2track / make_b2_map --track format) of a Dubai route from its rolled lap, kept ON THE ROAD.

The rolled lap (lap_routeN_*.csv, Blur2DubaiTest) goes up walls and through loops; a trace copied from it put the
Map Builder road (tile collision + respawn line) in mid-air beside the wall (Business Bay, 2026-11-18: crash into
it, respawn under the map). Here, after resampling every STEP m (as the editor): a point is OFF THE ROAD when the
nearest collision surface within REACH m is steep (|n.y| < 0.5: wall), or above it (loop top, ceiling), or when
there is none (in the air: loop drop-off, jump). Each run of such points (one more on each side) gets the straight
line, x z and h, between the road points around it. h = y - lowest lap y (as the editor and make_b2_map).

usage: b2trace.py ROUTE [--out FILE] [--force]     (default out: blur2_aid/dubai/dubai_routeN_trace.json)
"""
import argparse, glob, json, os, sys
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import b2gravity_zones, b2track, make_b2_map  # noqa: E402

REACH, STEEP = 3.0, 0.5


def off_road(pts, S, N):
    from scipy.spatial import cKDTree
    d, i = cKDTree(S).query(pts)
    near = d < REACH
    wall = near & (N[i] < STEEP)
    under = near & (S[i, 1] > pts[:, 1] + 0.5)
    air = ~near
    return wall | under | air, wall, under, air


def runs(mask):
    out, i = [], 0
    while i < len(mask):
        if mask[i]:
            j = i
            while j + 1 < len(mask) and mask[j + 1]:
                j += 1
            out.append((i, j))
            i = j + 1
        else:
            i += 1
    return out


def floors(route):
    """floor triangles (|n.y| > 0.7, either winding) of the route's collision, with their x z bounds"""
    import b2collision
    F = []
    for name, (v, tr) in b2collision.colliders(make_b2_map.UNITY).items():
        if name.startswith("physics_route_") and not name.startswith("physics_route_%d_" % route):
            continue
        T = v[tr]
        n = np.cross(T[:, 1] - T[:, 0], T[:, 2] - T[:, 0])
        ln = np.linalg.norm(n, axis=1)
        ok = ln > 1e-9
        F.append(T[ok][np.abs(n[ok, 1] / ln[ok]) > 0.7])
    F = np.vstack(F)
    return F, F[:, :, [0, 2]].min(1), F[:, :, [0, 2]].max(1)


def floor_heights(F, lo, hi, x, z):
    """heights of the floor triangles right under / over (x, z): vertical ray"""
    out = []
    for i in np.where((lo[:, 0] <= x) & (hi[:, 0] >= x) & (lo[:, 1] <= z) & (hi[:, 1] >= z))[0]:
        a, b, c = F[i]
        d = (b[2] - c[2]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[2] - c[2])
        if abs(d) < 1e-9:
            continue
        l1 = ((b[2] - c[2]) * (x - c[0]) + (c[0] - b[0]) * (z - c[2])) / d
        l2 = ((c[2] - a[2]) * (x - c[0]) + (a[0] - c[0]) * (z - c[2])) / d
        if min(l1, l2, 1 - l1 - l2) >= -1e-6:
            out.append(l1 * a[1] + l2 * b[1] + (1 - l1 - l2) * c[1])
    return out


def all_points(t):
    """main line then every branch (Marina has branches; the game may respawn a car on them too)"""
    return t["points"] + [q for b in t.get("branches", []) for q in b["points"]]


def snap(route, t, low, reach=6.0):
    """puts every point ON the road under it (the floor whose height is nearest, within reach m): the game respawns
    cars on the trace. Returns the points left without a road [(i, x, z, h)]"""
    F, lo, hi = floors(route)
    left = []
    allp = all_points(t)
    for i, q in enumerate(allp):
        y = q["h"] + low
        hs = floor_heights(F, lo, hi, q["x"], q["z"])
        near = min(hs, key=lambda h: abs(h - y)) if hs else None
        if near is not None and abs(near - y) <= reach:
            q["h"] = round(float(near - low), 2)
        else:
            left.append(i)
    # no road under it (the race line is ON the wall: Marina's south-west turn, Business Bay's drop): moved onto
    # the nearest floor within MOVE m (3D), e.g. the foot of the wall, so that a respawn there lands on a road
    from scipy.spatial import cKDTree
    C = F.mean(1)
    kd = cKDTree(C)
    still = []
    for i in left:
        q = allp[i]
        d, j = kd.query([q["x"], q["h"] + low, q["z"]])
        if d <= MOVE:
            q["x"], q["z"], q["h"] = round(float(C[j, 0]), 2), round(float(C[j, 2]), 2), round(float(C[j, 1] - low), 2)
            q["moved_m"] = round(float(d), 1)
        else:
            still.append((i, q["x"], q["z"], q["h"]))
    return still


MOVE = 40.0


def check(route, trace, low, tol=3.0):
    """respawn safety (2026-11-18, the user respawned under the map): every trace point is a place the game may put
    the car back; it needs a road within tol m above or below it. Returns the bad points [(i, x, z, h, nearest)]"""
    F, lo, hi = floors(route)
    bad = []
    for i, q in enumerate(all_points(json.load(open(trace)))):
        y = q["h"] + low
        hs = floor_heights(F, lo, hi, q["x"], q["z"])
        near = min(hs, key=lambda h: abs(h - y)) if hs else None
        if near is None or abs(near - y) > tol:
            bad.append((i, q["x"], q["z"], q["h"], None if near is None else round(near - low, 1)))
    return bad


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("route", type=int)
    ap.add_argument("--out")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--check", metavar="TRACE", help="only check a trace for respawn safety")
    ap.add_argument("--snap", metavar="TRACE", help="put an existing trace's points on the road (in place, .bak kept)")
    a = ap.parse_args()
    if a.snap:
        lap = glob.glob(os.path.join(b2track.DUBAI, "lap_route%d_*.csv" % a.route))[0]
        low = min(p[1] for p in make_b2_map.resample(b2track.read_lap(lap), make_b2_map.STEP))
        t = json.load(open(a.snap))
        if not os.path.exists(a.snap + ".bak"):
            json.dump(t, open(a.snap + ".bak", "w"), indent=1)
        left = snap(a.route, t, low)
        t["note"] = t.get("note", "") + "; b2trace --snap: points put on the road under them (respawn safety), %d left" % len(left)
        json.dump(t, open(a.snap, "w"), indent=1)
        print("%s: %d / %d points left without a road within 6 m" % (os.path.basename(a.snap), len(left), len(all_points(t))))
        for b in left:
            print("  point %d (%.0f, %.0f) h %.1f" % b)
        return
    if a.check:
        lap = glob.glob(os.path.join(b2track.DUBAI, "lap_route%d_*.csv" % a.route))[0]
        low = min(p[1] for p in make_b2_map.resample(b2track.read_lap(lap), make_b2_map.STEP))
        bad = check(a.route, a.check, low)
        n = len(all_points(json.load(open(a.check))))
        print("%s: %d / %d points without a road within 3 m (respawn risk)" % (os.path.basename(a.check), len(bad), n))
        for b in bad:
            print("  point %d (%.0f, %.0f) h %.1f, nearest road h %s" % b)
        return
    out = a.out or os.path.join(b2track.DUBAI, "dubai_route%d_trace.json" % a.route)
    if os.path.exists(out) and not a.force:
        sys.exit("%s exists (--force to replace it)" % out)
    lap = glob.glob(os.path.join(b2track.DUBAI, "lap_route%d_*.csv" % a.route))[0]
    P = np.array(make_b2_map.resample(b2track.read_lap(lap), make_b2_map.STEP))
    low = P[:, 1].min()
    S, N = b2gravity_zones.surface_samples(a.route)
    bad, wall, under, air = off_road(P, S, N)
    fixed = []
    for i, j in runs(bad):
        i0, j1 = i - 1, j + 1
        if i0 < 0 or j1 >= len(P):
            print("run %d-%d touches the lap ends: left as is" % (i, j))
            continue
        for k in range(i, j + 1):
            u = (k - i0) / (j1 - i0)
            P[k] = P[i0] + (P[j1] - P[i0]) * u
        kinds = "/".join(n for n, m in (("wall", wall), ("under", under), ("air", air)) if m[i:j + 1].any())
        fixed.append("%d-%d (%s)" % (i, j, kinds))
    t = {"points": [{"x": round(float(x), 2), "z": round(float(z), 2), "w": make_b2_map.WIDTH, "h": round(float(y - low), 2)}
                    for x, y, z in P],
         "branches": [],
         "note": "b2trace.py from %s: points off the road (wall, under a surface, in the air) replaced by the line "
                 "between the road points around them: %s" % (os.path.basename(lap), ", ".join(fixed) or "none")}
    json.dump(t, open(out, "w"), indent=1)
    print(len(P), "points, %d runs put back on the road:" % len(fixed), ", ".join(fixed), "->", out)
    print("max h %.1f" % max(q["h"] for q in t["points"]))


if __name__ == "__main__":
    main()
