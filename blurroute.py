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
NODE (323 B) = 48-byte header + 11 "lines" of 25 bytes (stats over all 99 181 nodes of the 33 files):
    +0 x, +4 y, +8 z   position (Z NEGATED vs level coordinates; this module re-negates every z)
    +12 width (m)      lateral scale of the 11 lines (logic nodes are wider: corridor)
    +16 f32[2]         lateral unit direction in XZ (dot with road perpendicular = -0.999 median)
    +24 f32[3]         unit 3D vector whose XZ DIRECTION == +16, but with a large y part (0.8 seen):
                       not a usable lateral offset [meaning unknown]
    +36 / +40          low / high height bounds, wider than the 11 line heights (track volume?) [hypothesis]
    +44                always 0
    line k (k = 0..10) at 48 + 25*k:
        +0  f32  correlates 0.65 with the line's turn angle between nodes [hypothesis: steering hint]
        +4  f32  length to the next node along this line (m; median error vs geometry 0.015)
        +8  u32  always 0
        +12 f32  height of the line point (median error 0 vs y + bank * lateral offset)
        +16 f32  lateral position across the width, 0..1 (medians 0.24 ... 0.77, centre line k=5 at 0.5);
                 point XZ = (x,z) + lateral2D * frac * width  (node = road EDGE: driven 2026-10-19)
        +20..+24 always 0

Writing: build(parse(b, raw=True)) == b on all 33 files (raw mode keeps block order and node bytes).

usage: blurroute.py FILE.aid [out.json] [out.png] [level actorpack.json] [--full: include the 11 lines]
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


FULL = "--full" in sys.argv


def _node(b, o):
    x, y, z, w, lx, lz, bx, by, bz, ylo, yhi = struct.unpack_from("<11f", b, o)
    n = {"x": x, "y": y, "z": -z, "width": w, "lateral": [lx, -lz], "lateral3d": [bx, by, -bz],
         "ylow": ylo, "yhigh": yhi}
    if FULL:
        n["lines"] = [dict(zip(("turn", "length", "height", "frac"),
                               struct.unpack_from("<2f4x2f", b, o + 48 + 25 * k))) for k in range(11)]
    return n


def _nodes(b, o, count, raw=False):
    if raw:                                           # keep the exact 323 bytes (for writing)
        return [b[o + 323 * k:o + 323 * (k + 1)] for k in range(count)]
    return [_node(b, o + 323 * k) for k in range(count)]


def parse(b, raw=False):
    """raw=True: nodes are the original 323-byte blobs and d['blocks'] keeps the file order (for build())."""
    _n = lambda o, c: _nodes(b, o, c, raw)
    version, nblocks = struct.unpack_from("<fI", b, 0)
    o, sections, junctions, blocks = 8, [], [], []
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
                             "extra": extra, "nodes": _n(q, c)})
            blocks.append(sections[-1])
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
                          "nodes": _n(p, c)})
        blocks.append(junctions[-1])
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
    d = {"version": version, "sections": sections, "junctions": junctions, "logic_table": table}
    if raw:
        d["blocks"] = blocks
    return d


def build(d):
    """Inverse of parse(b, raw=True): byte-identical on all 33 .aid files."""
    s = lambda text: struct.pack("<I", len(text)) + text.encode()
    out = [struct.pack("<fI", d["version"], len(d["blocks"]))]
    for blk in d["blocks"]:
        if "type" in blk:                             # section
            t = blk["type"]
            head = struct.pack("<3I", 0, 0, t)
            if t & 0x80:
                head += struct.pack("<I", blk["extra"])
            out.append(s(blk["name"]) + head + struct.pack("<I", len(blk["nodes"])))
        else:                                         # junction
            out.append(s(blk["name"]) + s(blk["from"]) + s(blk["to"]) + struct.pack("<I", blk["flags"]))
            r = blk["rule"]
            if blk["flags"] & 0x80:
                out.append(struct.pack("<I", r["kind"]))
                if r["kind"] == 2:
                    out.append(s(r["section"]) + struct.pack("<I", r["b"]))
                else:
                    out.append(struct.pack(f"<I{len(r['values'])}f", r["b"], *r["values"]))
            out.append(struct.pack("<I", len(blk["nodes"])))
        out.extend(blk["nodes"])
    out.append(struct.pack("<I", len(d["logic_table"])))
    for refs in d["logic_table"]:
        out.append(struct.pack("<I", len(refs)))
        out.extend(struct.pack("<I", i) + s(sec) for i, sec in refs)
    return b"".join(out)


if __name__ == "__main__":
    sys.argv = [a for a in sys.argv if a != "--full"]
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
