#!/usr/bin/env python3
"""Blur2DubaiTest (Unity "Brul") drive telemetry -> one clean lap CSV for lap2aid.py.

Run the game with BRUL_DRIVE_TELEMETRY=0.25 (Jeux_WII\\Blur2DubaiTest\\Lancer avec enregistrement.bat), drive laps.
Player.log lines "[Brul][drive-telemetry] t=.. pos=(x, y, z) .. vel=(..)" are in Unity axes:
game = (-x, y, -z)   (measured on Dubai: 88 % of the points within 5 m of the X360 collision, height gap 0.3 m).
Laps: a reference point on the early driving, a lap = back within 15 m of it after > 1500 m with no teleport
(> 40 m in one sample: R reset, fall); the shortest lap is kept (= the main loop, without detours).

usage: brul2lap.py [Player.log] OUT_lap.csv
"""
import csv, os, re, sys
import numpy as np

LOG = os.path.expandvars(r"%USERPROFILE%\AppData\LocalLow\Personal Prototype Inspection\Blur 2 Dubai Test\Player.log")
RX = re.compile(r"drive-telemetry\] t=([\d,.]+) pos=\(([-\d.]+), ([-\d.]+), ([-\d.]+)\).*?vel=\(([-\d.]+), ([-\d.]+), ([-\d.]+)\)")


def read(path):
    rows = []
    for line in open(path, encoding="utf-8", errors="replace"):
        m = RX.search(line)
        if m:
            t = float(m[1].replace(",", "."))
            x, y, z, vx, vy, vz = map(float, m.groups()[1:])
            rows.append((t, -x, y, -z, 3.6 * (vx * vx + vy * vy + vz * vz) ** .5))
    a = np.array(rows)
    return a[a[:, 2] > -50]                         # drop the falls into the void


def laps(a):
    t, x, y, z, kmh = a.T
    step = np.r_[0, np.hypot(np.diff(x), np.diff(z))]
    cum = np.cumsum(step)
    best = None
    for ref in range(20, min(400, len(a)), 10):
        if kmh[ref] < 60:
            continue
        found, start, last = [], ref, ref
        for i in range(ref + 1, len(a)):
            near = np.hypot(x[i] - x[ref], z[i] - z[ref]) < 15
            if step[i] > 40:
                start = None
                continue
            if start is None:
                if near:
                    start = last = i
                continue
            if near and cum[i] - cum[last] > 1500:
                found.append((start, i, cum[i] - cum[start]))
                start = last = i
        if found and (best is None or len(found) > len(best)):
            best = found
    return best or []


def main():
    log, out = (sys.argv[1], sys.argv[2]) if len(sys.argv) > 2 else (LOG, sys.argv[1])
    a = read(log)
    found = laps(a)
    for s, e, L in found:
        print("lap t=%.0f..%.0f s: %.0f m" % (a[s, 0], a[e, 0], L))
    assert found, "no complete lap in the log"
    s, e, L = min(found, key=lambda f: f[2])
    with open(out, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["t", "x", "y", "z", "kmh"])
        for r in a[s:e + 1]:
            w.writerow([round(v, 2) for v in r])
    print("written %s: %.0f m, %d points" % (out, L, e - s + 1))


if __name__ == "__main__":
    main()
