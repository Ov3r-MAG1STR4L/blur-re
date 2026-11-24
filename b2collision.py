#!/usr/bin/env python3
"""Blur 2 city collision (from Blur2DubaiTest's Unity data) -> a Blur 1 Level.levelphysics.

Source: the MeshColliders of the Unity build (UnityPy), world matrix from their Transform chain; game = (-x, y, -z)
(Dubai: 98 % of the vertices within 2 m of the X360 collision). Collider name suffixes: 17f road (63 % flat),
15d walls (71 % vertical), 8017f other drivable, physics_route_N_* = the barriers of route N (walls only).
Kept: triangles within RADIUS m of the given laps (as make_nfs_map.road_collision: whole city = 400 k triangles),
barriers of the other routes dropped. Written like make_nfs_map.road_collision (project J, confirmed in game):
type-0 mesh objects of <= 255 triangles / 256 vertices (addramp.mesh_object, template = the base level) inserted
first in the base level's Main stream (addramp.insert_objects); the base's own ground stays below.

usage: b2collision.py UNITY_DATA_DIR BASE_Level.levelphysics OUT --route N LAP.csv [LAP.csv ...] [--radius 60]
"""
import argparse, csv, os, sys
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import addramp  # noqa: E402


def quat(q):
    x, y, z, w = q.x, q.y, q.z, q.w
    return np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                     [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                     [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])


def world_matrix(tr):
    m = np.eye(4)
    while tr is not None:
        s = tr.m_LocalScale
        loc = np.eye(4)
        loc[:3, :3] = quat(tr.m_LocalRotation) * [s.x, s.y, s.z]
        loc[:3, 3] = [tr.m_LocalPosition.x, tr.m_LocalPosition.y, tr.m_LocalPosition.z]
        m = loc @ m
        tr = tr.m_Father.read() if tr.m_Father and tr.m_Father.path_id else None
    return m


COMPLEMENTS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "blur2_aid", "dubai",
                           "complements_collision.npz")      # b2visfill : collision tirée des meshes visibles


def colliders(data_dir, complements=True):
    """{name: (world vertices (n, 3) in GAME axes, triangles (m, 3))} of every MeshCollider of the build, plus the
    b2visfill complements (visible meshes with no collider: « complement_<mesh>_<k>_17f_collision », drivable)"""
    out = _unity_colliders(data_dir)
    if complements and os.path.exists(COMPLEMENTS):
        d = np.load(COMPLEMENTS)
        for k, name in enumerate(d["names"]):
            out["complement_%s_%d_17f_collision" % (name, k)] = (d["v%d" % k].astype(float), d["t%d" % k].astype(int))
    return out


def _unity_colliders(data_dir):
    import UnityPy
    from UnityPy.helpers.MeshHelper import MeshHandler
    env = UnityPy.load(data_dir)
    out = {}
    for o in env.objects:
        if o.type.name != "MeshCollider":
            continue
        c = o.read()
        go = c.m_GameObject.read()
        tr = [p.read() for p in (x.component if hasattr(x, "component") else x for x in go.m_Component)
              if p.type.name == "Transform"][0]
        h = MeshHandler(c.m_Mesh.read())
        h.process()
        v = np.array(h.m_Vertices, float).reshape(-1, 3)
        m = world_matrix(tr)
        w = v @ m[:3, :3].T + m[:3, 3]
        out[go.m_Name] = (w * [-1, 1, -1], np.array(h.get_triangles(), int).reshape(-1, 3))
    return out


def lap_points(paths):
    pts = []
    for p in paths:
        pts += [(float(r["x"]), float(r["z"])) for r in csv.DictReader(open(p))]
    return np.array(pts)


# 2026-11-18 (Business Bay, b2gravity): a triangle only collides while the car's centre is in FRONT of it
# (gravity ConvexTriangle.inl: early exit when the hull centre is behind the plane) and these surfaces have no
# thickness, so a car pressed onto a wall (gravity + downforce turned to the wall, ~2.3 g) that gets its centre past
# the plane after a knock goes through and falls. Steep (n.y < 0.5) and downward triangles get a copy BACKSTOP m
# behind, same side: a centre past the first plane is still in front of the second one, which pushes it back out.
# ponytail: one layer at a fixed depth; thicker or several layers if cars still get through.
# 2026-11-23: switched OFF at the user's request ("mal appliquée, pas sur les bons éléments"): addramp.mesh_object
# re-winds every triangle to face up, so the copy did not sit behind the face the car meets; and the first
# position captures (Business Bay) are on drivable 17f wall-ride surfaces, not 15d walls.
# 2026-11-23 (later, user's go-ahead): back ON now that the face is kept (mesh_object keep=True): the copy sits behind
# the face turned to the lap, only for oriented one-sided triangles with n.y < 0.5 (walls, wall-ride, overhangs).
BACKSTOP = 1.0


# 2026-11-18 ("walls and roads with no hitbox, unlike Unity"): Unity's MeshColliders block from both sides, Blur's
# triangles from their normal's side only, and 14 % (Business Bay) to 26 % (Marina) of the triangles within 20 m
# of the lap face AWAY from it (roads 17f 11-25 %, walls 15d 29-45 %). Within ORIENT m of the lap, a triangle is
# turned to face the lap; when the lap passes on both sides of it (within ORIENT_BOTH m: thin wall between two
# roads, bridge deck with a road under it) it is kept with both faces.
# Switched OFF the same day at the user's request ("it became a bit chaotic", back to the build just before).
# 2026-11-23: that try never reached the game: addramp.mesh_object re-wound every triangle up afterwards (and the
# "both faces" copy became a duplicate). Back ON with keep=True, for n.y < 0.5 only (walls, wall-ride surfaces,
# overhangs, loop tops); floors (n.y >= 0.5) keep facing up. Faces the nearest lap point clearly off the plane
# (|s| > 0.3 m). Triangles with no lap point within ORIENT m: faced up as before.
ORIENT, ORIENT_BOTH = 60.0, 20.0


# 2026-11-23 (Business Bay loop, part_003_17f, triangles of 58-71 m2): the car going down the wall-ride at ~34 m/s got
# behind these huge faces and stuck there / fell under the map. Steep triangles (n.y < 0.5) larger than SPLIT m2 are
# cut in 4 (edge midpoints, same plane, same winding) until all are below it.
SPLIT, SPLIT_NEAR = 8.0, 40.0


def split_steep(T):
    """(m, 3, 3) triangles -> same surface, steep ones cut to <= SPLIT m2"""
    out = [T[:0]]
    while len(T):
        n = np.cross(T[:, 1] - T[:, 0], T[:, 2] - T[:, 0])
        a = np.linalg.norm(n, axis=1) / 2
        big = (a > SPLIT) & (n[:, 1] < 0.5 * 2 * a)
        out.append(T[~big])
        B = T[big]
        m01, m12, m20 = (B[:, 0] + B[:, 1]) / 2, (B[:, 1] + B[:, 2]) / 2, (B[:, 2] + B[:, 0]) / 2
        T = np.concatenate([np.stack(s, 1) for s in ((B[:, 0], m01, m20), (m01, B[:, 1], m12),
                                                      (m20, m12, B[:, 2]), (m01, m12, m20))]) if len(B) else B
    return np.concatenate(out)


def lap_points_3d(paths, dy):
    pts = []
    for p in paths:
        pts += [(float(r["x"]), float(r["y"]) + dy, float(r["z"])) for r in csv.DictReader(open(p))]
    return np.array(pts)


def build(cols, base, route, laps, radius, dy=0.0):
    """dy: height shift (a Map Builder map puts the route's lowest point 1 m above its floor: dy = 1 - lowest y)"""
    from scipy.spatial import cKDTree
    near = cKDTree(lap_points(laps))
    L3 = lap_points_3d(laps, dy)
    lap3 = cKDTree(L3)
    tris, flipped, both = [], 0, 0
    for name, (v, t) in cols.items():
        if name.startswith("physics_route_") and not name.startswith("physics_route_%d_" % route):
            continue                                   # another route's barriers
        T = v[t] + (0, dy, 0)
        close = lap3.query(T.mean(1))[0] < SPLIT_NEAR   # only where the car drives (Marina: 828 k triangles, 88 MB
        T = np.concatenate([split_steep(T[close]), T[~close]])   # when every facade within 150 m was cut)
        c = T.mean(1)
        d, k = near.query(c[:, [0, 2]])
        n = np.cross(T[:, 1] - T[:, 0], T[:, 2] - T[:, 0])
        n /= np.linalg.norm(n, axis=1, keepdims=True) + 1e-12
        for i in np.where(d < radius)[0]:
            tri, nn, two, oriented = T[i], n[i], False, False
            if nn[1] < 0.5 and ORIENT > 0:              # wall, wall-ride, overhang: face the lap
                idx = lap3.query_ball_point(c[i], ORIENT)
                if idx:
                    s = (L3[idx] - c[i]) @ nn              # lap points in front (> 0) / behind (< 0)
                    dist = np.linalg.norm(L3[idx] - c[i], axis=1)
                    clear = np.abs(s) > 0.3
                    if clear.any():
                        oriented = True
                        front = (s > 0.3) & (dist < ORIENT_BOTH)
                        back = (s < -0.3) & (dist < ORIENT_BOTH)
                        if front.any() and back.any():
                            two = True                     # the lap on both sides: both faces
                        elif s[clear][np.argmin(dist[clear])] < 0:   # nearest clear lap point behind: face it
                            tri, nn = tri[[0, 2, 1]], -nn
                            flipped += 1
            if not oriented and nn[1] < 0:                 # floors and far triangles: up, as before
                tri, nn = tri[[0, 2, 1]], -nn
            tris.append((k[i], tri))
            if two:
                tris.append((k[i], tri[[0, 2, 1]]))
                both += 1
            elif BACKSTOP and oriented and nn[1] < 0.5:  # a second layer behind the face the car meets
                tris.append((k[i], tri - nn * BACKSTOP))
    print("orientation: %d triangles turned to face the lap, %d kept with both faces" % (flipped, both))
    tris.sort(key=lambda x: x[0])                      # along the route: compact objects
    objs, verts, idx, key = [], [], [], {}
    for _, tri in tris:
        ks = [tuple(np.round(p, 3)) for p in tri]
        new = [k for k in dict.fromkeys(ks) if k not in key]
        if len(idx) >= 255 or len(verts) + len(new) > 256:
            objs.append(addramp.mesh_object(verts, idx, base, keep=True))
            verts, idx, key = [], [], {}
            new = list(dict.fromkeys(ks))
        for k in new:
            key[k] = len(verts)
            verts.append(k)
        idx.append(tuple(key[k] for k in ks))
    if idx:
        objs.append(addramp.mesh_object(verts, idx, base, keep=True))
    return addramp.insert_objects(open(base, "rb").read(), b"".join(objs)), len(tris), len(objs)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("unity_data"), ap.add_argument("base"), ap.add_argument("out")
    ap.add_argument("--route", type=int, required=True)
    ap.add_argument("laps", nargs="+")
    ap.add_argument("--radius", type=float, default=60.0)
    ap.add_argument("--dy", type=float, default=0.0)
    a = ap.parse_args()
    cols = colliders(a.unity_data)
    data, ntri, nobj = build(cols, a.base, a.route, a.laps, a.radius, a.dy)
    open(a.out, "wb").write(data)
    print("%d colliders, %d triangles kept (<= %.0f m of the laps) -> %d objects, %d bytes -> %s"
          % (len(cols), ntri, a.radius, nobj, len(data), a.out))


if __name__ == "__main__":
    main()
