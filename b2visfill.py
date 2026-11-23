#!/usr/bin/env python3
"""Collision tirée des meshes VISIBLES de Blur2DubaiTest là où les données Unity n'ont pas de collider.

Cas d'origine (2026-11-23, Dubai Island) : la route haute 17f s'arrête vers (−49 ; 1012), la route au sol visible
(draws_d0036, y ≈ 10) et la structure voisine (draws_d0084…) n'ont aucun collider : la voiture tombe.
Dans chaque zone ZONES (axes du jeu, min / max x y z) : triangles des MeshFilter visibles (pas les *_collision),
tournés vers le haut (|n.y| > NY), d'aire <= MAX_AREA (exclut les grands plans de décor), sans collider à moins de
GAP m de leur centre -> écrits face vers le haut dans blur2_aid/dubai/complements_collision.npz.
b2collision.colliders() les ajoute sous le nom « complement_<mesh>_17f_collision » (traités comme route 17f par
toute la chaîne : build, b2recale, b2blender). Ne construit ni n'installe.

usage: b2visfill.py            (réécrit le .npz ; le supprimer annule les compléments)
"""
import os, sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import b2collision  # noqa: E402
import config  # noqa: E402

UNITY = os.path.join(config.JEUX, "Blur2DubaiTest", "Blur2DubaiTest_Data")
OUT = b2collision.COMPLEMENTS
ZONES = {"dubai_island_route_haute": ((-200, 0, 930), (-20, 35, 1060))}
NY, MAX_AREA, GAP = 0.6, 1500.0, 2.0


def main():
    import UnityPy
    from UnityPy.helpers.MeshHelper import MeshHandler
    from scipy.spatial import cKDTree
    cols = b2collision.colliders(UNITY, complements=False)
    kd = cKDTree(np.concatenate([v[t].mean(1) for v, t in cols.values()]))
    env = UnityPy.load(UNITY)
    out, names = {}, []
    for o in env.objects:
        if o.type.name != "MeshFilter":
            continue
        try:
            mf = o.read()
            go = mf.m_GameObject.read()
        except Exception:
            continue
        if "collision" in go.m_Name or go.m_Name == "default":
            continue
        tr = [p.read() for p in (x.component if hasattr(x, "component") else x for x in go.m_Component)
              if p.type.name == "Transform"][0]
        h = MeshHandler(mf.m_Mesh.read())
        h.process()
        v = np.array(h.m_Vertices, float).reshape(-1, 3)
        t = np.array(h.get_triangles(), int).reshape(-1, 3)
        if not len(t):
            continue
        m = b2collision.world_matrix(tr)
        w = (v @ m[:3, :3].T + m[:3, 3]) * [-1, 1, -1]
        T = w[t]
        c = T.mean(1)
        n = np.cross(T[:, 1] - T[:, 0], T[:, 2] - T[:, 0])
        a = np.linalg.norm(n, axis=1) / 2
        ny = n[:, 1] / (2 * a + 1e-9)
        inz = np.zeros(len(t), bool)
        for lo, hi in ZONES.values():
            inz |= ((c >= lo) & (c <= hi)).all(1)
        sel = inz & (np.abs(ny) > NY) & (a <= MAX_AREA) & (a > 0.01)
        if not sel.any():
            continue
        sel &= kd.query(c)[0] > GAP
        if not sel.any():
            continue
        tt = t[sel].copy()
        down = ny[sel] < 0
        tt[down] = tt[down][:, [0, 2, 1]]                  # face vers le haut (mesh visible parfois retourné)
        k = len(names)
        used = np.unique(tt)
        remap = np.full(len(w), -1)
        remap[used] = np.arange(len(used))
        out["v%d" % k], out["t%d" % k] = w[used].astype(np.float32), remap[tt].astype(np.int32)
        names.append(go.m_Name)
        cs = c[sel]
        print("%-14s %4d triangles (%6.0f m2)  x %.0f..%.0f  y %.1f..%.1f  z %.0f..%.0f" % (
            go.m_Name, sel.sum(), a[sel].sum(), cs[:, 0].min(), cs[:, 0].max(), cs[:, 1].min(), cs[:, 1].max(),
            cs[:, 2].min(), cs[:, 2].max()))
    np.savez_compressed(OUT, names=np.array(names), **out)
    print("%d morceaux -> %s" % (len(names), OUT))


if __name__ == "__main__":
    main()
