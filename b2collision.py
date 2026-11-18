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


def colliders(data_dir):
    """{name: (world vertices (n, 3) in GAME axes, triangles (m, 3))} of every MeshCollider of the build"""
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
BACKSTOP = 1.0


def build(cols, base, route, laps, radius, dy=0.0):
    """dy: height shift (a Map Builder map puts the route's lowest point 1 m above its floor: dy = 1 - lowest y)"""
    from scipy.spatial import cKDTree
    near = cKDTree(lap_points(laps))
    tris = []
    for name, (v, t) in cols.items():
        if name.startswith("physics_route_") and not name.startswith("physics_route_%d_" % route):
            continue                                   # another route's barriers
        v = v + (0, dy, 0)
        c = v[t].mean(1)
        d, k = near.query(c[:, [0, 2]])
        T = v[t]
        n = np.cross(T[:, 1] - T[:, 0], T[:, 2] - T[:, 0])
        n /= np.linalg.norm(n, axis=1, keepdims=True) + 1e-12
        for i in np.where(d < radius)[0]:
            tris.append((k[i], T[i]))
            if BACKSTOP and n[i, 1] < 0.5:              # steep or facing down: a second layer behind
                tris.append((k[i], T[i] - n[i] * BACKSTOP))
    tris.sort(key=lambda x: x[0])                      # along the route: compact objects
    objs, verts, idx, key = [], [], [], {}
    for _, tri in tris:
        ks = [tuple(np.round(p, 3)) for p in tri]
        new = [k for k in dict.fromkeys(ks) if k not in key]
        if len(idx) >= 255 or len(verts) + len(new) > 256:
            objs.append(addramp.mesh_object(verts, idx, base))
            verts, idx, key = [], [], {}
            new = list(dict.fromkeys(ks))
        for k in new:
            key[k] = len(verts)
            verts.append(k)
        idx.append(tuple(key[k] for k in ks))
    if idx:
        objs.append(addramp.mesh_object(verts, idx, base))
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
