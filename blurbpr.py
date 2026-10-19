#!/usr/bin/env python3
"""Blur UI texture bundle (.bpr, magic '2RZB', e.g. root.pak ui/data/ui_frontend.bpr): read / export / replace images in place.

Layout (LE), checked on ui_frontend.bpr (226 images, every size matches its format):
  0x00 '2RZB'  u16 version (0x203)  u16 table + names bytes  u32 table bytes (= n * 28)  u32 data bytes  u32 0
  0x14 n records of 28 B: u16 flag (0x1C), u16 name offset (into the name table), u32 data offset (into the data),
       u32 1, u32 data size, u32 0, u16 format (1 = DXT1, 5 = DXT5, 6 = RGBA8), u16 mip count, u16 width, u16 height
  then the name table (NUL-terminated names), then the data, starting RIGHT AFTER THE NAMES (0x14 + u16 at +6),
  then padding to the end of the file. (Read from len - data bytes, every picture came out shifted by the
  1392-byte padding = a wrapped horizontal shift, seen in game 2026-10-19; the game uses 0x14 + u16 at +6.)
Route thumbnails / loading pictures are named after the Route Name (e.g. JPN_MHaruna_1, DXT1 512x256, 2 mips).

usage: blurbpr.py FILE.bpr                      list
       blurbpr.py FILE.bpr NAME OUT.png         export one image
"""
import io, struct, sys
import numpy as np
from PIL import Image

REC = 28
FOURCC = {1: b"DXT1", 5: b"DXT5"}


def _565(c):
    c = np.clip(np.rint(c), 0, 255).astype(np.int32)
    return (c[..., 0] >> 3 << 11) | (c[..., 1] >> 2 << 5) | (c[..., 2] >> 3)


def _rgb(v):
    r, g, b = (v >> 11) & 31, (v >> 5) & 63, v & 31
    return np.stack([(r << 3) | (r >> 2), (g << 2) | (g >> 4), (b << 3) | (b >> 2)], -1).astype(np.float64)


def dxt1(img):
    """Opaque DXT1 of an RGB image (w, h multiples of 4). Endpoints on each block's principal colour axis, then
    2 least-squares refinements; 4-colour mode only. Smoother than Pillow's encoder on glows (seen 2026-10-19)."""
    a = np.asarray(img.convert("RGB"), np.float64)
    h, w = a.shape[:2]
    blk = a.reshape(h // 4, 4, w // 4, 4, 3).transpose(0, 2, 1, 3, 4).reshape(-1, 16, 3)
    mean = blk.mean(1, keepdims=True)
    d = blk - mean
    _, _, vt = np.linalg.svd(d, full_matrices=False)
    axis = vt[:, 0][:, None, :]
    t = (d * axis).sum(-1)
    e0, e1 = mean[:, 0] + t.min(1)[:, None] * axis[:, 0], mean[:, 0] + t.max(1)[:, None] * axis[:, 0]
    W4 = np.array([0, 1 / 3, 2 / 3, 1.0])
    for _ in range(3):
        c0, c1 = _rgb(_565(e0)), _rgb(_565(e1))
        pal = c0[:, None] + W4[None, :, None] * (c1 - c0)[:, None]           # n, 4, 3
        idx = ((blk[:, :, None] - pal[:, None]) ** 2).sum(-1).argmin(-1)    # n, 16
        wt = W4[idx]                                                         # least squares for e0, e1
        A00, A01, A11 = ((1 - wt) ** 2).sum(1), ((1 - wt) * wt).sum(1), (wt ** 2).sum(1)
        B0, B1 = ((1 - wt)[..., None] * blk).sum(1), (wt[..., None] * blk).sum(1)
        det = A00 * A11 - A01 ** 2
        ok = np.abs(det) > 1e-6
        e0 = np.where(ok[:, None], (A11[:, None] * B0 - A01[:, None] * B1) / np.where(ok, det, 1)[:, None], e0)
        e1 = np.where(ok[:, None], (A00[:, None] * B1 - A01[:, None] * B0) / np.where(ok, det, 1)[:, None], e1)
    v0, v1 = _565(e0), _565(e1)
    swap = v0 < v1                                                           # 4-colour mode needs v0 > v1
    v0, v1 = np.where(swap, v1, v0), np.where(swap, v0, v1)
    c0, c1 = _rgb(v0), _rgb(v1)
    pal = np.stack([c0, c1, (2 * c0 + c1) / 3, (c0 + 2 * c1) / 3], 1)        # DXT1 index order 0, 1, 2/3, 1/3
    idx = ((blk[:, :, None] - pal[:, None]) ** 2).sum(-1).argmin(-1)
    idx = np.where((v0 == v1)[:, None], 0, idx)
    bits = (idx.astype(np.uint32) << (2 * np.arange(16, dtype=np.uint32))).sum(1).astype(np.uint32)
    out = np.zeros((len(blk), 2), np.uint32)
    out[:, 0] = v0.astype(np.uint32) | (v1.astype(np.uint32) << 16)
    out[:, 1] = bits
    return out.astype("<u4").tobytes()


def encode(img, fmt, mips):
    """Raw mip chain (largest first) as stored in a .bpr: DXT1 with our encoder, DXT5 with Pillow's."""
    out, im = b"", img.convert("RGBA" if fmt == 5 else "RGB")
    for _ in range(mips):
        if fmt == 1:
            out += dxt1(im)
        else:
            buf = io.BytesIO()
            im.save(buf, "DDS", pixel_format=FOURCC[fmt].decode())
            out += buf.getvalue()[128:]
        im = im.resize((max(1, im.width // 2), max(1, im.height // 2)), Image.LANCZOS)
    return out


class Bpr:
    def __init__(self, path=None, data=None):
        b = self.b = data if data is not None else open(path, "rb").read()
        assert b[:4] == b"2RZB", "not a 2RZB bundle"
        self.head = b[:0x14]
        tbl_names, = struct.unpack_from("<H", b, 6)
        tbl, datasz = struct.unpack_from("<II", b, 8)
        n = tbl // REC
        self.recs = [list(struct.unpack_from("<2H4I4H", b, 0x14 + REC * i)) for i in range(n)]
        nt = 0x14 + tbl
        self.data0 = 0x14 + tbl_names                         # the game reads the data from here
        self.names_raw = b[nt:self.data0]
        self.names = [self.names_raw[r[1]:self.names_raw.index(b"\0", r[1])].decode("latin-1") for r in self.recs]

    def raw(self, name):
        r = self.recs[self.names.index(name)]
        return r, self.b[self.data0 + r[2]:self.data0 + r[2] + r[4]]

    def spare_slot(self, fmt, mips, w, h, min_name=0, skip=()):
        """Index of the 2nd copy of a duplicated name whose 2 images are identical, in this format (free to reuse),
        whose own name string is at least `min_name` bytes (so a new name can be written in its place)."""
        seen = {}
        for i, (n, r) in enumerate(zip(self.names, self.recs)):
            if (n in seen and i not in skip and r[6:] == [fmt, mips, w, h] and len(n) >= min_name
                    and r[1] != self.recs[seen[n]][1]):
                j = seen[n]
                a, b = self.recs[j], r
                if self.b[self.data0 + a[2]:self.data0 + a[2] + a[4]] == self.b[self.data0 + b[2]:self.data0 + b[2] + b[4]]:
                    return i
            seen.setdefault(n, i)
        raise LookupError("no identical duplicate in this format")

    def reuse(self, slot, name, raw):
        """Record `slot` gets `name` (written over its own name string, padded with NULs) and `raw` data.
        Only those bytes change. Tested 2026-10-19: the u16 at +6 (table + names bytes) tells the game where the
        data starts: changing it (appending, or adding a name) shifted EVERY UI picture (garbage everywhere)."""
        b = bytearray(self.b)
        r = self.recs[slot]
        assert len(raw) == r[4], "same size only"
        nt = 0x14 + REC * len(self.recs)
        old = len(self.names[slot])
        enc = name.encode("latin-1")
        assert len(enc) <= old, "new name longer than the slot's name"
        b[nt + r[1]:nt + r[1] + old] = enc.ljust(old, b"\0")
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
