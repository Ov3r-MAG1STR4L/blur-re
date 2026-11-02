"""Reverse Studio : vue 3D d'une route inversée construite, avant de l'essayer en jeu, et verrou des routes validées.

python reverse_web.py [DOSSIER_BUILD]   puis http://127.0.0.1:8766   (défaut : le build reverse_* le plus récent)
Serveur local (127.0.0.1 seulement), lecture seule sur le jeu et le build :
  GET  /                      page web/reverse.html (three.js)
  GET  /api/routes            routes de make_reverse.ROUTES + verrouillée ou non
  GET  /api/route?name=R      collision proche de la route (float32 x y z par sommet, triangles à plat, base64),
                              ligne centrale + largeur (.aid), acteurs des listes clonées (grilles, textes, bonus),
                              sol mesuré en roulant (ground/<orig>.csv), hauteur de collision sous chaque place
  GET  /thumb?name=R          vignette de chargement (ui_frontend.bpr du build) en PNG
  POST /api/edits {name, edits}      retouches (déplacement / rotation) -> blur_extracted/edits/<route>.json
  POST /api/lock, /api/unlock {name}   maplock (verrouille la route telle qu'elle est dans le build affiché)
"""
import base64, glob, io, json, os, sys, threading, urllib.parse, webbrowser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import aidreverse, blurbpr, blurroute, bmb_levelphysics, gridreverse, maplock, make_reverse as MR  # noqa: E402
from blurxt import XT  # noqa: E402

PORT = 8766
NEAR = 60.0           # m : triangles de collision gardés autour de la ligne centrale (tout le niveau = trop lourd)
BUILD = None
_cache = {}


def _city(r):
    return json.load(open(os.path.join(MR.E, "xt_json", "amax.json")))["Route"][r["orig"]]["City"].split("/")[-1].lower()


def clone_usage(r, city):
    """Listes clonées par make_reverse (même choix, même ordre : hash = route + 1 + n) et où la route d'origine
    les utilise : ActorLists = solo, MultiplayerActorLists = multi (la course perso prend la multi)."""
    src = json.load(open(os.path.join(MR.E, "xt_json", "amax.json")))["Route"][r["orig"]]
    A = json.load(open(os.path.join(MR.E, "xt_json", f"{city}.actorpack.json"), encoding="utf-8"))["LevelActorList"]
    used = {}
    for field in ("ActorLists", "MultiplayerActorLists"):
        for ref in src[field]:
            pk, _, lst = ref.split("/")
            acts = [a for a in A.get(lst, {}).get("LevelActors", []) if a]
            if pk == f"{city}.actorpack" and any(gridreverse.is_start_position(a) or "PickupType" in a or
                                                 a.get("Name", "").startswith("Start_Text") for a in acts):
                used.setdefault(lst, set()).add(field)
    return {r["hash"] + 1 + n: (lst, f, "|".join((a or {}).get("Name", "") for a in A[lst]["LevelActors"]))
            for n, (lst, f) in enumerate(used.items())}


def paths(r, city, lvl):
    """Chemins du .aid inversé (sauf la boucle principale, déjà en ruban) + ceux de l'original retirés à
    l'inversion (raccourcis abandonnés pour les IA : toujours roulables par les joueurs)."""
    def read(path):
        d = blurroute.parse(open(path, "rb").read())
        return {s["name"]: [gridreverse._centre(n).tolist() for n in s["nodes"]] for s in d["sections"] if s["nodes"]}
    main = aidreverse.roles(blurroute.parse(open(os.path.join(lvl, r["new"].lower() + ".aid"), "rb").read(),
                                            raw=True))["main"]["name"]
    rev = read(os.path.join(lvl, r["new"].lower() + ".aid"))
    orig = read(os.path.join(MR.G, "levels", city, r["orig"].lower() + ".aid"))
    return ([dict(name=k, pts=v, origin="reverse") for k, v in rev.items() if k not in (main, "Logic")] +
            [dict(name=k, pts=v, origin="original") for k, v in orig.items() if k not in rev and k != "Logic"])


def route_data(name):
    if name in _cache:
        return _cache[name]
    r = next(r for r in MR.ROUTES if r["new"] == name)
    city = _city(r)
    lvl = os.path.join(maplock._files(BUILD), "gamedata", "levels", city)
    P, arc, lat, W, loop = gridreverse._route(os.path.join(lvl, name.lower() + ".aid"))
    # collision : celle du build si make_reverse l'a modifiée (rampes), sinon celle du jeu (lecture seule)
    phys = next(p for p in (os.path.join(maplock._files(BUILD), "levels", city, "Level.levelphysics"),
                            os.path.join(MR.GAME, "levels", city, "Level.levelphysics")) if os.path.isfile(p))
    gf = os.path.join(MR.E, "ground", r["orig"] + ".csv")
    ground = np.loadtxt(gf, delimiter=",", skiprows=1)[:, :3] if os.path.isfile(gf) else np.zeros((0, 3))
    try:
        g = bmb_levelphysics.Ground(phys)
    except AssertionError:      # le lecteur ne lit que les niveaux dont le 1er objet est un maillage (pas Haruna)
        g = None
    if g:
        tri = np.stack([g.A, g.B, g.C], 1)                   # (n, 3, 3)
        c = tri.mean(1)[:, [0, 2]]
        keep = np.zeros(len(tri), bool)
        for i in range(0, len(P), 4):                        # ponytail: balayage O(points x triangles), vectorisé
            keep |= np.hypot(*(c - P[i, [0, 2]]).T) < NEAR
    else:
        tri, keep = np.zeros((0, 3, 3)), np.zeros(0, bool)

    def ground_y(p):
        """Sol sous une place : collision, sinon le point roulé le plus proche (< 4 m), sinon inconnu."""
        if g:
            return g.ground(p[0], p[2], p[1])
        if len(ground):
            dist = np.hypot(ground[:, 0] - p[0], ground[:, 2] - p[2])
            return float(ground[dist.argmin(), 1]) if dist.min() < 4 else None
        return None
    # acteurs des listes clonées ; usage = {hash: (liste source, {ActorLists, MultiplayerActorLists}, noms des acteurs)}
    usage = clone_usage(r, city)
    lists = []
    keys = {n: k for k, n, _ in maplock._lists(os.path.join(lvl, "actorpack.xt"), r["hash"])}
    x = XT(os.path.join(lvl, "actorpack.xt"))
    for n, t, v, h in sorted(x.records(), key=lambda e: e[3]):
        if t != "LevelActorList" or not r["hash"] < h < maplock.hash_top(r["hash"]):
            continue
        acts = []
        for i, a in enumerate(v.get("LevelActors", [])):
            if not a or not a.get("WorldMatrix"):
                continue
            m = a["WorldMatrix"]
            p = [m["aw"][k] for k in ("vx", "vy", "vz")]
            kind = ("grid" if gridreverse.is_start_position(a) else "pickup" if "PickupType" in a else
                    "text" if a.get("Name", "").startswith(("Start_Text", "Finish_Text")) else "other")
            gy = ground_y(p) if kind == "grid" else None
            # place par rapport à la route : nœud le plus proche, écart latéral signé au centre, demi-largeur
            k = int(np.hypot(P[:, 0] - p[0], P[:, 2] - p[2]).argmin())
            off = float((p[0] - P[k, 0]) * lat[k][0] + (p[2] - P[k, 2]) * lat[k][1])
            road = dict(offset=off, half=float(W[k] / 2), dy=float(p[1] - P[k, 1]))
            acts.append(dict(i=str(i), name=a.get("Name", ""), kind=kind, pos=p, fwd=[m["az"][k] for k in ("vx", "vy", "vz")],
                             start=a.get("StartNumber"), pickup=a.get("PickupType"), ground=gy, road=road))
        sig = "|".join((a or {}).get("Name", "") for a in v.get("LevelActors", []))
        use = usage.get(h)
        # solo / multi : sûr seulement si la liste source de ce hash a les mêmes acteurs (sinon build plus ancien)
        lists.append(dict(record=n, key=keys[n], hash=f"{h:#x}", actors=acts,
                          fields=sorted(use[1]) if use and use[2] == sig else []))
    d = dict(name=name, orig=r["orig"], city=city, loop=bool(loop), locked=maplock.locked(name),
             centre=P.tolist(), width=W.tolist(), lateral=lat.tolist(), lists=lists, ground=ground[::5].tolist(), collision=g is not None,
             paths=paths(r, city, lvl),
             # y d'un nœud .aid = bas de son volume (ylow), pas le bitume : places 3 à 14 m plus haut selon la route.
             # Le studio remonte route et chemins de l'écart médian des places (hauteur ESTIMÉE, pour la lecture)
             road_dy=float(np.median([a["road"]["dy"] for l in lists for a in l["actors"] if a["kind"] == "grid"] or [0])),
             tris=base64.b64encode(tri[keep].astype(np.float32).tobytes()).decode(), n_tris=int(keep.sum()))
    _cache[name] = d
    return d


def with_edits(d):
    ef = os.path.join(maplock.EDITS, d["name"] + ".json")
    return dict(d, edits=json.load(open(ef)) if os.path.isfile(ef) else {})


def thumb_png(name):
    from PIL import Image
    bpr = blurbpr.Bpr(os.path.join(maplock._files(BUILD), "ui", "data", "ui_frontend.bpr"))
    img = bpr.image(name)
    out = io.BytesIO()
    (img if isinstance(img, Image.Image) else Image.fromarray(np.asarray(img))).save(out, "PNG")
    return out.getvalue()


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **k):
        super().__init__(*a, directory=os.path.join(HERE, "web"), **k)

    def log_message(self, *a):
        pass

    def send_bytes(self, b, ctype, code=200):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def send_json(self, obj, code=200):
        self.send_bytes(json.dumps(obj).encode(), "application/json", code)

    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        q = {k: v[0] for k, v in urllib.parse.parse_qs(u.query).items()}
        try:
            if u.path == "/":
                self.path = "/reverse.html"
            elif u.path == "/api/routes":
                return self.send_json(dict(build=os.path.abspath(BUILD), routes=[
                    dict(name=r["new"], orig=r["orig"], locked=maplock.locked(r["new"])) for r in MR.ROUTES]))
            elif u.path == "/api/route":
                return self.send_json(with_edits(route_data(q["name"])))
            elif u.path == "/thumb":
                return self.send_bytes(thumb_png(q["name"]), "image/png")
        except Exception as ex:  # noqa: BLE001  (l'erreur complète part dans la page)
            return self.send_json({"error": f"{type(ex).__name__}: {ex}"}, 500)
        return super().do_GET()

    def do_POST(self):
        u = urllib.parse.urlparse(self.path)
        q = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0) or 0)))
        name = q["name"]
        try:
            if u.path == "/api/edits":         # retouches : appliquées par make_reverse au prochain build
                if maplock.locked(name):
                    raise ValueError(f"{name} est verrouillée : la déverrouiller avant de la retoucher")
                os.makedirs(maplock.EDITS, exist_ok=True)
                ef = os.path.join(maplock.EDITS, name + ".json")
                if q["edits"]:
                    json.dump(q["edits"], open(ef, "w"), indent=1)
                elif os.path.isfile(ef):
                    os.remove(ef)
                return self.send_json({"ok": True})
            if u.path == "/api/lock":
                maplock.lock(name, BUILD)
            elif u.path == "/api/unlock":
                os.remove(os.path.join(maplock.LOCKS, name + ".json"))
            _cache.pop(name, None)
            return self.send_json({"ok": True, "locked": maplock.locked(name)})
        except (Exception, SystemExit) as ex:  # noqa: BLE001
            return self.send_json({"error": str(ex)}, 500)


if __name__ == "__main__":
    BUILD = sys.argv[1] if len(sys.argv) > 1 else max(
        (d for d in glob.glob(os.path.join(MR.E, "mods", "reverse*")) if os.path.isdir(d)), key=os.path.getmtime)
    print("build :", os.path.abspath(BUILD))
    srv = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print("Reverse Studio : http://127.0.0.1:%d  (Ctrl+C pour arrêter)" % PORT)
    threading.Timer(1.0, lambda: webbrowser.open("http://127.0.0.1:%d" % PORT)).start()
    srv.serve_forever()
