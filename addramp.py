#!/usr/bin/env python3
"""Add an invisible drivable ramp to a level's collision (Level.levelphysics), for a reversed route that meets a
step it can only go down in the original direction (New York Dumbo 3: the dock platform, 2026-10-22).

The ramp is a small ROAD-type mesh object (a deck of 2 triangles, as Blur Map Builder's decks: write_flat.py, MIT,
by MDPRO) INSERTED AS THE FIRST OBJECT of the "Main" physics stream ("Head", u32 version, objects... until
0x0FFFFFFF): the level's own objects (boxes, meshes... in a level-specific order, not all decodable) are left
untouched. Object template (type-0 mesh header, surface table, root node box, group header, triangle flags and the
84-byte trailer) taken from LA River, whose first object is a road mesh.

usage: addramp.py LEVELPHYSICS_IN OUT  x0 y0 z0  x1 y1 z1  width
  (bottom centre, top centre in game coordinates as recorded by trackrec.py, width in m)
"""
import os, struct, sys
import config
import numpy as np
import bmb_levelphysics as lp

TEMPLATE = os.path.join(config.BLUR_TEST, "levels", "usa_la_river", "Level.levelphysics")
TRAILER = 84


def pack_normal(n):
    """triangle u32 = unit face normal: x 11-bit*1023, y 11-bit*1023 (<< 11), z 10-bit*511 (<< 22) (MDPRO)"""
    n = np.asarray(n, float)
    n = n / (np.linalg.norm(n) + 1e-12)
    return (int(round(n[0] * 1023)) & 0x7FF) | (int(round(n[1] * 1023)) & 0x7FF) << 11 | \
        (int(round(n[2] * 511)) & 0x3FF) << 22


def ramp_object(bottom, top, width, steps=12, kicker=False):
    """bytes of a type-0 road mesh object: a strip from bottom to top (centre points), `width` m wide, in `steps`
    bands following a smoothstep height profile (flat at both ends: no kicker that throws the AI in the air)."""
    t = open(TEMPLATE, "rb").read()
    m = lp.read_mesh(TEMPLATE)
    body, _ = lp.find_chunk(t, "Main")
    start = body + 4 + 4 + 4 + 8 * 4 + 12 + 4 + (4 if m["version"] > 6 else 0)   # mesh counts of the 1st object
    header = t[body + 8:start]                                                       # u32 type 0 + base fields
    nv = len(m["verts"])
    table = t[start + 16 + 24 + nv * 12:start + 16 + 24 + nv * 12 + 4 * len(m["table"])]
    p = m["stream_pos"]
    end = p + 4 + 12 * struct.unpack_from("<I", t, p)[0]
    trailer = t[end:end + TRAILER]
    V, T = m["verts"], lp.triangles(m)
    nrm = np.cross(V[T[:, 1]] - V[T[:, 0]], V[T[:, 2]] - V[T[:, 0]])
    nrm /= np.linalg.norm(nrm, axis=1, keepdims=True) + 1e-12
    floor = int(np.argmax(np.abs(nrm[:, 1])))
    sign = 1 if nrm[floor, 1] > 0 else -1                 # winding of the template's floor
    flags = m["surfaces"][floor][1]
    g = m["groups"][0][1]
    root = m["nodes"][0]

    b, e = np.array(bottom, float), np.array(top, float)
    f = e - b
    side = np.array([-f[2], 0.0, f[0]])
    side /= np.linalg.norm(side)
    h = side * width / 2
    rows = []
    for k in range(steps + 1):
        u = k / steps
        p = b + f * u
        # smoothstep: slope 0 at the bottom and at the top; kicker: u^2, slope 0 at the bottom, steepest at the top (a jump)
        p[1] = b[1] + f[1] * (u * u if kicker else u * u * (3 - 2 * u))
        rows += [p - h, p + h]
    verts = np.array(rows, np.float32)
    tris = []
    for k in range(steps):
        l0, r0, l1, r1 = 2 * k, 2 * k + 1, 2 * k + 2, 2 * k + 3
        for a, bb, c in ((l0, r0, r1), (l0, r1, l1)):
            cr = np.cross(verts[bb] - verts[a], verts[c] - verts[a])
            tris.append((a, bb, c) if cr[1] * sign > 0 else (a, c, bb))
    return mesh_object(verts, tris)


def mesh_object(verts, tris, template=TEMPLATE):
    """bytes of a type-0 road mesh object (template: the first object of a levelphysics, LA River by default; its
    surface table is copied whole: a small one keeps the object small) for verts [(x, y, z)] (<= 256) and
    triangles [(a, b, c)] (<= 255), wound so that cross(b - a, c - a) points up like the template's floor"""
    t = open(template, "rb").read()
    m = lp.read_mesh(template)
    body, _ = lp.find_chunk(t, "Main")
    start = body + 4 + 4 + 4 + 8 * 4 + 12 + 4 + (4 if m["version"] > 6 else 0)
    header = t[body + 8:start]
    nv = len(m["verts"])
    table = t[start + 16 + 24 + nv * 12:start + 16 + 24 + nv * 12 + 4 * len(m["table"])]
    p = m["stream_pos"]
    end = p + 4 + 12 * struct.unpack_from("<I", t, p)[0]
    trailer = t[end:end + TRAILER]
    V, T = m["verts"], lp.triangles(m)
    nrm = np.cross(V[T[:, 1]] - V[T[:, 0]], V[T[:, 2]] - V[T[:, 0]])
    nrm /= np.linalg.norm(nrm, axis=1, keepdims=True) + 1e-12
    floor = int(np.argmax(np.abs(nrm[:, 1])))
    sign = 1 if nrm[floor, 1] > 0 else -1
    flags = m["surfaces"][floor][1]
    g = m["groups"][0][1]
    root = m["nodes"][0]
    verts = np.asarray(verts, np.float32)
    assert len(tris) <= 255 and len(verts) <= 256
    lo, hi = verts.min(0), verts.max(0)
    out = bytearray(header)
    out += struct.pack("<4I", len(verts), len(m["table"]), 16 + 12 * len(tris), 1)
    out += struct.pack("<6f", lo[0] - 1, lo[1] - 2.0, lo[2] - 1, hi[0] + 1, hi[1] + 20.0, hi[2] + 1)
    out += verts.tobytes()
    out += table
    out += lp.NODE.pack(*root[:6], len(tris), 0, 0, len(verts))
    out += lp.GROUP.pack(g[0], g[1], g[2], g[3], len(tris))
    for a, bb, c in tris:
        n = np.cross(verts[bb] - verts[a], verts[c] - verts[a])
        if n[1] * sign < 0:
            bb, c = c, bb
            n = -n
        out += lp.TRI.pack(a, bb, c, pack_normal(n * sign), flags)
    out += struct.pack("<I", 0)
    out += trailer
    return bytes(out)


def wall_object(points, thick=0.3):
    """bytes of an invisible wall: a closed box strip (both faces, top and ends) along `points` [(x, bottom y, top y,
    z)] in game coordinates, `thick` m thick (both faces exist, so the winding of vertical triangles does not matter)"""
    v, t = [], []
    for i, (x, yb, yt, z) in enumerate(points):
        a, b = points[max(i - 1, 0)], points[min(i + 1, len(points) - 1)]
        dx, dz = b[0] - a[0], b[3] - a[3]
        n = (dx * dx + dz * dz) ** 0.5
        ox, oz = -dz / n * thick / 2, dx / n * thick / 2
        v += [(x - ox, yb, z - oz), (x - ox, yt, z - oz), (x + ox, yt, z + oz), (x + ox, yb, z + oz)]
    for i in range(len(points) - 1):
        for k in range(4):                                  # 4 long faces (side, top, side, bottom)
            a, b = 4 * i + k, 4 * i + (k + 1) % 4
            t += [(a, b, b + 4), (a, b + 4, a + 4)]
    last = 4 * (len(points) - 1)
    t += [(0, 1, 2), (0, 2, 3), (last, last + 2, last + 1), (last, last + 3, last + 2)]
    return mesh_object(v, t)


def add_ramp(src, bottom, top, width, kicker=False):
    return insert_objects(open(src, "rb").read(), ramp_object(bottom, top, width, kicker=kicker))


def insert_objects(d, obj):
    """`obj` (bytes of one or more mesh objects) inserted first in the Main stream of levelphysics bytes `d`"""
    body, _ = lp.find_chunk(d, "Main")
    assert d[body:body + 4] == b"Head"
    at = body + 8                                          # after "Head" + version: our object comes first
    new = bytearray(d[:at]) + obj + d[at:]
    main_hdr = body - 16
    struct.pack_into("<I", new, main_hdr + 8, struct.unpack_from("<I", d, main_hdr + 8)[0] + len(obj))
    struct.pack_into("<I", new, 0x0C, struct.unpack_from("<I", d, 0x0C)[0] + len(obj))
    return bytes(new)


if __name__ == "__main__":
    a = sys.argv
    out = add_ramp(a[1], [float(v) for v in a[3:6]], [float(v) for v in a[6:9]], float(a[9]))
    open(a[2], "wb").write(out)
    m = lp.read_mesh(a[2])                                  # our object is first: readable as a mesh
    g = lp.Ground(a[2])
    print("écrit", a[2], ": 1er objet", len(m["verts"]), "sommets,", len(m["tris_raw"]), "triangles")
    for k in (0.0, 0.25, 0.5, 0.75, 1.0):
        x = float(a[3]) + (float(a[6]) - float(a[3])) * k
        z = float(a[5]) + (float(a[8]) - float(a[5])) * k
        print("  sol de la rampe à %.0f %% : x %.1f z %.1f -> y %s" % (k * 100, x, z, g.heights(x, z)))
