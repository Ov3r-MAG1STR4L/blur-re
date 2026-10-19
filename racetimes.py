#!/usr/bin/env python3
"""Race times of every car from a trackrec.py --all recording (loop route): progress along the road centre line,
unwrapped over laps, measured from the start line; a car finishes when it has covered LAPS full laps.
usage: racetimes.py RECORDING.csv ROUTE.aid LINE_X LINE_Z LAPS     (line = the original Start text position)
"""
import sys
import numpy as np
import gridreverse


def times(rec, aid, line_xz, laps):
    P, arc, _, _, loop = gridreverse._route(aid)
    L = arc[-1]
    near = lambda x, z: int(np.argmin(np.hypot(P[:, 0] - x, P[:, 2] - z)))
    a0 = arc[near(*line_xz)]
    D = np.genfromtxt(rec, delimiter=",", names=True)
    out = {}
    for car in sorted(set(D["car"].astype(int))):
        d = D[D["car"] == car]
        # follow the car node by node: a global nearest-node search jumps between close stretches of road
        n, idx, s = len(P), near(d["x"][0], d["z"][0]), []
        for x, z in zip(d["x"], d["z"]):
            win = (idx + np.arange(-40, 41)) % n
            idx = int(win[np.argmin(np.hypot(P[win, 0] - x, P[win, 2] - z))])
            s.append((arc[idx] - a0) % L)
        s = np.array(s)
        s = np.where(s > L / 2, s - L, s)            # behind the line at the start: negative
        prog = [s[0]]
        for a, b in zip(s, s[1:]):                   # unwrap: a jump of about one lap means the line was crossed
            step = b - a
            step -= L * round(step / L)
            prog.append(prog[-1] + step)
        prog = np.array(prog)
        done = np.nonzero(prog >= laps * L)[0]
        t0 = d["t"][np.nonzero(d["kmh"] > 5)[0][0]] if (d["kmh"] > 5).any() else d["t"][0]
        out[car] = dict(player=bool(d["player"][0]), finish=float(d["t"][done[0]] - t0) if len(done) else None,
                        dist=float(prog[-1]), vmax=float(d["kmh"].max()),
                        vmean=float(d["kmh"][d["kmh"] > 5].mean()) if (d["kmh"] > 5).any() else 0.0)
    return out


if __name__ == "__main__":
    rec, aid, x, z, laps = sys.argv[1], sys.argv[2], float(sys.argv[3]), float(sys.argv[4]), int(sys.argv[5])
    res = times(rec, aid, (x, z), laps)
    fin = sorted(v["finish"] for v in res.values() if v["finish"] and not v["player"])
    for car, v in res.items():
        print(f"voiture {car:2} {'JOUEUR' if v['player'] else '      '} temps {v['finish'] and round(v['finish'], 1)} s"
              f"  distance {v['dist']:.0f} m  vmoy {v['vmean']:.0f}  vmax {v['vmax']:.0f} km/h")
    if fin:
        print(f"IA arrivées : {len(fin)}  meilleur {fin[0]:.1f} s  médian {np.median(fin):.1f} s  dernier {fin[-1]:.1f} s")
