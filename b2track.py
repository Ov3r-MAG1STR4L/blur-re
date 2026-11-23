r"""Éditeur des tracés des maps Blur 2 (dans le navigateur, vue de dessus + aperçu 3D) : route principale et chemins
secondaires, puis construction et installation dans Blur_test (Dubaï).

python b2track.py   puis http://127.0.0.1:8767   (« Tracés Blur 2.bat » dans Jeux_WII ouvre tout)
Maps : les 4 routes de Dubaï (murs = collision Unity de Blur2DubaiTest, make_b2_map.wall_points ; constructibles)
et les autres villes Blur 2 (fond = collision X360 de blur2_dessin\<mois>\<ville>_map.npz ; tracé seulement).
Conduite (vert) : positions des journaux de Blur2DubaiTest (blur2_aid\journaux\*.log + le Player.log en cours),
rangées par route grâce aux lignes SURVEY_TRACK_LOAD_BEGIN … Route 0N.
Tracé de départ : fichier enregistré s'il existe, sinon le tour roulé (Dubaï) ou la boucle IA officielle (Miami),
sinon vide. Fichier : {"points": [{x, z, w, h}], "branches": [{from_m, to_m, width, points}]}, relu par
make_b2_map.py --track. Construire = make_b2_map (avec --decor --track) ; Installer = copie dans Blur_test, les
originaux remplacés gardés une fois pour toutes dans b2_dubai_marina\backup_blur_test (et remis s'ils ne font plus
partie de la map installée).
Serveur local (127.0.0.1 seulement) : GET / /maps /data?map= /drive?map= /build /png?map= ;
POST /save?map= /build?map= /install?map=
"""
import csv
import glob
import json
import os
import re
import subprocess
import sys
import threading
import time
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import brul2lap  # noqa: E402
import config  # noqa: E402
import make_b2_map  # noqa: E402
import studio_safe as SAFE  # noqa: E402

PORT = int(os.environ.get("BLURRE_PORT", 8767))        # autre port : tests (tests/test_studios_http.py)
AID = os.path.join(config.JEUX, "blur2_aid")
DUBAI = os.path.join(AID, "dubai")
JOURNAUX = os.path.join(AID, "journaux")
LIVE = os.path.join(os.environ["USERPROFILE"], "AppData", "LocalLow", "Personal Prototype Inspection",
                    "Blur 2 Dubai Test", "Player.log")
MODS = os.path.join(config.JEUX, "blur_extracted", "mods")
BACKUP = os.path.join(MODS, "b2_dubai_marina", "backup_blur_test")    # Blur_test originals, shared by the 4 routes
ROUTES = {1: ("Business Bay", (90, -174)), 2: ("Dubai Island", (-540, 482)), 3: ("Construction", (429, -1014)),
          4: ("Marina", (-647, 509.5))}                                  # official grids (Marina: real start gantry)
ROUTE_RX = re.compile(r"SURVEY_TRACK_LOAD_BEGIN .*Route 0?(\d+)")


def maps():
    out = {}
    for r, (name, grid) in ROUTES.items():
        slug = name.lower().replace(" ", "_")
        out["dubai%d" % r] = dict(
            title="Dubaï %d - %s" % (r, name), route=r, name=name, grid=grid, build=True,
            lap=glob.glob(os.path.join(DUBAI, "lap_route%d_*.csv" % r))[0],
            track=os.path.join(DUBAI, "marina_trace.json" if r == 4 else "dubai_route%d_trace.json" % r),
            out=os.path.join(MODS, "b2_dubai_" + slug))
    for f in sorted(glob.glob(os.path.join(config.JEUX, "blur2_dessin", "*", "*_map.npz"))):
        month, city = os.path.basename(os.path.dirname(f)), os.path.basename(f)[:-8]
        key = city if month == "novembre" else "%s_%s" % (city, month)
        if key == "dubai":
            continue
        off = glob.glob(os.path.join(AID, city, city + "_officiel_1.csv")) if month == "novembre" else []
        out[key] = dict(title="%s (%s)" % (city.replace("_", " ").title(), month), npz=f, build=False,
                        lap=off[0] if off else None, track=os.path.join(AID, city, key + "_trace.json"))
    return out


MAPS = maps()


def read_lap(f):
    return [(float(r["x"]), float(r["y"]), float(r["z"])) for r in csv.DictReader(open(f))]


def load_data(m):
    """track + background (x, y, z) + low (track h = y - low)"""
    if m.get("route"):
        pts = make_b2_map.resample(read_lap(m["lap"]), make_b2_map.STEP)
        low = min(p[1] for p in pts)                   # as make_b2_map.world
        bg = make_b2_map.wall_points(m["route"])
    else:
        pts = make_b2_map.resample(read_lap(m["lap"]), make_b2_map.STEP) if m["lap"] else []
        low = 0.0
        bg = np.load(m["npz"])["points"]
    if os.path.exists(m["track"]):
        t = json.load(open(m["track"], encoding="utf-8"))
    else:                                              # first time: lap, one point / 12 m, 30 m wide (or empty)
        t = {"points": [{"x": round(x, 2), "z": round(z, 2), "w": make_b2_map.WIDTH, "h": round(y - low, 2)}
                        for x, y, z in pts], "branches": []}
    P = np.array([(q["x"], q["z"]) for q in t["points"] + [q for b in t["branches"] for q in b["points"]]])
    if len(P):
        lo, hi = P.min(0) - 300, P.max(0) + 300
        bg = bg[(bg[:, [0, 2]] > lo).all(1) & (bg[:, [0, 2]] < hi).all(1)]
    _, keep = np.unique(np.round(bg[:, [0, 2]] / 2), axis=0, return_index=True)    # one point per 2 m square
    bg = bg[keep]
    return {"track": t, "walls": np.round(bg, 1).ravel().tolist(), "low": low, "file": m["track"],
            "build": m["build"]}


def drives(route):
    """[{log, pts: x y z flat}] for each journal with positions on this Dubai route"""
    out, logs = [], sorted(glob.glob(os.path.join(JOURNAUX, "*.log")))
    if os.path.exists(LIVE) and os.path.getsize(LIVE) not in {os.path.getsize(f) for f in logs}:
        logs.append(LIVE)                              # not yet copied by the launcher at the game's exit
    for f in logs:
        cur, pts = None, []
        for line in open(f, encoding="utf-8", errors="replace"):
            r = ROUTE_RX.search(line)
            if r:
                cur = int(r[1])
                continue
            p = brul2lap.RX.search(line) if cur == route else None
            if p:
                x, y, z, vx, vy, vz = map(float, p.groups()[1:])
                if y > -50 and vx * vx + vy * vy + vz * vz > 2:          # in the void / stopped: out
                    pts += [round(-x, 1), round(y, 1), round(-z, 1)]
        if pts:
            out.append({"log": "Player.log (en cours)" if f == LIVE else os.path.basename(f), "pts": pts})
    return out


class Build:
    """one make_b2_map run at a time; its output kept for the page. Killed (whole process tree) after LIMIT s.
    On success, files of OUT/files not rewritten by this build (left by an older one) go to OUT/perimes/<date>."""
    LIMIT = 3600
    lock = threading.Lock()
    proc, lines, key, code, t0 = None, [], None, None, 0.0

    @classmethod
    def running(cls):
        return bool(cls.proc and cls.proc.poll() is None)

    @classmethod
    def start(cls, key):
        m = MAPS[key]
        with cls.lock:
            if cls.running():
                return False
            os.makedirs(m["out"], exist_ok=True)
            cmd = [sys.executable, "-u", os.path.join(HERE, "make_b2_map.py"), m["lap"],
                   os.path.join(DUBAI, "dubai_pickups_officiels.json"), m["out"], "--name", m["name"], "--city", "Dubai",
                   "--route", str(m["route"]), "--grid", *map(str, m["grid"]), "--decor", "--track", m["track"]]
            cls.t0 = time.time()
            cls.proc = subprocess.Popen(cmd, cwd=HERE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                        text=True, encoding="utf-8", errors="replace")
            cls.lines, cls.key, cls.code = ["> " + " ".join(cmd[2:])], key, None
        threading.Thread(target=cls.pump, args=(cls.proc, m), daemon=True).start()
        return True

    @classmethod
    def pump(cls, proc, m):
        def kill():     # make_b2_map runs Map Builder's build.py: the whole tree goes (taskkill /T)
            cls.lines.append("délai de %d min dépassé : construction arrêtée" % (cls.LIMIT // 60))
            subprocess.run(["taskkill", "/T", "/F", "/PID", str(proc.pid)], capture_output=True)
        timer = threading.Timer(cls.LIMIT, kill)
        timer.start()
        try:
            for line in proc.stdout:
                cls.lines.append(line.rstrip())
            code = proc.wait()
        finally:
            timer.cancel()
        if code == 0:
            try:
                old = SAFE.ecarter_perimes(os.path.join(m["out"], "files"), cls.t0, os.path.join(m["out"], "perimes"))
                if old:
                    cls.lines.append("%d fichiers d'une construction précédente mis de côté (perimes\\, non installés) :"
                                     " %s" % (len(old), ", ".join(old[:8]) + (" …" if len(old) > 8 else "")))
            except OSError as ex:
                cls.lines.append("mise de côté des fichiers périmés impossible : %s" % ex)
                code = 1
        cls.lines.append("terminé, code %d" % code)
        cls.code = code


def blur_running():
    r = subprocess.run(["tasklist", "/fi", "imagename eq Blur.exe"], capture_output=True, text=True)
    return "Blur.exe" in r.stdout


def install(m):
    """OUT/files sur Blur_test (studio_safe.installer : copie de test seulement, copies vérifiées avant de remplacer,
    originaux gardés une fois dans BACKUP). Rien d'autre n'est écrit : les fichiers d'une installation précédente
    absents de celle-ci (ex. road_21_KK en trop) restent tels quels et sont seulement signalés. Plus de remise
    automatique depuis BACKUP (2026-11-10, étape 0) : cette sauvegarde mélange plusieurs générations de maps (« 1re
    version vue » à des dates différentes), un fichier remis pouvait venir d'une autre map. Ni suppression ni remise
    tant que l'historique commun (studio_history) n'existe pas."""
    files = os.path.join(m["out"], "files")
    n, saved = SAFE.installer(files, config.BLUR_TEST, BACKUP)
    new = set(SAFE.fichiers(files))
    fa = os.path.join(BACKUP, "_absents.json")
    connus = set(SAFE.fichiers(BACKUP)) | set(json.load(open(fa)) if os.path.isfile(fa) else [])
    restes = sorted(r for r in connus - new - {"_absents.json"} if os.path.exists(os.path.join(config.BLUR_TEST, r)))
    return "%d fichiers installés et vérifiés, %d originaux sauvegardés%s" % (
        n, saved, "" if not restes else ", %d fichiers d'une installation précédente laissés en place (rien remis ni "
        "supprimé) : %s" % (len(restes), ", ".join(restes[:5]) + (" …" if len(restes) > 5 else "")))


def besoin(key):
    if key is None:
        raise SAFE.Refus("paramètre map manquant")
    return key


def verifier_trace(t):
    """tracé posté par la page : structure attendue par make_b2_map --track (+ surfaces) -> Refus sinon"""
    num = (int, float)
    try:
        ok = (isinstance(t, dict) and len(t["points"]) >= 3
              and all(isinstance(q[c], num) for q in t["points"] for c in "xzwh")
              and all(isinstance(b["from_m"], num) and isinstance(b["to_m"], num) and len(b["points"]) >= 2
                      and all(isinstance(q[c], num) for q in b["points"] for c in "xzwh") for b in t["branches"]))
    except (KeyError, TypeError):
        ok = False
    if not ok:
        raise SAFE.Refus("tracé invalide : au moins 3 points de route {x, z, w, h}, embranchements {from_m, to_m, "
                         "2 points}")
    bad = [a.get("id") if isinstance(a, dict) else a for a in t.get("areas", []) if not (
        isinstance(a, dict) and isinstance(a.get("id"), str) and isinstance(a.get("name"), str)
        and isinstance(a.get("type"), str) and isinstance(a.get("exportable"), bool)
        and isinstance(a.get("pts"), list) and len(a["pts"]) >= 3
        and all(isinstance(p, dict) and isinstance(p.get(c), num) for p in a["pts"] for c in "xyz"))]
    if bad:
        raise SAFE.Refus("surfaces invalides (id, nom, type, exportable, 3 sommets x y z) : %s" % bad)


def main():
    page = os.path.join(HERE, "web", "b2track.html")
    cache = {}

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def send(self, body, ctype="application/json", code=200):
            if not isinstance(body, bytes):
                body = json.dumps(body).encode()
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.end_headers()
            self.wfile.write(body)

        def garde(self, ecriture):
            """True (et réponse 403 envoyée) si la requête vient d'un autre site ou d'un autre nom d'hôte"""
            r = SAFE.refus(self.headers, PORT, ecriture)
            if r:
                self.send(r, code=403)
            return bool(r)

        def do_GET(self):
            self.traiter(self.get)

        def do_POST(self):
            self.traiter(self.post)

        def traiter(self, fn):
            """garde, puis fn(chemin, map) ; toute erreur devient un message pour la page (jamais une connexion
            coupée). map hors de MAPS (liste blanche) -> 404"""
            if self.garde(ecriture=self.command == "POST"):
                return
            try:
                u = urllib.parse.urlparse(self.path)
                key = urllib.parse.parse_qs(u.query).get("map", [None])[0]
                if key is not None and key not in MAPS:
                    raise SAFE.Refus("map inconnue : %r" % (key,), 404)
                fn(u.path, key)
            except SAFE.Refus as ex:
                self.send(str(ex), code=ex.code)
            except Exception as ex:  # noqa: BLE001 - montrée dans la page
                self.send("erreur serveur : %s: %s" % (type(ex).__name__, ex), code=500)

        def get(self, path, key):
            if path == "/maps":
                self.send([{"key": k, "title": m["title"], "build": m["build"]} for k, m in MAPS.items()])
            elif path == "/build":
                self.send({"key": Build.key, "lines": Build.lines[-400:], "code": Build.code,
                           "running": bool(Build.proc and Build.proc.poll() is None)})
            elif path in ("/data", "/drive", "/png"):
                m = MAPS[besoin(key)]
                if path == "/data":
                    if key not in cache:
                        cache[key] = json.dumps(load_data(m)).encode()
                    self.send(cache[key])
                elif path == "/drive":
                    self.send(drives(m["route"]) if m.get("route") else [])
                else:
                    self.send(open(os.path.join(m["out"], "bords_trace.png"), "rb").read(), "image/png")
            else:
                self.send(open(page, "rb").read(), "text/html; charset=utf-8")

        def post(self, path, key):
            m = MAPS[besoin(key)]
            if path == "/save":
                t = SAFE.lire_json(self)
                verifier_trace(t)
                SAFE.ecrire_json(m["track"], t)
                cache.pop(key, None)
                self.send("enregistré : " + m["track"])
            elif path == "/build":
                if not m["build"]:
                    raise SAFE.Refus("construction : Dubaï seulement pour l'instant")
                ok = Build.start(key)
                self.send("lancée" if ok else "une construction est déjà en cours", code=200 if ok else 409)
            elif path == "/install":
                if Build.key != key or Build.code != 0 or Build.running():
                    raise SAFE.Refus("construire cette map d'abord (sans erreur)")
                if blur_running():
                    raise SAFE.Refus("Blur est ouvert : le fermer avant d'installer", 409)
                self.send(install(m))
            else:
                raise SAFE.Refus("inconnu : " + path, 404)

    ThreadingHTTPServer.allow_reuse_address = False   # Windows would share the port with an editor already open
    try:
        srv = ThreadingHTTPServer(("127.0.0.1", PORT), H)
    except OSError:
        sys.exit("Un éditeur des tracés est déjà ouvert (port %d) : fermer sa fenêtre d'abord." % PORT)
    url = "http://127.0.0.1:%d" % PORT
    print("Tracés Blur 2 :", url)
    if not os.environ.get("BLURRE_NO_BROWSER"):
        webbrowser.open(url)
    srv.serve_forever()


if __name__ == "__main__":
    main()
