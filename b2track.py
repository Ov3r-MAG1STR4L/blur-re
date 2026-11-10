"""Éditeur des tracés des maps Blur 2 (dans le navigateur, vue de dessus + aperçu 3D) : route principale et chemins
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
import shutil
import subprocess
import sys
import threading
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import brul2lap  # noqa: E402
import config  # noqa: E402
import make_b2_map  # noqa: E402

PORT = 8767
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
        t = json.load(open(m["track"]))
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
    """one make_b2_map run at a time; its output kept for the page"""
    lock = threading.Lock()
    proc, lines, key, code = None, [], None, None

    @classmethod
    def start(cls, key):
        m = MAPS[key]
        with cls.lock:
            if cls.proc and cls.proc.poll() is None:
                return False
            os.makedirs(m["out"], exist_ok=True)
            cmd = [sys.executable, "-u", os.path.join(HERE, "make_b2_map.py"), m["lap"],
                   os.path.join(DUBAI, "dubai_pickups_officiels.json"), m["out"], "--name", m["name"], "--city", "Dubai",
                   "--route", str(m["route"]), "--grid", *map(str, m["grid"]), "--decor", "--track", m["track"]]
            cls.proc = subprocess.Popen(cmd, cwd=HERE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                        text=True, encoding="utf-8", errors="replace")
            cls.lines, cls.key, cls.code = ["> " + " ".join(cmd[2:])], key, None
        threading.Thread(target=cls.pump, daemon=True).start()
        return True

    @classmethod
    def pump(cls):
        for line in cls.proc.stdout:
            cls.lines.append(line.rstrip())
        cls.code = cls.proc.wait()
        cls.lines.append("terminé, code %d" % cls.code)


def blur_running():
    r = subprocess.run(["tasklist", "/fi", "imagename eq Blur.exe"], capture_output=True, text=True)
    return "Blur.exe" in r.stdout


def install(m):
    """OUT/files over Blur_test; the originals replaced go once to BACKUP; backed up files not in this map go back"""
    files = os.path.join(m["out"], "files")
    new = {os.path.relpath(os.path.join(d, f), files) for d, _, fs in os.walk(files) for f in fs}
    saved = restored = 0
    for rel in sorted(new):
        dst, bak = os.path.join(config.BLUR_TEST, rel), os.path.join(BACKUP, rel)
        if os.path.exists(dst) and not os.path.exists(bak):
            os.makedirs(os.path.dirname(bak), exist_ok=True)
            shutil.copy2(dst, bak)
            saved += 1
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(os.path.join(files, rel), dst)
    for d, _, fs in os.walk(BACKUP):
        for f in fs:
            rel = os.path.relpath(os.path.join(d, f), BACKUP)
            if rel not in new:                         # left by an earlier install (e.g. road_21_KK): original back
                shutil.copy2(os.path.join(d, f), os.path.join(config.BLUR_TEST, rel))
                restored += 1
    return "%d fichiers installés, %d originaux sauvegardés, %d originaux remis" % (len(new), saved, restored)


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

        def route(self):
            u = urllib.parse.urlparse(self.path)
            return u.path, urllib.parse.parse_qs(u.query).get("map", [None])[0]

        def do_GET(self):
            path, key = self.route()
            if path == "/maps":
                self.send([{"key": k, "title": m["title"], "build": m["build"]} for k, m in MAPS.items()])
            elif path == "/data":
                if key not in cache:
                    cache[key] = json.dumps(load_data(MAPS[key])).encode()
                self.send(cache[key])
            elif path == "/drive":
                self.send(drives(MAPS[key]["route"]) if MAPS[key].get("route") else [])
            elif path == "/build":
                self.send({"key": Build.key, "lines": Build.lines[-400:], "code": Build.code,
                           "running": bool(Build.proc and Build.proc.poll() is None)})
            elif path == "/png":
                self.send(open(os.path.join(MAPS[key]["out"], "bords_trace.png"), "rb").read(), "image/png")
            else:
                self.send(open(page, "rb").read(), "text/html; charset=utf-8")

        def do_POST(self):
            path, key = self.route()
            m = MAPS[key]
            body = self.rfile.read(int(self.headers.get("Content-Length") or 0))
            if path == "/save":
                t = json.loads(body)
                if len(t["points"]) < 3 or any(len(b["points"]) < 2 for b in t["branches"]):
                    return self.send("il faut au moins 3 points de route et 2 par embranchement", code=400)
                os.makedirs(os.path.dirname(m["track"]), exist_ok=True)
                if os.path.exists(m["track"]):
                    os.replace(m["track"], m["track"] + ".bak")
                json.dump(t, open(m["track"], "w"), indent=1)
                cache.pop(key, None)
                self.send("enregistré : " + m["track"])
            elif path == "/build":
                if not m["build"]:
                    return self.send("construction : Dubaï seulement pour l'instant", code=400)
                ok = Build.start(key)
                self.send("lancée" if ok else "une construction est déjà en cours", code=200 if ok else 409)
            elif path == "/install":
                if Build.key != key or Build.code != 0:
                    return self.send("construire cette map d'abord (sans erreur)", code=400)
                if blur_running():
                    return self.send("Blur est ouvert : le fermer avant d'installer", code=409)
                self.send(install(m))

    ThreadingHTTPServer.allow_reuse_address = False   # Windows would share the port with an editor already open
    try:
        srv = ThreadingHTTPServer(("127.0.0.1", PORT), H)
    except OSError:
        sys.exit("Un éditeur des tracés est déjà ouvert (port %d) : fermer sa fenêtre d'abord." % PORT)
    url = "http://127.0.0.1:%d" % PORT
    print("Tracés Blur 2 :", url)
    webbrowser.open(url)
    srv.serve_forever()


if __name__ == "__main__":
    main()
