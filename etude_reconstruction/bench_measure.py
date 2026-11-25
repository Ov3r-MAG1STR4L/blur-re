"""Écart géométrique entre l'original et une version simplifiée (pymeshlab, distance de Hausdorff échantillonnée).
python bench_measure.py original.obj simplifie.obj
original -> simplifié : formes perdues ; simplifié -> original : déformations ajoutées. En millimètres."""
import sys

import pymeshlab


def measure(hi, lo, n=200000):
    ms = pymeshlab.MeshSet()
    ms.load_new_mesh(hi); ms.load_new_mesh(lo)
    tris = ms.current_mesh().face_number()
    a = ms.get_hausdorff_distance(sampledmesh=0, targetmesh=1, samplenum=n, samplevert=False, sampleface=True)
    b = ms.get_hausdorff_distance(sampledmesh=1, targetmesh=0, samplenum=n, samplevert=False, sampleface=True)
    return tris, a, b


if __name__ == '__main__':
    tris, a, b = measure(sys.argv[1], sys.argv[2])
    mm = lambda d: f"moy {d['mean'] * 1000:5.1f}  rms {d['RMS'] * 1000:5.1f}  max {d['max'] * 1000:6.1f}"
    print(f'triangles {tris}')
    print(f'  formes perdues    (orig -> simp) : {mm(a)} mm')
    print(f'  déformations      (simp -> orig) : {mm(b)} mm')
