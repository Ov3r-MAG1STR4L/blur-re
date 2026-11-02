"""Blur .model (CPModel) de TAILLE LIBRE, à partir d'un gabarit du jeu (Projet J).

Map Builder (cpmodel.make_mesh) réécrit un modèle sans changer ses tailles. Ici on agrandit : flux de sommets,
flux de faces et texture couleur sont remplacés, puis on corrige les longueurs des sections qui les contiennent.

Gabarit : models/objects/usa_la_downtown/misc/sign_wetfloor.model (root.pak), 11 695 o : 1 flux de sommets
(pos f32x3, normale u8x4 canal 3, uv f16x2 = 20 o), 1 flux de faces u16, 2 maillages (bandes), textures
« sign_wetfloor_diff » (couleur) et « sign_wetfloor_ipr0 » (matériau, VERT = lumière propre).
Faits (2026-10-27, lus dans le gabarit) :
- section = titre 8 o + u32 longueur (en-tête compris) + u32 drapeaux ; "  CP" + section Model (longueur @0xC) ;
- flux de sommets : … u32 nb sommets, "RA\\0\\0", u32 octets, u32 16, zéros jusqu'à pos % 16 == 12, données ;
- flux de faces : 02 "RA\\1\\0" u32 nb index, 0, "RA\\0\\0", u32 octets, u32 16, zéros, données ;
- texture : … u32 longueur (= 0x1C + données), u32 largeur, u32 hauteur, u32 ?, u32 mips, "DXT1", 8 o, données ;
- maillage : "RA\\1\\0" matériau, définition, type de faces (0 liste, 1 bande), … puis
  "RA\\0\\0" début faces, nb index, début sommets, nb sommets.
Relecture de contrôle : lecteur BlurImportExport (TimberStalker) via cpmodel.parse de Map Builder (MIT).
"""
import math
import os
import struct
import sys

import config

MB = os.environ.get("BMB_DIR", config.MAP_BUILDER_DIR)
os.environ.setdefault("BMB_GAME", os.path.dirname(MB))
os.environ.setdefault("BMB_INSTALLED", "1")
sys.path[:0] = [os.path.join(MB, "model"), MB]
import cpmodel  # noqa: E402

DIFF, MAT = "sign_wetfloor_diff", "sign_wetfloor_ipr0"
SECTIONS = (b"Header", b"MdlDat", b"StrTab", b"Models", b"Element", b"Constr", b"Render", b"Scene", b"Coll",
            b"MtaDbg")


def _find1(d, pat, start=0):
    i = d.find(pat, start)
    assert i >= 0 and d.find(pat, i + 1) < 0, "motif absent ou pas unique : %r" % pat
    return i


def _sections(d):
    """[(offset du champ longueur, début, longueur)] de toutes les sections"""
    out = [(0xC, 4, struct.unpack_from("<I", d, 0xC)[0])]
    for name in SECTIONS:
        key = name.ljust(8, b"\0")
        i = d.find(key)
        while i >= 0:
            if d[i + 14:i + 16] in (b"A\0", b"C\0"):
                out.append((i + 8, i, struct.unpack_from("<I", d, i + 8)[0]))
            i = d.find(key, i + 1)
    return out


def _dxt1_alpha(px, w, h):
    """RGBA w x h (multiples de 4) -> DXT1 ; bloc avec un pixel transparent (alpha < 128) : mode 3 couleurs
    (c0 <= c1), index 3 = transparent ; sinon 4 couleurs. Extrémités = boîte des couleurs opaques du bloc."""
    import numpy as np
    a = np.frombuffer(px, np.uint8).reshape(h // 4, 4, w // 4, 4, 4).transpose(0, 2, 1, 3, 4).reshape(-1, 16, 4)
    rgb, op = a[:, :, :3].astype(np.int32), a[:, :, 3] >= 128
    big = np.where(op[:, :, None], rgb, -1).max(1)
    small = np.where(op[:, :, None], rgb, 999).min(1)
    big, small = np.maximum(big, 0), np.minimum(small, 255)
    c565 = lambda c: (c[:, 0] >> 3 << 11) | (c[:, 1] >> 2 << 5) | (c[:, 2] >> 3)
    hi, lo = c565(big), c565(small)
    alpha = ~op.all(1)
    c0, c1 = np.where(alpha, np.minimum(hi, lo), np.maximum(hi, lo)), np.where(alpha, np.maximum(hi, lo), np.minimum(hi, lo))
    four = ~alpha & (c0 == c1)                                   # couleur unie : c0 > c1 impossible, index 0 partout
    exp = lambda c: np.stack([(c >> 11 & 31) * 255 // 31, (c >> 5 & 63) * 255 // 63, (c & 31) * 255 // 31], 1)
    e0, e1 = exp(c0), exp(c1)
    pal = np.where(alpha[:, None, None], np.stack([e0, e1, (e0 + e1) // 2, e0], 1),
                   np.stack([e0, e1, (2 * e0 + e1) // 3, (e0 + 2 * e1) // 3], 1))
    idx = ((rgb[:, :, None, :] - pal[:, None, :, :]) ** 2).sum(3)
    idx[:, :, 3] = np.where(alpha[:, None], 1 << 30, idx[:, :, 3])
    k = idx.argmin(2)
    k = np.where(alpha[:, None] & ~op, 3, k)
    k = np.where(four[:, None], 0, k)
    bits = (k.astype(np.uint32) << (2 * np.arange(16, dtype=np.uint32))).sum(1).astype(np.uint32)
    out = np.zeros(len(a), dtype=[("c0", "<u2"), ("c1", "<u2"), ("i", "<u4")])
    out["c0"], out["c1"], out["i"] = c0, c1, bits
    return out.tobytes()


def _mips_alpha(px, w, h, mips):
    """comme cpmodel.encode_mips, mais RGBA (transparence 1 bit gardée à chaque niveau)"""
    import numpy as np
    img = np.frombuffer(px, np.uint8).reshape(h, w, 4).astype(np.float32)
    out = bytearray()
    for i in range(mips):
        if i:
            hh, ww = max(1, img.shape[0] // 2), max(1, img.shape[1] // 2)
            img = img[:hh * 2, :ww * 2].reshape(hh, 2, ww, 2, 4).mean((1, 3)) if img.shape[0] > 1 and img.shape[1] > 1                 else img[::2 if img.shape[0] > 1 else 1, ::2 if img.shape[1] > 1 else 1]
        bh, bw = max(4, -(-img.shape[0] // 4) * 4), max(4, -(-img.shape[1] // 4) * 4)
        pad = np.pad(img, ((0, bh - img.shape[0]), (0, bw - img.shape[1]), (0, 0)), mode="edge")
        out += _dxt1_alpha(np.round(pad).astype(np.uint8).tobytes(), bw, bh)
    return bytes(out)


def build(template, verts, indices, rgb, w, h, glow=160, salt=None, pad_verts=None, pad_indices=None):
    """verts = [(x, y, z, nx, ny, nz, u, v)], indices = triangles (u16), rgb = octets RGB (ou RGBA : transparence
    1 bit du DXT1) w x h -> .model
    salt : nouveaux identifiants de texture (le jeu garde une texture par identifiant ; Map Builder fait pareil) ;
    pad_verts / pad_indices : taille fixe (sommets répétés, triangles vides) - tous les modèles Map Builder issus
    d'un même gabarit ont la même taille ; les nôtres de tailles différentes plantent au chargement (0x6DB2EB)"""
    if pad_verts:
        assert len(verts) <= pad_verts, (len(verts), pad_verts)
        verts = list(verts) + [verts[0]] * (pad_verts - len(verts))
    if pad_indices:
        assert len(indices) <= pad_indices, (len(indices), pad_indices)
        indices = list(indices) + [indices[0]] * (pad_indices - len(indices))
    assert len(verts) <= 0xFFFF
    d = template
    P = cpmodel.parse(d)
    assert P["stride"] == 20 and P["vcount"] == 68 and P["fcount"] == 104, "pas le gabarit attendu"
    rep = []                                        # (début, fin, octets) ou (début, fin, en-tête, données alignées)

    # texture couleur (taille libre)
    toff = P["textures"][DIFF][0]
    j = toff - 12                                   # "DXT1"
    assert d[j:j + 4] == b"DXT1"
    old_len = struct.unpack_from("<I", d, j - 20)[0]
    mips = int(math.log2(max(w, h))) + 1         # jusqu'au grand côté (gabarit 32x128 : 8 niveaux)
    if len(rgb) == w * h * 4 and min(rgb[3::4]) < 128:         # transparence : notre encodeur 1 bit
        tex = _mips_alpha(rgb, w, h, mips)              # (le shader du gabarit rend le transparent en noir, vu en jeu)
    else:                                                      # opaque : encodeur de Map Builder, comme avant
        tex = cpmodel.encode_mips(bytes(rgb[i] for i in range(len(rgb)) if i % 4 != 3) if len(rgb) == w * h * 4
                                  else rgb, w, h, mips)
    rep.append((j - 20, j - 8, struct.pack("<3I", 0x1C + len(tex), w, h)))
    rep.append((j - 4, j, struct.pack("<I", mips)))
    rep.append((toff, j - 16 + old_len, tex))
    # texture matériau : même taille, couleur unie (VERT = lumière : le niveau Map Builder n'éclaire pas les objets)
    moff, mw, mh, mm = P["textures"][MAT]
    mat = cpmodel.encode_mips(cpmodel.solid(mw, mh, (0, glow, 0)), mw, mh, mm)
    rep.append((moff, moff + len(mat), mat))

    # sommets
    vc = _find1(d, struct.pack("<I", 68) + b"RA\0\0" + struct.pack("<2I", 68 * 20, 16))
    vdata = b"".join(struct.pack("<3f4B2e", x, y, z, *(max(0, min(254, round(127 + 127 * c))) for c in (nx, ny, nz)),
                                 0, u, v) for x, y, z, nx, ny, nz, u, v in verts)
    vs = P["vstart"]
    rep.append((vc, vs + 68 * 20, struct.pack("<I", len(verts)) + b"RA\0\0" + struct.pack("<2I", len(vdata), 16),
                vdata))
    # faces
    fc = _find1(d, b"\x02RA\x01\x00" + struct.pack("<I", 104), vs) + 5
    assert d[fc + 8:fc + 12] == b"RA\0\0" and struct.unpack_from("<I", d, fc + 12)[0] == 208
    fs = P["fstart"]
    fdata = struct.pack("<%dH" % len(indices), *indices)
    rep.append((fc, fs + 208, struct.pack("<I", len(indices)) + d[fc + 4:fc + 12] + struct.pack("<2I", len(fdata), 16),
                fdata))
    # maillages : les 2 niveaux de détail = tout, en liste de triangles
    for old in (struct.pack("<4I", 76, 28, 4, 64), struct.pack("<4I", 0, 76, 0, 52)):
        i = _find1(d, b"RA\0\0" + old, fs) + 4
        rep.append((i, i + 16, struct.pack("<4I", 0, len(indices), 0, len(verts))))
    i = fs
    for _ in range(2):
        i = d.find(b"RA\x01\x00" + struct.pack("<3I", 0, 0, 1), i + 1)
        assert i > fs
        rep.append((i + 12, i + 16, struct.pack("<I", 0)))

    # assemblage ; shift[k] = (début dans le gabarit, décalage des octets du gabarit qui suivent)
    out, at, shifts = bytearray(), 0, []
    for r in sorted(rep):
        assert r[0] >= at, "remplacements qui se chevauchent"
        out += d[at:r[0]]
        out += r[2]
        if len(r) == 4:                             # données alignées : pos % 16 == 12
            out += b"\0" * ((12 - len(out)) % 16)
            out += r[3]
        at = r[1]
        shifts.append((r[0], len(out) - at))
    out += d[at:]

    def shift(pos):
        s = 0
        for a, g in shifts:
            if a < pos:
                s = g
        return s
    for lf, s, L in _sections(d):
        grow = shift(s + L) - shift(s)
        if grow:
            struct.pack_into("<I", out, lf + shift(lf), L + grow)
    xs, ys, zs = zip(*((v[0], v[1], v[2]) for v in verts))
    cpmodel.write_bbox(out, cpmodel.parse(bytes(out)), (min(xs), min(ys), min(zs), max(xs), max(ys), max(zs)))
    return cpmodel.new_texture_ids(bytes(out), salt) if salt else bytes(out)


def cube(size=10.0):
    V, I = [], []
    for ax in range(3):
        for s in (-1, 1):
            n = [0, 0, 0]
            n[ax] = s
            u_, v_ = (ax + 1) % 3, (ax + 2) % 3
            base = len(V)
            for a, b in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
                p = [0.0] * 3
                p[ax], p[u_], p[v_] = size / 2 * s, size / 2 * a, size / 2 * b
                V.append((p[0], p[1] + size / 2, p[2], *n, (a + 1) / 2, (b + 1) / 2))
            I += [base, base + 1, base + 2, base, base + 2, base + 3] if s > 0 else \
                [base, base + 2, base + 1, base, base + 3, base + 2]
    return V, I


if __name__ == "__main__":
    # contrôle : un cube (damier 64x64) relu par le lecteur BlurImportExport
    t = open(sys.argv[1], "rb").read()
    V, I = cube()
    w = h = 64
    rgb = b"".join(bytes([230 if (x // 8 + y // 8) % 2 else 30] * 3) for y in range(h) for x in range(w))
    out = build(t, V, I, rgb, w, h)
    P = cpmodel.parse(out)
    assert P["vcount"] == len(V) and P["fcount"] == len(I), P
    assert P["textures"][DIFF][1:3] == (w, h), P["textures"]
    print("cube OK :", len(out), "octets,", P["vcount"], "sommets,", P["fcount"], "index", P["meshes"], P["bbox"])
    if len(sys.argv) > 2:
        open(sys.argv[2], "wb").write(out)
