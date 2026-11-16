"""NFS Studio (web) : éditeur 3D dans le navigateur pour construire un circuit Blur à partir d'un lieu Hot Pursuit Wii.

python nfs_web.py      puis http://127.0.0.1:8765  (« NFS Studio.bat » ouvre tout)
Serveur local (127.0.0.1 seulement) :
  GET  /                       page web/index.html (three.js)
  GET  /api/locations          lieux .stm trouvés
  GET  /api/load?stm=CHEMIN    exporte (cache) la géométrie du lieu : web_cache/<lieu>/
  GET  /cache/<lieu>/...       index.json, textures PNG, géométrie (.bin : float32 x y z u v par sommet,
                               triangles à plat, positions monde HP, y + 1 - sol HP = hauteur Blur)
  GET  /api/world              circuit du lieu courant (world*.json : points x z h w, branches, pickups, start_m)
  POST /api/world              enregistre le circuit
  POST /api/options            réglages de construction
  POST /api/build, /api/install, GET /api/log   construction (nfs_atlas) / installation dans Blur_test / journal
"""
import collections
import glob
import json
import os
import re
import struct
import subprocess
import sys
import threading
import time
import urllib.parse
import webbrowser

import config
import studio_safe as SAFE
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import make_nfs_map as M  # noqa: E402
import nfs_atlas as A  # noqa: E402
import stm2obj  # noqa: E402

PORT = int(os.environ.get("BLURRE_PORT", 8765))        # autre port : tests (tests/test_studios_http.py)
ENV_DIR = config.ENV_DIR
WORK = os.path.dirname(M.WORLD)
CACHE = os.path.join(WORK, "web_cache")
BLUR_TEST = config.BLUR_TEST
# originaux de Blur_test remplacés par les installations de NFS Studio (studio_safe.installer). Le dossier voisin
# backup_blur_test (installation manuelle plus ancienne, contenu d'origine non garanti) n'est pas touché.
BACKUP = os.path.join(os.path.dirname(M.OUT), "backup_studio")
PERIMES = os.path.join(os.path.dirname(M.OUT), "perimes")      # sorties d'une construction précédente, mises de côté
LOG = []
BUSY = threading.Lock()         # une seule construction / installation ; pris par la requête, rendu par le thread


def log(*a):
    LOG.append(" ".join(map(str, a)))
    del LOG[:-400]


def world_path(stm):
    stem = os.path.splitext(os.path.basename(stm))[0].lower()
    return os.path.join(WORK, "world.json" if stem == "location11" else "world_%s.json" % stem)


def envmap_textures(d):
    """textures d'au moins un matériau à reflet (envmap.tex) : leur alpha est le masque du reflet (vitre
    opaque), pas une découpe -> pas d'alphaTest dans la page (diagnostic P1, 2026-11-02)"""
    mats = stm2obj.materials(d)
    out = set()
    for t, n, b in stm2obj.entries(d):
        if t != 6:
            continue
        try:
            for m in {s[0] for s in stm2obj.submeshes(b)}:
                if any(u.lower() == "envmap.tex" for u in mats.get(m, ("", []))[1]):
                    out.add(stm2obj.material_name(d, m))
        except (struct.error, ValueError, IndexError):
            continue
    return out


def export(stm):
    """géométrie + textures du lieu pour la page (une seule fois par lieu, mise en cache)"""
    stem = os.path.splitext(os.path.basename(stm))[0].lower()
    out = os.path.join(CACHE, stem)
    idx = os.path.join(out, "index.json")
    if os.path.exists(idx):
        info = json.load(open(idx))
        if "envmap" not in info:                  # cache d'avant 2026-11-02 : on ajoute seulement le repère
            env = envmap_textures(open(stm, "rb").read())
            info["envmap"] = [t in env for t in info["textures"]]
            json.dump(info, open(idx, "w"))
        return stem
    os.makedirs(out, exist_ok=True)
    d = open(stm, "rb").read()
    groups = collections.defaultdict(list)          # (calque, texture) -> lignes x y z u v
    road_y = []
    for t, n, b in stm2obj.entries(d):
        if t != 6:
            continue
        try:
            pos, uvs, _ = stm2obj.mesh(b)
            if not pos:
                continue
            P = np.array(pos)
            U = np.array(uvs) if uvs else np.zeros((1, 2))
            is_road = n.lower().startswith("road")
            if is_road:
                road_y.append(P[:, 1])
            for m in {s[0] for s in stm2obj.submeshes(b)}:
                tex = stm2obj.material_name(d, m) or "couleur:%02x%02x%02x" % stm2obj.material_color(d, m)
                f = stm2obj.mesh(b, m)[2]
                if not f:
                    continue
                ia = np.array([[a for a, _ in tri] for tri in f]).ravel()
                ic = np.array([[c for _, c in tri] for tri in f]).ravel()
                rows = np.c_[P[ia], U[np.clip(ic, 0, len(U) - 1)]].astype(np.float32)
                groups[("route" if is_road else "decor", tex)].append(rows)
        except (struct.error, ValueError, IndexError):
            continue
    ground = float(np.percentile(np.concatenate(road_y), 5)) if road_y else 0.0
    textures, chunks = [], []
    for k, ((layer, tex), parts) in enumerate(sorted(groups.items())):
        rows = np.concatenate(parts)
        rows[:, 1] += 1.0 - ground                    # hauteur Blur (sol de Map Builder à 1)
        rows.tofile(os.path.join(out, "g%03d.bin" % k))
        if tex not in textures:
            textures.append(tex)
            if not tex.startswith("couleur:"):
                stm2obj.texture_image(d, tex).save(os.path.join(out, "t%03d.png" % textures.index(tex)))
        chunks.append(dict(file="g%03d.bin" % k, layer=layer, tex=textures.index(tex), count=len(rows)))
    pickups = []
    for mm in re.finditer(rb"powerup[0-9]+\x00", d):
        x, y, z, one = struct.unpack_from(">4f", d, mm.start() - 16)
        if abs(one - 1) < 1e-6 and abs(y) < 1000:
            pickups.append([x, y + 1.0 - ground, z])
    env = envmap_textures(d)
    json.dump(dict(stm=stm, ground=ground, scale=[1 / s for s in stm2obj.SCALE], textures=textures, chunks=chunks,
                   hp_pickups=pickups, envmap=[t in env for t in textures]), open(os.path.join(out, "index.json"), "w"))
    log("export %s : %d groupes, %d textures, sol HP %.1f" % (stem, len(chunks), len(textures), ground))
    return stem


class State:
    stm = M.STM
    asphalt = None          # (stm, sommets x z de l'asphalte « road_* » du lieu)


def asphalt():
    if State.asphalt is None or State.asphalt[0] != State.stm:
        d = open(State.stm, "rb").read()
        pts = []
        for t, n, b in stm2obj.entries(d):
            if t != 6 or not n.lower().startswith("road"):
                continue
            try:
                pos, _, _ = stm2obj.mesh(b)
                for m in {s[0] for s in stm2obj.submeshes(b)}:
                    if (stm2obj.material_name(d, m) or "").lower().startswith("road_"):
                        pts += [pos[a] for f in stm2obj.mesh(b, m)[2] for a, _ in f]
            except (struct.error, ValueError, IndexError):
                continue
        State.asphalt = (State.stm, np.unique(np.round(np.array(pts)[:, [0, 2]], 1), axis=0))
    return State.asphalt[1]


def recenter(points, closed=True, step=10.0, passes=8):
    """tracé (liste de {x, z}) -> rééchantillonné tous les `step` m, recentré entre les bords de l'asphalte (3 m max
    par passe : ne saute pas sur une route voisine) ; largeur w = distance entre les bords (couloir des IA)"""
    from scipy.spatial import cKDTree
    A_ = asphalt()
    tree = cKDTree(A_)
    P = np.array([(p["x"], p["z"]) for p in points] + ([(points[0]["x"], points[0]["z"])] if closed else []))
    L = np.r_[0, np.cumsum(np.hypot(*np.diff(P, axis=0).T))]
    s = np.arange(0, L[-1] + (0 if closed else 1e-6), step)
    C = np.c_[np.interp(s, L, P[:, 0]), np.interp(s, L, P[:, 1])]
    W = np.full(len(C), np.nan)
    for _ in range(passes):
        if closed:
            T = np.roll(C, -1, 0) - np.roll(C, 1, 0)
        else:
            T = np.gradient(C, axis=0)
        T /= np.linalg.norm(T, axis=1, keepdims=True) + 1e-9
        N = np.c_[-T[:, 1], T[:, 0]]
        new = C.copy()
        for i, (c, t, n) in enumerate(zip(C, T, N)):
            r = A_[tree.query_ball_point(c, 40)] - c
            if len(r) < 4:
                continue
            lat = np.sort((r @ n)[np.abs(r @ t) < 4])
            if len(lat) < 4:
                continue
            lo = hi = lat[np.abs(lat).argmin()]
            for v in lat[lat < lo][::-1]:
                if lo - v > 3:
                    break
                lo = v
            for v in lat[lat > hi]:
                if v - hi > 3:
                    break
                hi = v
            new[i] = c + n * float(np.clip((lo + hi) / 2, -3, 3))
            # largeur : sommets plus clairsemés en travers (bords, lignes) -> fenêtre 12 m, écarts tolérés 8 m
            lw = np.sort((r @ n)[np.abs(r @ t) < 12])
            a = b = lw[np.abs(lw).argmin()]
            for v in lw[lw < a][::-1]:
                if a - v > 8:
                    break
                a = v
            for v in lw[lw > b]:
                if v - b > 8:
                    break
                b = v
            W[i] = b - a
        if closed:
            C = (np.roll(new, 1, 0) + 2 * new + np.roll(new, -1, 0)) / 4
        else:
            C = new
    W = np.where(np.isnan(W), np.nanmedian(W) if np.isfinite(W).any() else 30, W)
    W = np.clip(np.convolve(np.r_[W[:2], W, W[-2:]], np.ones(5) / 5, "valid"), 10, 120)   # largeurs lissées
    return [dict(x=round(float(x), 2), z=round(float(z), 2), w=round(float(w), 1)) for (x, z), w in zip(C, W)]


def locations():
    return sorted(glob.glob(os.path.join(ENV_DIR, "*", "*.stm")))


def load_location(stm):
    """stm : un des lieux de ENV_DIR (liste blanche : pas de chemin quelconque lu, ni de cache écrit pour lui)"""
    connus = {os.path.normcase(os.path.realpath(f)): f for f in locations()}
    stm = connus.get(os.path.normcase(os.path.realpath(stm)))
    if stm is None:
        raise SAFE.Refus("lieu inconnu : choisir un .stm de la liste")
    State.stm = stm
    M.STM = stm
    M.WORLD = world_path(stm)
    stem = export(stm)
    M.HP_GROUND = json.load(open(os.path.join(CACHE, stem, "index.json")))["ground"]
    return stem


def build():
    t0 = time.time()
    try:
        log("construction : début (plusieurs minutes)")
        import builtins
        orig = builtins.print
        # le lecteur de modèles (BlurImportExport) affiche toute son analyse : on ne garde que nos messages
        noise = ("|", "Shaders", "Meshes", "Vert", "Face", "Rendering", "Textures", "FX ", "ARCH", "Len ", "StrTab",
                 "Models", "Element", "Constr", "Render", "Header", "Scene", "Coll", "MtaDbg", "MdlDat")
        builtins.print = lambda *a, **k: None if not a or str(a[0]).strip().startswith(noise)                 or not str(a[0]).strip() else log(*a)
        try:
            A.rebuild(auto_pickups=False)
        finally:
            builtins.print = orig
        old = SAFE.ecarter_perimes(M.OUT, t0, PERIMES)
        if old:
            log("%d fichiers d'une construction précédente mis de côté dans %s (non installés) : %s"
                % (len(old), PERIMES, ", ".join(old[:8])))
        log("construction : terminée")
    except Exception:  # noqa: BLE001 - montré dans le journal, en entier
        import traceback
        log("construction : ERREUR " + traceback.format_exc())


def install():
    """studio_safe.installer : Blur_test seulement (fichier témoin), copies vérifiées avant de remplacer quoi que ce
    soit (un écart annule tout), originaux gardés une fois dans BACKUP"""
    if "blur.exe" in subprocess.run(["tasklist"], capture_output=True, text=True).stdout.lower():
        log("installation refusée : Blur tourne")
        return
    try:
        n, saved = SAFE.installer(M.OUT, BLUR_TEST, BACKUP)
        log("installation : %d fichiers copiés et vérifiés dans Blur_test, %d originaux sauvegardés dans %s"
            % (n, saved, BACKUP))
    except Exception as ex:  # noqa: BLE001 - montrée dans le journal
        log("installation refusée ou annulée (Blur_test inchangé) : %s" % ex)


def run_locked(fn):
    """fn dans un thread ; BUSY a été pris par la requête et est rendu à la fin, quoi qu'il arrive"""
    def go():
        try:
            fn()
        finally:
            BUSY.release()
    threading.Thread(target=go, daemon=True).start()


def check_world(w):
    """circuit posté par la page : structure de world.json (Map Builder) -> Refus sinon"""
    try:
        ok = isinstance(w, dict) and isinstance(w["locations"], list) and len(w["locations"]) > 0 and all(
            isinstance(loc, dict) and isinstance(loc["maps"], list) and all(
                isinstance(m, dict) and isinstance(m.get("points", []), list) for m in loc["maps"])
            for loc in w["locations"])
    except (KeyError, TypeError):
        ok = False
    if not ok:
        raise SAFE.Refus("circuit invalide : world.json attendu ({locations: [{maps: [...]}]})")


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **k):
        super().__init__(*a, directory=os.path.join(HERE, "web"), **k)

    def log_message(self, *a):
        pass

    def send_json(self, obj, code=200):
        b = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def garde(self, ecriture):
        """True (et réponse 403 envoyée) si la requête vient d'un autre site ou d'un autre nom d'hôte"""
        r = SAFE.refus(self.headers, PORT, ecriture)
        if r:
            self.send_json({"error": r}, 403)
        return bool(r)

    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        q = urllib.parse.parse_qs(u.query)
        if self.garde(ecriture=u.path == "/api/load"):     # /api/load change le lieu courant et écrit le cache
            return None
        if u.path == "/api/locations":
            return self.send_json(dict(current=State.stm, all=locations()))
        if u.path == "/api/load":
            if BUSY.locked():       # changer de lieu change les entrées de la construction en cours
                return self.send_json({"error": "construction ou installation en cours : réessayer à la fin"}, 409)
            try:
                return self.send_json({"stem": load_location(q.get("stm", [State.stm])[0])})
            except SAFE.Refus as ex:
                return self.send_json({"error": str(ex)}, ex.code)
            except Exception as ex:  # noqa: BLE001
                return self.send_json({"error": str(ex)}, 500)
        if u.path == "/api/world":
            return self.send_json(json.load(open(M.WORLD)) if os.path.exists(M.WORLD) else None)
        if u.path == "/api/log":
            return self.send_json(LOG[-60:])
        if u.path.startswith("/cache/"):
            try:
                p = SAFE.dans_dossier(CACHE, os.path.join(CACHE, urllib.parse.unquote(u.path[7:])))
            except SAFE.Refus:
                return self.send_error(404)
            if not os.path.isfile(p):
                return self.send_error(404)
            data = open(p, "rb").read()
            self.send_response(200)
            self.send_header("Content-Type", "image/png" if p.endswith(".png") else
                             "application/json" if p.endswith(".json") else "application/octet-stream")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return None
        return super().do_GET()

    def do_POST(self):
        u = urllib.parse.urlparse(self.path)
        if self.garde(ecriture=True):
            return None
        try:
            return self.post(u.path)
        except SAFE.Refus as ex:
            return self.send_json({"error": str(ex)}, ex.code)
        except Exception as ex:  # noqa: BLE001 - montrée dans la page, au lieu d'une connexion coupée
            return self.send_json({"error": "erreur serveur : %s: %s" % (type(ex).__name__, ex)}, 500)

    def post(self, path):
        if path in ("/api/build", "/api/install"):
            if not BUSY.acquire(blocking=False):
                return self.send_json({"error": "une opération est déjà en cours"}, 409)
            run_locked(build if path == "/api/build" else install)
            return self.send_json({"ok": True})
        body = SAFE.lire_json(self)
        if path == "/api/world":
            check_world(body)
            if BUSY.locked():       # la construction lit world.json
                raise SAFE.Refus("construction ou installation en cours : réessayer à la fin", 409)
            SAFE.ecrire_json(M.WORLD, body)
            log("circuit enregistré :", M.WORLD, "(ancienne version : .bak)")
            return self.send_json({"ok": True})
        if path == "/api/recenter":
            try:
                pts = [dict(x=float(p["x"]), z=float(p["z"])) for p in body["points"]]
                closed = bool(body.get("closed", True))
            except (KeyError, TypeError, ValueError):
                raise SAFE.Refus("points {x, z} attendus")
            return self.send_json(recenter(pts, closed))
        if path == "/api/options":
            if BUSY.locked():       # la construction utilise ces réglages
                raise SAFE.Refus("construction ou installation en cours : réessayer à la fin", 409)
            o = body if isinstance(body, dict) else {}
            M.TRACK_WIDTH = float(o.get("width", M.TRACK_WIDTH))
            A.GRID_GAP = float(o.get("grid_gap", A.GRID_GAP))
            A.RADIUS = float(o.get("radius", A.RADIUS))
            M.DECOR_DRAW = float(o.get("draw", M.DECOR_DRAW))
            A.ZONE = float(o.get("zone", A.ZONE))
            A.GLOW = int(o.get("glow", A.GLOW))
            return self.send_json({"ok": True})
        return self.send_json({"error": "inconnu : " + path}, 404)


if __name__ == "__main__":
    os.makedirs(CACHE, exist_ok=True)
    ThreadingHTTPServer.allow_reuse_address = False      # Windows : sinon un 2e studio écoute le même port sans erreur
    try:
        srv = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    except OSError:
        print("NFS Studio est déjà ouvert : ferme l'autre fenêtre noire, puis relance.")
        sys.exit(1)
    print("NFS Studio : http://127.0.0.1:%d  (Ctrl+C pour arrêter)" % PORT)
    if "--no-browser" not in sys.argv and not os.environ.get("BLURRE_NO_BROWSER"):
        threading.Timer(1.0, lambda: webbrowser.open("http://127.0.0.1:%d" % PORT)).start()
    srv.serve_forever()
