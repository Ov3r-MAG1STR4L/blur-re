#!/usr/bin/env python3
"""Build every file of the reversed-Haruna mod (projet C) from the extracted game data, off-game.

Output tree mirrors the game folder (loose files override paks, see docs/CONNAISSANCES.md 3.1 bis):
  OUT/gamedata/levels/jpn_mharuna/jpn_mharuna_7.aid    reversed AI / logic route
  OUT/gamedata/levels/jpn_mharuna/actorpack.xt         + 2 start lists (solo #62, multi #15) at the bottom
  OUT/gamedata/xt/amax.bin                             + Route JPN_MHaruna_7 pointing to the new lists
  OUT/gamedata/xt/multiplayer.bin                      + JPN_MHaruna_7 in MultiplayerConfig.routes
usage: make_haruna_reverse.py OUT_DIR
"""
import os, sys
import aidreverse, blurroute, gridreverse
from blurxt import XT
from kslfwrite import KSLF

E = os.path.join(os.path.dirname(__file__), "..", "blur_extracted")
G = os.path.join(E, "gamedata", "gamedata")
H_ROUTE, H_SOLO, H_MULTI = 0xFFFF0001, 0xFFFF0002, 0xFFFF0003   # above every existing hash (max 0xFFFE3216)
LOC_ASCENT = 226956641   # hash of CRN_MOUNT_HARUNA_2 = "Ascent" / "Montée", unused string left in cityandroutenames.loc


def main(out):
    lvl = os.path.join(out, "gamedata", "levels", "jpn_mharuna")
    xt = os.path.join(out, "gamedata", "xt")
    os.makedirs(lvl, exist_ok=True)
    os.makedirs(xt, exist_ok=True)

    aid = os.path.join(lvl, "jpn_mharuna_7.aid")
    orig_aid = os.path.join(G, "levels", "jpn_mharuna", "jpn_mharuna_1.aid")
    d = aidreverse.reverse(blurroute.parse(open(orig_aid, "rb").read(), raw=True))
    open(aid, "wb").write(blurroute.build(d))

    # actorpack: clone the two start lists, then move cars and start/finish texts
    ap = os.path.join(lvl, "actorpack.xt")
    k = KSLF(os.path.join(G, "levels", "jpn_mharuna", "actorpack.xt"))
    names = {}
    for src, h in (("#62", H_SOLO), ("#15", H_MULTI)):
        k.clone(src, None, h)
        names[src] = f"#{len(k.index) - 1}"           # nameless records are named after their index slot
    open(ap, "wb").write(k.build())
    grid = gridreverse.compute(orig_aid, aid, os.path.join(E, "xt_json", "jpn_mharuna.actorpack.json"))
    for src, moves in grid.items():
        for i, _, m in moves:
            for row in ("ax", "ay", "az", "aw"):
                for c, v in zip(("vx", "vy", "vz"), m[row]):
                    b = XT(ap).patched(names[src], f"LevelActors[{i}].WorldMatrix.{row}.{c}", float(v))
                    open(ap, "wb").write(b)

    # amax.bin: route JPN_MHaruna_7 = copy of _1 with the new start lists
    a = KSLF(os.path.join(G, "xt", "amax.bin"))
    a.clone("JPN_MHaruna_1", "JPN_MHaruna_7", H_ROUTE)
    solo, multi = a.add_external(H_SOLO, "LevelActorList"), a.add_external(H_MULTI, "LevelActorList")
    p = os.path.join(xt, "amax.bin")
    open(p, "wb").write(a.build())
    a = KSLF(p)
    a.set_array_ref("JPN_MHaruna_7", "ActorLists", 1, solo)            # was #62
    a.set_array_ref("JPN_MHaruna_7", "MultiplayerActorLists", 0, multi)  # was #15
    open(p, "wb").write(a.build())
    for field, v in (("RouteNumber", 7), ("Index", 3),            # _1 has Index 2
                     ("LocString", LOC_ASCENT)):                    # menu name "Ascent" / "Montée"
        b = XT(p).patched("JPN_MHaruna_7", field, v)              # read before opening for writing
        open(p, "wb").write(b)

    m = KSLF(os.path.join(G, "xt", "multiplayer.bin"))
    m.append_to_array("#735", "routes", m.add_external(H_ROUTE, "Route"))
    open(os.path.join(xt, "multiplayer.bin"), "wb").write(m.build())
    print("written to", out)


if __name__ == "__main__":
    main(sys.argv[1])
