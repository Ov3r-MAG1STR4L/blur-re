"""Projet J : toute la carte HP (route + décor, sols et murs, toutes textures) en modèles « atlas » par zone.

Un .model Blur généré n'a qu'une texture : chaque modèle reçoit un atlas 4 x 4 (1024 x 1024) des textures de sa
zone. Les UV HP se répètent (> 1) : chaque triangle est découpé sur les lignes entières des UV pour qu'un morceau
tombe dans une seule répétition, puis ramené dans sa case. Tous les modèles ont la même taille (sommets, index,
texture : obligatoire, voir CONNAISSANCES.md). Les 12 emplacements fixes de Map Builder (11 morceaux de route +
arche) prennent les 12 premiers modèles, les emplacements « tower_nfs » le reste, acteur au centre de la zone.

python nfs_atlas.py        (reconstruit tout : tracé, Map Builder, fichiers en clair, collision, modèles)
"""
import collections
import json
import math
import os
import shutil
import struct
import subprocess
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import make_nfs_map as M  # noqa: E402
import stm2obj  # noqa: E402

ZONE = 200.0           # côté des zones (m)
GRID = 8               # atlas 8 x 8 cases (64 textures par modèle)
CELL = 128             # px par case (atlas 1024 x 1024)
VERTS = 52000          # sommets max par modèle (x 1,25 de marge <= 65 535 : index u16)
RADIUS = 300.0         # décor gardé jusqu'à cette distance du tracé
INSET = 0.01           # marge dans chaque case (débordement des mips)
MAX_MODELS = 130       # au plus (la liste de 144 acteurs décide, voir road_layout)
GLOW = 110            # lumière propre des modèles (le niveau Map Builder ne les éclaire pas)
GRID_GAP = 25.0        # 1re rangée de la grille de départ à 25 m derrière la ligne (8 avant)


def _clip(poly, axis, k, above):
    """Sutherland-Hodgman : partie de poly [(position, (u, v))] avec uv[axis] >= k (above) ou <= k"""
    out = []
    for a, b in zip(poly, poly[1:] + poly[:1]):
        ia = a[1][axis] >= k if above else a[1][axis] <= k
        ib = b[1][axis] >= k if above else b[1][axis] <= k
        if ia:
            out.append(a)
        if ia != ib:
            t = (k - a[1][axis]) / (b[1][axis] - a[1][axis])
            out.append((tuple(p + (q - p) * t for p, q in zip(a[0], b[0])),
                        tuple(p + (q - p) * t for p, q in zip(a[1], b[1]))))
    return out


def tile_split(ps, us):
    """triangle -> [(positions, uv locaux 0..1)] découpés sur les lignes entières des UV"""
    poly = list(zip(ps, us))
    u0, u1 = min(u for u, _ in us), max(u for u, _ in us)
    v0, v1 = min(v for _, v in us), max(v for _, v in us)
    out = []
    for i in range(math.floor(u0), max(math.floor(u0) + 1, math.ceil(u1))):
        pu = _clip(_clip(poly, 0, i, True), 0, i + 1, False)
        if len(pu) < 3:
            continue
        for j in range(math.floor(v0), max(math.floor(v0) + 1, math.ceil(v1))):
            pv = _clip(_clip(pu, 1, j, True), 1, j + 1, False)
            for k in range(1, len(pv) - 1):
                tri = (pv[0], pv[k], pv[k + 1])
                out.append(([q[0] for q in tri], [(q[1][0] - i, q[1][1] - j) for q in tri]))
    return out


def jobs(world_json):
    """[(distance au tracé, textures de l'atlas, [(positions, uv atlas, v vers le bas)])] par zone"""
    from scipy.spatial import cKDTree
    pts = np.array([(p["x"], p["z"]) for p in json.load(open(world_json))["locations"][0]["maps"][0]["points"]])
    dense = np.concatenate([np.linspace(a, b, 20, endpoint=False) for a, b in zip(pts, np.roll(pts, -1, 0))])
    tree = cKDTree(dense)
    d = open(M.STM, "rb").read()
    zones = collections.defaultdict(lambda: collections.defaultdict(list))
    zdist = collections.defaultdict(lambda: 9e9)
    for t, n, b in stm2obj.entries(d):
        if t != 6:
            continue
        try:
            pos, uvs, _ = stm2obj.mesh(b)
            if not pos:
                continue
            dist = tree.query(np.array(pos)[:, [0, 2]])[0]
            for m in {s[0] for s in stm2obj.submeshes(b)}:
                if M.see_through(d, m):                # nature (buissons, palmiers, haies) : ni affichée ni solide
                    continue
                tex = stm2obj.material_name(d, m) or "couleur:%02x%02x%02x" % stm2obj.material_color(d, m)
                for f in stm2obj.mesh(b, m)[2]:
                    ids = [a for a, _ in f]
                    dm = float(dist[ids].min())
                    if dm > RADIUS:
                        continue
                    c = np.array([pos[a] for a in ids]).mean(0)
                    z = (int(c[0] // ZONE), int(c[2] // ZONE))
                    zdist[z] = min(zdist[z], dm)
                    zones[z][tex].append(([pos[a] for a in ids], [(uvs[cc][0], 1 - uvs[cc][1]) for _, cc in f]))
        except (struct.error, ValueError, IndexError):
            continue
    out = []
    for z, by_tex in zones.items():
        cur, keys, texs = [], set(), []
        for tex, tris in sorted(by_tex.items(), key=lambda kv: -len(kv[1])):
            for ps, us in (pc for ps0, us0 in tris for pc in tile_split(ps0, us0)):
                k = {(tuple(round(c, 3) for c in p), (round(u, 4), round(v, 4))) for p, (u, v) in zip(ps, us)}
                if len(keys | k) > VERTS or (tex not in texs and len(texs) == GRID * GRID):
                    out.append((zdist[z], texs, cur))
                    cur, keys, texs = [], set(), []
                if tex not in texs:
                    texs.append(tex)
                cell = texs.index(tex)
                cx, cy = cell % GRID, cell // GRID
                cur.append((ps, [((cx + INSET + u * (1 - 2 * INSET)) / GRID, (cy + INSET + v * (1 - 2 * INSET)) / GRID)
                                 for u, v in us]))
                keys |= k
        if cur:
            out.append((zdist[z], texs, cur))
    out.sort(key=lambda j: j[0])
    print(len(zones), "zones ->", len(out), "modèles possibles,", min(len(out), MAX_MODELS), "gardés")
    return out[:MAX_MODELS]


def atlas(texs):
    from PIL import Image
    d = open(M.STM, "rb").read()
    img = Image.new("RGBA", (GRID * CELL, GRID * CELL), (128, 128, 128, 255))   # alpha gardé (feuillages, grillages)
    for k, tex in enumerate(texs):
        if tex.startswith("couleur:"):
            cell = Image.new("RGBA", (CELL, CELL), tuple(int(tex[8 + 2 * i:10 + 2 * i], 16) for i in range(3)))
        else:
            cell = stm2obj.texture_image(d, tex).convert("RGBA").resize((CELL, CELL))
        img.paste(cell, ((k % GRID) * CELL, (k // GRID) * CELL))
    return img


def centre(tris):
    P = np.array([p for ps, _ in tris for p in ps])
    c = (P.min(0) + P.max(0)) / 2
    return [round(float(c[0]), 2), round(float(c[1] + 1.0 - M.HP_GROUND), 2), round(float(c[2]), 2)]


def rebuild(auto_pickups=True, log=print):
    """auto_pickups=False : garder la largeur / les bonus / le départ déjà écrits dans world.json (nfs_studio)"""
    M.set_heights(M.WORLD)
    if auto_pickups:
        M.set_track(M.WORLD)
    shutil.copyfile(M.WORLD, os.path.join(M.BMB, "Blur Map Builder", "maps", "world.json"))
    J = jobs(M.WORLD)
    spots = os.path.join(M.OUT, "..", "nfs_spots.json")
    json.dump([centre(t) for _, _, t in J], open(spots, "w"))
    env = dict(os.environ, BMB_GAME=M.BMB, BMB_INSTALLED="1", NFS_COUNT=str(len(J)),
               NFS_SPOTS=os.path.abspath(spots), NFS_DRAW=str(M.DECOR_DRAW), NFS_NO_WALLS="1", NFS_FLOOR_Y="-5",
               NFS_GRID_GAP=str(GRID_GAP))
    r = subprocess.run([sys.executable, "build.py"], cwd=os.path.join(M.BMB, "map_builder", "flat_earth"), env=env,
                       capture_output=True, text=True)
    for line in r.stdout.splitlines():
        if line.startswith("NFS"):
            print(line)
    if r.returncode:
        raise RuntimeError("Map Builder a échoué : " + (r.stderr or r.stdout)[-2000:])
    M.main()
    M.road_collision(os.path.join(M.BMB, "levels", "flat_earth", "level.levelphysics"),
                     os.path.join(M.OUT, "levels", "flat_earth", "level.levelphysics"), M.WORLD)
    ap = os.path.join(M.OUT, "gamedata", "levels", "flat_earth", "actorpack.xt")
    flat = os.path.join(M.OUT, "models", "objects", "flat_earth")
    # même taille pour tous (obligatoire, crash 0x6DB2EB sinon) = celle du plus gros modèle réel, pas VERTS : avec 65 000
    # sommets partout, 150 modèles faisaient 391 Mo et le jeu ramait. Marge 1,25 : arrondis différents du comptage.
    most = max(len({(tuple(np.round(p, 3)), tuple(np.round(u, 4))) for ps, us in t for p, u in zip(ps, us)}) for _, _, t in J)
    pad = (min(int(VERTS * 1.25), int(most * 1.25) + 3), 6 * max(len(t) for _, _, t in J))   # 6 index / triangle (faces doublées)
    # la route et l'arche de Map Builder (leur nombre dépend du découpage de sa route) : cachées, même taille
    hidden = [(u, "road_21_%02d.model" % k) for k, u in enumerate(M.road_slots(ap))] + [(0xF1E20005, "arch_lap.model")]
    tiny = [([(0, -60, 0), (0.01, -60, 0), (0, -60, 0.01)], [(0, 0), (0, 0), (0, 0)])]
    for k, (slot, fname) in enumerate(hidden):
        M.write_model(tiny, "couleur:000000", M.slot_matrix(ap, slot), os.path.join(flat, fname), 0,
                      salt=0x4E465400 + k, pad=pad, image=atlas([]))
    written = 0
    for k, (_, texs, tris) in enumerate(J):
        try:
            mx = M.slot_matrix(ap, M.NFS_UID + 2 * k + 1)
        except AssertionError:                         # pas d'acteur : liste pleine (zone la plus lointaine)
            continue
        # write_model attend des uv « stm » (u, 1 - v) et écrit (u, v) : on lui donne (u, 1 - v atlas)
        M.write_model([(ps, [(u, 1 - v) for u, v in us]) for ps, us in tris], "atlas", mx,
                      os.path.join(flat, "nfs_%03d.model" % k), GLOW, salt=0x4E465500 + k, pad=pad, image=atlas(texs))
        written += 1
    print(written, "modèles de décor sur", len(J), "; route Map Builder cachée :", len(hidden), "emplacements")


if __name__ == "__main__":
    pcs = tile_split([(0, 0, 0), (10, 0, 0), (0, 0, 10)], [(0.5, 0.5), (2.5, 0.5), (0.5, 1.7)])
    assert pcs and all(-1e-9 <= c <= 1 + 1e-9 for _, us in pcs for uv in us for c in uv), pcs
    rebuild()
