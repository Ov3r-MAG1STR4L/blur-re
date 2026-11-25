"""Modèle de voiture Assetto Corsa (.kn5) -> OBJ + MTL + textures, pour glb_reduce_blender.py / Map Builder.

python kn5.py modele.kn5 dossier_sortie [--list] [groupes à retirer, ex. COCKPIT_HR WHEEL_ SUSP_]

Format (en-tête « sc6969 », versions 5 et 6) : textures (nom + fichier), matériaux (shader, propriétés,
textures par échantillonneur), puis arbre de nœuds : 1 = repère (matrice 4x4, lignes, translation en bas),
2 = maillage, 3 = maillage à os. Sommet : position, normale, UV, tangente (+ poids et os pour le type 3).
Repère AC : x gauche, y haut, z avant (mètres). L'OBJ garde ce repère (axes à donner à l'import).
"""
import os
import struct
import sys

import numpy as np


class R:
    def __init__(self, d): self.d, self.p = d, 0
    def take(self, n): self.p += n; return self.d[self.p - n:self.p]
    def i(self): return struct.unpack('<i', self.take(4))[0]
    def f(self, n=1): return struct.unpack(f'<{n}f', self.take(4 * n))
    def b(self): return self.take(1)[0]
    def s(self): return self.take(self.i()).decode('utf-8', 'replace')


def read(path):
    r = R(open(path, 'rb').read())
    assert r.take(6) == b'sc6969', 'pas un kn5'
    if r.i() > 5: r.i()                      # version 6 : un entier de plus (0)
    textures = {}
    for _ in range(r.i()):
        r.i(); name = r.s(); textures[name] = r.take(r.i())
    mats = []
    for _ in range(r.i()):
        m = {'name': r.s(), 'shader': r.s()}
        r.b(); r.b(); r.i()                  # alpha blend, alpha test, profondeur
        m['props'] = {}
        for _ in range(r.i()):
            k = r.s(); m['props'][k] = r.f(); r.f(9)   # valeur + vec2, vec3, vec4
        m['tex'] = {}
        for _ in range(r.i()):
            k = r.s(); r.i(); m['tex'][k] = r.s()
        mats.append(m)
    meshes = []

    def node(parent, path):
        kind, name, nchild = r.i(), r.s(), r.i(); r.b()
        path = path + (name,)
        world = parent
        if kind == 1:
            world = np.array(r.f(16)).reshape(4, 4) @ parent
        elif kind in (2, 3):
            r.b(); r.b(); r.b()              # ombre, visible, transparent
            if kind == 3:
                for _ in range(r.i()): r.s(); r.f(16)
            nv = r.i(); stride = 44 if kind == 2 else 76
            v = np.frombuffer(r.take(nv * stride), '<f4').reshape(nv, stride // 4)
            idx = np.frombuffer(r.take(2 * r.i()), '<u2')
            mat = r.i(); r.i(); lod_in, lod_out = r.f(2)
            if kind == 2: r.f(4); r.b()      # sphère englobante, rendu
            pos = np.c_[v[:, :3], np.ones(nv)] @ (parent if kind == 2 else np.eye(4))
            nrm = v[:, 3:6] @ parent[:3, :3] if kind == 2 else v[:, 3:6]
            meshes.append({'name': name, 'mat': mat, 'pos': pos[:, :3], 'nrm': nrm, 'uv': v[:, 6:8],
                           'idx': idx.reshape(-1, 3), 'lod': (lod_in, lod_out), 'path': '/'.join(path)})
        for _ in range(nchild): node(world, path)

    node(np.eye(4), ())
    assert r.p == len(r.d), f'fin de fichier non atteinte ({r.p} / {len(r.d)})'
    return textures, mats, meshes


def mat_name(m):
    """Nom lisible par Map Builder : « paint » (CarPaint) et « glass » reconnus ; les verres de feux colorés
    (Glass Red / Orange) ne doivent pas devenir des vitres claires."""
    n = m['name'].replace(' ', '_')
    return n.lower().replace('glass_', 'light_') if n.lower().startswith('glass_') else n


def to_obj(textures, mats, meshes, out, skip=()):
    os.makedirs(out, exist_ok=True)
    used = set()
    with open(os.path.join(out, 'model.obj'), 'w') as f:
        f.write('mtllib model.mtl\n'); base = 1
        for m in meshes:
            if any(s.lower() in m['path'].lower() for s in skip): continue
            f.write(f"o {m['name']}\nusemtl {mat_name(mats[m['mat']])}\n"); used.add(m['mat'])
            f.writelines(f'v {x:.5f} {y:.5f} {z:.5f}\n' for x, y, z in m['pos'])
            f.writelines(f'vt {u:.5f} {1 - v:.5f}\n' for u, v in m['uv'])
            f.writelines(f'vn {x:.4f} {y:.4f} {z:.4f}\n' for x, y, z in m['nrm'])
            f.writelines(f'f {a}/{a}/{a} {b}/{b}/{b} {c}/{c}/{c}\n' for a, b, c in m['idx'].astype(np.int64) + base)
            base += len(m['pos'])
    with open(os.path.join(out, 'model.mtl'), 'w') as f:
        for k in sorted(used):
            m = mats[k]; f.write(f"newmtl {mat_name(m)}\n# {m['shader']}\n")
            tex = m['tex'].get('txDiffuse')
            if tex in textures:
                fn = tex.replace(' ', '_')   # un espace coupe le chemin dans le .mtl
                open(os.path.join(out, fn), 'wb').write(textures[tex]); f.write(f'map_Kd {fn}\n')
            else:
                f.write('Kd {:.3f} {:.3f} {:.3f}\n'.format(*(m['props'].get('ksDiffuse', (0.8,)) * 3)))
            if 'glass' in mat_name(m).lower(): f.write('d 0.35\n')   # vitres seulement (feux = light_*)


if __name__ == '__main__':
    tex, mats, meshes = read(sys.argv[1])
    print(f'{len(tex)} textures, {len(mats)} matériaux, {len(meshes)} maillages, '
          f'{sum(len(m["idx"]) for m in meshes)} triangles')
    if '--list' in sys.argv:
        for m in sorted(meshes, key=lambda m: -len(m['idx'])):
            print(f"{len(m['idx']):8d}  {m['path']:70s} {mats[m['mat']]['name']}")
    else:
        to_obj(tex, mats, meshes, sys.argv[2], skip=[a for a in sys.argv[3:] if not a.startswith('--')])
