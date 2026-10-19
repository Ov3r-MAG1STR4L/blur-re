#!/usr/bin/env python3
"""Start grid and start/finish texts of a reversed route (projet C), point-to-point or loop.

Measures are taken on the road CENTRE line (a .aid node is one road EDGE: road = node + lateral * 0..width, and an
edge is not the same length both ways). Each original StartPosition is measured from the original start line
(along the road, negative = behind) and across the road (fraction of the width, 0.5 = centre); the same measures
are applied from the reversed start line. Facts (docs/CONNAISSANCES.md):
- actor WorldMatrix rows: az = forward, ax = -(aid lateral axis), aw = position;
- the original Start_Text_* effects sit exactly on the painted lines (Haruna, measured by driving);
- .aid heights are below the real ground (Haruna: 11-14 m): spawn height comes from nearby ground objects
  (cfg ground_lists) or, by default, from the original grid's own height above the .aid.
Point-to-point (Haruna): the reversed start line is the old finish line and the other way round.
Loop: one line, driven the other way: grid on the other side, texts turned 180 deg.

cfg keys: lines = {"orig_start", "start", "finish"} world (x, z) points; loop; front_gap (m, None = keep the
original gap); max_behind (m, None = no limit); ground_lists + car_above (m) for the ground-object method.
"""
import json
import numpy as np
import blurroute
import aidreverse

# Haruna (point-to-point), tested in game 2026-10-19:
# - the road collision ends ~250 m after the old finish line; driven down to 324 m behind the reversed start line;
# - the original grid sits off-centre on a 36 m road (copied as is, a column was off the 20 m road at the bottom);
# - the original multiplayer grid starts 140 m behind the line (looked far away once reversed); solo: 20 m;
# - painted lines measured by stopping on them in a Descent (trackrec.py); the original texts sit on them.
HARUNA = dict(
    lines={"orig_start": (-2474.1, -1305.1),      # top line (old start)
           "start": (1112.4, -3071.2),            # bottom line (old finish) = reversed start
           "finish": (-2474.1, -1305.1)},         # top line = reversed finish
    loop=False, front_gap=20.0, max_behind=295.0,
    ground_lists=("#37", "#16"), car_above=2.0)   # 1.0 gave 0.7 m under a driven car
CENTRE_GRID = True


def _centre(n):
    """Road centre at a node (the node itself is one road EDGE: road = node + lateral * 0..width)."""
    return np.array([n["x"] + n["lateral"][0] * n["width"] / 2, n["y"], n["z"] + n["lateral"][1] * n["width"] / 2])


def _route(path):
    """Centre line of the racing line (closed for a loop), arc length, lateral axis, width, loop flag."""
    raw = blurroute.parse(open(path, "rb").read(), raw=True)
    main_name = aidreverse.roles(raw)["main"]["name"]
    d = blurroute.parse(open(path, "rb").read())
    S = {s["name"]: s for s in d["sections"]}
    M = S[main_name]["nodes"]
    loop = bool(S[main_name]["type"] & 1)
    if loop:
        M = M + M[:1]
    P = np.array([_centre(n) for n in M])
    arc = np.r_[0, np.cumsum(np.linalg.norm(np.diff(P[:, [0, 2]], axis=0), axis=1))]
    lat = np.array([n["lateral"] for n in M])
    W = np.array([n["width"] for n in M])
    return P, arc, lat, W, loop


def _vec(m, k):
    return np.array([m[k]["vx"], m[k]["vy"], m[k]["vz"]])


def is_start_position(x):
    """Grid slot, by type (StartNumber field), not by name: Brighton's multiplayer slots are 'NewStartPosition0..19'
    (missed by a name test, they stayed on the original grid, facing the old way: seen 2026-10-19)."""
    return bool(x) and "StartNumber" in x and "WorldMatrix" in x


def start_line(actors):
    """(x, z) of the Start text of an original start list = the painted line (loops: start = finish)."""
    for x in actors:
        if x and x.get("Name", "").startswith("Start_Text") and x.get("Type") == "Start":
            p = _vec(x["WorldMatrix"], "aw")
            return float(p[0]), float(p[2])
    return None


def compute(orig_aid, rev_aid, actorpack_json, lists, cfg):
    A = json.load(open(actorpack_json, encoding="utf-8"))["LevelActorList"]
    P0, arc0, lat0, W0, loop = _route(orig_aid)
    P1, arc1, lat1, W1, _ = _route(rev_aid)
    L0, L1 = arc0[-1], arc1[-1]

    def near(P, xz):
        return int(np.argmin(np.hypot(P[:, 0] - xz[0], P[:, 2] - xz[1])))

    line0 = near(P0, cfg["lines"]["orig_start"])
    line1 = {k: near(P1, cfg["lines"][k]) for k in ("start", "finish")}
    refs = None
    if cfg.get("ground_lists"):
        refs = np.array([_vec(x["WorldMatrix"], "aw") for key in cfg["ground_lists"]
                         for x in A[key]["LevelActors"] if x and x.get("WorldMatrix")])

    def measure(p):
        """(m from the original start line, fraction across the road (0.5 = centre), height above the node)."""
        i = near(P0, (p[0], p[2]))
        a = arc0[i] - arc0[line0]
        if loop:
            a = (a + L0 / 2) % L0 - L0 / 2
        return a, 0.5 + float(np.dot(p[[0, 2]] - P0[i, [0, 2]], lat0[i])) / W0[i], p[1] - P0[i, 1]

    def place(along, frac, line):
        """Point `along` m after a reversed line, at `frac` across the road; returns (pos, j)."""
        s = arc1[line1[line]] + along
        if loop:
            s %= L1
        j = int(np.clip(np.searchsorted(arc1, s), 1, len(arc1) - 1))
        t = (s - arc1[j - 1]) / max(arc1[j] - arc1[j - 1], 1e-6)
        c = P1[j - 1] + t * (P1[j] - P1[j - 1])
        c[[0, 2]] += lat1[j] * (frac - 0.5) * W1[j]
        return c, j

    def ground(p):
        k = near(P1, (p[0], p[2]))
        close = np.hypot(refs[:, 0] - p[0], refs[:, 2] - p[2]) < 30
        if close.sum() >= 3:                          # offset between real ground and .aid height, locally
            ks = [near(P1, (r[0], r[2])) for r in refs[close]]
            return P1[k, 1] + float(np.median(refs[close, 1] - P1[ks, 1]))
        return P1[k, 1] + 12.0                        # typical Haruna offset

    def along_road(j):
        n = len(P1)
        a, b = (j + 2) % n if loop else min(j + 2, n - 1), (j - 2) % n if loop else max(j - 2, 0)
        f = P1[a] - P1[b]
        return f / np.linalg.norm(f)

    out = {}
    for key in lists:
        actors = A[key]["LevelActors"]
        new, meas = [], {k: measure(_vec(x["WorldMatrix"], "aw")) for k, x in enumerate(actors)
                         if is_start_position(x)}
        if meas:
            mid = float(np.mean([f for _, f, _ in meas.values()])) - 0.5 if CENTRE_GRID else 0.0
            dy = float(np.median([h for _, _, h in meas.values()]))   # original spawn height above the .aid
            if cfg.get("front_gap") is not None:
                front = max(a for a, _, _ in meas.values())
                meas = {k: (a - front - cfg["front_gap"], f, h) for k, (a, f, h) in meas.items()}
            if cfg.get("max_behind"):
                squeeze = min(1.0, cfg["max_behind"] / -min(a for a, _, _ in meas.values()))
                meas = {k: (a * squeeze, f, h) for k, (a, f, h) in meas.items()}
        for k, x in enumerate(actors):
            if k in meas:
                along, frac, _ = meas[k]
                pos, j = place(along, frac - mid, "start")
                pos[1] = ground(pos) + cfg["car_above"] if refs is not None else P1[j, 1] + dy
                az = along_road(j)
                ax = -np.array([lat1[j][0], 0.0, lat1[j][1]])
                ax -= az * np.dot(ax, az)
                ax /= np.linalg.norm(ax)
                ay = np.cross(az, ax)                 # sign checked against the original matrix
                if np.dot(ay, _vec(x["WorldMatrix"], "ay")) < 0:
                    ay = -ay
                new.append((k, x["Name"], {"ax": ax, "ay": ay, "az": az, "aw": pos}))
        # texts on the reversed lines (the original ones sit on the painted lines), turned 180 deg; a
        # point-to-point route swaps them: the Finish text takes the old Start text's orientation and the reverse
        texts = {x["Type"]: (k, x) for k, x in enumerate(actors) if x["Name"].startswith("Start_Text")}
        if "Finish" in texts and "Start" in texts:
            fin, st = texts["Finish"][1]["WorldMatrix"], texts["Start"][1]["WorldMatrix"]
            for typ, (k, x) in texts.items():
                src = (st if typ == "Finish" else fin) if not loop else x["WorldMatrix"]
                line = "finish" if typ == "Finish" else "start"
                _, frac, h = measure(_vec(x["WorldMatrix"], "aw"))
                pos, j = place(0.0, frac, line)
                pos[1] = P1[j, 1] + h
                new.append((k, x["Name"], {"ax": -_vec(src, "ax"), "ay": _vec(src, "ay"),
                                           "az": -_vec(src, "az"), "aw": pos}))
        out[key] = new
    return out
