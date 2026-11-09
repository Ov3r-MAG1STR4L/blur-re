#!/usr/bin/env python3
"""Official Blur 2 race data of a city (X360 Nov 10 prototype actorpack.xt) -> laps, .aid and a check image.

In a Blur 2 actorpack (KSLF big-endian, read with x360/b2race.py):
  StartPosition       : start slots, WorldMatrix (Mat43 at +12, position at +48) + StartNumber (+60); one record
                        per race grid (16-20 slots).
  AIDataActor         : WorldMatrix (+12) + AIData (+60: u32 closedLoopTrack, +64 linkNodes array: pointer, count).
                        Its link nodes are a SLICE (start, count) of the record's AILinkNode chunk, in the actor's
                        local frame: world = aw + p @ [ax, ay, az]. Closed actor = the race's main loop, the others
                        = branches. (Dubai: 94-100 % of the nodes within 8 m of the road collision.)
  AILinkNode (72 B)   : position, trackNormal, direction, profile..., links.
A main loop becomes a lap (rotated to start at its nearest grid's slot 0) -> lap2aid (width --width, the link node
profile is not decoded yet). Branches are drawn, not written to the .aid.

usage: b2official.py ACTORPACK.xt CITY_map.npz OUT_DIR [--width 24]
"""
import argparse, collections, csv, os, struct, subprocess, sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "x360"))
import b2race as R, blurxt_be as M  # noqa: E402


def official(path):
    r = R.read(path)
    f = R.f
    grids = collections.defaultdict(list)
    for b, s, idx, _ in r["StartPosition"]:
        grids[idx].append((struct.unpack_from(">i", b, 60)[0], f(b, 48), f(b, 52), f(b, 56)))
    nodes = collections.defaultdict(list)
    for b, s, idx, _ in r["AILinkNode"]:
        nodes[idx].append((f(b, 0), f(b, 4), f(b, 8)))
    races = collections.defaultdict(lambda: {"loop": None, "branches": []})
    for b, s, idx, _ in r["AIDataActor"]:
        mat = np.array([[f(b, 12 + 4 * i) for i in range(3 * j, 3 * j + 3)] for j in range(4)])
        closed = struct.unpack_from(">I", b, 60)[0]
        raw, n = struct.unpack_from(">II", b, 64)
        start = M.rot(raw) >> 16
        pts = mat[3] + np.array(nodes[idx][start:start + n]) @ mat[:3]
        if closed and races[idx]["loop"] is None:
            races[idx]["loop"] = pts
        else:
            races[idx]["branches"].append(pts)
    return {k: v for k, v in races.items() if v["loop"] is not None}, {k: sorted(v) for k, v in grids.items()}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("actorpack"), ap.add_argument("map_npz"), ap.add_argument("out")
    ap.add_argument("--width", type=float, default=24.0)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    city = os.path.basename(os.path.dirname(a.actorpack))
    races, grids = official(a.actorpack)
    print("%s: %d grids %s, %d AI races" % (city, len(grids), [len(g) for g in grids.values()], len(races)))
    from PIL import Image, ImageDraw
    mp = np.load(a.map_npz)
    lo, k, size = mp["lo"], float(mp["k"]), int(mp["size"])
    P = lambda x, z: ((x - lo[0]) * k + 10, size - 1 - ((z - lo[1]) * k + 10))
    img = Image.open(a.map_npz.replace("_map.npz", ".png")).convert("RGB")
    dr = ImageDraw.Draw(img)
    cols = [(230, 0, 0), (0, 110, 255), (0, 160, 0), (255, 140, 0), (160, 0, 200), (0, 190, 190)]
    for j, g in enumerate(grids.values()):
        for _, x, y, z in g:
            p = P(x, z)
            dr.rectangle((p[0] - 8, p[1] - 8, p[0] + 8, p[1] + 8), fill=cols[j % 6])
        p = P(g[0][1], g[0][3])
        dr.text((p[0] + 12, p[1] - 12), "grille %d" % (j + 1), fill=cols[j % 6])
    for n, (idx, race) in enumerate(sorted(races.items()), 1):
        loop = race["loop"]
        for br in race["branches"]:
            dr.line([P(x, z) for x, _, z in br], fill=(120, 120, 120), width=4)
        dr.line([P(x, z) for x, _, z in loop] + [P(loop[0, 0], loop[0, 2])], fill=(0, 0, 0), width=5)
        # start: the grid whose slot 0 is nearest to the loop, the loop rotated to begin next to it
        g = min(grids.values(), key=lambda g: np.hypot(loop[:, 0] - g[0][1], loop[:, 2] - g[0][3]).min())
        i0 = int(np.hypot(loop[:, 0] - g[0][1], loop[:, 2] - g[0][3]).argmin())
        lap = np.vstack([loop[i0:], loop[:i0], loop[i0:i0 + 1]])
        length = np.hypot(np.diff(lap[:, 0]), np.diff(lap[:, 2])).sum()
        name = "%s_officiel_%d" % (city, n)
        with open(os.path.join(a.out, name + ".csv"), "w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["t", "x", "y", "z", "kmh"])
            for i, (x, y, z) in enumerate(lap):
                w.writerow([i, round(x, 2), round(y, 2), round(z, 2), 0])
        subprocess.run([sys.executable, "-I", os.path.join(HERE, "lap2aid.py"), os.path.join(a.out, name + ".csv"),
                        os.path.join(a.out, name + ".aid"), "--width", str(a.width)], check=True)
        print("  course %d (record %d): boucle %d noeuds, %.0f m, %d embranchements, depart grille de %d places"
              % (n, idx, len(loop), length, len(race["branches"]), len(g)))
    img.resize((1600, 1600)).save(os.path.join(a.out, city + "_officiel.png"))


if __name__ == "__main__":
    main()
