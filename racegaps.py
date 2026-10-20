#!/usr/bin/env python3
"""Gap of every AI to the player over time (every 20 s) from a trackrec.py --all recording of ONE race.
usage: racegaps.py RECORDING.csv ROUTE.aid"""
import sys, numpy as np, gridreverse
rec, aid = sys.argv[1], sys.argv[2]
P, arc, *_ = gridreverse._route(aid); L = arc[-1]
D = np.genfromtxt(rec, delimiter=",", names=True)
ts = np.unique(D["t"])
prog = {}
for car in sorted(set(D["car"].astype(int))):
    d = D[D["car"] == car]
    idx = [int(np.argmin(np.hypot(P[:, 0] - x, P[:, 2] - z))) for x, z in zip(d["x"], d["z"])]
    pr = [0.0]
    for a, b in zip(idx, idx[1:]):
        s = arc[b] - arc[a]; s -= L * round(s / L); pr.append(pr[-1] + s)
    prog[car] = (d["t"], abs(np.array(pr)))
sign = 1
pt, pp = prog[0]
print("lap", round(L), "m ; écart à toi en m (+ = devant toi), toutes les 20 s")
for T in range(0, int(pt[-1]), 20):
    me = np.interp(T, pt, pp)
    g = sorted(round(np.interp(T, t, p) - me) for c, (t, p) in prog.items() if c)
    print(f"{T:4}s  devant {sum(x>0 for x in g):2}  min {g[0]:6}  médiane {int(np.median(g)):5}  max {g[-1]:5}  à ±50 m: {sum(abs(x)<=50 for x in g):2}")
