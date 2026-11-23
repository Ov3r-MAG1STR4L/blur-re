#!/usr/bin/env python3
"""Capture de position en jeu (touche Inser), lecture seule de la mémoire de Blur. Ne modifie aucune donnée du jeu.

Touches (lues en arrière-plan avec GetAsyncKeyState : le jeu garde le focus, pas de pause) :
  Inser  capturer la voiture du joueur          (bip aigu = enregistré, bip grave = pas en course / erreur)
  Début  dernière capture = « bloquant »    Fin = « traversable »    Pg.Préc = « anormal »
  (F9 et F5-F7 servent déjà dans Blur ; touches à changer dans KEYS)
Les commentaires s'ajoutent après coup (le jeu se met en pause dès qu'on clique ailleurs, ce n'est pas grave) :
  poscapture.py                       écoute (lancé par « Capturer position.bat »)
  poscapture.py liste                 sessions et captures
  poscapture.py annoter CHEMIN RESULTAT [commentaire...]   RESULTAT : bloquant | traversable | anormal | inconnu | -
  poscapture.py classer CHEMIN CIRCUIT   déplace une capture non identifiée vers un circuit (nouvelle session « reclassement »)
  poscapture.py export                captures/captures_toutes.csv (toutes les sessions, régénéré)
  poscapture.py test                  auto-test hors jeu (dossier temporaire)

Rangement : captures/<Circuit>/session_AAAA-MM-JJ_HH-MM-SS/capture_NNN.json. Une session par circuit et par
lancement du programme ; rien n'est jamais écrasé (création exclusive). Circuit : route installée dans la copie du
jeu qui tourne (en-tête de amax/dlls/b2gravity.txt) ET voiture à moins de PRES m de son tracé ; sinon
Non_identifie (avec le circuit supposé et la distance), à reclasser avec « classer ».
Lecture mémoire : blur_live.chain (chaîne validée en jeu le 2026-10-18) ; matrice +0xCC (AX, haut +0xD8, avant +0xE4).
"""
import ctypes, csv, glob, json, math, os, re, struct, sys, tempfile, time, uuid
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import config  # noqa: E402

ROOT = os.path.join(HERE, "captures")
AID = os.path.join(config.JEUX, "blur2_aid", "dubai")
ORIGINAL = os.path.normcase(r"C:\Program Files (x86)\Activision")      # installation d'origine : refusée
CIRCUITS = {1: "Business_Bay", 2: "Dubai_Island", 3: "Construction", 4: "Marina"}
TRACES = {1: "dubai_route1_trace.json", 2: "dubai_route2_trace.json", 3: "dubai_route3_trace.json",
          4: "marina_trace.json"}
UNKNOWN = "Non_identifie"
PRES = 60.0                                                            # m (x, z) du tracé pour identifier
KEYS = {0x2D: "capture", 0x24: "bloquant", 0x23: "traversable", 0x21: "anormal"}   # Inser, Début, Fin, Pg.Préc
RESULTS = ("bloquant", "traversable", "anormal", "inconnu")


# ---------- lecture du jeu (lecture seule) ----------
def exe_path(pm):
    buf, n = ctypes.create_unicode_buffer(1024), ctypes.c_ulong(1024)
    ctypes.windll.kernel32.QueryFullProcessImageNameW(pm.process_handle, 0, buf, ctypes.byref(n))
    return buf.value


def attach():
    """(pymem, chemin de l'exe) du jeu lancé, ou (None, raison)"""
    import pymem
    for name in ("Blur.exe", "Blur REBORN.exe"):
        try:
            pm = pymem.Pymem(name)
        except Exception:
            continue
        path = exe_path(pm)
        if os.path.normcase(path).startswith(ORIGINAL):
            return None, "jeu lancé depuis l'installation d'origine (%s) : refusé, utiliser une copie de test" % path
        return pm, path
    return None, "Blur n'est pas lancé"


def read_player(pm):
    """état de la voiture du joueur, ou lève RuntimeError (pas en course)"""
    import blur_live
    R = blur_live.chain(pm)
    if not R:
        raise RuntimeError("pas en course (chaîne nulle)")
    n = pm.read_uint(R + 0x1A0)
    me = pm.read_bytes(R + 0x2EC, 1)[0]
    if not 0 < n <= 20 or me >= n:
        raise RuntimeError("liste des véhicules incohérente (%d voitures, joueur %d)" % (n, me))
    v = pm.read_uint(R + 0x68 + me * 0x10)
    m = struct.unpack("<9f", pm.read_bytes(v + 0xCC, 36))
    x, y, z, vx, vy, vz = struct.unpack("<6f", pm.read_bytes(v + 0x130, 24))
    return {"x": x, "y": y, "z": z, "axes": {"lateral": m[0:3], "haut": m[3:6], "avant": m[6:9]},
            "vitesse_ms": [vx, vy, vz], "vehicules": n, "index_joueur": me}


def installed_route(exe):
    """route de Dubaï installée dans le dossier de cet exe (en-tête de b2gravity.txt), ou None"""
    try:
        head = open(os.path.join(os.path.dirname(exe), "amax", "dlls", "b2gravity.txt"),
                    encoding="utf-8", errors="replace").readline()
    except OSError:
        return None
    m = re.search(r"Dubai route (\d+)", head)
    return int(m.group(1)) if m else None


_traces = {}


def trace_distance(route, x, z):
    """distance (x, z) au tracé de la route (points + embranchements), ou None sans tracé"""
    if route not in _traces:
        try:
            d = json.load(open(os.path.join(AID, TRACES[route]), encoding="utf-8"))
            pts = [(p["x"], p["z"]) for p in d.get("points", [])]
            for b in d.get("branches", []) or []:
                pts += [(p["x"], p["z"]) for p in b.get("points", []) if isinstance(p, dict)]
            _traces[route] = pts
        except (OSError, KeyError, ValueError):
            _traces[route] = []
    pts = _traces[route]
    return min(math.hypot(px - x, pz - z) for px, pz in pts) if pts else None


def identify(route, x, z):
    """(dossier du circuit, statut, détail)"""
    if route not in CIRCUITS:
        return UNKNOWN, "non_identifie", "aucune route de Dubaï installée dans cette copie"
    d = trace_distance(route, x, z)
    if d is None:
        return UNKNOWN, "non_identifie", "tracé de %s introuvable" % CIRCUITS[route]
    if d <= PRES:
        return CIRCUITS[route], "identifie", "route installée %d, %.0f m du tracé" % (route, d)
    return UNKNOWN, "non_identifie", "route installée %d mais %.0f m du tracé (menu, garage, hors piste ?)" % (route, d)


# ---------- archivage ----------
def write_new(path, data):
    """création exclusive : n'écrase jamais (FileExistsError sinon)"""
    with open(path, "x", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)


def rewrite(path, data):
    """mise à jour d'une capture existante (annotation) : fichier temporaire puis remplacement"""
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


class Archive:
    def __init__(self, root=ROOT):
        self.root, self.sessions = root, {}           # circuit -> dossier de session de ce lancement

    def session(self, circuit, label=""):
        if circuit not in self.sessions:
            base = os.path.join(self.root, circuit, "session_" + datetime.now().strftime("%Y-%m-%d_%H-%M-%S") + label)
            d, k = base, 2
            os.makedirs(os.path.dirname(base), exist_ok=True)
            while True:
                try:
                    os.mkdir(d)
                    break
                except FileExistsError:
                    d, k = "%s_%d" % (base, k), k + 1
            self.sessions[circuit] = d
        return self.sessions[circuit]

    def add(self, circuit, data, label=""):
        d = self.session(circuit, label)
        while True:
            n = 1 + max([int(m.group(1)) for f in os.listdir(d) for m in [re.match(r"capture_(\d+)\.json$", f)] if m],
                        default=0)
            path = os.path.join(d, "capture_%03d.json" % n)
            data.update(numero=n, session=os.path.basename(d), circuit=circuit)
            try:
                write_new(path, data)
                return path
            except FileExistsError:
                continue


def make_record(state, exe, route):
    circuit, statut, detail = identify(route, state["x"], state["z"])
    ax = state["axes"]["avant"]
    vx, vy, vz = state["vitesse_ms"]
    return circuit, {
        "id": uuid.uuid4().hex, "date": datetime.now().isoformat(timespec="seconds"),
        "circuit": circuit, "statut_circuit": statut, "detail_circuit": detail,
        "circuit_suppose": CIRCUITS.get(route), "jeu": exe,
        "x": round(state["x"], 3), "y": round(state["y"], 3), "z": round(state["z"], 3),
        "cap_deg": round(math.degrees(math.atan2(ax[0], ax[2])) % 360, 1),
        "axes": {k: [round(c, 4) for c in v] for k, v in state["axes"].items()},
        "vitesse_kmh": round(math.sqrt(vx * vx + vy * vy + vz * vz) * 3.6, 1),
        "vitesse_ms": [round(c, 3) for c in state["vitesse_ms"]],
        "vehicules": state["vehicules"], "index_joueur": state["index_joueur"],
        "resultat": "inconnu", "commentaire": "",
    }


def all_captures(root=ROOT):
    return sorted(glob.glob(os.path.join(root, "*", "session_*", "capture_*.json")))


def export(root=ROOT):
    cols = ["circuit", "session", "numero", "id", "date", "statut_circuit", "circuit_suppose", "x", "y", "z",
            "cap_deg", "vitesse_kmh", "resultat", "commentaire", "detail_circuit", "fichier"]
    out = os.path.join(root, "captures_toutes.csv")
    rows = []
    for p in all_captures(root):
        d = json.load(open(p, encoding="utf-8"))
        d["fichier"] = os.path.relpath(p, root)
        rows.append(d)
    with open(out, "w", newline="", encoding="utf-8-sig") as f:      # utf-8-sig : lisible tel quel dans Excel
        w = csv.DictWriter(f, cols, extrasaction="ignore", delimiter=";")
        w.writeheader()
        w.writerows(rows)
    return out, len(rows)


# ---------- écoute ----------
def beep(ok):
    try:
        import winsound
        winsound.Beep(1400 if ok else 300, 120 if ok else 400)
    except Exception:
        pass


def listen():
    arc, last = Archive(), None
    get = ctypes.windll.user32.GetAsyncKeyState
    down = {k: False for k in KEYS}
    print("Capture de position : Inser capturer | Début bloquant, Fin traversable, Pg.Préc anormal (dernière capture)")
    print("Dossier :", ROOT, "\nCtrl+C pour arrêter.")
    while True:
        for k, what in KEYS.items():
            now = bool(get(k) & 0x8000)
            if now and not down[k]:
                if what == "capture":
                    last = do_capture(arc) or last
                elif last:
                    d = json.load(open(last, encoding="utf-8"))
                    d["resultat"] = what
                    rewrite(last, d)
                    print("   -> %s : %s" % (os.path.relpath(last, ROOT), what))
                    beep(True)
                else:
                    print("   pas encore de capture à annoter"); beep(False)
            down[k] = now
        time.sleep(0.02)


def do_capture(arc):
    pm, exe = attach()
    if not pm:
        print(time.strftime("%H:%M:%S"), exe); beep(False); return None
    try:
        state = read_player(pm)
    except Exception as e:
        print(time.strftime("%H:%M:%S"), "pas de capture :", e); beep(False); return None
    circuit, rec = make_record(state, exe, installed_route(exe))
    path = arc.add(circuit, rec)
    print("%s  %s  (%.1f ; %.1f ; %.1f)  cap %.0f°  %.0f km/h  [%s]" % (
        time.strftime("%H:%M:%S"), os.path.relpath(path, ROOT), rec["x"], rec["y"], rec["z"], rec["cap_deg"],
        rec["vitesse_kmh"], rec["detail_circuit"]))
    beep(True)
    return path


# ---------- commandes ----------
def resolve(p):
    q = p if os.path.isabs(p) else os.path.join(ROOT, p)
    if not os.path.isfile(q):
        sys.exit("capture introuvable : %s" % p)
    return q


def main(argv):
    cmd = argv[0] if argv else "ecoute"
    if cmd == "ecoute":
        try:
            listen()
        except KeyboardInterrupt:
            print("arrêté ; export :", *export())
    elif cmd == "liste":
        cur = None
        for p in all_captures():
            d = json.load(open(p, encoding="utf-8"))
            s = os.path.dirname(os.path.relpath(p, ROOT))
            if s != cur:
                print(s); cur = s
            print("   %03d  %s  (%.1f ; %.1f ; %.1f)  %5.0f km/h  %-11s %s" % (
                d["numero"], d["date"][11:], d["x"], d["y"], d["z"], d["vitesse_kmh"], d["resultat"], d["commentaire"]))
    elif cmd == "annoter":
        path, res = resolve(argv[1]), argv[2]
        if res != "-" and res not in RESULTS:
            sys.exit("résultat : " + " | ".join(RESULTS) + " | -")
        d = json.load(open(path, encoding="utf-8"))
        if res != "-":
            d["resultat"] = res
        if argv[3:]:
            d["commentaire"] = " ".join(argv[3:])
        rewrite(path, d)
        print("annotée :", os.path.relpath(path, ROOT))
    elif cmd == "classer":
        path, circuit = resolve(argv[1]), argv[2]
        if circuit not in CIRCUITS.values():
            sys.exit("circuit : " + " | ".join(CIRCUITS.values()))
        d = json.load(open(path, encoding="utf-8"))
        d.update(statut_circuit="classe_a_la_main", origine=os.path.relpath(path, ROOT))
        new = Archive().add(circuit, d, label="_reclassement")
        os.remove(path)
        print("déplacée :", os.path.relpath(new, ROOT))
    elif cmd == "export":
        print("%s (%d captures)" % export())
    elif cmd == "test":
        selftest()
    else:
        sys.exit(__doc__)


def selftest():
    """hors jeu : identification, numérotation, sessions uniques, jamais d'écrasement, annotation, export"""
    tmp = tempfile.mkdtemp()
    st = {"x": 36.0, "y": 5.0, "z": -155.0, "axes": {"lateral": (1, 0, 0), "haut": (0, 1, 0), "avant": (0, 0, 1)},
          "vitesse_ms": [0.0, 0.0, 10.0], "vehicules": 2, "index_joueur": 0}
    c, r = make_record(dict(st), "x", 1)
    assert c == "Business_Bay" and r["statut_circuit"] == "identifie", r["detail_circuit"]
    assert r["vitesse_kmh"] == 36.0 and r["cap_deg"] == 0.0
    assert make_record(dict(st, x=5000.0), "x", 1)[0] == UNKNOWN
    assert make_record(dict(st), "x", None)[0] == UNKNOWN
    a = Archive(tmp)
    p1, p2 = a.add(c, dict(r)), a.add(c, dict(r))
    assert p1.endswith("capture_001.json") and p2.endswith("capture_002.json") and os.path.dirname(p1) == os.path.dirname(p2)
    b = Archive(tmp)                                         # 2e lancement dans la même seconde : autre session
    p3 = b.add(c, dict(r))
    assert os.path.dirname(p3) != os.path.dirname(p1) and p3.endswith("capture_001.json")
    try:
        write_new(p1, {}); raise AssertionError("écrasement possible")
    except FileExistsError:
        pass
    d = json.load(open(p1, encoding="utf-8")); d["resultat"] = "bloquant"; rewrite(p1, d)
    out, n = export(tmp)
    assert n == 3 and "bloquant" in open(out, encoding="utf-8-sig").read()
    print("auto-test OK (%s)" % tmp)


if __name__ == "__main__":
    main(sys.argv[1:])
