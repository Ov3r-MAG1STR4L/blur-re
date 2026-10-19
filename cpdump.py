#!/usr/bin/env python3
"""Dump the chunk tree of Blur "CP" files (.level, .levelphysics, .levelrender, .model ...).

Layout (LE): "  CP" magic, then chunks. Chunk = tag[8] (NUL padded), u32 size (whole chunk incl.
this 16-byte header), u16 count, u16 kind: 'C' = container (count child chunks follow),
'A' = atom (raw data after the header).
usage: cpdump.py FILE [maxdepth]
"""
import re, struct, sys


def chunks(b, off, end):
    while off + 16 <= end:
        tag = b[off:off + 8].rstrip(b"\0").decode("latin-1")
        size, count, kind = struct.unpack_from("<IHH", b, off + 8)
        if size < 16 or off + size > end or kind not in (0x41, 0x43):
            return
        yield off, tag, size, count, chr(kind)
        off += size


def dump(b, off, end, depth, maxd):
    for o, tag, size, count, kind in chunks(b, off, end):
        data = b[o + 16:o + size]
        strs = [s.decode() for s in re.findall(rb"[ -~]{4,}", data[:4096])][:4] if kind == "A" else []
        print(f"{'  ' * depth}{tag:10} {kind} size={size:<9} n={count:<5} @{o:#x}" + (f"  {strs}" if strs else ""))
        if kind == "C" and depth < maxd:
            dump(b, o + 16, o + size, depth + 1, maxd)


if __name__ == "__main__":
    b = open(sys.argv[1], "rb").read()
    assert b[:4] == b"  CP", "not a CP file"
    dump(b, 4, len(b), 0, int(sys.argv[2]) if len(sys.argv) > 2 else 3)
