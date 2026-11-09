#!/usr/bin/env python3
"""Blur .ipf (root.pak ui/data/ipf) vector shapes: read, rebuild, add a reversed route outline.

The menu / loading screen draws the glowing route outline from ui/data/ipf/minimap/<city>_ui.ipf: one group per
route, named like the route (lower case), holding the outline and "<route>_start_line". Layout (LE, no offsets):
  file   u32 0x100000, u32 1, u32 3, u32 0, str "ui", u32 group count, groups
  group  u32 3, u32 id, str "<group>", u32 child count, children
  shape  u32 1, u32 id, str name, 70 bytes (colour, width, bounds...), u32 1, u32 n, n vertices of 8 f32:
         map x, map y (0..1), stroke offset x, y, 0, 0, t = progress along the outline 0..1 (the drawing
         animation), side 0/1 (vertex pairs of a strip)
  str = u32 length + bytes, no NUL.
usage: bluripf.py FILE.ipf      (lists the groups)
"""
import struct, sys
import numpy as np

SHAPE_HEAD = 70


def _str(b, o):
    n = struct.unpack_from("<I", b, o)[0]
    return b[o + 4:o + 4 + n].decode("latin1"), o + 4 + n


def _pstr(s):
    return struct.pack("<I", len(s)) + s.encode("latin1")


def parse(b):
    head = b[:16]
    ui, o = _str(b, 16)
    ng = struct.unpack_from("<I", b, o)[0]
    o += 4
    groups = []
    for _ in range(ng):
        kind, gid = struct.unpack_from("<II", b, o)
        assert kind == 3, hex(o)
        gname, o = _str(b, o + 8)
        nc = struct.unpack_from("<I", b, o)[0]
        o += 4
        children = []
        for _ in range(nc):
            ckind, cid = struct.unpack_from("<II", b, o)
            assert ckind == 1, hex(o)
            name, o = _str(b, o + 8)
            shead = b[o:o + SHAPE_HEAD]
            one, n = struct.unpack_from("<II", b, o + SHAPE_HEAD)
            o += SHAPE_HEAD + 8
            verts = np.frombuffer(b[o:o + 32 * n], "<f4").reshape(n, 8).copy()
            o += 32 * n
            children.append(dict(id=cid, name=name, head=shead, one=one, verts=verts))
        groups.append(dict(id=gid, name=gname, children=children))
    assert o == len(b), (o, len(b))
    return dict(head=head, ui=ui, groups=groups)


def build(d):
    out = bytearray(d["head"]) + _pstr(d["ui"]) + struct.pack("<I", len(d["groups"]))
    for g in d["groups"]:
        out += struct.pack("<II", 3, g["id"]) + _pstr(g["name"]) + struct.pack("<I", len(g["children"]))
        for c in g["children"]:
            out += struct.pack("<II", 1, c["id"]) + _pstr(c["name"]) + c["head"]
            out += struct.pack("<II", c["one"], len(c["verts"])) + c["verts"].astype("<f4").tobytes()
    return bytes(out)


def _shape_at(b, name):
    """(start, end, vertex offset, vertex count) of the plain shape named `name` (kind 1, one == 1)."""
    key = _pstr(name)
    o = b.index(key) - 8
    assert struct.unpack_from("<I", b, o)[0] == 1, name
    v = o + 8 + len(key) + SHAPE_HEAD
    one, n = struct.unpack_from("<II", b, v)
    assert one == 1, (name, one)
    return o, v + 8 + 32 * n, v + 8, n


def add_reversed(b, orig, new):
    """File bytes + a new top-level group for route `new`: copies of route `orig`'s outline (drawn the other way:
    t -> 1 - t) and start line, renamed. Nothing else in the file is rewritten (some files hold an <exclude> mask
    of another layout, or groups nested in a group: Long Beach Docks), only the top-level count goes up by one."""
    orig, new = orig.lower(), new.lower()
    parts = []
    # the outline is named "<route>" or "<route>_ui" (Gracia 1, River 3 / 6): the copy follows the same pattern
    outline = "_ui" if _pstr(orig + "_ui") in b else ""
    for suffix in (outline, "_start_line"):
        s, e, v, n = _shape_at(b, orig + suffix)
        shape = bytearray(b[s:e])
        old_name = _pstr(orig + suffix)
        shape[8:8 + len(old_name)] = b""
        shape[8:8] = _pstr(new + suffix)
        if suffix == outline:
            vo = v - s - len(old_name) + len(_pstr(new + suffix))
            verts = np.frombuffer(bytes(shape[vo:vo + 32 * n]), "<f4").reshape(n, 8).copy()
            verts[:, 6] = 1.0 - verts[:, 6]
            shape[vo:vo + 32 * n] = verts.astype("<f4").tobytes()
        parts.append(bytes(shape))
    count_at = 16 + 4 + struct.unpack_from("<I", b, 16)[0]
    out = bytearray(b)
    struct.pack_into("<I", out, count_at, struct.unpack_from("<I", b, count_at)[0] + 1)
    gid = 1000 + struct.unpack_from("<I", b, count_at)[0]          # ids repeat in the game's files: not keys
    out += struct.pack("<II", 3, gid) + _pstr("<group>") + struct.pack("<I", len(parts)) + b"".join(parts)
    return bytes(out)


def add_reversed_game(b, orig, new):
    """In-race HUD minimap (<city>_game.ipf, another shape layout, not decoded): the "<route>" and "<route>_alt" shapes
    copied, renamed, at the end of the file. Same roads both ways, so the same outline. Every route file ends with
    its "<group>" (route shapes are its last children): appending adds children to it, its count goes up."""
    import re
    orig, new = orig.lower(), new.lower()
    names = sorted(m.start() - 4 for m in re.finditer(rb"[a-z0-9_<>]{4,}", b)
                   if struct.unpack_from("<II", b, m.start() - 12) [0] == 1
                   and struct.unpack_from("<I", b, m.start() - 4)[0] == len(m.group()))
    starts = {_str(b, o)[0]: o - 8 for o in names}
    ends = dict(zip([o - 8 for o in names], [o - 8 for o in names[1:]] + [len(b)]))
    assert ends[max(starts.values())] == len(b) and orig in starts, (orig, list(starts))
    parts = []
    for suffix in ("", "_alt"):
        if orig + suffix not in starts:
            continue
        s = starts[orig + suffix]
        shape = b[s:ends[s]]
        old = _pstr(orig + suffix)
        parts.append(shape[:8] + _pstr(new + suffix) + shape[8 + len(old):])
    g = b.index(_pstr("<group>")) + len(_pstr("<group>"))
    out = bytearray(b)
    struct.pack_into("<I", out, g, struct.unpack_from("<I", b, g)[0] + len(parts))
    return bytes(out) + b"".join(parts)


if __name__ == "__main__":
    d = parse(open(sys.argv[1], "rb").read())
    for g in d["groups"]:
        print(g["id"], g["name"], [(c["name"], len(c["verts"])) for c in g["children"]])
