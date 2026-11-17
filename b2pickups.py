#!/usr/bin/env python3
"""Official Blur 2 power-ups at their exact 3D place and with their own type, in a built Blur 2 map (2026-11-17).

Map Builder only gets (x, z) rows: it projects them on the middle of its road, at its road height, with types in
turn (road_layout.AUTO_PATTERN), and the two lists of 109 PickupPosition (699ADE84 single player, 73B55A31
multiplayer) ended with stacked power-ups. Here, after the build, both lists are rewritten with gen_actorpack's own
place_pickups: k-th actor = k-th official power-up (Blur2DubaiTest <city>.json, Unity axes -> game (-x, y, -z),
y shifted like the map), heading of the nearest track point, the rest parked under the floor.
Types (texts and executables of the Blur 2 prototype): Blindfire = Bolt, Bomb = Mine, Nitrous = Nitro;
Javelin and Icewall (new in Blur 2) -> Railgun = the cut SuperShield type (natif/railgun).

usage: b2pickups.py ACTORPACK PICKUPS.json LAP.csv [BRANCH.csv ...] --low Y
"""
import argparse, csv, json, math, os, shutil, sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import config  # noqa: E402

FE = os.path.join(config.MAP_BUILDER_DIR, "flat_earth")
sys.path[:0] = [FE, os.path.join(config.MAP_BUILDER_DIR, "kslf"), config.MAP_BUILDER_DIR]

RAILGUN = "B85C8D7A"                 # PickupType of the SuperShield (Type 10), turned into the Railgun by railgun.dll
TYPES = {"Shunt": "2BEC03D3", "Barge": "60A35DF0", "Shock": "3A03CB15", "Mine": "2BB324A4", "Bolt": "4CF8489B",
         "Nitro": "8DAF6717", "Shield": "6F453F79", "Repair": "09B1575A"}
BLUR2 = {"Blindfire": "Bolt", "Bomb": "Mine", "Nitrous": "Nitro", "Icewall": "Railgun", "Javelin": "Railgun"}
NEAR = 40.0                          # m from a track line (top view): the power-ups of this route


def spots(pickups, lines, low):
    """[(x, y, z, heading, type uid hex)] for the official power-ups near the track lines"""
    P = np.vstack(lines)
    seg = [(a, b) for L in lines for a, b in zip(L, L[1:])]
    out = []
    for pk in pickups:
        x, y, z = -pk["position"][0], pk["position"][1] + 1.0 - low, -pk["position"][2]
        if np.hypot(P[:, 0] - x, P[:, 2] - z).min() > NEAR:
            continue
        a, b = min(seg, key=lambda s: math.hypot((s[0][0] + s[1][0]) / 2 - x, (s[0][2] + s[1][2]) / 2 - z))
        heading = math.atan2(b[0] - a[0], b[2] - a[2])          # forward = (sin a, cos a), as place_pickups
        name = BLUR2.get(pk["pickupType"], pk["pickupType"])
        out.append((x, y, z, heading, RAILGUN if name == "Railgun" else TYPES[name]))
    return out


def apply(actorpack, sp):
    """rewrite both power-up lists of ACTORPACK in place (a .bak kept once)"""
    import dump, gen_actorpack, kslf_write
    if not os.path.exists(actorpack + ".bak"):
        shutil.copyfile(actorpack, actorpack + ".bak")
    data = open(actorpack, "rb").read()
    data, _ = kslf_write.insert_uid(data, int(RAILGUN, 16), "PickupType")     # external row at its sorted place
    open(actorpack, "wb").write(data)
    for lst in gen_actorpack.PICKUP_LISTS:
        oi = {u: o for u, t, o in dump.File(actorpack).refs if o != 0xFFFF}[int(lst, 16)]
        tmp = actorpack + ".tmp"
        kslf_write.edit_object(actorpack, tmp, oi, gen_actorpack.place_pickups(sp, (1, 0, 0, 0, 1, 0, 0, 0, 1)))
        os.replace(tmp, actorpack)


def check(actorpack, sp):
    from blurxt import XT
    want = {(round(s[0], 1), round(s[2], 1)) for s in sp}
    for n, t, v, h in XT(actorpack).records():
        acts = [a for a in v.get("LevelActors", []) or [] if a and "PickupType" in a]
        vis = [a for a in acts if a["WorldMatrix"]["aw"]["vy"] > -100]
        got = {(round(a["WorldMatrix"]["aw"]["vx"], 1), round(a["WorldMatrix"]["aw"]["vz"], 1)) for a in vis}
        if got and got <= want:
            print("list", n, len(vis), "power-ups shown,", len(got), "distinct places,",
                  sum(a["PickupType"] == "@%s" % RAILGUN.lower() for a in vis), "railguns")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("actorpack"), ap.add_argument("pickups"), ap.add_argument("laps", nargs="+")
    ap.add_argument("--low", type=float, required=True, help="lowest lap y of the map (Map Builder floor at 1)")
    a = ap.parse_args()
    lines = [np.array([(float(r["x"]), float(r["y"]), float(r["z"])) for r in csv.DictReader(open(f))]) for f in a.laps]
    sp = spots(json.load(open(a.pickups))["pickups"], lines, a.low)
    from collections import Counter
    print(len(sp), "official power-ups near the track:", Counter(s[4] for s in sp))
    apply(a.actorpack, sp)
    check(a.actorpack, sp)


if __name__ == "__main__":
    main()
