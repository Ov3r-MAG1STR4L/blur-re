#!/usr/bin/env python3
"""Complements from the Blur 2 Nov 4 2010 X360 build for a city (Dubai): its PickupPosition records (absent or moved
in the Nov 10 build) and the AI metadata dropped later (AIMetaDataSpan, AIWallrideMetaData, AITunnelMetaData).

PickupPosition (92 B, name "Power-Up"): WorldMatrix at +12, position at +48 (game axes, as StartPosition).
AIMetaDataSpan (16 B): f32 t0, f32 t1, u32 link node A, u32 link node B (low 16 bits = node index in the record's
AILinkNode chunk) = the part t0..t1 of the AI link A -> B.
AIWallrideMetaData / AITunnelMetaData (12 B): u32 0x000B00SS (SS = first span), u32 span count, u32 flags (16 / 1)
-- reading of the two records seen, Probable.

usage: b2nov04.py ACTORPACK_NOV4 ACTORPACK_NOV10 LAP.csv OUT_DIR
"""
import csv, json, os, struct, sys
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "x360"))
import b2race  # noqa: E402

f = b2race.f


def pickups(r):
    return np.array([(f(b, 48), f(b, 52), f(b, 56)) for b, *_ in r["PickupPosition"]])


def meta(r):
    """[{kind, race, spans: [(t0, t1, A xyz, B xyz)]}] in game axes"""
    out = []
    spans = r["AIMetaDataSpan"]
    for kind in ("AIWallrideMetaData", "AITunnelMetaData"):
        for b, s, idx, _ in r.get(kind, []):
            first, count, flags = struct.unpack_from(">III", b, 0)
            first &= 0xFF
            nodes = [(f(x, 0), f(x, 4), f(x, 8)) for x, s2, i2, _ in r["AILinkNode"] if i2 == idx]
            act = next(x for x, s2, i2, _ in r["AIDataActor"] if i2 == idx)
            m = np.array([[f(act, 12 + 4 * i) for i in range(3 * j, 3 * j + 3)] for j in range(4)])
            W = m[3] + np.array(nodes) @ m[:3]
            sp = []
            for x, *_ in spans[first:first + count]:
                t0, t1 = f(x, 0), f(x, 4)
                a, c = (struct.unpack_from(">I", x, o)[0] & 0xFFFF for o in (8, 12))
                sp.append({"t0": round(t0, 3), "t1": round(t1, 3), "a": W[a].round(2).tolist(), "b": W[c].round(2).tolist()})
            out.append({"kind": kind[2:-8].lower(), "race": idx, "flags": flags, "spans": sp})
    return out


def main():
    p4, p10, lap, out = sys.argv[1:5]
    r4, r10 = b2race.read(p4), b2race.read(p10)
    a, c = pickups(r4), pickups(r10)
    d = np.array([np.linalg.norm(c - p, axis=1).min() for p in a])
    pk = [{"position": p.round(2).tolist(), "in_nov10": bool(x < 2)} for p, x in zip(a, d)]
    json.dump({"pickups": pk}, open(os.path.join(out, "dubai_bonus_nov04.json"), "w"), indent=1)
    mt = meta(r4)
    json.dump(mt, open(os.path.join(out, "dubai_ia_meta_nov04.json"), "w"), indent=1)
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    L = np.array([(float(q["x"]), float(q["z"])) for q in csv.DictReader(open(lap))])
    fig = plt.figure(figsize=(10, 12))
    plt.plot(*L.T, "grey", lw=1, label="tour Marina")
    plt.scatter(c[:, 0], c[:, 2], s=14, c="blue", label="bonus 10 nov (%d)" % len(c))
    new = a[d >= 2]
    plt.scatter(new[:, 0], new[:, 2], s=14, c="orange", label="bonus 4 nov seulement (%d)" % len(new))
    for m, col in zip(mt, ("red", "green")):
        for k, s in enumerate(m["spans"]):
            plt.plot([s["a"][0], s["b"][0]], [s["a"][2], s["b"][2]], col, lw=4, label=m["kind"] if k == 0 else None)
    plt.gca().set_aspect("equal")
    plt.legend()
    fig.savefig(os.path.join(out, "dubai_nov04_complements.png"), dpi=90, bbox_inches="tight")
    print(len(a), "bonus (", int((d >= 2).sum()), "absents du 10 ) ;", [(m["kind"], len(m["spans"])) for m in mt], "->", out)


if __name__ == "__main__":
    main()
