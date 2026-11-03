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
block names/types kept); logic table re-indexed. Junctions (main -> branch): rebuilt at the mirror place
(_reverse_junction), rule kept.
"""
import struct, sys
import blurroute

SWAP_FLAG = {0x02: 0x04, 0x04: 0x02, 0x08: 0x10, 0x10: 0x08}


def _reverse_nodes(nodes, loop=False):
    n = len(nodes)
    out = []
    for j in range(n):
        i = n - 1 - j
        cur = nodes[i]
        prev = nodes[i - 1] if i > 0 or loop else None   # next node in the reversed direction (a loop wraps)
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


SPLIT = 6.0        # m between branch and main centres: beyond this the branch has left the main road


def _split_after(bc, mc, start):
    """first branch index >= start whose centre is more than SPLIT m from every main centre (the branch leaves)"""
    for i in range(start, len(bc)):
        if min((bc[i][0] - x) ** 2 + (bc[i][1] - z) ** 2 for x, z in mc) > SPLIT ** 2:
            return i
    return len(bc)


def _nearest(cs, p):
    return min(range(len(cs)), key=lambda i: (cs[i][0] - p[0]) ** 2 + (cs[i][1] - p[1]) ** 2)


def _reverse_junction(j, old, new):
    """Junction j (from main to branch) rebuilt for the reversed route. Original: an overlap strip where the branch
    still runs on the main road, `gap` branch nodes before the branch leaves it (Tokyo Bayshore: 8 nodes, 22 m
    wide, between main and branch centres). Reversed: the same strip before the split the other way (near the
    original rejoin). Each node = the reversed branch node, centred halfway to the main road, original width; line
    fractions rescaled so every line point stays where it was. Returns [(junction node, main node index)] for the
    logic table. old / new: block name -> raw nodes."""
    mo, bo = _centres(old[j["from"]]), _centres(old[j["to"]])
    first = _nearest(bo, _centres(j["nodes"][:1])[0])
    last = _nearest(bo, _centres(j["nodes"][-1:])[0])
    gap = _split_after(bo, mo, last) - last
    mn, bn = _centres(new[j["from"]]), _centres(new[j["to"]])
    end = max(len(j["nodes"]) - 1, _split_after(bn, mn, 0) - gap)
    widths = [struct.unpack_from("<f", nd, 12)[0] for nd in j["nodes"]]
    out = []
    for k in range(len(j["nodes"])):
        src = new[j["to"]][end - (len(j["nodes"]) - 1) + k]
        x, y, z, wb, lx, lz = struct.unpack_from("<6f", src, 0)
        bc = (x + lx * wb / 2, z + lz * wb / 2)
        mi = _nearest(mn, bc)
        c = ((bc[0] + mn[mi][0]) / 2, (bc[1] + mn[mi][1]) / 2)
        wj = widths[k]
        shift = (bc[0] - c[0]) * lx + (bc[1] - c[1]) * lz        # old centre - new centre, along the lateral axis
        b = bytearray(src[:48])
        struct.pack_into("<f", b, 0, c[0] - lx * wj / 2)
        struct.pack_into("<f", b, 8, c[1] - lz * wj / 2)
        struct.pack_into("<f", b, 12, wj)
        for m in range(11):
            line = bytearray(src[48 + 25 * m:48 + 25 * (m + 1)])
            f = struct.unpack_from("<f", line, 16)[0]
            struct.pack_into("<f", line, 16, 0.5 + ((f - 0.5) * wb + shift) / wj)
            b += line
        out.append((bytes(b), mi))
    print(f"  junction {j['name']}: original on branch nodes {first}-{last} ({gap} before the split), "
          f"reversed on branch nodes {end - len(out) + 1}-{end}")
    return out


def reverse(d):
    """Reverse every section; junctions (from main to a branch) rebuilt at the mirror place (_reverse_junction)."""
    sections = [blk for blk in d["blocks"] if "from" not in blk]
    names = {blk["name"] for blk in sections}
    # dead junctions in the original files (Gracia 5, Amboy 3, Downtown 3/4: a branch that does not exist) are dropped
    dead = {blk["name"] for blk in d["blocks"] if "from" in blk and not {blk["from"], blk["to"]} <= names}
    d["blocks"] = [blk for blk in d["blocks"] if blk["name"] not in dead]
    d["logic_table"] = [[r for r in refs if r[1] not in dead] for refs in d["logic_table"]]
    junctions = [blk for blk in d["blocks"] if "from" in blk]
    gate = {blk["type"] & 0x1E: blk for blk in sections if blk["type"] & 0x1E}
    old_nodes = {blk["name"]: blk["nodes"] for blk in d["blocks"]}
    rename = {}                                       # old block name -> block that now holds its nodes
    for blk in sections:
        bit = blk["type"] & 0x1E
        src = gate[SWAP_FLAG[bit]] if bit in SWAP_FLAG and SWAP_FLAG[bit] in gate else blk
        rename[src["name"]] = blk["name"]
        blk["nodes"] = _reverse_nodes(old_nodes[src["name"]], loop=bool(src["type"] & 1))
    new_nodes = {blk["name"]: blk["nodes"] for blk in sections}
    count = {name: len(nodes) for name, nodes in old_nodes.items()}
    jnames = {j["name"] for j in junctions}
    d["logic_table"] = [[[count[sec] - 1 - idx, rename[sec]] for idx, sec in reversed(refs) if sec not in jnames]
                        for refs in reversed(d["logic_table"])]
    for j in junctions:
        built = _reverse_junction(j, old_nodes, new_nodes)
        j["nodes"] = [nd for nd, _ in built]
        # logic rows that see the main node under a junction node see that junction node too (as in the original)
        under = {}
        for k, (_, mi) in enumerate(built):
            under.setdefault(mi, []).append(k)
        d["logic_table"] = [refs + [[k, j["name"]] for idx, sec in refs if sec == j["from"] for k in under.get(idx, [])]
                            for refs in d["logic_table"]]
    return d


def _centres(nodes):
    """Road centres (file frame, x z) of raw nodes: node = road edge, centre = node + lateral2D * width / 2."""
    out = []
    for nd in nodes:
        x, y, z, w, lx, lz = struct.unpack_from("<6f", nd, 0)
        out.append((x + lx * w / 2, z + lz * w / 2))
    return out


def roles(d):
    """Blocks by role, whatever their names (mainLoop, START, Start_line...): racing line = the biggest block with
    no gate / logic bit; start / finish / inter gates by type bit (0x02 / 0x04 / 0x08 / 0x10), logic 0x20."""
    secs = [b for b in d["blocks"] if "nodes" in b and "type" in b]   # junction blocks have no type
    out = {"main": max((b for b in secs if not b["type"] & 0x3E), key=lambda b: len(b["nodes"]))}
    for role, bit in (("start", 0x02), ("finish", 0x04), ("inter1", 0x08), ("inter2", 0x10), ("logic", 0x20)):
        found = [b for b in secs if b["type"] & bit]
        if found:
            out[role] = found[0]
    return out


def move_gate(d, name, first_main):
    """Slide gate block `name` along the road so its first node lies on Main node `first_main` (same node count,
    same gate width, centred on the road). Logic-table references to the gate are re-attached by geometry.
    Why: reversed, each gate's first node lies ~92 m before the painted line it belongs to, and a race starts /
    ends at the first node of its gate (original Haruna: start gate 16 m before the painted start line, finish
    gate 4 m after the painted finish line; player report: the finish fired before the line)."""
    blk = {b["name"]: b for b in d["blocks"] if "nodes" in b}
    main_name = roles(d)["main"]["name"]
    main, gate = blk[main_name]["nodes"], blk[name]["nodes"]
    mc = _centres(main)

    def nearest(p):
        return min(range(len(mc)), key=lambda i: (mc[i][0] - p[0]) ** 2 + (mc[i][1] - p[1]) ** 2)

    old = [nearest(p) for p in _centres(gate)]
    shift = first_main - old[0]
    new_nodes, under = [], []
    for nd, m in zip(gate, old):
        j = (m + shift) % len(main)                       # wraps on a loop; a point-to-point gate stays inside
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
        mains = [r[0] for r in refs if r[1] == main_name]
        keep += [[k, name] for j in mains for k in at.get(j, [])]
        table.append(keep)
    d["logic_table"] = table
    return shift


if __name__ == "__main__":
    d = reverse(blurroute.parse(open(sys.argv[1], "rb").read(), raw=True))
    open(sys.argv[2], "wb").write(blurroute.build(d))
    print("written", sys.argv[2])
