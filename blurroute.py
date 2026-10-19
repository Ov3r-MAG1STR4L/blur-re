#!/usr/bin/env python3
"""Blur AI track data (gamedata/levels/<lvl>/<lvl>_<n>.aid) - full parser, all 33 files read to EOF.

File: f32 version (6.0), u32 nBlocks, nBlocks blocks, then the logic table.
Strings are u32 length + chars (no NUL, no padding). Node = 323 bytes (see NODE).

Section block: name, u32 0, u32 0, u32 type, [u32 extra if type & 0x80], u32 count, count nodes.
    type bits (names from Blur.exe debug draw "AmaxAI.DebugDraw.TrackData.*"):
      0x01 closed loop, 0x02 LogicStart (start/finish line), 0x04 LogicFinish,
      0x08 LogicInter1, 0x10 LogicInter2, 0x20 Logic (progress line), 0x80 extra u32
      (e.g. "river_reset"), 0x400 unknown (5 MainLoops). 0 = racing section (shortcut/alt route),
      1 = main loop, 0x21 = logic loop, 0x20 = point-to-point logic.
Junction block: name, from-section name, to-section name, u32 flags (0x40 or 0xC0),
    if flags & 0x80: u32 kind, then kind 5: u32 b + 3 f32 | 9: u32 b + 2 f32 | 6: u32 b + 1 f32 |
    2: section name + u32 b  (AI route-choice rule? values not interpreted), then u32 count + nodes.
Logic table (after the blocks): u32 N (== Logic node count), N x [u32 n, n x (u32 nodeIdx, name)]
    = racing nodes associated with each logic node (137 032 refs over all files, all valid).
NODE (323 B): +0 x, +4 y, +8 z (Z NEGATED vs level coordinates), +12 width (m; logic nodes are
    wider: corridor), rest unidentified (+16.. unit vectors, +36 lateral value, 3 sub-blocks).

usage: blurroute.py FILE.aid [out.json] [out.png] [level actorpack.json for start positions]
"""
import json, struct, sys

RULE_FLOATS = {5: 3, 9: 2, 6: 1}
TYPE_NAMES = {0x01: "loop", 0x02: "start", 0x04: "finish", 0x08: "inter1", 0x10: "inter2",
              0x20: "logic", 0x80: "extra", 0x400: "flag400"}


def _name(b, o):
    n = struct.unpack_from("<I", b, o)[0]
    if not (1 <= n <= 64 and all(32 <= c < 127 for c in b[o + 4:o + 4 + n])):
        raise ValueError(f"bad string at {o:#x}")
    return b[o + 4:o + 4 + n].decode(), o + 4 + n


def _nodes(b, o, count):
    return [dict(zip(("x", "y", "z", "width"), (x, y, -z, w)))
            for x, y, z, w in (struct.unpack_from("<4f", b, o + 323 * k) for k in range(count))]


def parse(b):
    version, nblocks = struct.unpack_from("<fI", b, 0)
    o, sections, junctions = 8, [], []
    for _ in range(nblocks):
        name, p = _name(b, o)
        z0, z1, t, c = struct.unpack_from("<4I", b, p)
        if (z0, z1) == (0, 0):                        # section
            q = p + 16
            extra = None
            if t & 0x80:
                extra, c = c, struct.unpack_from("<I", b, q)[0]
                q += 4
            sections.append({"name": name, "type": t, "flags": [v for k, v in TYPE_NAMES.items() if t & k],
                             "extra": extra, "nodes": _nodes(b, q, c)})
            o = q + 323 * c
            continue
        frm, p = _name(b, p)                          # junction
        to, p = _name(b, p)
        flags = struct.unpack_from("<I", b, p)[0]; p += 4
        rule = None
        if flags & 0x80:
            kind = struct.unpack_from("<I", b, p)[0]; p += 4
            if kind == 2:
                ref, p = _name(b, p)
                rule = {"kind": 2, "section": ref, "b": struct.unpack_from("<I", b, p)[0]}; p += 4
            else:
                nf = RULE_FLOATS[kind]
                bo, *vals = struct.unpack_from(f"<I{nf}f", b, p); p += 4 + 4 * nf
                rule = {"kind": kind, "b": bo, "values": vals}
        c = struct.unpack_from("<I", b, p)[0]; p += 4
        junctions.append({"name": name, "from": frm, "to": to, "flags": flags, "rule": rule,
                          "nodes": _nodes(b, p, c)})
        o = p + 323 * c
    n = struct.unpack_from("<I", b, o)[0]; o += 4
    table = []
    for _ in range(n):
        k = struct.unpack_from("<I", b, o)[0]; o += 4
        refs = []
        for _ in range(k):
            idx = struct.unpack_from("<I", b, o)[0]
            sec, o = _name(b, o + 4)
            refs.append([idx, sec])
        table.append(refs)
    assert o == len(b), f"stopped at {o:#x} of {len(b):#x}"
    return {"version": version, "sections": sections, "junctions": junctions, "logic_table": table}


if __name__ == "__main__":
    d = parse(open(sys.argv[1], "rb").read())
    for s in d["sections"]:
        print(f"section  {s['name']:20} {len(s['nodes']):5} nodes  {'/'.join(s['flags']) or 'racing'}")
    for j in d["junctions"]:
        print(f"junction {j['name']:20} {j['from']} -> {j['to']}  {len(j['nodes'])} nodes  rule={j['rule']}")
    print(f"logic table: {len(d['logic_table'])} entries")
    if len(sys.argv) > 2:
        json.dump(d, open(sys.argv[2], "w"), indent=1)
    if len(sys.argv) > 3:
        import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
        fig, ax = plt.subplots(figsize=(11, 11))
        for s in d["sections"]:
            xs, zs = [n["x"] for n in s["nodes"]], [n["z"] for n in s["nodes"]]
            if s["type"] & 0x20:
                ax.plot(xs, zs, "k--", lw=.8, label=f"{s['name']} (logic)")
            elif s["type"] & 0x1E:
                ax.plot(xs, zs, lw=4, alpha=.7, label=f"{s['name']} ({'/'.join(s['flags'])})")
            else:
                ax.plot(xs, zs, lw=2 if s["type"] & 1 else .9, label=f"{s['name']} ({len(xs)})")
        for j in d["junctions"]:
            ax.plot([n["x"] for n in j["nodes"]], [n["z"] for n in j["nodes"]], "m:", lw=1.5)
        if len(sys.argv) > 4:
            a = json.load(open(sys.argv[4], encoding="utf-8"))["LevelActorList"]
            S = [x["WorldMatrix"]["aw"] for l in a.values() for x in ((l or {}).get("LevelActors") or [])
                 if x and (x.get("Name") or "").startswith("StartPosition")]
            ax.plot([p["vx"] for p in S], [p["vz"] for p in S], "r+", label="StartPosition")
        ax.set_aspect("equal"); ax.legend(fontsize=6); plt.savefig(sys.argv[3], dpi=80)
