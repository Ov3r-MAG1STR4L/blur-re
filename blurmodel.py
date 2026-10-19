#!/usr/bin/env python3
"""Extract embedded textures from Blur .model (CPModel) files -> proper .dds files.

Parsing logic follows the community Blender importer (TimberStalker/BlurImportExport, read-only reference):
sections are 8-byte padded titles + (length,end) ints; textures live after the FX-file list.
Only what is needed to reach the texture block is parsed.
"""
import struct, sys, os


DEBUG = bool(os.environ.get("BLURDEBUG"))


class R:
    def __init__(self, b): self.b = b; self.p = 0
    def read(self, n): v = self.b[self.p:self.p + n]; self.p += n; return v
    def i(self): return struct.unpack("<i", self.read(4))[0]
    def s(self, n=0, clip=0):
        if n == 0: n = self.i()
        v = self.read(n - clip)
        self.p += clip
        return v.decode("utf-8", "replace")
    def cs(self):
        e = self.b.index(b"\0", self.p); v = self.b[self.p:e]; self.p = e + 1; return v.decode("utf-8", "replace")
    def ad(self, n=4): self.p += n


def parse_textures(b):
    r = R(b)
    def sec(n, c):
        t = (r.s(n, c), r.i(), r.i())
        if DEBUG: print("sec", t, hex(r.p))
        return t
    r.s(4)                       # "  CP"
    sec(8, 3)                    # Model
    sec(8, 2); r.ad()            # Header
    sec(8, 2)                    # MdlDat
    sec(8, 2); r.ad()            # Header
    nmodels = r.i(); nelems = r.i(); r.ad(); r.read(24)    # counts, bbox
    sec(8, 2)                    # strtab
    n = r.i() + 1
    [r.i() for _ in range(n)]
    names = [r.cs() for _ in range(1, n)]
    sec(8, 2)                    # Models
    r.ad(100 * nmodels)
    sec(8, 1)                    # Elements
    r.ad(104 * nelems)
    for t in (2, 2, 2):          # constr, render, render
        sec(8, t)
    sec(8, 2); r.ad()            # Header
    sec(8, 3)                    # Scene
    r.ad(); r.ad(8); r.ad(); r.ad(8); r.ad(12); r.ad(8); r.ad(8); r.ad(8); r.ad()
    n_arch = r.i(); r.ad(8 * n_arch)
    r.ad(0xc); r.ad(8); r.ad(0x20); r.ad(8); r.ad()
    ff = r.i(); r.ad(ff + 4)
    r.ad(8); r.ad(8); r.ad()
    nvd = r.i()
    for _ in range(nvd):
        r.ad(); nd = r.i()
        for _ in range(nd):
            r.ad(); r.read(2); r.read(2); r.i(); r.ad(); r.i(); r.read(1)
    r.ad()
    nfx = r.i(); fx = []
    for _ in range(nfx):
        r.ad(); r.ad(); fx.append(r.s())
    r.ad(); r.ad(); r.ad(); r.ad()
    ntex = r.i()
    if DEBUG: print("nfx", nfx, "ntex", ntex, hex(r.p))
    tex = []
    for _ in range(ntex):
        name = r.s(); tu1 = r.i(); r.ad(12)
        name2 = r.s(); r.ad()
        for _ in range(11): r.i()
        length = r.i(); height = r.i(); width = r.i(); r.i()
        mips = r.i(); dxt = r.i(); r.i(); r.i()
        if DEBUG: print("tex", name, name2, length, height, width, mips, hex(dxt), hex(r.p))
        data = r.read(length - 0x1c)
        tex.append(dict(name=name, name2=name2, width=width, height=height, mips=mips,
                        fourcc=struct.pack("<I", dxt & 0xffffffff), data=data))
    return names, fx, tex


def scan_textures(b):
    """Find every texture record by its DXT fourcc (robust: models hold several texture blocks)."""
    import re
    out = []
    for m in re.finditer(rb"DXT[1-5]", b):
        p = m.start()
        if p < 80: continue
        length, height, width, _, mips = struct.unpack_from("<5i", b, p - 20)
        if not (0 < width <= 4096 and 0 < height <= 4096 and 0 < mips <= 13 and length > 0x1c): continue
        data = b[p + 12: p + 12 + length - 0x1c]
        bs = 8 if m.group() == b"DXT1" else 16
        exp = sum(max(1, (width >> k + 3) // 4) * max(1, (height >> k + 3) // 4) * bs for k in range(mips))
        if len(data) < exp: continue
        name = "tex_%x" % p
        mk = p - 68                                   # 'RA\x01\x00' marker preceding the 11 ints
        for L in range(1, 65):
            o = mk - L - 4
            if o >= 0 and struct.unpack_from("<i", b, o)[0] == L:
                s = b[o + 4:o + 4 + L]
                if all(32 <= c < 127 for c in s): name = s.decode(); break
        out.append(dict(name=name, width=width, height=height, mips=mips, fourcc=m.group(), data=data[:exp], off=p))
    return out


def extract_all(path, outdir):
    b = open(path, "rb").read()
    os.makedirs(outdir, exist_ok=True)
    seen = {}
    res = []
    for t in scan_textures(b):
        k = seen.get(t["name"], 0); seen[t["name"]] = k + 1
        fn = t["name"] + ("" if k == 0 else "_%d" % k)
        open(os.path.join(outdir, fn + ".dds"), "wb").write(
            dds_header(t["width"], t["height"], t["mips"], t["fourcc"]) + t["data"])
        res.append((fn, t["width"], t["height"], t["mips"], t["fourcc"].decode(), hex(t["off"])))
    return res


def dds_header(w, h, mips, fourcc):
    bs = 8 if fourcc == b"DXT1" else 16
    lin = max(1, (w + 3) // 4) * max(1, (h + 3) // 4) * bs
    hdr = b"DDS " + struct.pack("<7I", 124, 0x000A1007, h, w, lin, 0, mips) + b"\0" * 44
    hdr += struct.pack("<II", 32, 4) + fourcc + b"\0" * 20
    hdr += struct.pack("<I", 0x401008) + b"\0" * 16
    return hdr


def extract(path, outdir):
    b = open(path, "rb").read()
    names, fx, tex = parse_textures(b)
    os.makedirs(outdir, exist_ok=True)
    out = []
    for t in tex:
        fn = os.path.join(outdir, t["name"] + ".dds")
        open(fn, "wb").write(dds_header(t["width"], t["height"], t["mips"], t["fourcc"]) + t["data"])
        out.append((t["name"], t["width"], t["height"], t["mips"], t["fourcc"], len(t["data"])))
    return names, fx, out


if __name__ == "__main__":
    for o in extract_all(sys.argv[1], sys.argv[2]): print(o)
