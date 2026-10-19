#!/usr/bin/env python3
"""Blur .loc (OLTX) reader -> JSON / TSV.

Layout (LE):
  0x00 'OLTX' u32 ver(1) u32 hdrsize(0x10) u32 keyblock_size
  0x10 u32 ?  u32 nlang  u32 langtable_ofs(0x84)?  then nlang * 24-byte entries:
         [lang(4 ascii) 0 0 0 blockOfs blockSize]
  key block  (right after lang table): u32 count, u32 entsize(8), count*(u32 hash, u32 ofs), NUL-terminated key names
             (ofs relative to key-block start)
  per-language block: same shape, table sorted by hash, ofs -> NUL-terminated string (UTF-8) relative to block start.
The hash function of the keys is not needed to read a .loc: keys carry their own hash.
"""
import struct, sys, json, os, glob


def parse(path):
    b = open(path, "rb").read()
    assert b[:4] == b"OLTX", "not OLTX"
    nlang = struct.unpack_from("<I", b, 0x14)[0]
    langs = []
    for i in range(nlang):
        o = 0x1C + 24 * i
        code = b[o:o + 4].rstrip(b"\0").decode()
        ofs, size = struct.unpack_from("<II", b, o + 16)
        langs.append((code, ofs, size))
    kb = 0x1C + 24 * nlang

    def table(base):
        cnt, es = struct.unpack_from("<II", b, base)
        return [struct.unpack_from("<II", b, base + 8 + 8 * i) for i in range(cnt)]

    def cstr(base, ofs):
        o = base + ofs
        return b[o:b.index(b"\0", o)]

    keys = {h: cstr(kb, ofs).decode("latin1") for h, ofs in table(kb)}
    out = {}
    for code, base, size in langs:
        d = {}
        for h, ofs in table(base):
            o = base + ofs
            e = o
            while b[e:e + 2] != b"\0\0":     # UTF-16LE, NUL terminated
                e += 2
            d[keys.get(h, "0x%08x" % h)] = b[o:e].decode("utf-16-le", "replace")
        out[code] = d
    return out


if __name__ == "__main__":
    src = sys.argv[1]
    dst = sys.argv[2] if len(sys.argv) > 2 else None
    files = glob.glob(os.path.join(src, "*.loc")) if os.path.isdir(src) else [src]
    allout = {}
    for f in files:
        allout[os.path.basename(f)] = parse(f)
    if dst:
        os.makedirs(dst, exist_ok=True)
        for n, d in allout.items():
            json.dump(d, open(os.path.join(dst, n + ".json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    for n, d in allout.items():
        print(n, {k: len(v) for k, v in d.items()})
