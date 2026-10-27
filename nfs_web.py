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
import shutil
import struct
import subprocess
import sys
import threading
import urllib.parse
import webbrowser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import make_nfs_map as M  # noqa: E402
import nfs_atlas as A  # noqa: E402
import stm2obj  # noqa: E402

PORT = 8765
ENV_DIR = r"C:\Users\sanqu\Jeux_WII\nfs_extracted\files\Data\Environments"
WORK = os.path.dirname(M.WORLD)
CACHE = os.path.join(WORK, "web_cache")
BLUR_TEST = r"C:\Users\sanqu\Jeux_WII\Blur_test"
LOG = []
BUSY = threading.Lock()


def log(*a):
    LOG.append(" ".join(map(str, a)))
    del LOG[:-400]


def world_path(stm):
    stem = os.path.splitext(os.path.basename(stm))[0].lower()
    return os.path.join(WORK, "world.json" if stem == "location11" else "world_%s.json" % stem)


def export(stm):
    """géométrie + textures du lieu pour la page (une seule fois par lieu, mise en cache)"""
    stem = os.path.splitext(os.path.basename(stm))[0].lower()
    out = os.path.join(CACHE, stem)
    if os.path.exists(os.path.join(out, "index.json")):
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
    json.dump(dict(stm=stm, ground=ground, scale=[1 / s for s in stm2obj.SCALE], textures=textures, chunks=chunks,
                   hp_pickups=pickups), open(os.path.join(out, "index.json"), "w"))
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


def load_location(stm):
    State.stm = stm
    M.STM = stm
    M.WORLD = world_path(stm)
    stem = export(stm)
    M.HP_GROUND = json.load(open(os.path.join(CACHE, stem, "index.json")))["ground"]
    return stem


def build():
    with BUSY:
        try:
            log("construction : début (plusieurs minutes)")
            import builtins
            orig = builtins.print
            builtins.print = log
            try:
                A.rebuild(auto_pickups=False)
            finally:
                builtins.print = orig
            log("construction : terminée")
        except Exception as ex:  # noqa: BLE001 - montré dans le journal
            log("construction : ERREUR", ex)


def install():
    with BUSY:
        if "blur.exe" in subprocess.run(["tasklist"], capture_output=True, text=True).stdout.lower():
            log("installation refusée : Blur tourne")
            return
        n = 0
        for root, _, files in os.walk(M.OUT):
            for f in files:
                src = os.path.join(root, f)
                dst = os.path.join(BLUR_TEST, os.path.relpath(src, M.OUT))
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.copyfile(src, dst)
                if open(src, "rb").read() != open(dst, "rb").read():
                    log("installation : copie différente", dst)
                    return
                n += 1
        log("installation : %d fichiers copiés et vérifiés dans Blur_test" % n)


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

    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        q = urllib.parse.parse_qs(u.query)
        if u.path == "/api/locations":
            return self.send_json(dict(current=State.stm, all=sorted(glob.glob(os.path.join(ENV_DIR, "*", "*.stm")))))
        if u.path == "/api/load":
            try:
                return self.send_json({"stem": load_location(q.get("stm", [State.stm])[0])})
            except Exception as ex:  # noqa: BLE001
                return self.send_json({"error": str(ex)}, 500)
        if u.path == "/api/world":
            return self.send_json(json.load(open(M.WORLD)) if os.path.exists(M.WORLD) else None)
        if u.path == "/api/log":
            return self.send_json(LOG[-60:])
        if u.path.startswith("/cache/"):
            p = os.path.normpath(os.path.join(CACHE, urllib.parse.unquote(u.path[7:])))
            if not p.startswith(os.path.normpath(CACHE)) or not os.path.isfile(p):
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
        body = self.rfile.read(int(self.headers.get("Content-Length", 0) or 0))
        if u.path == "/api/world":
            json.dump(json.loads(body), open(M.WORLD, "w"), indent=1)
            log("circuit enregistré :", M.WORLD)
            return self.send_json({"ok": True})
        if u.path == "/api/recenter":
            q = json.loads(body)
            return self.send_json(recenter(q["points"], q.get("closed", True)))
        if u.path == "/api/options":
            o = json.loads(body)
            M.TRACK_WIDTH = float(o.get("width", M.TRACK_WIDTH))
            A.GRID_GAP = float(o.get("grid_gap", A.GRID_GAP))
            A.RADIUS = float(o.get("radius", A.RADIUS))
            M.DECOR_DRAW = float(o.get("draw", M.DECOR_DRAW))
            A.ZONE = float(o.get("zone", A.ZONE))
            A.GLOW = int(o.get("glow", A.GLOW))
            return self.send_json({"ok": True})
        if u.path in ("/api/build", "/api/install"):
            if BUSY.locked():
                return self.send_json({"error": "une opération est déjà en cours"}, 409)
            threading.Thread(target=build if u.path == "/api/build" else install, daemon=True).start()
            return self.send_json({"ok": True})
        return self.send_error(404)


if __name__ == "__main__":
    os.makedirs(CACHE, exist_ok=True)
    srv = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print("NFS Studio : http://127.0.0.1:%d  (Ctrl+C pour arrêter)" % PORT)
    if "--no-browser" not in sys.argv:
        threading.Timer(1.0, lambda: webbrowser.open("http://127.0.0.1:%d" % PORT)).start()
    srv.serve_forever()
