"""Verrou des routes inversées validées en jeu : un passage global de make_reverse ne peut plus les changer.

python maplock.py lock   ROUTE DOSSIER_MOD   fige ROUTE telle qu'elle est dans DOSSIER_MOD (<mod>/files ou build)
python maplock.py unlock ROUTE               enlève le verrou
python maplock.py list                       routes verrouillées
python maplock.py check  DOSSIER_MOD         compare un build aux verrous (rien n'est écrit)

Ce qui est figé (ce qui appartient à UNE route ; amax.bin, le .bpr, les .ipf sont partagés par toutes) :
  - son .aid (levels/<ville>/<route>.aid), copié tel quel ;
  - les WorldMatrix de ses listes d'acteurs clonées (grilles solo / multi, textes de ligne, bonus), retrouvées par
    leur hash (route + 1 + n, fixe d'un build à l'autre) dans levels/<ville>/actorpack.xt.
make_reverse appelle apply_edits() (retouches de Reverse Studio) puis restore() après avoir calculé chaque route : une route verrouillée ressort à l'identique.
"""
import base64, glob, hashlib, json, os, struct, sys

from blurxt import XT

LOCKS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "blur_extracted", "locks")   # hors dépôt : .aid de ~2 Mo
EDITS = os.path.join(os.path.dirname(LOCKS), "edits")      # retouches de Reverse Studio, une fiche par route
ROWS = ("ax", "ay", "az", "aw")


def _files(mod):
    return os.path.join(mod, "files") if os.path.isdir(os.path.join(mod, "files")) else mod


def _route(new):
    import make_reverse
    return next(r for r in make_reverse.ROUTES if r["new"] == new)


def _lists(ap, base):
    """Listes clonées de la route (hash base+1 .. base+0xFF), dans l'ordre des hash : [(clé, nom, {index: WorldMatrix})].
    clé = noms des acteurs + n° d'occurrence : l'ordre des hash change quand make_reverse clone d'autres listes
    (bonus ajoutés le 2026-10-26), les noms des acteurs non ; deux listes aux mêmes noms (solo / multi) : 0 et 1."""
    out, seen = [], {}
    for n, t, v, h in sorted(XT(ap).records(), key=lambda e: e[3]):
        if t == "LevelActorList" and base < h <= base + 0xFF:
            acts = v.get("LevelActors", [])
            sig = "|".join((a or {}).get("Name", "") for a in acts)
            seen[sig] = seen.get(sig, -1) + 1
            out.append((f"{seen[sig]}:{sig}", n, {str(i): a["WorldMatrix"] for i, a in enumerate(acts)
                                                  if a and a.get("WorldMatrix")}))
    return out


def _find(mod, new):
    aid = glob.glob(os.path.join(_files(mod), "gamedata", "levels", "*", new.lower() + ".aid"))
    if len(aid) != 1:
        raise SystemExit(f"{new} : .aid introuvable dans {mod}")
    return aid[0], os.path.join(os.path.dirname(aid[0]), "actorpack.xt")


def locked(new):
    return os.path.isfile(os.path.join(LOCKS, new + ".json"))


def lock(new, mod):
    r = _route(new)
    aid, ap = _find(mod, new)
    lists = _lists(ap, r["hash"])
    if not lists:
        raise SystemExit(f"{new} : aucune liste clonée (hash {r['hash']:#x}) dans {ap}")
    os.makedirs(LOCKS, exist_ok=True)
    raw = open(aid, "rb").read()
    json.dump(dict(route=new, source=os.path.abspath(mod), aid=base64.b64encode(raw).decode(),
                   aid_sha256=hashlib.sha256(raw).hexdigest(), lists={k: m for k, _, m in lists}),
              open(os.path.join(LOCKS, new + ".json"), "w"))
    print(f"{new} verrouillé : .aid {len(raw)} o, {len(lists)} listes, {sum(len(m) for *_, m in lists)} acteurs")


def _write(ap_path, by_record):
    """Écrit des WorldMatrix dans un actorpack : {nom d'enregistrement: {index d'acteur: matrice}}."""
    x = XT(ap_path)
    buf = bytearray(x.b)
    for name, acts in by_record.items():
        # XT.locate relit tout le fichier : un appel par acteur (les acteurs ne sont pas contigus), les 12 valeurs
        # de sa matrice aux mêmes écarts que dans le 1er acteur
        i0 = next(iter(acts))
        first = {(row, c): x.locate(name, f"LevelActors[{i0}].WorldMatrix.{row}.{c}")[0]
                 for row in ROWS for c in ("vx", "vy", "vz")}
        for i, m in acts.items():
            o = x.locate(name, f"LevelActors[{i}].WorldMatrix.ax.vx")[0] - first["ax", "vx"]
            for (row, c), off in first.items():
                struct.pack_into("<f", buf, off + o, m[row][c])
    open(ap_path, "wb").write(buf)


def edited(new):
    return os.path.isfile(os.path.join(EDITS, new + ".json"))


def apply_edits(new, ap_path, base_hash):
    """Retouches faites dans Reverse Studio (edits/<route>.json : {clé de liste: {index: {pos, yaw}}}) :
    position (aw) remplacée, axes ax / az tournés de `yaw` radians autour de la verticale."""
    import math
    d = json.load(open(os.path.join(EDITS, new + ".json")))
    now = {k: (n, m) for k, n, m in _lists(ap_path, base_hash)}
    out = {}
    for k, acts in d.items():
        if k not in now:
            raise SystemExit(f"{new} : retouches sur une liste qui n'existe plus ({k[:40]}…) : refaire les retouches")
        name, mats = now[k]
        for i, e in acts.items():
            m = json.loads(json.dumps(mats[i]))
            c, s_ = math.cos(e["yaw"]), math.sin(e["yaw"])
            for row in ("ax", "az"):
                vx, vz = m[row]["vx"], m[row]["vz"]
                m[row]["vx"], m[row]["vz"] = c * vx + s_ * vz, -s_ * vx + c * vz
            m["aw"] = dict(zip(("vx", "vy", "vz"), e["pos"]))
            out.setdefault(name, {})[i] = m
    _write(ap_path, out)
    print(new, "retouches appliquées :", sum(map(len, out.values())), "acteurs")


def restore(new, aid_path, ap_path, base_hash):
    """Remet la route verrouillée (son .aid, ses grilles et bonus) dans un build en cours."""
    d = json.load(open(os.path.join(LOCKS, new + ".json")))
    now = {k: n for k, n, _ in _lists(ap_path, base_hash)}
    missing = set(d["lists"]) - set(now)
    if missing:
        raise SystemExit(f"{new} verrouillée mais ses listes ont changé ({len(missing)}) : maplock.py unlock {new}")
    open(aid_path, "wb").write(base64.b64decode(d["aid"]))
    _write(ap_path, {now[k]: acts for k, acts in d["lists"].items()})
    print(new, "VERROUILLÉE : .aid, grilles et bonus remis à l'identique")


def check(mod):
    """Routes verrouillées qui diffèrent dans le build `mod` (vide = tout est conforme)."""
    bad = []
    for f in sorted(glob.glob(os.path.join(LOCKS, "*.json"))):
        d = json.load(open(f))
        aid, ap = _find(mod, d["route"])
        now = {k: m for k, _, m in _lists(ap, _route(d["route"])["hash"])}
        same_aid = hashlib.sha256(open(aid, "rb").read()).hexdigest() == d["aid_sha256"]
        same = all(k in now and abs(now[k][i][row][c] - m[row][c]) < 1e-4
                   for k, acts in d["lists"].items() for i, m in acts.items() for row in ROWS for c in ("vx", "vy", "vz"))
        print(d["route"], "OK" if same_aid and same else
              f"DIFFÉRENT (aid {'ok' if same_aid else 'changé'}, grilles/bonus {'ok' if same else 'changés'})")
        if not (same_aid and same):
            bad.append(d["route"])
    return bad


if __name__ == "__main__":
    cmd, *args = sys.argv[1:] or ["list"]
    if cmd == "lock":
        lock(*args)
    elif cmd == "unlock":
        os.remove(os.path.join(LOCKS, args[0] + ".json"))
        print(args[0], "déverrouillé")
    elif cmd == "check":
        sys.exit(1 if check(args[0]) else 0)
    else:
        for f in sorted(glob.glob(os.path.join(LOCKS, "*.json"))):
            print(os.path.basename(f)[:-5], "<-", json.load(open(f))["source"])
