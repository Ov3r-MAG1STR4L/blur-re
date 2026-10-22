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
import struct, sys
import numpy as np
import bmb_levelphysics as lp

TEMPLATE = r"C:\Users\sanqu\Jeux_WII\Blur_test\levels\usa_la_river\Level.levelphysics"
TRAILER = 84


def pack_normal(n):
    """triangle u32 = unit face normal: x 11-bit*1023, y 11-bit*1023 (<< 11), z 10-bit*511 (<< 22) (MDPRO)"""
    n = np.asarray(n, float)
    n = n / (np.linalg.norm(n) + 1e-12)
    return (int(round(n[0] * 1023)) & 0x7FF) | (int(round(n[1] * 1023)) & 0x7FF) << 11 | \
        (int(round(n[2] * 511)) & 0x3FF) << 22


def ramp_object(bottom, top, width):
    """bytes of a type-0 road mesh object: a flat strip from bottom to top (centre points), `width` m wide."""
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
    verts = np.array([b - h, b + h, e + h, e - h], np.float32)
    tris = []
    for a, bb, c in ((0, 1, 2), (0, 2, 3)):
        cr = np.cross(verts[bb] - verts[a], verts[c] - verts[a])
        tris.append((a, bb, c) if cr[1] * sign > 0 else (a, c, bb))
    lo, hi = verts.min(0), verts.max(0)
    out = bytearray(header)
    out += struct.pack("<4I", len(verts), len(m["table"]), 16 + 12 * len(tris), 1)
    out += struct.pack("<6f", lo[0] - 1, lo[1] - 2.0, lo[2] - 1, hi[0] + 1, hi[1] + 20.0, hi[2] + 1)
    out += verts.tobytes()
    out += table
    out += lp.NODE.pack(*root[:6], len(tris), 0, 0, len(verts))
    out += lp.GROUP.pack(g[0], g[1], g[2], g[3], len(tris))
    for a, bb, c in tris:
        n = np.cross(verts[bb] - verts[a], verts[c] - verts[a]) * sign
        out += lp.TRI.pack(a, bb, c, pack_normal(n), flags)
    out += struct.pack("<I", 0)
    out += trailer
    return bytes(out)


def add_ramp(src, bottom, top, width):
    d = open(src, "rb").read()
    body, _ = lp.find_chunk(d, "Main")
    assert d[body:body + 4] == b"Head"
    obj = ramp_object(bottom, top, width)
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
