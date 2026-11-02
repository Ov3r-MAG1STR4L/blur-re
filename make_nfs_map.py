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

import config
from blurpak import Pak

BMB = sys.argv[1] if len(sys.argv) > 1 else config.BMB_GAME
OUT = sys.argv[2] if len(sys.argv) > 2 else config.NFS_OUT
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
    add_thumbnail(os.path.join(config.BLUR_TEST, "UI", "data", "ui_frontend.bpr"),
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


# --- bâtiment de Hot Pursuit posé dans un emplacement d'objet de Map Builder (2026-10-27) ---
STM = os.path.join(config.ENV_DIR, "Location1", "location11.stm")
HP_GROUND = -323.8           # hauteur de la route HP près de la ligne de départ ; Blur (Map Builder) : sol à y = 1
TEMPLATE = os.path.join(config.BLUR_EXTRACTED, "nfs_models", "sign_wetfloor.model")


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


def write_model(tris, texture, matrix, out_path, glow=160, up=False, square=None, salt=None, pad=None, image=None):
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
            key = (tuple(np.round(p, 3)), u, v)                    # sommets partagés
            if key is None or key not in seen:
                if key is not None:
                    seen[key] = len(verts)
                ids.append(len(verts))
                verts.append((*p, *n, u, 1 - v))
            else:
                ids.append(seen[key])
        idx += ids if up else ids + ids[::-1]
    d = open(STM, "rb").read()
    if image is not None:                                    # atlas déjà prêt (nfs_atlas.py)
        img = image
    elif texture.startswith("couleur:"):                     # matériau sans texture : couleur unie de sa fiche
        from PIL import Image
        img = Image.new("RGB", (64, 64), tuple(int(texture[8 + 2 * i:10 + 2 * i], 16) for i in range(3)))
    else:
        img = stm2obj.texture_image(d, texture).convert("RGBA")
    if square:
        img = img.resize((square, square))
    data = blurmodel_write.build(open(TEMPLATE, "rb").read(), verts, idx, img.tobytes(), *img.size, glow=glow,
                                 salt=salt, pad_verts=pad and pad[0], pad_indices=pad and pad[1])
    open(out_path, "wb").write(data)
    print(texture, len(verts), "sommets ->", out_path)


def road_slots(actorpack):
    """DynamicObjDef des morceaux de route Map Builder (0xF1A721xx impairs, un acteur visible chacun), dans l'ordre
    road_21_00, _01… (leur nombre dépend de la longueur du tracé : 420 m par morceau)"""
    from blurxt import XT
    u = sorted({int(a["DynamicObjType"][1:], 16) for n, t, v, _ in XT(actorpack).records()
                for a in v.get("LevelActors", []) if str(a.get("DynamicObjType", "")).startswith("@f1a721")})
    assert u == [0xF1A72101 + 2 * k for k in range(len(u))], [hex(x) for x in u]
    return u
# crash au chargement (Blur.exe 0x6DB2EB, accès mémoire) dès 1 854 sommets (37 080 o) ; 1 353 (27 060 o) passe :
# plafond supposé 32 768 o de sommets (1 638 à 20 o)
MAX_VERTS = 3000   # 1 500 avant le correctif « même taille » ; 3 000 à confirmer en jeu
ROAD_FIRST = ("road_plaintarmac", "road_whitedotrwhitelinel", "road_junction_arrows")   # priorité si place manque


def road_models(files, world_json, radius=40.0, glow=110, pad=None):
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
        if t != 6 or not n.lower().startswith("road"):
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
    def prio(m):
        n = stm2obj.material_name(d, m) or ""
        first = [k for k, p in enumerate(ROAD_FIRST) if n.startswith(p)]
        return (first[0] if first else len(ROAD_FIRST), -len(by_mat[m]))
    for m in sorted(by_mat, key=prio):
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
    pad_idx = 3 * max(len(t) for _, t in jobs[:len(road_slots(ap)) + 1])   # même nombre d'index partout
    slots = [(u, "road_21_%02d.model" % k) for k, u in enumerate(road_slots(ap))] + [(0xF1E20005, "arch_lap.model")]
    for k, ((slot, fname), (m, tris)) in enumerate(zip(slots, jobs)):
        write_model(tris, stm2obj.material_name(d, m), slot_matrix(ap, slot),
                    os.path.join(files, "models", "objects", "flat_earth", fname), glow,
                    up=True, square=256, salt=0x4E465300 + k, pad=pad or (MAX_VERTS, pad_idx))
    print("pas de place pour :", [(stm2obj.material_name(d, m), len(t)) for m, t in jobs[len(slots):]])


_SEE = {}


def see_through(d, m, share=0.5):
    """matériau dont la texture est transparente à `share` ou plus : buissons, palmiers, haies, barbelés -> sans
    collision (Location45 : touffes vegasdesert_2 51 %, palmiers 65-75 % ; glissières street_guard 23-45 % gardées).
    Grillages, barrières, bornes et pylônes (même très transparents) gardent leur collision."""
    import numpy as np
    import stm2obj
    tex = stm2obj.material_name(d, m)
    if tex not in _SEE:
        try:
            a = np.array(stm2obj.texture_image(d, tex).convert("RGBA"))[:, :, 3]
            _SEE[tex] = float((a < 128).mean())
        except Exception:  # noqa: BLE001 - couleur unie ou texture illisible : opaque
            _SEE[tex] = 0.0
    solid = any(k in (tex or "").lower() for k in ("fence", "barrier", "bollard", "pylon", "guard"))
    return _SEE[tex] >= share and not solid


def road_collision(src, out, world_json, radius=40.0, road_only=False):   # 40 m : au-delà, le tube (50 m) replace la voiture
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
        if t != 6 or (road_only and not n.lower().startswith("road")):
            continue                      # tout le LOD0 : route, trottoirs, terrains, glissières, murs, immeubles
        try:
            pos = stm2obj.mesh(b)[0]
            faces = [f for m in {s[0] for s in stm2obj.submeshes(b)} if not see_through(d, m)
                     for f in stm2obj.mesh(b, m)[2]]
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


WORLD = os.path.join(config.STM_WORK, "world.json")


def set_heights(world_json, ground=1.0):
    """hauteur de chaque point du tracé = route HP (médiane des sommets ROAD à moins de 6 m) : Map Builder y pose
    sa grille de départ, ses bonus, son tracé IA et ses caméras (sinon départ sous la route HP, en hauteur).
    Map Builder ne prend pas de hauteur négative : si le tracé descend sous le sol de référence, HP_GROUND est
    abaissé d'autant (toute la carte remonte : modèles, collision, bonus restent alignés) au lieu de couper à 0
    (Location45, bord de rivière : tracé à 0 m au-dessus de la vraie route, voiture « en vol »)"""
    global HP_GROUND
    import json
    import numpy as np
    from scipy.spatial import cKDTree
    import stm2obj
    d = open(STM, "rb").read()
    V = []
    for t, n, b in stm2obj.entries(d):
        if t == 6 and n.lower().startswith("road"):
            try:
                V += stm2obj.mesh(b)[0]
            except (struct.error, ValueError, IndexError):
                pass
    V = np.array(V)
    tree = cKDTree(V[:, [0, 2]])
    w = json.load(open(world_json))
    mp = w["locations"][0]["maps"][0]
    lines = [mp["points"]] + [br["points"] for br in mp.get("branches") or []]   # route + chemins secondaires
    raw = [[float(np.median(V[near, 1])) if near else None
            for near in (tree.query_ball_point((p["x"], p["z"]), 6.0) for p in pts)] for pts in lines]
    low = min((y for ys in raw for y in ys if y is not None), default=HP_GROUND)
    if low < HP_GROUND:
        print("tracé sous le sol de référence : sol abaissé de %.1f m" % (HP_GROUND - low))
        HP_GROUND = low
    for pts, ys in zip(lines, raw):
        hs = [None if y is None else max(0.0, y + 1.0 - HP_GROUND - ground) for y in ys]
        for k, h in enumerate(hs):                   # trous : valeur du voisin connu le plus proche
            if h is None:
                h = next((hs[(k + i) % len(hs)] for i in range(1, len(hs)) if hs[(k + i) % len(hs)] is not None), 0.0)
            pts[k]["h"] = round(h, 2)
    pts = mp["points"]
    json.dump(w, open(world_json, "w"), indent=1)
    print("hauteurs du tracé : %.1f à %.1f m" % (min(p["h"] for p in pts), max(p["h"] for p in pts)))


TRACK_WIDTH = 50.0            # largeur du « tube » de course (hors-piste -> replacement) : route HP + trottoirs


def set_track(world_json):
    """largeur du circuit + bonus aux emplacements de Hot Pursuit (fiches powerupNNN du .stm : 3 floats de position
    puis 1.0 juste avant le nom ; une rangée par fiche, seulement celles à moins de 40 m du tracé)"""
    import json
    import re
    import numpy as np
    d = open(STM, "rb").read()
    hp = []
    for m in re.finditer(rb"powerup[0-9]+\x00", d):
        x, y, z, one = struct.unpack_from(">4f", d, m.start() - 16)
        if abs(one - 1) < 1e-6:
            hp.append((x, z))
    w = json.load(open(world_json))
    mp = w["locations"][0]["maps"][0]
    pts = np.array([(p["x"], p["z"]) for p in mp["points"]])
    rows = [{"kind": "row", "x": round(x, 2), "z": round(z, 2)} for x, z in hp
            if np.hypot(*(pts - (x, z)).T).min() < 40]
    mp["width"] = TRACK_WIDTH
    mp["pickups"] = rows
    json.dump(w, open(world_json, "w"), indent=1)
    print(len(rows), "rangées de bonus aux emplacements HP ; largeur", TRACK_WIDTH)


def rebuild_all():
    """tout refaire : décor choisi -> build Map Builder (NFS_COUNT) -> fichiers en clair -> collision HP ->
    route HP (12 modèles) + décor HP, tous les modèles à la même taille"""
    import subprocess
    set_heights(WORLD)
    set_track(WORLD)
    shutil.copyfile(WORLD, os.path.join(BMB, "Blur Map Builder", "maps", "world.json"))
    jobs = decor_jobs(WORLD)
    mb = os.path.join(BMB, "map_builder", "flat_earth")
    import json
    spots = os.path.join(OUT, "..", "nfs_spots.json")
    json.dump([zone_centre(t) for _, t in jobs], open(spots, "w"))
    env = dict(os.environ, BMB_GAME=BMB, BMB_INSTALLED="1", NFS_COUNT=str(len(jobs)), NFS_SPOTS=os.path.abspath(spots),
               NFS_DRAW=str(DECOR_DRAW), NFS_NO_WALLS="1", NFS_FLOOR_Y="-5")   # murs Map Builder retirés
    subprocess.run([sys.executable, "build.py"], cwd=mb, env=env, check=True, stdout=subprocess.DEVNULL)
    main()
    road_collision(os.path.join(BMB, "levels", "flat_earth", "level.levelphysics"),
                   os.path.join(OUT, "levels", "flat_earth", "level.levelphysics"), WORLD)
    pad = (DECOR_VERTS, 6 * max(len(t) for _, t in jobs))        # faces doublées : 6 index par triangle
    road_models(OUT, WORLD, pad=pad)    # 11 morceaux de route + l'emplacement de l'arche
    decor_models(OUT, jobs, pad)


NFS_UID = 0xF1E40000          # modèles de décor ajoutés à Map Builder (build.py : NFS_COUNT, défs NFS_UID + 2k + 1)
DECOR_VERTS = 10000           # à confirmer en jeu (3 000 OK)
DECOR_MAX = 110               # place dans la liste de 144 acteurs (route, feux, arche… prennent le reste)


ZONE = 120.0                  # côté des zones de décor (m) : boîte serrée -> le jeu écarte ce qui est loin / caché
DECOR_DRAW = 700.0            # distance d'affichage du décor HP (m)


def decor_jobs(world_json, radius=300.0, road_radius=40.0, max_verts=DECOR_VERTS, limit=DECOR_MAX):
    """décor HP (tous les maillages LOD0 sauf la route du tracé) : [(texture, triangles)] par matériau, en morceaux
    <= max_verts sommets partagés, les plus proches du tracé d'abord, au plus `limit` morceaux"""
    import collections
    import json
    import numpy as np
    from scipy.spatial import cKDTree
    import stm2obj
    pts = np.array([(p["x"], p["z"]) for p in json.load(open(world_json))["locations"][0]["maps"][0]["points"]])
    dense = np.concatenate([np.linspace(a, b, 20, endpoint=False) for a, b in zip(pts, np.roll(pts, -1, 0))])
    tree = cKDTree(dense)
    d = open(STM, "rb").read()
    by_tex = collections.defaultdict(list)
    for t, n, b in stm2obj.entries(d):
        if t != 6:
            continue
        try:
            pos, uvs, _ = stm2obj.mesh(b)
            dist = tree.query(np.array(pos)[:, [0, 2]])[0] if pos else None
            for m in {s[0] for s in stm2obj.submeshes(b)}:
                tex = stm2obj.material_name(d, m) or "couleur:%02x%02x%02x" % stm2obj.material_color(d, m)
                for f in stm2obj.mesh(b, m)[2]:
                    dm = float(dist[[a for a, _ in f]].min())
                    if dm > radius or (n.lower().startswith("road") and dm < road_radius):
                        continue
                    cc = np.array([pos[a] for a, _ in f]).mean(0)
                    zone = (tex, int(cc[0] // ZONE), int(cc[2] // ZONE))
                    by_tex[zone].append((dm, [pos[a] for a, _ in f], [uvs[c] for _, c in f]))
        except (struct.error, ValueError, IndexError):
            continue
    jobs = []
    for tex, tris in by_tex.items():
        tris.sort(key=lambda x: x[0])
        cur, keys = [], set()
        for dm, ps, us in tris:
            k = {(tuple(np.round(p, 3)), tuple(u)) for p, u in zip(ps, us)}
            if len(keys | k) > max_verts:
                jobs.append((cur[0][0], tex, [(p, u) for _, p, u in cur]))
                cur, keys = [], set()
            cur.append((dm, ps, us))
            keys |= k
        if cur:
            jobs.append((cur[0][0], tex, [(p, u) for _, p, u in cur]))
    jobs.sort(key=lambda j: j[0])
    print(len(jobs), "morceaux de décor possibles,", min(limit, len(jobs)), "gardés")
    return [(key[0], tris) for _, key, tris in jobs[:limit]]


def zone_centre(tris):
    """centre (x, y Blur, z) d'un morceau : position de son acteur"""
    import numpy as np
    P = np.array([p for ps, _ in tris for p in ps])
    c = (P.min(0) + P.max(0)) / 2
    return [round(float(c[0]), 2), round(float(c[1] + 1.0 - HP_GROUND), 2), round(float(c[2]), 2)]


def decor_models(files, jobs, pad, glow=110):
    ap = os.path.join(files, "gamedata", "levels", "flat_earth", "actorpack.xt")
    flat = os.path.join(files, "models", "objects", "flat_earth")
    for k, (tex, tris) in enumerate(jobs):
        write_model(tris, tex, slot_matrix(ap, NFS_UID + 2 * k + 1), os.path.join(flat, "nfs_%03d.model" % k), glow,
                    square=256, salt=0x4E465400 + k, pad=pad)



if __name__ == "__main__":
    rebuild_all()
