"""Diagnostic P1 phase B (lecture seule) : ce que make_nfs_map.see_through retire du décor exporté, par matériau,
et simulation de nfs_atlas.jobs avec / sans les matériaux à reflet (envmap). Rien n'est écrit.
usage : python pb_see_through.py STM WORLD_JSON [simuler]"""
import collections
import os
import sys

import numpy as np

stm, world = sys.argv[1], sys.argv[2]
sim = len(sys.argv) > 3
del sys.argv[1:]
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import make_nfs_map as M  # noqa: E402
import nfs_atlas as A  # noqa: E402
import stm2obj as S  # noqa: E402

d = open(stm, "rb").read()
mats = S.materials(d)
env = {m for m, (_, used) in mats.items() if any(u.lower() == "envmap.tex" for u in used)}
KIND = (("grillage", ("fence", "barrier", "bollard", "pylon", "guard", "armco", "rail")),
        ("grue / échafaudage", ("crane", "scaffold", "beam", "const", "tower")),
        ("végétation", ("tree", "palm", "bush", "grass", "org_", "shrub", "scrub", "hedge", "plant", "leaf")))


def kind(m, tex):
    if m in env:
        return "vitre à reflet"
    t = (tex or "").lower()
    return next((k for k, keys in KIND if any(x in t for x in keys)), "autre")


tri = collections.Counter()
for t, n, b in S.entries(d):
    if t == 6:
        for m in {s[0] for s in S.submeshes(b)}:
            tri[m] += len(S.mesh(b, m)[2])
rows = []
for m, k in tri.items():
    if M.see_through(d, m):
        tex = S.material_name(d, m)
        rows.append((kind(m, tex), k, m, tex, round(M._SEE[tex], 2)))
print(os.path.basename(stm), ": triangles", sum(tri.values()), "; retirés par see_through", sum(r[1] for r in rows))
by = collections.Counter()
for r in rows:
    by[r[0]] += r[1]
print("  par catégorie :", dict(by))
# textures partagées entre matériaux à reflet et sans reflet, et ce que see_through en fait
share = collections.defaultdict(set)
for m in tri:
    share[S.material_name(d, m)].add(m in env)
print("  textures mixtes (reflet + sans reflet) :", [(t, round(M._SEE.get(t, 0), 2), M.see_through(d, next(m for m in tri if S.material_name(d, m) == t)))
                                                     for t, v in share.items() if len(v) == 2])
for r in sorted(rows, key=lambda r: -r[1])[:30]:
    print("   ", r)

if sim:
    M.STM = stm
    base = M.see_through

    def run(label):
        J = A.jobs(world)
        nv = [len({(tuple(np.round(p, 3)), tuple(np.round(u, 4))) for ps, us in t for p, u in zip(ps, us)}) for _, _, t in J]
        nt = [len(t) for _, _, t in J]
        pad_v = min(int(A.VERTS * 1.25), int(max(nv) * 1.25) + 3)
        print("  [%s] modèles %d (+12 emplacements fixes = %d acteurs sur 144) ; triangles %d ; sommets max %d ; "
              "taille commune %d sommets / %d index ; sommets x modèles %d"
              % (label, len(J), len(J) + 12, sum(nt), max(nv), pad_v, 6 * max(nt), pad_v * len(J)))

    run("actuel")
    M.see_through = lambda dd, m, share=0.5: base(dd, m, share) and m not in env
    run("vitres à reflet gardées")
