"""Contrôle d'intégrité d'un .glb (avant import dans Map Builder) et comptage exact des triangles par pièce.
python glb_check.py fichier.glb [budget]
Vérifie : en-tête et longueurs, accesseurs dans leurs buffers, index < nombre de sommets, positions / normales / UV
finies, normales unitaires, images décodables (PIL), références de textures et de matériaux valides."""
import io
import json
import struct
import sys

import numpy as np
from PIL import Image

COMP = {5120: ('i1', 1), 5121: ('u1', 1), 5122: ('<i2', 2), 5123: ('<u2', 2), 5125: ('<u4', 4), 5126: ('<f4', 4)}
NCOMP = {'SCALAR': 1, 'VEC2': 2, 'VEC3': 3, 'VEC4': 4, 'MAT4': 16}


def check(path, budget=None):
    err, d = [], open(path, 'rb').read()
    magic, ver, length = struct.unpack_from('<4sII', d, 0)
    if magic != b'glTF' or ver != 2: err.append('en-tête glTF 2 absent')
    if length != len(d): err.append(f'longueur annoncée {length} != fichier {len(d)}')
    jl, jt = struct.unpack_from('<I4s', d, 12); j = json.loads(d[20:20 + jl])
    bl, bt = struct.unpack_from('<I4s', d, 20 + jl); binc = d[28 + jl:28 + jl + bl]
    if jt != b'JSON' or bt != b'BIN\0': err.append('blocs JSON / BIN manquants')
    for i, bv in enumerate(j.get('bufferViews', [])):
        if bv.get('byteOffset', 0) + bv['byteLength'] > len(binc): err.append(f'bufferView {i} hors du buffer')

    def acc(i):
        a = j['accessors'][i]; bv = j['bufferViews'][a['bufferView']]
        dt, size = COMP[a['componentType']]; n = NCOMP[a['type']]
        stride = bv.get('byteStride', size * n); off = bv.get('byteOffset', 0) + a.get('byteOffset', 0)
        if off + stride * (a['count'] - 1) + size * n > len(binc): err.append(f'accesseur {i} hors du buffer'); return None
        raw = np.frombuffer(binc, np.uint8, stride * (a['count'] - 1) + size * n, off)
        rows = np.lib.stride_tricks.as_strided(raw, (a['count'], size * n), (stride, 1))
        return np.ascontiguousarray(rows).view(dt).reshape(a['count'], n)

    for i, img in enumerate(j.get('images', [])):
        bv = j['bufferViews'][img['bufferView']]; o = bv.get('byteOffset', 0)
        try: Image.open(io.BytesIO(binc[o:o + bv['byteLength']])).load()
        except Exception as e: err.append(f'image {i} illisible : {e}')
    for i, t in enumerate(j.get('textures', [])):
        if t.get('source', -1) >= len(j.get('images', [])): err.append(f'texture {i} -> image absente')
    for m in j.get('materials', []):
        t = m.get('pbrMetallicRoughness', {}).get('baseColorTexture')
        if t and t['index'] >= len(j.get('textures', [])): err.append(f"matériau {m.get('name')} -> texture absente")

    pieces, total = [], 0
    for mesh in j['meshes']:
        n_tri = 0
        for p in mesh['primitives']:
            if p.get('mode', 4) != 4: err.append(f"{mesh['name']} : primitive non triangulaire")
            if p.get('material', 0) >= len(j.get('materials', [1])): err.append(f"{mesh['name']} : matériau absent")
            pos = acc(p['attributes']['POSITION']); idx = acc(p['indices']) if 'indices' in p else None
            if pos is None: continue
            if not np.isfinite(pos).all(): err.append(f"{mesh['name']} : positions non finies")
            if 'NORMAL' in p['attributes']:
                nr = acc(p['attributes']['NORMAL'])
                if nr is not None and (not np.isfinite(nr).all() or np.abs(np.linalg.norm(nr, axis=1) - 1).max() > 0.01):
                    err.append(f"{mesh['name']} : normales non unitaires")
            else: err.append(f"{mesh['name']} : pas de normales")
            if 'TEXCOORD_0' in p['attributes']:
                uv = acc(p['attributes']['TEXCOORD_0'])
                if uv is not None and not np.isfinite(uv).all(): err.append(f"{mesh['name']} : UV non finies")
            if idx is not None:
                if idx.size and idx.max() >= len(pos): err.append(f"{mesh['name']} : index hors des sommets")
                n_tri += idx.size // 3
            else: n_tri += len(pos) // 3
        pieces.append((mesh['name'], n_tri)); total += n_tri
    if budget and total > budget: err.append(f'{total} triangles > budget {budget}')
    return err, pieces, total, j


if __name__ == '__main__':
    budget = int(sys.argv[2]) if len(sys.argv) > 2 else None
    err, pieces, total, j = check(sys.argv[1], budget)
    print(f"{sys.argv[1]} : {total} triangles, {len(pieces)} pièces, {len(j.get('materials', []))} matériaux, "
          f"{len(j.get('images', []))} images")
    print('INTÈGRE' if not err else 'PROBLÈMES :\n  ' + '\n  '.join(err))
