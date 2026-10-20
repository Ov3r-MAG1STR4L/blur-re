#!/usr/bin/env python3
"""Readable dump of a JBOA audio graph (.dat): one line per object, references shown by name.
Object i is named names[i + 1] (names[0] = graph name). Words: FFFF + value = constant, i << 16 = object i,
(port << 16) | i in mixers. Record boundaries = the word pairs [type, name offset of object k] in order.
usage: jboadump.py FILE.dat"""
import struct, sys
import make_music


def dump(path):
    j = make_music.Jboa(open(path, "rb").read())
    raw = j.names.split(b"\0")
    names = [n.decode(errors="replace") for n in raw]
    offs, o = [], 0
    for n in raw:
        offs.append(o)
        o += len(n) + 1
    by_off = dict(zip(offs, names))
    # object starts: name of object k is names[k+1], found as word right after its type word
    starts, i = [], 0
    for k in range(j.count):
        no = offs[k + 1]
        while not (j.w[i + 1] == no):
            i += 1
        starts.append(i)
        i += 2
    starts.append(len(j.w))

    def show(v):
        f = struct.unpack("<f", struct.pack("<I", v))[0]
        if v == 0xFFFF:
            return "#"
        if v == 0xFF800000:
            return "-inf"
        if v > 0x1000000 and 1e-6 < abs(f) < 1e7:
            return "%g" % f
        if v >= 0x10000 and (v & 0xFFFF) == 0 and (v >> 16) < j.count:
            return "@" + names[(v >> 16) + 1]
        if v >= 0x10000 and (v >> 16) < 64 and (v & 0xFFFF) < j.count:
            return "%d|@%s" % (v >> 16, names[(v & 0xFFFF) + 1])
        if v in by_off and v > 0:
            return "'" + by_off[v] + "'"
        return str(v)

    for k in range(j.count):
        w = j.w[starts[k]:starts[k + 1]]
        print(f"[{k}] type {w[0]} {names[k + 1]}: " + " ".join(show(v) for v in w[2:]))


if __name__ == "__main__":
    dump(sys.argv[1])
