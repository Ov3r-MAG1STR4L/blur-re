"""Projet J : récupère les fichiers produits par Blur Map Builder (dossier séparé bmb_game) en fichiers en clair.

Usage : python make_nfs_map.py [BMB_GAME] [SORTIE]
Map Builder doit avoir été construit avec, comme base (`base/unpacked/gamedata/xt`), les amax.bin /
multiplayer.bin / cityandroutenames.loc de Blur_test : ses ajouts se font alors PAR-DESSUS nos mods.
Ici : fichiers neufs ou changés de ses paks (sauf ui_frontend.bpr : sa vignette est posée dans NOTRE bpr
moddé avec blurbpr), plus le dossier de niveau levels/flat_earth.
"""
import os
import shutil
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


def hp_model(mesh_name, mat, matrix, out_path):
    """géométrie HP (un matériau d'un maillage .stm) -> .model Blur, en coordonnées locales de l'emplacement
    (monde = x*ax + y*ay + z*az + aw) ; faces doublées (sens d'enroulement Wii / PC pas vérifié)"""
    import numpy as np
    import stm2obj
    import blurmodel_write
    d = open(STM, "rb").read()
    b = next(b for t, n, b in stm2obj.entries(d) if t == 6 and n == mesh_name)
    pos, uvs, faces = stm2obj.mesh(b, mat)
    M = np.array(matrix[:3]).T
    o = np.array(matrix[3])
    inv = np.linalg.inv(M)
    verts, idx, seen = [], [], {}
    for tri in faces:
        P = [inv @ (np.array(pos[a]) + (0, 1.0 - HP_GROUND, 0) - o) for a, _ in tri]
        n = np.cross(P[1] - P[0], P[2] - P[0])
        n = n / (np.linalg.norm(n) or 1)
        ids = []
        for p, (a, c) in zip(P, tri):
            u, v = uvs[c]
            ids.append(len(verts))
            verts.append((*p, *n, u, 1 - v))
        idx += ids + ids[::-1]
    img = stm2obj.texture_image(d, stm2obj.material_name(d, mat)).convert("RGB")
    data = blurmodel_write.build(open(TEMPLATE, "rb").read(), verts, idx, img.tobytes(), *img.size)
    open(out_path, "wb").write(data)
    print(mesh_name, hex(mat), stm2obj.material_name(d, mat), len(verts), "sommets ->", out_path)
