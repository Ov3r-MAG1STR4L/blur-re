#!/usr/bin/env python3
"""Tracé principal + chemins secondaires d'une route de Dubaï depuis une partie roulée dans Blur2DubaiTest.

Protocole de conduite (2026-11-23) : un tour complet par le chemin principal, puis chaque chemin secondaire une fois,
sans s'arrêter (Lancer avec enregistrement.bat, positions toutes les 0,25 s).
  1. positions du Player.log (axes du jeu, comme brul2lap) ; coupures aux téléportations (> 40 m en un pas : R,
     réapparition) ; chutes repérées (descente > 15 m sous le point le plus bas du tour, puis téléportation) ;
  2. tour principal = premier tour trouvé par brul2lap.laps (retour à 15 m du départ après > 1 500 m) ;
  3. chemins secondaires = morceaux du reste de la partie à plus de FAR m (3D) du tour principal, prolongés jusqu'aux
     points à moins de NEAR m (embranchement et retour), longs d'au moins MIN_LEN m ; un morceau qui repasse sur
     un chemin déjà gardé est ignoré ; from_m / to_m = positions des deux bouts projetées sur le tracé principal ;
  4. recalage de tout sur les routes 17f (b2recale.recale_line, niveau choisi d'après la partie roulée).
Sortie (n'écrase pas le tracé utilisé par les builds) : blur2_aid/dubai/<tracé>_v2.json, même format que les tracés
de l'éditeur (+ « controle » par point, « chutes »). h = y - le plus bas du tour d'origine (comme make_b2_map).

usage: b2paths.py ROUTE PLAYER.log
"""
import json, os, sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import b2recale, brul2lap  # noqa: E402

FAR, NEAR, MIN_LEN, JUMP = 15.0, 6.0, 80.0, 40.0


def read_all(path):
    """comme brul2lap.read, sans retirer les chutes : (t, x, y, z, kmh) en axes du jeu"""
    rows = []
    for line in open(path, encoding="utf-8", errors="replace"):
        m = brul2lap.RX.search(line)
        if m:
            t = float(m[1].replace(",", "."))
            x, y, z, vx, vy, vz = map(float, m.groups()[1:])
            rows.append((t, -x, y, -z, 3.6 * (vx * vx + vy * vy + vz * vz) ** .5))
    return np.array(rows)


def cumlen(P):
    return np.r_[0, np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))]


def falls(a, main_low):
    """[(x, y, z) du dernier point avant la chute, hauteur atteinte)] : descente sous la route puis téléportation"""
    out, i = [], 1
    xyz = a[:, 1:4]
    while i < len(a):
        if xyz[i, 1] < main_low - 15:
            j = i
            while j > 0 and xyz[j - 1, 1] - xyz[j, 1] > 0.3:     # remonte la descente
                j -= 1
            k = i
            while k + 1 < len(a) and np.linalg.norm(xyz[k + 1] - xyz[k]) < JUMP:
                k += 1
            out.append((xyz[max(j - 1, 0)].round(1).tolist(), float(xyz[i:k + 1, 1].min().round(1))))
            i = k + 1
        else:
            i += 1
    return out


def branches(a, main, s, e):
    """morceaux du reste de la partie loin du tour principal"""
    from scipy.spatial import cKDTree
    xyz = a[:, 1:4]
    d, _ = cKDTree(main).query(xyz)
    jump = np.r_[False, np.linalg.norm(np.diff(xyz, axis=0), axis=1) > JUMP]
    rest = np.ones(len(a), bool)
    rest[s:e + 1] = False
    found, i = [], 0
    while i < len(a):
        if not (rest[i] and d[i] > FAR):
            i += 1
            continue
        j = i
        while j + 1 < len(a) and rest[j + 1] and d[j + 1] > NEAR and not jump[j + 1]:
            j += 1
        k0 = i
        while k0 > 0 and rest[k0 - 1] and d[k0 - 1] > NEAR and not jump[k0]:
            k0 -= 1
        k0, k1 = max(k0 - 1, 0), min(j + 1, len(a) - 1)
        seg = xyz[k0:k1 + 1]
        ok = (d[k0] <= NEAR and d[k1] <= NEAR and not jump[k0 + 1:k1 + 1].any() and cumlen(seg)[-1] >= MIN_LEN)
        if ok and not any(np.median(cKDTree(f).query(seg)[0]) < 10 for f in found):
            found.append(seg)
        i = j + 1
    return found


def main(route, log):
    import b2collision, b2track, make_b2_map
    tf, lf = b2recale.ROUTES[route]
    raw = b2track.read_lap(os.path.join(b2recale.AID, lf))
    low = min(p[1] for p in make_b2_map.resample(raw, make_b2_map.STEP))
    a = read_all(log)
    keep = np.where(a[:, 2] > -50)[0]
    lp = brul2lap.laps(a[keep])
    if not lp:
        sys.exit("aucun tour complet trouvé dans %s" % log)
    # plusieurs tours roulés, chacun par un chemin différent (partie du 2026-11-23) : le principal = celui qui
    # recouvre le mieux le tour d'origine (grille et builds actuels) ; les autres fournissent les chemins secondaires
    from scipy.spatial import cKDTree
    old = cKDTree(np.array(raw)[:, [0, 2]])

    def match(l):
        m = a[keep[l[0]]:keep[l[1]] + 1, [1, 3]]
        return (old.query(m)[0] < 15).mean() + (cKDTree(m).query(np.array(raw)[:, [0, 2]])[0] < 15).mean()
    s, e, length = max(lp, key=match)
    s, e = int(keep[s]), int(keep[e])
    main_xyz = a[s:e + 1, 1:4]
    pts = np.array(make_b2_map.resample([tuple(p) for p in main_xyz], make_b2_map.STEP))
    main_pts = [{"x": round(float(x), 2), "z": round(float(z), 2), "w": make_b2_map.WIDTH, "h": round(float(y - low), 2)}
                for x, y, z in pts]
    cum = cumlen(pts[:, [0, 2]])
    total = cum[-1] + float(np.hypot(*(pts[0, [0, 2]] - pts[-1, [0, 2]])))
    bs = []
    for seg in branches(a, main_xyz, s, e):
        sp = np.array(make_b2_map.resample([tuple(p) for p in seg], make_b2_map.STEP))
        i0, i1 = (int(np.argmin(np.hypot(*(pts[:, [0, 2]] - sp[k, [0, 2]]).T))) for k in (0, -1))
        fm, tm = float(cum[i0]), float(cum[i1])
        if tm < fm:
            tm += total
        bs.append({"from_m": round(fm), "to_m": round(tm), "width": make_b2_map.WIDTH,
                   "points": [{"x": round(float(x), 2), "z": round(float(z), 2), "w": make_b2_map.WIDTH,
                               "h": round(float(y - low), 2)} for x, y, z in sp], "longueur_m": round(cumlen(sp)[-1])})
    F = b2recale.Floors(b2collision.colliders(b2recale.UNITY))
    lap_all = a[keep][:, 1:4]
    rp, rc = b2recale.recale_line(F, main_pts, low, lap_all, closed=True)
    out = {"points": rp, "controle": rc, "branches": [],
           "chutes": [{"depart": p, "y_min": y} for p, y in falls(a, float(main_xyz[:, 1].min()))]}
    for b in bs:
        bp, bc = b2recale.recale_line(F, b["points"], low, lap_all, closed=False)
        out["branches"].append(dict(b, points=bp, controle=bc))
    out["note"] = ("b2paths %s : tour principal %.0f m (positions %d-%d), %d chemins secondaires, recalés sur les "
                   "routes 17f" % (os.path.basename(log), length, s, e, len(bs)))
    dst = os.path.join(b2recale.AID, tf.replace(".json", "_v2.json"))
    json.dump(out, open(dst, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    allc = rc + [c for b in out["branches"] for c in b["controle"]]
    print("route %d : tour %.0f m, %d points ; %d chemins secondaires %s ; points sans route %d, déplacés > 8 m %d ;"
          " chutes %d -> %s" % (route, length, len(rp), len(bs),
                                [(b["from_m"], b["to_m"], b["longueur_m"]) for b in bs],
                                sum("sans_route" in c["drapeaux"] for c in allc),
                                sum("deplace" in c["drapeaux"] for c in allc), len(out["chutes"]),
                                os.path.basename(dst)))
    for c in out["chutes"]:
        p = c["depart"]
        h = F.heights(p[0], p[2])
        print("   chute depuis (%.0f ; %.0f ; %.0f) jusqu'à y %.0f ; sols de route 17f sous ce point : %s" % (
            p[0], p[1], p[2], c["y_min"], ", ".join("%.1f" % v for v in sorted(h)) or "aucun"))


if __name__ == "__main__":
    main(int(sys.argv[1]), sys.argv[2])
