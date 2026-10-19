#!/usr/bin/env python3
"""Compute a start grid for a reversed point-to-point route (projet C, Haruna).

Each original StartPosition is measured against the original route (Main section of the .aid):
distance along the road from the Start gate (negative = behind the line) and position across the
road as a fraction of the road width. The same measures are applied from the reversed route's Start
gate. Facts used (measured on Haruna, see docs/CONNAISSANCES.md):
- actor WorldMatrix rows ax, ay, az, aw: az = forward (dot road tangent 1.00), ax = -(aid lateral axis);
- .aid heights are ~11-14 m below the real ground on Haruna, so ground height is estimated from nearby
  ground objects (cones list #37, lamps list #16) and cars are placed CAR_ABOVE_GROUND above it.
Start_Text_* effects: Start/Final/Checkpoint texts move to the old Finish text and vice versa, turned 180 deg.
"""
import json
import numpy as np
import blurroute

CAR_ABOVE_GROUND = 1.0          # m; a small drop at spawn is safer than a car inside the ground
# Tested 2026-10-19 on Haruna: the road collision ends ~250 m after the old finish line (cars spawned past it
# fell through), and the original grid sits off-centre on a 36 m road (copied as is, one column was off the
# 20 m road at the bottom). So the grid is squeezed (front row kept) to end MAX_BEHIND m behind the start
# line, and centred on the road.
MAX_BEHIND = 219.0              # m behind the reversed start line; calibration knob (collision end ~250 m)
CENTRE_GRID = True
GROUND_LISTS = ("#37", "#16")


def _route(path):
    d = blurroute.parse(open(path, "rb").read())
    S = {s["name"]: s for s in d["sections"]}
    M = S["Main"]["nodes"]
    P = np.array([[n["x"], n["y"], n["z"]] for n in M])
    arc = np.r_[0, np.cumsum(np.linalg.norm(np.diff(P[:, [0, 2]], axis=0), axis=1))]
    lat = np.array([n["lateral"] for n in M])
    W = np.array([n["width"] for n in M])
    g = S["Start"]["nodes"][0]
    ig = int(np.argmin(np.hypot(P[:, 0] - g["x"], P[:, 2] - g["z"])))
    return P, arc, lat, W, ig


def _vec(m, k):
    return np.array([m[k]["vx"], m[k]["vy"], m[k]["vz"]])


def compute(orig_aid, rev_aid, actorpack_json, lists=("#62", "#15")):
    A = json.load(open(actorpack_json, encoding="utf-8"))["LevelActorList"]
    refs = np.array([_vec(x["WorldMatrix"], "aw") for key in GROUND_LISTS
                     for x in A[key]["LevelActors"] if x and x.get("WorldMatrix")])
    P0, arc0, lat0, W0, ig0 = _route(orig_aid)
    P1, arc1, lat1, W1, ig1 = _route(rev_aid)

    def ground(p):
        near = np.hypot(refs[:, 0] - p[0], refs[:, 2] - p[2]) < 30
        k = int(np.argmin(np.hypot(P1[:, 0] - p[0], P1[:, 2] - p[2])))
        if near.sum() >= 3:                           # offset between real ground and .aid height, locally
            ks = [int(np.argmin(np.hypot(P1[:, 0] - r[0], P1[:, 2] - r[2]))) for r in refs[near]]
            return P1[k, 1] + float(np.median(refs[near, 1] - P1[ks, 1]))
        return P1[k, 1] + 12.0                        # typical Haruna offset

    out = {}
    for key in lists:
        actors = A[key]["LevelActors"]
        new, meas = [], {}
        for k, x in enumerate(actors):
            if x["Name"].startswith("StartPosition"):
                p = _vec(x["WorldMatrix"], "aw")
                i = int(np.argmin(np.hypot(P0[:, 0] - p[0], P0[:, 2] - p[2])))
                meas[k] = (arc0[i] - arc0[ig0],
                           0.5 + float(np.dot(p[[0, 2]] - P0[i, [0, 2]], lat0[i])) / W0[i])
        mid = float(np.mean([f for _, f in meas.values()])) - 0.5 if CENTRE_GRID else 0.0
        squeeze = min(1.0, MAX_BEHIND / -min(a for a, _ in meas.values()))
        meas = {k: (a * squeeze, f) for k, (a, f) in meas.items()}
        for k, x in enumerate(actors):
            name = x["Name"]
            m = x["WorldMatrix"]
            if k in meas:
                along, frac = meas[k]
                frac -= mid
                s = arc1[ig1] + along
                j = int(np.clip(np.searchsorted(arc1, s), 1, len(arc1) - 2))
                t = (s - arc1[j - 1]) / max(arc1[j] - arc1[j - 1], 1e-6)
                c = P1[j - 1] + t * (P1[j] - P1[j - 1])
                lat = lat1[j]
                pos = np.array([c[0], 0.0, c[2]])
                pos[[0, 2]] += lat * (frac - 0.5) * W1[j]
                pos[1] = ground(pos) + CAR_ABOVE_GROUND
                fwd = P1[min(j + 2, len(P1) - 1)] - P1[max(j - 2, 0)]
                az = fwd / np.linalg.norm(fwd)
                ax = -np.array([lat[0], 0.0, lat[1]])
                ax -= az * np.dot(ax, az)
                ax /= np.linalg.norm(ax)
                ay = np.cross(az, ax)                 # sign checked against the original matrices below
                if np.dot(ay, _vec(m, "ay")) < 0:
                    ay = -ay
                new.append((k, name, {"ax": ax, "ay": ay, "az": az, "aw": pos}))
        texts = {x["Type"]: (k, x) for k, x in enumerate(actors) if x["Name"].startswith("Start_Text")}
        if "Finish" in texts:
            fin = texts["Finish"][1]["WorldMatrix"]
            st = texts.get("Start", (None, None))[1]
            for typ, (k, x) in texts.items():
                src = (st["WorldMatrix"] if typ == "Finish" else fin) if st else None
                if src is None:
                    continue
                new.append((k, x["Name"], {"ax": -_vec(src, "ax"), "ay": _vec(src, "ay"),
                                           "az": -_vec(src, "az"), "aw": _vec(src, "aw")}))
        out[key] = new
    return out
