"""NFS Hot Pursuit (Wii) : export de la géométrie d'un fichier de lieu .stm (STME) en OBJ.

Usage : python stm2obj.py location11.stm sortie.obj [filtre_nom ...]
Format (déduit le 2026-10-26, voir CONNAISSANCES.md « Projet J ») :
- en-tête "STME", u32, "WI01", u32 n ; n entrées de 64 o : u32 type, nom[28], 8 u32 (… off @+8, taille @+12) ;
- maillage (types 6/7/8 = niveaux de détail .1f1/.011, .1f2/.012, .1f3) : nœuds de 0x38 o à partir de 0x40
  (+8 = offset liste GX), bloc sommets à u32 @0x14 : 3 offsets (positions s16x3, normales s8x3, UV s16x2) puis
  3 octets « index sur 1 octet ? » ; positions monde = s16 * échelle par axe (fixe pour tout le lieu).
"""
import struct
import sys

SCALE = (1 / 17.565, 1 / 76.8, 1 / 18.818)  # Location1 ; recalculé pour chaque lieu par entries() (calibrate)
UV_SCALE = 1 / 2048  # s16, 11 bits fractionnaires : VAT TEX0 des captures FIFO (Dubaï, Las Vegas), PROUVÉ 2026-10-27
_CAL = {}


def calibrate(d):
    """échelle par axe du lieu : médiane, sur les maillages, de (2 x demi-taille de la boîte d'en-tête @0x34) /
    (étendue des positions s16) ; fixe pour tout un .stm (Location1 : 17,565 / 76,8 / 18,818 unités par m)"""
    global SCALE
    key = (len(d), d[:64])
    if key not in _CAL:
        r = [[], [], []]
        for t, _, b in _entries(d):
            if t != 6 or len(b) < 0x40:
                continue
            try:
                vb = struct.unpack_from('>I', b, 0x14)[0]
                p0, p1 = struct.unpack_from('>2I', b, vb)
                q = [struct.unpack_from('>3h', b, p0 + 6 * j) for j in range((p1 - p0) // 6)]
                half = struct.unpack_from('>3f', b, 0x34)
            except struct.error:
                continue
            for a in range(3):
                span = max(v[a] for v in q) - min(v[a] for v in q) if q else 0
                if span > 50 and half[a] > 0.5:
                    r[a].append(2 * half[a] / span)
        _CAL[key] = tuple(sorted(x)[len(x) // 2] if x else s for x, s in zip(r, SCALE))
    SCALE = _CAL[key]
    return SCALE


def entries(d):
    calibrate(d)
    return _entries(d)


def _entries(d):
    n = struct.unpack_from('>I', d, 12)[0]
    for i in range(n):
        o = 16 + i * 64
        t = struct.unpack_from('>I', d, o)[0]
        name = d[o + 4:o + 32].split(b'\0')[0].decode('latin1')
        f = struct.unpack_from('>8I', d, o + 32)
        yield t, name, d[f[2]:f[2] + f[3]]


def mesh(b, mat=None):
    """-> (positions, uvs, faces[(pi,ti)x3]) d'un maillage STM."""
    vb = struct.unpack_from('>I', b, 0x14)[0]
    p0, p1, p2 = struct.unpack_from('>3I', b, vb)
    small = b[vb + 12:vb + 15]
    sizes = [1 if s else 2 for s in small]
    pos = [tuple(q * s for q, s in zip(struct.unpack_from('>3h', b, p0 + 6 * j), SCALE))
           for j in range((p1 - p0) // 6)]
    uvs = [(u * UV_SCALE, 1 - v * UV_SCALE) for u, v in
           (struct.unpack_from('>2h', b, p2 + 4 * j) for j in range((len(b) - p2) // 4))]
    subs = submeshes(b)
    ends = sorted({o for _, o, _ in subs}) + [vb]
    faces = []
    for m, p in sorted({(m, o) for m, o, _ in subs}, key=lambda x: x[1]):
        if mat is None or m == mat:
            faces += _dl(b, p, ends[ends.index(p) + 1], sizes)
    return pos, uvs, faces


def submeshes(b):
    """[(matériau, offset liste GX, n ?)] : entrées de 16 o (0, mat << 16, offset, n) des nœuds ; une liste va
    jusqu'à la suivante (bourrage 0x00 = NOP GX entre les primitives)."""
    vb = struct.unpack_from('>I', b, 0x14)[0]
    out, o, first = [], 0x40, vb
    while o + 16 <= first:
        w = struct.unpack_from('>4I', b, o)
        if w[0] == 0 and w[1] & 0xFFFF == 0 and 0x40 < w[2] < vb and b[w[2]] in (0x90, 0x98, 0xA0) and 0 < w[3] < 5000:
            out.append((w[1] >> 16, w[2], w[3]))
            first = min(first, w[2])
            o += 16
        else:
            o += 4
    return out


def _dl(b, p, end, sizes):
    faces = []
    while p < end:
        op = b[p]
        if op == 0:
            p += 1
            continue
        if op not in (0x90, 0x98, 0xA0):
            break
        cnt = struct.unpack_from('>H', b, p + 1)[0]
        p += 3
        vs = []
        for _ in range(cnt):
            idx = []
            for s in sizes:
                idx.append(b[p] if s == 1 else struct.unpack_from('>H', b, p)[0])
                p += s
            vs.append((idx[0], idx[2]))
        if op == 0x98:
            tri = [(vs[i], vs[i + 1], vs[i + 2]) if i % 2 == 0 else (vs[i + 1], vs[i], vs[i + 2])
                   for i in range(cnt - 2)]
        elif op == 0x90:
            tri = [tuple(vs[i:i + 3]) for i in range(0, cnt - 2, 3)]
        else:
            tri = [(vs[0], vs[i], vs[i + 1]) for i in range(1, cnt - 1)]
        faces += [t for t in tri if len({v[0] for v in t}) == 3]
    return faces


# Matériau m (u16 des sous-maillages) = fiche n° m - 1 de la table des matériaux rangée dans l'entrée .pvs
# (PROUVÉ par capture FIFO Dolphin, 2026-10-27, nfs_diag/d5_fifo.py : plus de 50 matériaux, 2 captures).
# Table : u32 nombre de fiches (0x18A pour location11) puis fiches de 0x160 o, la 1re sans nom : nom (0x40),
# en-tête (0x20, dernier u32 = nombre de textures), 4 emplacements de 0x40 (nom du .tex sur 0x20 puis paramètres).
# Emplacement utilisé si son 1er octet n'est pas 0 (sinon : reste de la fiche précédente, à ignorer). Fiche à
# 2 textures : la couleur visible est la dernière qui n'est pas envmap.tex (reflet des vitres). Fiche à 0 texture (« Material #… ») : couleur unie.
_MATS = {}


def materials(d):
    """{m: (nom de la fiche, [noms des .tex utilisés])}"""
    if id(d) in _MATS:
        return _MATS[id(d)]
    pvs = next(b for t, n, b in entries(d) if t == 1)
    base = pvs.find(bytes.fromhex("0000411cdcdd0000")) - 0x40 - 0x160      # fiche sans nom = fiche 0
    out = {}
    k = 0
    while base + (k + 1) * 0x160 <= len(pvs) and k < 0x400:
        o = base + k * 0x160
        if k and not 32 <= pvs[o] < 127:
            break
        name = pvs[o:o + 0x40].split(b"\0")[0].decode("latin1")
        used = [pvs[o + 0x60 + s * 0x40:o + 0x80 + s * 0x40].split(b"\0")[0].decode("latin1")
                for s in range(4) if pvs[o + 0x60 + s * 0x40]]
        out[k + 1] = (name, used)
        k += 1
    _MATS[id(d)] = out
    return out


def material_name(d, m):
    """entrée .tex de la texture visible du matériau m (None : pas de texture ou inconnu)"""
    used = [u for u in materials(d).get(m, (None, []))[1] if u.lower() != "envmap.tex"]   # envmap = reflet
    if not used:
        return None
    want = used[-1].lower()
    for typ, n, _ in entries(d):                     # noms d'entrées en minuscules, coupés à 27 caractères
        if typ == 4 and (n.lower() == want or (len(n) >= 26 and want.startswith(n.lower()))):
            return n
    return None


def material_color(d, m):
    """couleur unie (r, g, b) de la fiche du matériau m (en-tête +0x0B..+0x0D : ff RR GG BB), pour les fiches
    sans texture"""
    pvs = next(b for t, n, b in entries(d) if t == 1)
    base = pvs.find(bytes.fromhex("0000411cdcdd0000")) - 0x40 - 0x160
    o = base + (m - 1) * 0x160 + 0x40
    return tuple(pvs[o + 0x0B:o + 0x0E])


def texture_table(d):
    """table des noms de textures du .pvs (noms complets de 36 o, 255 pour location11 ; ordre de 1re utilisation,
    PAS un index de matériau)"""
    import re
    pvs = next(b for t, n, b in entries(d) if t == 1)
    names = {}
    for m in re.finditer(rb"\.tex\x00", pvs):
        q = pvs.rfind(bytes(1), 0, m.start()) + 1
        names[q] = pvs[q:m.start() + 4].decode("latin1")
    run = max((sum(1 for k in range(400) if a + 36 * k in names), a) for a in names)[1]
    out = []
    while run in names:
        out.append(names[run])
        run += 36
    return out


def texture_dxt1(d, name):
    """texture .tex/.mp1 (CMPR Wii) -> (largeur, hauteur, niveaux DXT1 [bytes]) ; en-tête 0x60 : u32 l, u32 h, …
    @0x14 = 0xFB (CMPR), puis niveaux de mip. CMPR = DXT1 en tuiles 8x8 de 4 blocs, couleurs big-endian,
    index 2 bits dans l'ordre inverse : conversion sans perte."""
    b = next(b for t, n, b in entries(d) if n == name)
    w, h = struct.unpack_from('>2I', b, 0)
    assert struct.unpack_from('>I', b, 0x14)[0] == 0xFB, 'pas du CMPR'
    p, levels = 0x60, []
    while w >= 4 and h >= 4 and p + w * h // 2 <= len(b):
        bx, by = w // 4, h // 4
        out = bytearray(bx * by * 8)
        k = p
        for ty in range(0, by, 2):
            for tx in range(0, bx, 2):
                for sy, sx in ((0, 0), (0, 1), (1, 0), (1, 1)):
                    c0, c1 = struct.unpack_from('>2H', b, k)
                    idx = bytes(sum(((v >> (2 * i)) & 3) << (6 - 2 * i) for i in range(4)) for v in b[k + 4:k + 8])
                    if ty + sy < by and tx + sx < bx:
                        struct.pack_into('<2H4s', out, ((ty + sy) * bx + tx + sx) * 8, c0, c1, idx)
                    k += 8
        levels.append(bytes(out))
        p += w * h // 2
        w, h = w // 2, h // 2
    w0, h0 = struct.unpack_from('>2I', b, 0)
    return w0, h0, levels


def texture_image(d, name):
    """texture -> image Pillow RGBA. En-tête : u32 l, h, f32 l, h, u32 mips, format @0x14, …, taille palette @0x1C,
    offset pixels @0x24, offset palette @0x28. Formats vus : 0xFB CMPR (via DXT1 + DDS en mémoire) ; 5 = C8
    (tuiles 8x4, palette RGB5A3)."""
    import io
    from PIL import Image
    b = next(b for t, n, b in entries(d) if n == name)
    w, h, _, _, _, fmt, _, pal, _, pix, poff = struct.unpack_from('>11I', b, 0)
    if fmt == 0xFB:
        w, h, lv = texture_dxt1(d, name)
        hdr = struct.pack('<4s7I44x2I4s20x I16x', b'DDS ', 124, 0x1007, h, w, len(lv[0]), 0, 1,
                          32, 4, b'DXT1', 0x1000)
        return Image.open(io.BytesIO(hdr + lv[0])).convert('RGBA')
    assert fmt == 5, 'format %#x pas géré' % fmt
    cols = []
    for v in struct.unpack_from('>%dH' % (pal // 2), b, poff):
        if v & 0x8000:
            cols.append(((v >> 10 & 31) * 255 // 31, (v >> 5 & 31) * 255 // 31, (v & 31) * 255 // 31, 255))
        else:
            cols.append(((v >> 8 & 15) * 17, (v >> 4 & 15) * 17, (v & 15) * 17, (v >> 12 & 7) * 255 // 7))
    img = Image.new('RGBA', (w, h))
    px, k = img.load(), pix
    for by in range(0, h, 4):
        for bx in range(0, w, 8):
            for y in range(4):
                for x in range(8):
                    px[bx + x, by + y] = cols[b[k]]
                    k += 1
    return img


def texture_png(d, name, path):
    texture_image(d, name).save(path)


def export(stm, out, filters=()):
    d = open(stm, 'rb').read()
    vo = to = 0
    with open(out, 'w') as f:
        for t, name, b in entries(d):
            if t != 6 or (filters and not name.lower().startswith(tuple(x.lower() for x in filters))):
                continue
            try:
                pos, uvs, faces = mesh(b)
            except (struct.error, ValueError, IndexError):
                print('ignoré', name)
                continue
            f.write(f'o {name}\n')
            # repère Blender/OBJ : on garde x, y en haut, z
            f.writelines(f'v {x:.3f} {y:.3f} {z:.3f}\n' for x, y, z in pos)
            f.writelines(f'vt {u:.5f} {v:.5f}\n' for u, v in uvs)
            for tri in faces:
                f.write('f ' + ' '.join(f'{vo + a + 1}/{to + c + 1}' for a, c in tri) + '\n')
            vo += len(pos)
            to += len(uvs)
    print(out, vo, 'sommets')


if __name__ == '__main__':
    export(sys.argv[1], sys.argv[2], sys.argv[3:])
