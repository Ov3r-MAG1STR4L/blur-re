"""Diagnostic après le 1er essai en jeu de Dubaï (2026-11-03) : lignes blanches, collision, performances, visibilité.
Lecture seule (aucun fichier écrit).  python nfs_diag/pc_diag.py STM WORLD SPOTS LEVELPHYSICS_ORIGINAL"""
import collections
import json
import math
import os
import struct
import sys

import numpy as np

STM, WORLD, SPOTS, ORIG = sys.argv[1:5]
del sys.argv[1:]
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import make_nfs_map as M  # noqa: E402
import nfs_atlas as A  # noqa: E402
import stm2obj  # noqa: E402
import bmb_levelphysics as lp  # noqa: E402
from scipy.spatial import cKDTree  # noqa: E402

M.STM = STM
stem = os.path.splitext(os.path.basename(STM))[0]
M.HP_GROUND = json.load(open(os.path.join(os.path.dirname(WORLD), "web_cache", stem, "index.json")))["ground"]
d = open(STM, "rb").read()
pts = np.array([(p["x"], p["z"]) for p in json.load(open(WORLD))["locations"][0]["maps"][0]["points"]])
dense = np.concatenate([np.linspace(a, b, 20, endpoint=False) for a, b in zip(pts, np.roll(pts, -1, 0))])
tree = cKDTree(dense)
up = 1.0 - M.HP_GROUND

# --- tous les triangles LOD0 avec matériau, texture, uv, distance au tracé
T = []          # (pos 3x3, uv 3x2, tex, glass, see, mesh)
for t, n, b in stm2obj.entries(d):
    if t != 6:
        continue
    try:
        pos, uvs, _ = stm2obj.mesh(b)
        if not pos:
            continue
        for m in {s[0] for s in stm2obj.submeshes(b)}:
            tex = stm2obj.material_name(d, m) or "couleur"
            g, s = M.has_envmap(d, m), M.see_through(d, m)
            for f in stm2obj.mesh(b, m)[2]:
                T.append((np.array([pos[a] for a, _ in f]), np.array([uvs[c] for _, c in f]), tex, g, s, n))
    except (struct.error, ValueError, IndexError):
        continue
P = np.array([x[0] for x in T])
UV = np.array([x[1] for x in T])
cen = P.mean(1)
dc = tree.query(cen[:, [0, 2]])[0]
dmin = tree.query(P.reshape(-1, 3)[:, [0, 2]])[0].reshape(-1, 3).min(1)
nrm = np.cross(P[:, 1] - P[:, 0], P[:, 2] - P[:, 0])
area = np.linalg.norm(nrm, axis=1) / 2
nrm /= np.linalg.norm(nrm, axis=1, keepdims=True) + 1e-12
ny = np.abs(nrm[:, 1])
see = np.array([x[4] and not x[3] for x in T])
road = np.array([x[5].lower().startswith("road") for x in T])
print("triangles LOD0", len(T))

# ===== 1. lignes blanches
dec = (dmin <= A.RADIUS) & ~see
span = UV[dec].max(1) - UV[dec].min(1)
fl = np.floor(UV[dec].min(1))
crosses = (np.ceil(UV[dec].max(1)) - fl > 1).any(1)
print("\n[1] décor gardé", dec.sum(), "; triangles coupés par tile_split (uv qui passe un entier)", crosses.sum(),
      "(%.0f %%)" % (100 * crosses.mean()), "; étendue uv max médiane %.2f" % np.median(span.max(1)))
for k in range(5):
    print("    mip %d : case %d px, marge INSET %.2f px" % (k, A.CELL >> k, A.CELL * A.INSET / (1 << k)))
# arêtes communes à 2 triangles gardés dont les coupes uv diffèrent -> sommet en T (fente)
edges = collections.defaultdict(list)
idx = np.where(dec)[0]
for i in idx:
    for a, b in ((0, 1), (1, 2), (2, 0)):
        ka, kb = tuple(np.round(P[i, a], 3)), tuple(np.round(P[i, b], 3))
        key = (ka, kb) if ka < kb else (kb, ka)
        ua, ub = (UV[i, a], UV[i, b]) if ka < kb else (UV[i, b], UV[i, a])
        edges[key].append((i, ua, ub))


def cuts(ua, ub):
    out = set()
    for ax in (0, 1):
        lo, hi = sorted((ua[ax], ub[ax]))
        for kk in range(math.floor(lo) + 1, math.ceil(hi)):
            if ub[ax] != ua[ax]:
                out.add(round((kk - ua[ax]) / (ub[ax] - ua[ax]), 3))
    return out


shared = tj = 0
tj_tex = collections.Counter()
for key, L in edges.items():
    if len(L) != 2:
        continue
    shared += 1
    (i, a1, b1), (j, a2, b2) = L
    if cuts(a1, b1) != cuts(a2, b2):
        tj += 1
        tj_tex[tuple(sorted((T[i][2][:28], T[j][2][:28])))] += 1
print("    arêtes partagées", shared, "; dont coupées différemment des deux côtés (fente en T)", tj,
      "(%.1f %%)" % (100 * tj / max(1, shared)))
for (a, b), c in tj_tex.most_common(10):
    print("      ", c, a, "|", b)

# ===== 2. collision
col = (dc < 40) & ~np.array([x[4] for x in T])
kind = np.where(ny > 0.7, "sol", np.where(ny < 0.3, "mur", "pente"))
print("\n[2] collision (règle actuelle : centre < 40 m, see_through exclu) :", col.sum(), "triangles",
      dict(collections.Counter(kind[col])))
# sens après la règle d'addramp (normale forcée vers le haut) : un mur regarde-t-il le tracé ?
w = col & (kind == "mur")
n2 = nrm.copy()
n2[n2[:, 1] < 0] *= -1
k = tree.query(cen[:, [0, 2]])[1]
to_track = dense[k] - cen[:, [0, 2]]
facing = (n2[:, [0, 2]] * to_track).sum(1) > 0
print("    murs gardés", w.sum(), ": face vers le tracé", (w & facing).sum(), "; dos au tracé", (w & ~facing).sum())
print("    murs presque verticaux (|ny| < 0,02 : sens décidé par l'arrondi)", (w & (ny < 0.02)).sum())
miss = (kind == "mur") & (dmin < 15) & (dc >= 40) & ~np.array([x[4] for x in T])
print("    murs à moins de 15 m du tracé mais centre >= 40 m (pas de collision) :", miss.sum(),
      "aire %.0f m2" % area[miss].sum())
nsee = (dmin < 15) & np.array([x[4] for x in T]) & ~road
print("    triangles see_through à moins de 15 m (affichés si vitre, jamais solides) :", nsee.sum(),
      "dont vitres", (nsee & np.array([x[3] for x in T])).sum())
small = col & (area < 0.05)
print("    petits triangles (< 0,05 m2) dans la collision :", small.sum(), "; aire médiane %.2f m2" % np.median(area[col]))
nm = collections.Counter(x[5].split("_")[0][:6].lower() for x, c in zip(T, col) if c)
print("    familles de maillages dans la collision :", nm.most_common(8))
# collision d'origine (1er objet du Main) : drapeaux de surface par orientation
o = lp.read_mesh(ORIG)
V, TT = o["verts"], lp.triangles(o)
on = np.cross(V[TT[:, 1]] - V[TT[:, 0]], V[TT[:, 2]] - V[TT[:, 0]])
on /= np.linalg.norm(on, axis=1, keepdims=True) + 1e-12
ok = np.where(np.abs(on[:, 1]) > 0.7, "sol", np.where(np.abs(on[:, 1]) < 0.3, "mur", "pente"))
sf = collections.defaultdict(collections.Counter)
for kk, (s, f) in zip(ok, o["surfaces"]):
    sf[kk][(s, f)] += 1
print("    original", os.path.basename(os.path.dirname(ORIG)), "1er objet :", len(TT), "triangles",
      dict(collections.Counter(ok)), "; nœuds", len(o["nodes"]))
for kk, c in sf.items():
    print("      ", kk, "(surface, drapeaux) les plus fréquents :", c.most_common(4))

# ===== 3. / 4. performances et visibilité
spots = np.array(json.load(open(SPOTS)))
sample = dense[::40]
dd = np.linalg.norm(sample[:, None, :] - spots[None, :, [0, 2]], axis=2)
inr = (dd < M.DECOR_DRAW).sum(1)
print("\n[3] acteurs NFS", len(spots), "; à moins de DrawDistance (%d m) d'un point du tracé : min %d, médiane %d, max %d"
      % (M.DECOR_DRAW, inr.min(), np.median(inr), inr.max()))
never = (dd.min(0) > M.DECOR_DRAW).sum()
print("    acteurs jamais à portée depuis le tracé :", never)
far = ~see & (dmin > A.RADIUS)
print("\n[4] décor non exporté (> %d m du tracé) : %d triangles (%.0f %%)" % (A.RADIUS, far.sum(), 100 * far.mean()))
hb = far & (P[:, :, 1].max(1) + up > 30)
print("    dont haut (> 30 m au-dessus du sol Blur, visible de loin) :", hb.sum())
