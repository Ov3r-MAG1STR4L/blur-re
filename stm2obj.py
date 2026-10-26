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

SCALE = (1 / 17.565, 1 / 76.8, 1 / 18.818)  # ponytail: mesuré sur Location1, à vérifier sur les autres lieux
UV_SCALE = 1 / 1024  # ponytail: supposé (2^10), à vérifier avec une texture


def entries(d):
    n = struct.unpack_from('>I', d, 12)[0]
    for i in range(n):
        o = 16 + i * 64
        t = struct.unpack_from('>I', d, o)[0]
        name = d[o + 4:o + 32].split(b'\0')[0].decode('latin1')
        f = struct.unpack_from('>8I', d, o + 32)
        yield t, name, d[f[2]:f[2] + f[3]]


def mesh(b):
    """-> (positions, uvs, faces[(pi,ti)x3]) d'un maillage STM."""
    vb = struct.unpack_from('>I', b, 0x14)[0]
    p0, p1, p2 = struct.unpack_from('>3I', b, vb)
    small = b[vb + 12:vb + 15]
    sizes = [1 if s else 2 for s in small]
    pos = [tuple(q * s for q, s in zip(struct.unpack_from('>3h', b, p0 + 6 * j), SCALE))
           for j in range((p1 - p0) // 6)]
    uvs = [(u * UV_SCALE, 1 - v * UV_SCALE) for u, v in
           (struct.unpack_from('>2h', b, p2 + 4 * j) for j in range((len(b) - p2) // 4))]
    # listes GX : du premier offset de nœud jusqu'au bloc sommets
    starts = []
    o = 0x40
    while o + 0x20 <= vb and (not starts or o < min(starts)):
        dl = struct.unpack_from('>I', b, o + 8)[0]
        if not 0 < dl < vb:
            break
        starts.append(dl)
        o += 0x38
    faces = []
    p = min(starts)
    while p < vb:
        op = b[p]
        if op not in (0x90, 0x98, 0xA0):
            p += 1
            continue
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
    return pos, uvs, faces


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
