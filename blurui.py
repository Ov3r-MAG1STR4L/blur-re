#!/usr/bin/env python3
"""Menu / HUD Lua scripts embedded in Blur.exe: 'BZUI' archive (read-only extractor).

Layout (big-endian, Xbox 360 heritage), found 2026-10-19 at file offset ~0xB9DEF1 of Blur.exe:
  'BZUI'  u32 count (144)
  count x 16 B: u32 name offset, u32 data offset, u32 compressed size, u32 size   (offsets from the name table)
  name table (NUL-terminated, e.g. 'Screens\\Multiplayer\\Shared\\MpCustomRace.lua'), then the data:
  each script = zlib stream of a compiled Lua 5.1 chunk ('\\x1bLuaQ', little-endian, 4-byte int/size_t, 8-byte number).
usage: blurui.py BLUR.EXE OUT_DIR       (writes OUT_DIR/<name>.luac)
"""
import os, struct, sys, zlib


def scripts(exe):
    b = open(exe, "rb").read()
    hdr = b.find(b"BZUI")
    while not 0 < struct.unpack_from(">I", b, hdr + 4)[0] < 10000:   # the word also appears as plain text
        hdr = b.find(b"BZUI", hdr + 1)
    n = struct.unpack_from(">I", b, hdr + 4)[0]
    tab = hdr + 8
    names0 = tab + 16 * n
    for i in range(n):
        no, do, cs, us = struct.unpack_from(">4I", b, tab + 16 * i)
        name = b[names0 + no:b.index(b"\0", names0 + no)].decode()
        data = zlib.decompress(b[names0 + do:names0 + do + cs])
        assert len(data) == us
        yield name, data


if __name__ == "__main__":
    for name, data in scripts(sys.argv[1]):
        p = os.path.join(sys.argv[2], name.replace("\\", os.sep) + "c")
        os.makedirs(os.path.dirname(p), exist_ok=True)
        open(p, "wb").write(data)
    print("written to", sys.argv[2])
