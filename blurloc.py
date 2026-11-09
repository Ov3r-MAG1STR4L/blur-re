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


def parse_raw(b):
    """Everything needed to rebuild the file: keys [(hash, name)] in file order, languages [(code, {hash: text})]."""
    assert b[:4] == b"OLTX", "not OLTX"
    nlang = struct.unpack_from("<I", b, 0x14)[0]
    kb = 0x1C + 24 * nlang

    def table(base):
        cnt = struct.unpack_from("<I", b, base)[0]
        return [struct.unpack_from("<II", b, base + 8 + 8 * i) for i in range(cnt)]

    keys = [(h, b[kb + o:b.index(b"\0", kb + o)].decode("latin1")) for h, o in table(kb)]
    langs = []
    for i in range(nlang):
        o = 0x1C + 24 * i
        base = struct.unpack_from("<I", b, o + 16)[0]
        texts = {}
        for h, so in table(base):
            s = e = base + so
            while b[e:e + 2] != b"\0\0":
                e += 2
            texts[h] = b[s:e].decode("utf-16-le")
        langs.append((b[o:o + 16], texts))
    return dict(head=b[:0x1C], keys=keys, langs=langs)


def build(d):
    """Inverse of parse_raw (identical bytes on the game's 23 .loc files). Key table in the given order; every
    language table sorted by hash (unsigned, as in all the game's files: the game looks texts up by hash)."""
    nlang = len(d["langs"])
    kb = 0x1C + 24 * nlang
    names = bytearray()
    ktab = bytearray(struct.pack("<II", len(d["keys"]), 8))
    for h, name in d["keys"]:
        ktab += struct.pack("<II", h, 8 + 8 * len(d["keys"]) + len(names))
        names += name.encode("latin1") + b"\0"
    blocks, ofs = [], kb + len(ktab) + len(names)
    entries = bytearray()
    for code, texts in d["langs"]:
        tab = bytearray(struct.pack("<II", len(texts), 8))
        strs = bytearray()
        for h in sorted(texts):
            tab += struct.pack("<II", h, 8 + 8 * len(texts) + len(strs))
            strs += texts[h].encode("utf-16-le") + b"\0\0"
        blk = bytes(tab + strs)
        entries += code + struct.pack("<II", ofs, len(blk))
        blocks.append(blk)
        ofs += len(blk)
    head = bytearray(d["head"])
    struct.pack_into("<I", head, 0x0C, kb + len(ktab) + len(names) - 0x10)
    struct.pack_into("<I", head, 0x14, nlang)
    return bytes(head) + bytes(entries) + bytes(ktab) + bytes(names) + b"".join(blocks)


def add_text(d, key, hash_, texts):
    """Add a key (new hash: the game's key -> hash function is unknown, a Route's LocString holds the hash itself)
    with one text per language code ({"en": ..., "fr": ...}; missing languages get the English text)."""
    assert all(h != hash_ for h, _ in d["keys"]), hex(hash_)
    d["keys"].append((hash_, key))
    for code, t in d["langs"]:
        t[hash_] = texts.get(code.rstrip(b"\0").decode(), texts["en"])


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
