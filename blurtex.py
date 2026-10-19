#!/usr/bin/env python3
"""Extract ALL textures of a Blur .model (inline ones + streamed mip-chain ones) to DDS (+PNG).

Record layout found by RE (fourcc position p):
  p-28 u32 texhash | p-24 u32 flag | p-20 i32 length | p-16 height | p-12 width | p-8 1 | p-4 mips | p 'DXTn'
  p+4 u32 0 | p+8 u32 3 | p+12 'RA\0\0' | p+16 u32 datasize | p+20 u32 align | data @ align_up(p+24, align)
  inline textures (length > 0x1c): data directly at p+12, (length-0x1c) bytes.
Streamed textures are one record per mip level (16x16 first, then 32,64,...); the 16x16 record carries the
tail of the mip chain (16..1).  Full DDS = levels from biggest to smallest.
"""
import re, struct, os, sys
from blurmodel import dds_header


def find_name(b, p):
    mk = b.rfind(b"RA\x01\x00", max(0, p - 160), p)
    if mk < 0: return None
    for L in range(1, 65):
        o = mk - L - 4
        if o >= 0 and struct.unpack_from("<i", b, o)[0] == L and all(32 <= c < 127 for c in b[o + 4:o + 4 + L]):
            return b[o + 4:o + 4 + L].decode()
    return None


def records(b):
    out = []
    for m in re.finditer(rb"DXT[1-5]", b):
        p = m.start()
        if p < 40: continue
        length, h, w, _, mips = struct.unpack_from("<5i", b, p - 20)
        if not (0 < w <= 4096 and 0 < h <= 4096 and 0 < mips <= 13): continue
        rec = dict(p=p, w=w, h=h, mips=mips, fourcc=m.group(), name=find_name(b, p))
        if length > 0x1c:
            rec["kind"] = "inline"; rec["data"] = b[p + 12:p + 12 + length - 0x1c]
            rec["off"] = p + 12
        elif b[p + 12:p + 16] == b"RA\x00\x00":
            size, align = struct.unpack_from("<II", b, p + 16)
            if not (0 < size < 1 << 26 and align in (1, 2, 4, 8, 16, 32, 64, 128, 256, 512, 1024, 2048, 4096)): continue
            start = (p + 24 + align - 1) // align * align
            rec["kind"] = "level"; rec["data"] = b[start:start + size]; rec["off"] = start
        else:
            continue
        out.append(rec)
    return out


def _gray(data, w, h, fourcc):
    import io
    import numpy as np
    from PIL import Image
    try:
        return np.asarray(Image.open(io.BytesIO(dds_header(w, h, 1, fourcc) + data)).convert("L"), dtype=np.float32)
    except Exception:
        return None


def _bsize(w, h, fourcc):
    return ((w + 3) // 4) * ((h + 3) // 4) * (8 if fourcc == b"DXT1" else 16)


def _fix_starts(b, lv):
    """Pick the real start of each mip-level block: level data is 8-byte-block aligned to p+24, but the padding
    length (0..48) varies -> choose the shift whose image best matches the box-downsampled bigger level."""
    import numpy as np
    lv = sorted(lv, key=lambda r: r["w"])
    prev = None                                   # decoded gray of the previous (smaller) level
    for r in lv:
        w, h, fc = r["w"], r["h"], r["fourcc"]
        n = _bsize(w, h, fc)
        cands = [r["p"] + 24 + j for j in range(0, 56, 8)]
        best = None
        if r["w"] == 16 or prev is None:
            # chain record: compare its 16x16 level with its own 8x8 level
            for s in cands:
                g = _gray(b[s:s + n], w, h, fc)
                g2 = _gray(b[s + n:s + n + _bsize(w // 2, h // 2, fc)], w // 2, h // 2, fc) if w >= 8 else None
                if g is None or g2 is None: continue
                d = float(np.abs(g.reshape(h // 2, 2, w // 2, 2).mean(axis=(1, 3)) - g2).mean())
                if best is None or d < best[0]: best = (d, s)
        else:
            for s in cands:
                g = _gray(b[s:s + n], w, h, fc)
                if g is None: continue
                ph, pw = prev.shape
                d = float(np.abs(g.reshape(h // 2, 2, w // 2, 2).mean(axis=(1, 3)) - prev).mean()) if (ph, pw) == (h // 2, w // 2) else 1e9
                if best is None or d < best[0]: best = (d, s)
        if best is None:
            best = (0, cands[2])
        s = best[1]
        r["off"] = s
        r["data"] = b[s:s + (r["size"] if "size" in r else len(r["data"]))]
        prev = _gray(r["data"][:n], w, h, fc)
    return lv


def textures(b):
    recs = records(b)
    tex = []
    cur = None
    for r in recs:
        if r["kind"] == "inline":
            tex.append(dict(name=r["name"], w=r["w"], h=r["h"], mips=r["mips"], fourcc=r["fourcc"], data=r["data"],
                            recs=[r]))
            cur = None
        else:
            if r["name"] and r["name"] != (cur or {}).get("name") or cur is None or r["w"] <= cur["lw"] // 1 and r["name"]:
                cur = dict(name=r["name"], levels=[r], lw=r["w"], fourcc=r["fourcc"])
                tex.append(cur)
            elif r["w"] > cur["lw"] and r["fourcc"] == cur["fourcc"]:
                cur["levels"].append(r); cur["lw"] = r["w"]
            else:
                cur = dict(name=r["name"], levels=[r], lw=r["w"], fourcc=r["fourcc"]); tex.append(cur)
    res = []
    for t in tex:
        if "levels" in t:
            lv = sorted(_fix_starts(b, t["levels"]), key=lambda r: -r["w"])
            t["levels"] = lv
            top = lv[0]
            res.append(dict(name=t["name"], w=top["w"], h=top["h"], mips=top["mips"], fourcc=top["fourcc"],
                            data=b"".join(l["data"] for l in lv), recs=lv))
        else:
            res.append(t)
    return res


def extract(path, outdir, png=True):
    b = open(path, "rb").read()
    os.makedirs(outdir, exist_ok=True)
    seen = {}
    rows = []
    for t in textures(b):
        name = t["name"] or "tex"
        k = seen.get(name, 0); seen[name] = k + 1
        fn = name if k == 0 else "%s_%d" % (name, k)
        dds = dds_header(t["w"], t["h"], t["mips"], t["fourcc"]) + t["data"]
        fp = os.path.join(outdir, fn + ".dds")
        open(fp, "wb").write(dds)
        ok = "dds"
        if png:
            try:
                from PIL import Image
                Image.open(fp).convert("RGBA").save(os.path.join(outdir, fn + ".png")); ok = "dds+png"
            except Exception as e:
                ok = "dds (png failed: %s)" % e
        rows.append((fn, t["w"], t["h"], t["mips"], t["fourcc"].decode(), len(t["data"]), ok))
    return rows


def _compress(img, fourcc):
    """RGBA PIL image -> raw DXT blocks (no header)."""
    import io
    w, h = img.size
    if w < 4 or h < 4:
        img = img.resize((max(4, w), max(4, h)))
    bio = io.BytesIO()
    img.save(bio, "DDS", pixel_format=fourcc.decode())
    return bio.getvalue()[128:]


def _chain(img, w, h, n, fourcc):
    from PIL import Image
    out = b""
    for k in range(n):
        lw, lh = max(1, w >> k), max(1, h >> k)
        out += _compress(img.resize((lw, lh), Image.LANCZOS), fourcc)
    return out


def inject(model, pngdir, outpath):
    """Replace textures of `model` by <pngdir>/<name>.png (same names as extract()). Sizes never change."""
    from PIL import Image
    b = bytearray(open(model, "rb").read())
    done = []
    seen = {}
    for t in textures(bytes(b)):
        name = t["name"] or "tex"
        k = seen.get(name, 0); seen[name] = k + 1
        fn = name if k == 0 else "%s_%d" % (name, k)
        fp = os.path.join(pngdir, fn + ".png")
        if not os.path.exists(fp): continue
        img = Image.open(fp).convert("RGBA")
        if img.size != (t["w"], t["h"]):
            img = img.resize((t["w"], t["h"]), Image.LANCZOS)
        for r in t["recs"]:
            if r["kind"] == "inline":
                new = _chain(img, r["w"], r["h"], r["mips"], r["fourcc"])
            else:
                n = 1 if r["w"] > 16 else r["mips"]          # 16x16 record carries the tail of the chain
                # the record of width W holds levels W .. W>>(n-1)
                new = _chain(img.resize((r["w"], r["h"]), Image.LANCZOS), r["w"], r["h"], n, r["fourcc"])
            if len(new) != len(r["data"]):
                print("size mismatch for", fn, r["w"], len(new), len(r["data"])); break
            b[r["off"]:r["off"] + len(new)] = new
        else:
            done.append(fn)
    open(outpath, "wb").write(bytes(b))
    return done


if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1] == "inject":
        print(inject(sys.argv[2], sys.argv[3], sys.argv[4]))
    else:
        for r in extract(sys.argv[1], sys.argv[2]): print(r)
