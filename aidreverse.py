#!/usr/bin/env python3
"""Reverse a point-to-point Blur route (.aid): drive it the other way.

usage: aidreverse.py IN.aid OUT.aid

Per node (323 B, layout in blurroute.py):
  header: position moved to the opposite road edge (+ lateral2D * width), y / width / height bounds kept;
          lateral axis (+16 2D, +24 3D) negated.
  11 lines: order reversed and frac -> 1 - frac (point = node + lateral * frac * width stays in place);
            +4 length-to-next and +0 turn hint are taken from the previous original node
            (turn sign flipped: HYPOTHESIS, the field is not fully understood); last node gets 0.
Blocks: node order reversed; gates swapped (Start <-> Finish, Inter1 <-> Inter2: nodes exchanged,
block names/types kept); logic table re-indexed. Junctions (not on Haruna) are not supported.
"""
import struct, sys
import blurroute

SWAP_FLAG = {0x02: 0x04, 0x04: 0x02, 0x08: 0x10, 0x10: 0x08}


def _reverse_nodes(nodes):
    n = len(nodes)
    out = []
    for j in range(n):
        i = n - 1 - j
        cur = nodes[i]
        prev = nodes[i - 1] if i > 0 else None       # next node in the reversed direction
        b = bytearray(cur[:48])
        x, y, z, w, lx, lz, bx, by, bz = struct.unpack_from("<9f", b, 0)
        # the node is one EDGE of the road (driven 2026-10-19: road = node + lateral * 0..width), so the
        # reversed node moves to the opposite edge along the UNIT 2D axis (+16; the +24 vector has a large y part,
        # its XZ part is not unit); y kept (line heights are stored per line, ylow == y). File frame for both.
        struct.pack_into("<f", b, 0, x + lx * w)
        struct.pack_into("<f", b, 8, z + lz * w)
        struct.pack_into("<5f", b, 16, -lx, -lz, -bx, -by, -bz)
        for m in range(11):
            k = 10 - m
            line = bytearray(cur[48 + 25 * k:48 + 25 * (k + 1)])
            turn, length = (struct.unpack_from("<2f", prev, 48 + 25 * k) if prev else (0.0, 0.0))
            frac = struct.unpack_from("<f", line, 16)[0]
            struct.pack_into("<2f", line, 0, -turn if turn else 0.0, length)
            struct.pack_into("<f", line, 16, 1.0 - frac)
            b += line
        out.append(bytes(b))
    return out


def reverse(d):
    if any("from" in blk for blk in d["blocks"]):
        raise NotImplementedError("junctions are not supported (route with shortcuts)")
    gate = {blk["type"] & 0x1E: blk for blk in d["blocks"] if blk["type"] & 0x1E}
    old_nodes = {blk["name"]: blk["nodes"] for blk in d["blocks"]}
    rename = {}                                       # old block name -> block that now holds its nodes
    for blk in d["blocks"]:
        bit = blk["type"] & 0x1E
        src = gate[SWAP_FLAG[bit]] if bit in SWAP_FLAG and SWAP_FLAG[bit] in gate else blk
        rename[src["name"]] = blk["name"]
        blk["nodes"] = _reverse_nodes(old_nodes[src["name"]])
    count = {name: len(nodes) for name, nodes in old_nodes.items()}
    d["logic_table"] = [[[count[sec] - 1 - idx, rename[sec]] for idx, sec in reversed(refs)]
                        for refs in reversed(d["logic_table"])]
    return d


def _centres(nodes):
    """Road centres (file frame, x z) of raw nodes: node = road edge, centre = node + lateral2D * width / 2."""
    out = []
    for nd in nodes:
        x, y, z, w, lx, lz = struct.unpack_from("<6f", nd, 0)
        out.append((x + lx * w / 2, z + lz * w / 2))
    return out


def move_gate(d, name, first_main):
    """Slide gate block `name` along the road so its first node lies on Main node `first_main` (same node count,
    same gate width, centred on the road). Logic-table references to the gate are re-attached by geometry.
    Why: reversed, each gate's first node lies ~92 m before the painted line it belongs to, and a race starts /
    ends at the first node of its gate (original Haruna: start gate 16 m before the painted start line, finish
    gate 4 m after the painted finish line; player report: the finish fired before the line)."""
    blk = {b["name"]: b for b in d["blocks"]}
    main, gate = blk["Main"]["nodes"], blk[name]["nodes"]
    mc = _centres(main)

    def nearest(p):
        return min(range(len(mc)), key=lambda i: (mc[i][0] - p[0]) ** 2 + (mc[i][1] - p[1]) ** 2)

    old = [nearest(p) for p in _centres(gate)]
    shift = first_main - old[0]
    new_nodes, under = [], []
    for nd, m in zip(gate, old):
        j = max(0, min(len(main) - 1, m + shift))
        src = main[j]
        wg = struct.unpack_from("<f", nd, 12)[0]
        x, y, z, wm, lx, lz = struct.unpack_from("<6f", src, 0)
        b = bytearray(src[:48])
        cx, cz = x + lx * wm / 2, z + lz * wm / 2
        struct.pack_into("<4f", b, 0, cx - lx * wg / 2, y, cz - lz * wg / 2, wg)
        for k in range(11):
            line = bytearray(src[48 + 25 * k:48 + 25 * (k + 1)])
            fm = struct.unpack_from("<f", line, 16)[0]
            struct.pack_into("<f", line, 16, 0.5 + (fm - 0.5) * wm / wg)   # same point, wider gate
            b += line
        new_nodes.append(bytes(b))
        under.append(j)
    blk[name]["nodes"] = new_nodes
    at = {}
    for k, j in enumerate(under):
        at.setdefault(j, []).append(k)
    table = []
    for refs in d["logic_table"]:
        keep = [r for r in refs if r[1] != name]
        mains = [r[0] for r in refs if r[1] == "Main"]
        keep += [[k, name] for j in mains for k in at.get(j, [])]
        table.append(keep)
    d["logic_table"] = table
    return shift


if __name__ == "__main__":
    d = reverse(blurroute.parse(open(sys.argv[1], "rb").read(), raw=True))
    open(sys.argv[2], "wb").write(blurroute.build(d))
    print("written", sys.argv[2])
