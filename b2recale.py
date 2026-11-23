#!/usr/bin/env python3
"""Recale les tracés de Dubaï sur les routes (colliders 17f / 8017f à plat) en suivant les tours roulés dans Unity.

Pour chaque point du tracé actuel (principal et embranchements) :
  1. niveau : parmi les sols de route sous (x, z), celui le plus proche de la hauteur du tour roulé (point du tour le
     plus proche à <= LAP_NEAR m ; sinon hauteur du tracé) -> choisit le bon étage (pont, rampe, route dessous) ;
  2. largeur : on balaie en travers du tracé (±SCAN m, pas de 1 m) les sols au même niveau (±LEVEL_TOL m) ; la bande
     continue qui contient la position du tour roulé (ou du point) donne les deux bords ;
  3. point = milieu de la bande, h = hauteur du sol ; lissage léger des décalages (3 points).
Drapeaux (champ « controle » et sortie texte) : sans_route (aucun sol à <= LEVEL_MAX m du niveau attendu),
zone_large (bande > SCAN des deux côtés : place, parking : point laissé), deplace (> MOVE_WARN m), tour_loin (pas de
tour roulé à <= LAP_NEAR m). Le champ w (largeur Map Builder) est gardé ; la largeur mesurée est dans « controle ».
N'écrase rien : sortie <tracé>_recale.json à côté (dubai_route1_trace_recale.json …). Ne construit ni n'installe.

usage: b2recale.py [ROUTE ...]          (défaut : 1 2 3 4)
"""
import json, os, sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import config  # noqa: E402

AID = os.path.join(config.JEUX, "blur2_aid", "dubai")
UNITY = os.path.join(config.JEUX, "Blur2DubaiTest", "Blur2DubaiTest_Data")
ROUTES = {1: ("dubai_route1_trace.json", "lap_route1_business_bay.csv"),
          2: ("dubai_route2_trace.json", "lap_route2_dubai_island.csv"),
          3: ("dubai_route3_trace.json", "lap_route3_construction.csv"),
          4: ("marina_trace.json", "lap_route4_marina.csv")}
CELL, SCAN, LEVEL_TOL, LEVEL_MAX, LAP_NEAR, MOVE_WARN = 8.0, 40, 3.0, 6.0, 25.0, 8.0


class Floors:
    """sols de route (17f / 8017f, n.y >= 0.5) en axes du jeu, repère Unity ; hauteurs sous (x, z)"""

    def __init__(self, cols):
        T = []
        for name, (v, t) in cols.items():
            suf = name.replace("_collision", "").rsplit("_", 1)[-1]
            if name.startswith("physics_route_") or suf not in ("17f", "8017f"):
                continue
            tt = v[t]
            n = np.cross(tt[:, 1] - tt[:, 0], tt[:, 2] - tt[:, 0])
            ny = np.abs(n[:, 1]) / (np.linalg.norm(n, axis=1) + 1e-12)
            T.append(tt[ny >= 0.5])
        self.T = np.concatenate(T)
        lo = np.floor(self.T[:, :, [0, 2]].min(1) / CELL).astype(int)
        hi = np.floor(self.T[:, :, [0, 2]].max(1) / CELL).astype(int)
        grid = {}
        for k in range(len(self.T)):
            for i in range(lo[k, 0], hi[k, 0] + 1):
                for j in range(lo[k, 1], hi[k, 1] + 1):
                    grid.setdefault((i, j), []).append(k)
        self.grid = {c: np.array(v) for c, v in grid.items()}

    def heights(self, x, z):
        idx = self.grid.get((int(np.floor(x / CELL)), int(np.floor(z / CELL))))
        if idx is None:
            return np.empty(0)
        T = self.T[idx]
        a, b, c = T[:, 0], T[:, 1], T[:, 2]
        v0, v1 = (c - a)[:, [0, 2]], (b - a)[:, [0, 2]]
        v2 = np.array([x, z]) - a[:, [0, 2]]
        d00, d01, d11 = (v0 * v0).sum(1), (v0 * v1).sum(1), (v1 * v1).sum(1)
        d20, d21 = (v2 * v0).sum(1), (v2 * v1).sum(1)
        den = d00 * d11 - d01 * d01
        ok = np.abs(den) > 1e-9
        safe = np.where(ok, den, 1)
        u = np.where(ok, (d11 * d20 - d01 * d21) / safe, -1)
        w = np.where(ok, (d00 * d21 - d01 * d20) / safe, -1)
        inside = ok & (u >= -1e-6) & (w >= -1e-6) & (u + w <= 1 + 1e-6)
        return (a[:, 1] + u * (c - a)[:, 1] + w * (b - a)[:, 1])[inside]

    def level(self, x, z, want, tol):
        h = self.heights(x, z)
        if not len(h):
            return None
        k = np.argmin(np.abs(h - want))
        return float(h[k]) if abs(h[k] - want) <= tol else None


def lateral(P, i, closed):
    n = len(P)
    a = P[(i - 1) % n] if (closed or i > 0) else P[i]
    b = P[(i + 1) % n] if (closed or i < n - 1) else P[i]
    tg = np.array([b[0] - a[0], b[1] - a[1]])
    tg /= np.linalg.norm(tg) + 1e-9
    return np.array([-tg[1], tg[0]])


def recale_line(F, pts, low, lap, closed):
    """pts [{x, z, w, h}] -> (nouveaux points, contrôle)"""
    from scipy.spatial import cKDTree
    kd = cKDTree(lap[:, [0, 2]])
    P = np.array([[p["x"], p["z"], p["h"] + low] for p in pts], float)
    n = len(P)
    res = []
    for i in range(n):
        x, z, y = P[i]
        lat = lateral(P, i, closed)
        flags = []
        d, k = kd.query([x, z])
        if d <= LAP_NEAR:
            want, o_lap = lap[k, 1], float((lap[k, [0, 2]] - [x, z]) @ lat)
            lev = F.level(x, z, want, LEVEL_MAX)
        else:
            o_lap, lev = 0.0, None
            flags.append("tour_loin")
        if lev is None:                                    # tour roulé sur un mur / en l'air : niveau du tracé
            lev = F.level(x, z, y, LEVEL_MAX)
        if lev is None:
            res.append((None, flags + ["sans_route"], None))
            continue
        offs = np.arange(-SCAN, SCAN + 1)
        cov = np.array([F.level(x + o * lat[0], z + o * lat[1], lev, LEVEL_TOL) is not None for o in offs])
        target = int(np.clip(round(o_lap), -SCAN, SCAN)) + SCAN
        if not cov[target]:                                # position du tour hors route : bande la plus proche
            on = np.where(cov)[0]
            target = int(on[np.argmin(np.abs(on - target))]) if len(on) else SCAN
        lo_i = hi_i = target
        while lo_i > 0 and cov[lo_i - 1]:
            lo_i -= 1
        while hi_i < len(offs) - 1 and cov[hi_i + 1]:
            hi_i += 1
        width = float(hi_i - lo_i + 1)
        if lo_i == 0 and hi_i == len(offs) - 1:
            res.append((0.0, flags + ["zone_large"], width))
            continue
        res.append(((offs[lo_i] + offs[hi_i]) / 2.0, flags, width))
    good = [r[0] is not None and "zone_large" not in r[1] for r in res]
    shift = np.array([r[0] if r[0] is not None else 0.0 for r in res])
    sm = shift.copy()
    for i in range(n):                                     # lissage 3 points des décalages mesurés
        if not good[i]:
            continue
        nb = [shift[j % n] for j in (i - 1, i, i + 1) if (closed or 0 <= j < n) and good[j % n]]
        sm[i] = float(np.mean(nb))
    out, ctrl = [], []
    for i, p in enumerate(pts):
        o, flags, width = res[i]
        x, z, y = P[i]
        if o is None:
            out.append(dict(p))
            ctrl.append({"i": i, "drapeaux": flags, "deplacement_m": 0.0, "largeur_m": None})
            continue
        nx, nz = np.array([x, z]) + sm[i] * lateral(P, i, closed)
        g = F.level(nx, nz, y, LEVEL_MAX)
        ny = g if g is not None else y
        if abs(sm[i]) > MOVE_WARN:
            flags = flags + ["deplace"]
        out.append(dict(p, x=round(float(nx), 2), z=round(float(nz), 2), h=round(float(ny - low), 2)))
        ctrl.append({"i": i, "drapeaux": flags, "deplacement_m": round(float(abs(sm[i])), 1), "largeur_m": width})
    return out, ctrl


def main(routes):
    import b2collision, b2track, make_b2_map
    F = Floors(b2collision.colliders(UNITY))
    print("sols de route : %d triangles" % len(F.T))
    for r in routes:
        tf, lf = ROUTES[r]
        raw = b2track.read_lap(os.path.join(AID, lf))
        lap = np.array(raw)
        low = min(p[1] for p in make_b2_map.resample(raw, make_b2_map.STEP))     # comme l'éditeur et make_b2_map
        src = json.load(open(os.path.join(AID, tf), encoding="utf-8"))
        res = dict(src)
        pts, ctrl = recale_line(F, src["points"], low, lap, closed=True)
        res["points"], res["controle"] = pts, ctrl
        res["branches"] = []
        for b in src.get("branches") or []:
            bp, bc = recale_line(F, b["points"], low, lap, closed=False)
            res["branches"].append(dict(b, points=bp, controle=bc))
        res["note"] = (src.get("note", "") + "; b2recale: recalé sur les sols 17f/8017f, centré entre les bords, "
                       "niveau choisi d'après le tour roulé %s" % lf)
        out = os.path.join(AID, tf.replace(".json", "_recale.json"))
        json.dump(res, open(out, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
        allc = ctrl + [c for b in res["branches"] for c in b["controle"]]
        cnt = {f: sum(f in c["drapeaux"] for c in allc) for f in ("sans_route", "zone_large", "deplace", "tour_loin")}
        mv = [c["deplacement_m"] for c in allc if c["largeur_m"] is not None]
        wd = [c["largeur_m"] for c in allc if c["largeur_m"] is not None and "zone_large" not in c["drapeaux"]]
        print("route %d : %d points (+%d embranchements) ; déplacement médian %.1f m, max %.1f m ; largeur médiane %.0f m"
              " ; %s -> %s" % (r, len(pts), sum(len(b["points"]) for b in res["branches"]), np.median(mv), max(mv),
                               np.median(wd), ", ".join("%s %d" % kv for kv in cnt.items()), os.path.basename(out)))


if __name__ == "__main__":
    main([int(a) for a in sys.argv[1:]] or [1, 2, 3, 4])
