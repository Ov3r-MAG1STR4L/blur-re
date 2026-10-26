"""Projet J : récupère les fichiers produits par Blur Map Builder (dossier séparé bmb_game) en fichiers en clair.

Usage : python make_nfs_map.py [BMB_GAME] [SORTIE]
Map Builder doit avoir été construit avec, comme base (`base/unpacked/gamedata/xt`), les amax.bin /
multiplayer.bin / cityandroutenames.loc de Blur_test : ses ajouts se font alors PAR-DESSUS nos mods.
Ici : fichiers neufs ou changés de ses paks (sauf ui_frontend.bpr : sa vignette est posée dans NOTRE bpr
moddé avec blurbpr), plus le dossier de niveau levels/flat_earth.
"""
import os
import shutil
import struct
import sys

from blurpak import Pak

BMB = sys.argv[1] if len(sys.argv) > 1 else r"C:\Users\sanqu\Jeux_WII\bmb_game"
OUT = sys.argv[2] if len(sys.argv) > 2 else r"C:\Users\sanqu\Jeux_WII\blur_extracted\mods\nfs_dubai\files"
WORK = os.path.join(BMB, "Blur Map Builder", "work")


def main():
    n = 0
    for orig, built in (("gamedata.pak", "gamedata_track.pak"), ("root.pak", "root_track.pak")):
        a = {e.path.lower(): e for e in Pak(os.path.join(BMB, "cache", orig)).files}
        b = Pak(os.path.join(WORK, built))
        for e in b.files:
            x = a.get(e.path.lower())
            if x and (x.crc, x.usize) == (e.crc, e.usize):
                continue
            q = e.path.lower().replace("\\", "/").lstrip("/")
            if q.endswith("ui_frontend.bpr"):
                continue
            p = os.path.join(OUT, q)
            os.makedirs(os.path.dirname(p), exist_ok=True)
            open(p, "wb").write(b.read(e))
            n += 1
    lv = os.path.join(OUT, "levels", "flat_earth")
    os.makedirs(lv, exist_ok=True)
    for f in os.listdir(os.path.join(BMB, "levels", "flat_earth")):
        shutil.copyfile(os.path.join(BMB, "levels", "flat_earth", f), os.path.join(lv, f))
        n += 1
    print(n, "fichiers ->", OUT)
    add_thumbnail(r"C:\Users\sanqu\Jeux_WII\Blur_test\UI\data\ui_frontend.bpr",
                  os.path.join(OUT, "ui", "data", "ui_frontend.bpr"))


def add_thumbnail(test_bpr, out_bpr, route="Flat_Earth_1"):
    """vignette de Map Builder (entrée `route` de son ui_frontend.bpr) ajoutée à NOTRE bpr (celui de Blur_test)"""
    from blurbpr import Bpr
    p = Pak(os.path.join(WORK, "root_track.pak"))
    e = next(e for e in p.files if e.path.lower().endswith("ui_frontend.bpr"))
    mb = Bpr(data=p.read(e))
    rec, raw = mb.raw(route)
    ours = Bpr(test_bpr)
    if route in ours.names:
        print("vignette déjà présente")
        return
    tpl = next(n for n, r in zip(ours.names, ours.recs) if r[6:] == rec[6:] and r[4] == len(raw))
    os.makedirs(os.path.dirname(out_bpr), exist_ok=True)
    open(out_bpr, "wb").write(ours.rebuild([(route, tpl, raw)]).b)
    print("vignette", route, "(modèle", tpl + ") ->", out_bpr)


if __name__ == "__main__":
    main()


# --- bâtiment de Hot Pursuit posé dans un emplacement d'objet de Map Builder (2026-10-27) ---
STM = r"C:\Users\sanqu\Jeux_WII\nfs_extracted\files\Data\Environments\Location1\location11.stm"
HP_GROUND = -323.8           # hauteur de la route HP près de la ligne de départ ; Blur (Map Builder) : sol à y = 1
TEMPLATE = r"C:\Users\sanqu\Jeux_WII\blur_extracted\nfs_models\sign_wetfloor.model"


def slot_matrix(actorpack, def_uid):
    """matrice monde (3 axes + origine) de l'unique acteur visible qui utilise ce DynamicObjDef"""
    from blurxt import XT
    hits = [a["WorldMatrix"] for n, t, v, _ in XT(actorpack).records() for a in v.get("LevelActors", [])
            if a.get("DynamicObjType") == "@%08x" % def_uid and a["WorldMatrix"]["aw"]["vy"] > -100]
    # (décor coupé : Map Builder remplit les listes avec des copies cachées sous le sol, y = -299)
    assert len(hits) == 1, len(hits)
    m = hits[0]
    return [[m[k]["vx"], m[k]["vy"], m[k]["vz"]] for k in ("ax", "ay", "az", "aw")]


def hp_model(mesh_name, mat, matrix, out_path, glow=160):
    """géométrie HP (un matériau d'un maillage .stm) -> .model Blur posé dans l'emplacement `matrix`"""
    import stm2obj
    d = open(STM, "rb").read()
    b = next(b for t, n, b in stm2obj.entries(d) if t == 6 and n == mesh_name)
    pos, uvs, faces = stm2obj.mesh(b, mat)
    tris = [([pos[a] for a, _ in f], [uvs[c] for _, c in f]) for f in faces]
    write_model(tris, stm2obj.material_name(d, mat), matrix, out_path, glow)


def write_model(tris, texture, matrix, out_path, glow=160, up=False, square=None):
    """triangles HP [(3 positions, 3 uv)] + texture HP -> .model Blur, en coordonnées locales de l'emplacement
    (monde = x*ax + y*ay + z*az + aw). Face avant = cross(b - a, c - a) du côté de la normale (vérifié sur le
    gabarit, 36/36). up=True : faces simples tournées vers le haut (route) ; sinon faces doublées (murs).
    square=N : texture ramenée en N x N (prudence après un crash avec 128x1024 / > 32 767 index)"""
    import numpy as np
    import stm2obj
    import blurmodel_write
    M = np.array(matrix[:3]).T
    o = np.array(matrix[3])
    inv = np.linalg.inv(M)
    verts, idx, seen = [], [], {}
    for ps, us in tris:
        P = [inv @ (np.array(p) + (0, 1.0 - HP_GROUND, 0) - o) for p in ps]
        n = np.cross(P[1] - P[0], P[2] - P[0])
        n = n / (np.linalg.norm(n) or 1)
        if up and n[1] < 0:
            n, P, us = -n, [P[0], P[2], P[1]], [us[0], us[2], us[1]]
        ids = []
        for p, (u, v) in zip(P, us):
            key = (tuple(np.round(p, 3)), u, v) if up else None    # route : sommets partagés
            if key is None or key not in seen:
                if key is not None:
                    seen[key] = len(verts)
                ids.append(len(verts))
                verts.append((*p, *n, u, 1 - v))
            else:
                ids.append(seen[key])
        idx += ids if up else ids + ids[::-1]
    d = open(STM, "rb").read()
    img = stm2obj.texture_image(d, texture).convert("RGB")
    if square:
        img = img.resize((square, square))
    data = blurmodel_write.build(open(TEMPLATE, "rb").read(), verts, idx, img.tobytes(), *img.size, glow=glow)
    open(out_path, "wb").write(data)
    print(texture, len(verts), "sommets ->", out_path)


ROAD_SLOTS = [0xF1A72101 + 2 * k for k in range(11)]    # morceaux de route Map Builder (un acteur visible chacun)
# crash au chargement à 3 444 sommets (68 880 o de sommets), 1 353 passe : plafond supposé 65 535 o de sommets
MAX_VERTS = 3000


def road_models(files, world_json, radius=40.0, glow=110):
    """route visible : les 11 matériaux HP les plus présents le long du tracé, un par emplacement de route Map
    Builder (son modèle road_21_KK.model est remplacé : sa route lumineuse disparaît)"""
    import collections
    import json
    import numpy as np
    import stm2obj
    pts = np.array([(p["x"], p["z"]) for p in json.load(open(world_json))["locations"][0]["maps"][0]["points"]])
    dense = np.concatenate([np.linspace(a, b, 20, endpoint=False) for a, b in zip(pts, np.roll(pts, -1, 0))])
    d = open(STM, "rb").read()
    by_mat = collections.defaultdict(list)
    for t, n, b in stm2obj.entries(d):
        if t != 6 or not n.startswith("ROAD"):
            continue
        try:
            pos, uvs, _ = stm2obj.mesh(b)
            P = np.array(pos)
            for m in {s[0] for s in stm2obj.submeshes(b)}:
                for f in stm2obj.mesh(b, m)[2]:
                    ids = [a for a, _ in f]
                    if np.hypot(*(dense - P[ids].mean(0)[[0, 2]]).T).min() < radius:
                        by_mat[m].append(([pos[a] for a in ids], [uvs[c] for _, c in f]))
        except (struct.error, ValueError, IndexError):
            continue
    ap = os.path.join(files, "gamedata", "levels", "flat_earth", "actorpack.xt")
    jobs = []                                       # (matériau, triangles) <= MAX_VERTS sommets partagés
    for m in sorted(by_mat, key=lambda m: -len(by_mat[m])):
        if not stm2obj.material_name(d, m):
            continue
        cur, keys = [], set()
        for tri in by_mat[m]:
            k = {(tuple(np.round(p, 3)), tuple(u)) for p, u in zip(*tri)}
            if len(keys | k) > MAX_VERTS:
                jobs.append((m, cur))
                cur, keys = [], set()
            cur.append(tri)
            keys |= k
        jobs.append((m, cur))
    for k, (slot, (m, tris)) in enumerate(zip(ROAD_SLOTS, jobs)):
        write_model(tris, stm2obj.material_name(d, m), slot_matrix(ap, slot),
                    os.path.join(files, "models", "objects", "flat_earth", "road_21_%02d.model" % k), glow,
                    up=True, square=256)
    print("pas de place pour :", [(stm2obj.material_name(d, m), len(t)) for m, t in jobs[len(ROAD_SLOTS):]])


def road_collision(src, out, world_json, radius=40.0):
    """sol de collision = triangles des maillages ROAD de HP à moins de `radius` m de la ligne centrale, hauteur
    HP + (1 - HP_GROUND), en objets de type route (<= 255 triangles / 256 sommets) insérés en tête du flux Main
    (addramp) ; le sol plat de Map Builder reste dessous (secours)"""
    import json
    import numpy as np
    import stm2obj
    import addramp
    pts = np.array([(p["x"], p["z"]) for p in json.load(open(world_json))["locations"][0]["maps"][0]["points"]])
    dense = np.concatenate([np.linspace(a, b, 20, endpoint=False) for a, b in zip(pts, np.roll(pts, -1, 0))])
    d = open(STM, "rb").read()
    tris = []
    for t, n, b in stm2obj.entries(d):
        if t != 6 or not n.startswith("ROAD"):
            continue
        try:
            pos, _, faces = stm2obj.mesh(b)
        except (struct.error, ValueError, IndexError):
            continue
        P = np.array(pos) + (0, 1.0 - HP_GROUND, 0)
        for f in faces:
            tri = P[[a for a, _ in f]]
            c = tri.mean(0)
            dist = np.hypot(*(dense - c[[0, 2]]).T)
            k = int(dist.argmin())
            if dist[k] < radius:
                tris.append((k, tri))
    tris.sort(key=lambda x: x[0])                     # le long du tracé : objets compacts
    objs, verts, idx, key = [], [], [], {}
    def flush():
        if idx:
            objs.append(addramp.mesh_object(verts, idx, src))
    for _, tri in tris:
        ks = [tuple(np.round(p, 3)) for p in tri]
        new = [k for k in dict.fromkeys(ks) if k not in key]
        if len(idx) >= 255 or len(verts) + len(new) > 256:
            flush()
            verts, idx, key = [], [], {}
            new = list(dict.fromkeys(ks))
        for k in new:
            key[k] = len(verts)
            verts.append(k)
        idx.append(tuple(key[k] for k in ks))
    flush()
    data = addramp.insert_objects(open(src, "rb").read(), b"".join(objs))
    open(out, "wb").write(data)
    print(len(tris), "triangles de route HP ->", len(objs), "objets de collision ->", out)
    return len(objs)
