#!/usr/bin/env python3
"""Blur UI texture bundle (.bpr, magic '2RZB', e.g. root.pak ui/data/ui_frontend.bpr): read / add images.

Layout (LE), checked on ui_frontend.bpr (226 images, every size matches its format):
  0x00 '2RZB'  u16 version (0x203)  u16 ?  u32 table bytes (= n * 28)  u32 data bytes  u32 0  u16 28 (record size) u16 ?
  0x14 n records of 28 B: u16 flag (0x1C), u16 name offset (into the name table), u32 data offset (into the data),
       u32 1, u32 data size, u32 0, u16 format (1 = DXT1, 5 = DXT5, 6 = RGBA8), u16 mip count, u16 width, u16 height
  then the name table (NUL-terminated names), then the data, which ends the file (data starts at len - data bytes).
Route thumbnails / loading pictures are named after the Route Name (e.g. JPN_MHaruna_1, DXT1 512x256, 2 mips).

usage: blurbpr.py FILE.bpr                      list
       blurbpr.py FILE.bpr NAME OUT.png         export one image
"""
import io, struct, sys
from PIL import Image

REC = 28
FOURCC = {1: b"DXT1", 5: b"DXT5"}


def encode(img, fmt, mips):
    """Raw mip chain (largest first) in DXT1 / DXT5, as stored in a .bpr (Pillow's DDS encoder per level)."""
    out, im = b"", img.convert("RGBA" if fmt == 5 else "RGB")
    for _ in range(mips):
        buf = io.BytesIO()
        im.save(buf, "DDS", pixel_format=FOURCC[fmt].decode())
        out += buf.getvalue()[128:]
        im = im.resize((max(1, im.width // 2), max(1, im.height // 2)), Image.LANCZOS)
    return out


class Bpr:
    def __init__(self, path):
        b = self.b = open(path, "rb").read()
        assert b[:4] == b"2RZB", "not a 2RZB bundle"
        self.head = b[:0x14]
        tbl, datasz = struct.unpack_from("<II", b, 8)
        n = tbl // REC
        self.recs = [list(struct.unpack_from("<2H4I4H", b, 0x14 + REC * i)) for i in range(n)]
        nt = 0x14 + tbl
        self.data0 = len(b) - datasz
        self.names_raw = b[nt:self.data0]
        self.names = [self.names_raw[r[1]:self.names_raw.index(b"\0", r[1])].decode("latin-1") for r in self.recs]

    def raw(self, name):
        r = self.recs[self.names.index(name)]
        return r, self.b[self.data0 + r[2]:self.data0 + r[2] + r[4]]

    def build(self, extra=()):
        """Rebuild the file; `extra` = [(name, fmt, mips, w, h, raw)] appended (record, name, data at the end).
        The bytes between the names and the data (junk / padding in the originals) are kept."""
        recs = [list(r) for r in self.recs]
        names_len = sum(len(n) + 1 for n in self.names)
        assert self.names_raw[:names_len].count(b"\0") == len(self.names), "names not packed"
        names, junk = bytearray(self.names_raw[:names_len]), self.names_raw[names_len:]
        data = bytearray(self.b[self.data0:])
        for name, fmt, mips, w, h, raw in extra:
            recs.append([0x1C, len(names), len(data), 1, len(raw), 0, fmt, mips, w, h])
            names += name.encode("latin-1") + b"\0"
            data += raw
        tbl = REC * len(recs)
        head = bytearray(self.head)
        struct.pack_into("<HII", head, 6, tbl + len(names), tbl, len(data))   # u16 at 6 = table + names bytes
        return bytes(head) + b"".join(struct.pack("<2H4I4H", *r) for r in recs) + bytes(names) + junk + bytes(data)

    def spare_slot(self, fmt, mips, w, h):
        """Index of the 2nd copy of a duplicated name whose 2 images are identical, in this format (free to reuse)."""
        seen = {}
        for i, (n, r) in enumerate(zip(self.names, self.recs)):
            if n in seen and r[6:] == [fmt, mips, w, h]:
                j = seen[n]
                a, b = self.recs[j], r
                if self.b[self.data0 + a[2]:self.data0 + a[2] + a[4]] == self.b[self.data0 + b[2]:self.data0 + b[2] + b[4]]:
                    return i
            seen.setdefault(n, i)
        raise LookupError("no identical duplicate in this format")

    def reuse(self, slot, name, raw):
        """Same-size file: record `slot` gets `name` (written in the unused bytes after the names) and `raw` data.
        Tested 2026-10-19: an image APPENDED at the end was found by the game but shown black (UI texture budget?)."""
        b = bytearray(self.b)
        r = self.recs[slot]
        assert len(raw) == r[4], "same size only"
        names_len = sum(len(n) + 1 for n in self.names)
        nt = 0x14 + REC * len(self.recs)
        enc = name.encode("latin-1") + b"\0"
        assert names_len + len(enc) <= self.data0 - nt, "no room after the names"
        b[nt + names_len:nt + names_len + len(enc)] = enc
        struct.pack_into("<H", b, 0x14 + REC * slot + 2, names_len)
        struct.pack_into("<H", b, 6, struct.unpack_from("<H", b, 6)[0] + len(enc))
        b[self.data0 + r[2]:self.data0 + r[2] + r[4]] = raw
        return bytes(b)

    def image(self, name):
        r, raw = self.raw(name)
        fl, no, data, one, size, z, fmt, mips, w, h = r
        hdr = struct.pack("<4s7I44x2I4s5I", b"DDS ", 124, 0x1007 | 0x20000, h, w, 0, 0, mips, 32, 4,
                          FOURCC[fmt], 0, 0, 0, 0, 0).ljust(128, b"\0")
        return Image.open(io.BytesIO(hdr + raw))


if __name__ == "__main__":
    p = Bpr(sys.argv[1])
    if len(sys.argv) > 3:
        p.image(sys.argv[2]).save(sys.argv[3])
        print("saved", sys.argv[3])
    else:
        for name, r in zip(p.names, p.recs):
            print(f"{name:40} fmt {r[6]} mips {r[7]} {r[8]}x{r[9]} size {r[4]}")
