"""NFS Most Wanted GEOMETRY.BIN (solid list) -> chunk tree / OBJ. Lecture seule."""
import struct, sys

def chunks(d, off, end):
    while off + 8 <= end:
        cid, size = struct.unpack_from('<II', d, off)
        yield cid, off + 8, off + 8 + size
        off += 8 + size

def tree(d, off=0, end=None, depth=0, out=None):
    end = len(d) if end is None else end
    for cid, a, b in chunks(d, off, end):
        print('  ' * depth + f'{cid:08X} @{a-8:#x} size {b-a}')
        if cid & 0x80000000:
            tree(d, a, b, depth + 1)

def jdlz(src):
    assert src[:4] == b'JDLZ', src[:4]
    ulen = struct.unpack_from('<I', src, 8)[0]
    out = bytearray(ulen); o = 0; i = 16; f1 = f2 = 1
    while i < len(src) and o < ulen:
        if f1 == 1: f1 = src[i] | 0x100; i += 1
        if f2 == 1: f2 = src[i] | 0x100; i += 1
        if f1 & 1:
            if f2 & 1:
                n = (src[i + 1] | ((src[i] & 0xF0) << 4)) + 3; back = (src[i] & 0x0F) + 1
            else:
                back = (src[i + 1] | ((src[i] & 0xE0) << 3)) + 17; n = (src[i] & 0x1F) + 3
            i += 2
            for k in range(n): out[o + k] = out[o + k - back]
            o += n; f2 >>= 1
        else:
            out[o] = src[i]; o += 1; i += 1
        f1 >>= 1
    return bytes(out)

def solids(d):
    """(hash, bytes) of each object, decompressed when the 0x134004 table says so"""
    a = d.find(struct.pack('<I', 0x00134004)); n = struct.unpack_from('<I', d, a + 4)[0]
    for k in range(0, n, 24):
        h, off, cs, us = struct.unpack_from('<4I', d, a + 8 + k)
        blob = d[off:off + cs]
        yield h, jdlz(blob) if blob[:4] == b'JDLZ' else blob

def _flat(b):
    ch = {}
    def walk(a, e):
        for cid, x, y in chunks(b, a, e):
            ch.setdefault(cid, []).append((x, y))
            if cid & 0x80000000: walk(x, y)
    walk(0, len(b)); return ch

def _skip11(b, x):
    while b[x] == 0x11: x += 1
    return x

def meshes(b):
    """name, texture hashes, groups [(tex_slot, verts[(pos, normal, uv)], tris)] of one solid (MW, stride 36)"""
    ch = _flat(b)
    hx, hy = ch[0x134011][0]
    name = b[hx + 0xA0:hy].split(b'\0')[0].decode()
    tx, ty = ch[0x134012][0]
    texs = [struct.unpack_from('<I', b, tx + k)[0] for k in range(0, ty - tx, 8)]
    gx, gy = ch[0x134B02][0]; gx = _skip11(b, gx)
    vx, vy = ch[0x134B01][0]; vx = _skip11(b, vx)
    ix, iy = ch[0x134B03][0]
    while b[ix:ix + 2] == b'\x11\x11': ix += 2   # alignment padding (0x1111 read as an index = spaghetti)
    idx = struct.unpack_from(f'<{(iy - ix) // 2}H', b, ix)
    # one vertex buffer per solid; group indices are global to it (groups share and interleave vertices)
    nv = (vy - vx) // 36
    verts = [struct.unpack_from('<6f4x2f', b, vx + 36 * k) for k in range(nv)]
    groups = []
    for g in range(gx, gy - 103, 104):
        slot = b[g + 24]   # texture slot into the 0x134012 list (offsets 24-29 = slots per texture role)
        i0 = struct.unpack_from('<I', b, g + 68)[0]
        icount = struct.unpack_from('<I', b, g + 92)[0]
        sub = idx[i0:i0 + icount]
        groups.append((slot, [(sub[k], sub[k + 1], sub[k + 2]) for k in range(0, icount - 2, 3)]))
    return name, texs, [(v[:3], v[3:6], v[6:8]) for v in verts], groups

def to_obj(d, path):
    NL = chr(10)
    with open(path, 'w') as f:
        n0 = 1
        for h, b in solids(d):
            name, texs, verts, groups = meshes(b)
            f.write(f'o {name}' + NL)
            for p, n, uv in verts: f.write('v %f %f %f' % p + NL + 'vt %f %f' % (uv[0], 1 - uv[1]) + NL)
            for slot, tri in groups:
                f.write(f'usemtl tex_{texs[slot] if slot < len(texs) else 0:08X}' + NL)
                for a, c, e in tri: f.write(f'f {a+n0}/{a+n0} {c+n0}/{c+n0} {e+n0}/{e+n0}' + NL)
            n0 += len(verts)

def textures(d):
    """{hash: (name, w, h, fourcc, data)} from a compressed MW TPK (0x33310003 table of JDLZ blocks, info at the end)"""
    a = d.find(struct.pack('<I', 0x33310003)); n = struct.unpack_from('<I', d, a + 4)[0]
    out = {}
    for k in range(0, n, 24):
        h, off, cs, us = struct.unpack_from('<4I', d, a + 8 + k)
        src = d[off:off + cs]
        if src[:4] != b'JDLZ':
            out[h] = (src[:4].decode('latin1'), 0, 0, b'', b''); continue   # ponytail: HUFF/RAWW not decoded yet
        blob = jdlz(src); t = blob[-0x9c:]
        name = t[12:36].split(bytes(1))[0].decode()
        size = struct.unpack_from('<I', t, 56)[0]
        w, hh = struct.unpack_from('<2H', t, 68)
        out[h] = (name, w, hh, t[-12:-8], blob[:size])
    return out

def dds(w, h, fourcc, data):
    """minimal DDS (first mip only is enough for Pillow) - DXT1/3/5 or 32-bit BGRA"""
    import struct as s
    if fourcc in (b'DXT1', b'DXT3', b'DXT5'):
        pf = s.pack('<2I4s5I', 32, 4, fourcc, 0, 0, 0, 0, 0)
    else:
        pf = s.pack('<2I4s5I', 32, 0x41, bytes(4), 32, 0xFF0000, 0xFF00, 0xFF, 0xFF000000)
    hdr = s.pack('<7I44x', 124, 0x1007, h, w, 0, 0, 0) + pf + s.pack('<5I', 0x1000, 0, 0, 0, 0)
    return b'DDS ' + hdr + data

if __name__ == '__main__':
    d = open(sys.argv[1], 'rb').read()
    for h, b in solids(d):
        print(f'== {h:08X} {len(b)}'); tree(b)
