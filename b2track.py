"""Éditeur des tracés d'une map Blur 2 (vue de dessus, dans le navigateur) : route principale et chemins secondaires.

python b2track.py [--track FICHIER] [--route 4] [--drive JOURNAL...]   puis http://127.0.0.1:8767
(« Tracés Blur 2.bat » dans Jeux_WII ouvre tout)
Affiche les murs de collision (gris, make_b2_map.wall_points), les passages de conduite (vert, brul2lap.read) et
les tracés avec leurs bords. Point de départ : FICHIER s'il existe, sinon la map du world.json de Map Builder.
Enregistrer écrit FICHIER : {"points": [{x, z, w, h}], "branches": [{from_m, to_m, width, points}]}, relu par
make_b2_map.py --track FICHIER (à la place de --edges / --drive).
Serveur local (127.0.0.1 seulement) : GET / (web/b2track.html), GET /data, POST /save.
"""
import argparse
import glob
import json
import os
import sys
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import config  # noqa: E402
import make_b2_map  # noqa: E402

PORT = 8767
WORLD = os.path.join(config.BMB_GAME, "Blur Map Builder", "maps", "world.json")
TRACK = os.path.join(config.JEUX, "blur2_aid", "dubai", "marina_trace.json")
LOGS = os.path.join(config.JEUX, "blur2_aid", "journaux", "Player_2026-11-10_0*.log")


def load_data(track, route, logs):
    import brul2lap
    if os.path.exists(track):
        t = json.load(open(track))
    else:
        mp = json.load(open(WORLD))["locations"][0]["maps"][0]
        t = {"points": mp["points"], "branches": mp.get("branches") or []}
    P = np.array([(q["x"], q["z"]) for q in t["points"] + [q for b in t["branches"] for q in b["points"]]])
    lo, hi = P.min(0) - 150, P.max(0) + 150
    w = make_b2_map.wall_points(route)[:, [0, 2]]
    w = w[((w > lo) & (w < hi)).all(1)]
    w = np.unique(np.round(w), axis=0)                 # one point per m²: enough to see, light to draw
    d = np.vstack([brul2lap.read(f) for f in logs]) if logs else np.zeros((0, 5))
    d = d[d[:, 4] > 5][:, [1, 3]]
    return {"track": t, "walls": w.ravel().tolist(), "drive": np.round(d, 1).ravel().tolist(), "file": track}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--track", default=TRACK)
    ap.add_argument("--route", type=int, default=4)
    ap.add_argument("--drive", nargs="*", default=sorted(glob.glob(LOGS)))
    a = ap.parse_args()
    data = json.dumps(load_data(a.track, a.route, a.drive)).encode()
    page = open(os.path.join(HERE, "web", "b2track.html"), "rb").read()

    class H(BaseHTTPRequestHandler):
        def send(self, body, ctype):
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            self.send(data if self.path == "/data" else page,
                      "application/json" if self.path == "/data" else "text/html; charset=utf-8")

        def do_POST(self):
            t = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            assert len(t["points"]) >= 3 and all(len(b["points"]) >= 2 for b in t["branches"])
            if os.path.exists(a.track):
                os.replace(a.track, a.track + ".bak")
            json.dump(t, open(a.track, "w"), indent=1)
            print("enregistré :", a.track)
            self.send(b'"ok"', "application/json")

    url = "http://127.0.0.1:%d" % PORT
    print("Tracés Blur 2 :", url, "(fichier", a.track + ")")
    webbrowser.open(url)
    ThreadingHTTPServer(("127.0.0.1", PORT), H).serve_forever()


if __name__ == "__main__":
    main()
