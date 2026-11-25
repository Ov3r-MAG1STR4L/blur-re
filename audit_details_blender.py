"""Audit des détails : original (OBJ de kn5.py) contre version réduite (.glb), pièce par pièce.
blender -b -P audit_details_blender.py -- original.obj reduit.glb sortie.csv
Par pièce : catégorie (vitre, contour de vitre, feu, rétro, échappement, peinture, chrome, pièce noire), triangles
avant/après, présence, matériau gardé, texture détaillée ou couleur unie, part de faces RETOURNÉES (invisibles dans Blur,
qui n'affiche qu'un côté) et part de surface perdue (sommets d'origine à plus de 1 cm de la version réduite)."""
import csv, os, sys
import bpy
from mathutils.bvhtree import BVHTree

a = sys.argv[sys.argv.index('--') + 1:]
hi_p, lo_p, out = (os.path.abspath(x) for x in a[:3])
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=lo_p)
low = {}
for o in [o for o in bpy.data.objects if o.type == 'MESH']:
    low[o.name] = o; o.name = 'L_' + o.name
bpy.ops.wm.obj_import(filepath=hi_p)
hi = {o.name: o for o in bpy.data.objects if o.type == 'MESH' and not o.name.startswith('L_')}
IMP = {'Circle.018': 'échappement', 'Circle.019': 'échappement', 'Circle.020': 'échappement',
       'Cube.001': 'rétro', 'Cube.002': 'rétro'}


def bvh(o):
    me = o.data; mw = o.matrix_world
    return BVHTree.FromPolygons([mw @ v.co for v in me.vertices], [p.vertices[:] for p in me.polygons])


def tex_size(o):
    m = o.data.materials[0] if o.data.materials else None
    if not m or not m.use_nodes: return 0
    t = [n for n in m.node_tree.nodes if n.type == 'TEX_IMAGE' and n.image]
    return max(t[0].image.size) if t else 0


hb = {n: bvh(o) for n, o in hi.items()}
mat = lambda o: o.data.materials[0].name if o.data.materials else ''
glass = [n for n, o in hi.items() if 'glass' in mat(o).lower()]
lights = [n for n, o in hi.items() if any(k in mat(o).lower() for k in ('light', 'glass_red', 'glass_orange'))
          or n in ('BrakeLights', 'REverseLight')]


def near(o, names, d=0.03):
    vs = [o.matrix_world @ v.co for v in o.data.vertices][::max(1, len(o.data.vertices) // 400)]
    return sum(any(hb[n].find_nearest(v, d)[0] is not None for n in names if n != o.name) for v in vs) / max(1, len(vs))


rows = []
for n, h in sorted(hi.items()):
    m = mat(h).lower(); l = low.get(n)
    cat = IMP.get(n) or ('vitre' if 'glass' in m else 'feu' if n in lights else None)
    if not cat:
        cat = ('contour de vitre' if near(h, glass) > 0.5 else 'feu' if near(h, lights) > 0.5 else
               'peinture' if 'carpaint' in m else 'chrome' if 'chrome' in m else 'pièce noire / aéro')
    hi_t = sum(len(p.vertices) - 2 for p in h.data.polygons)
    if not l:
        rows.append([n, cat, mat(h), hi_t, 0, 'ABSENTE', '', '', '', '']); continue
    lo_t = sum(len(p.vertices) - 2 for p in l.data.polygons)
    # faces retournées : aucune face d'origine à moins de 1 cm n'a la même orientation
    lw, flip, area = l.matrix_world, 0.0, 0.0
    for p in l.data.polygons:
        c, nn = lw @ p.center, (lw.to_3x3() @ p.normal).normalized()
        hits = hb[n].find_nearest_range(c, 0.01) or [hb[n].find_nearest(c)]
        ok = any(hn is not None and hn.dot(nn) > 0.3 for _, hn, _, _ in hits)
        area += p.area; flip += 0 if ok else p.area
    # surface perdue : sommets d'origine à plus de 1 cm de la version réduite
    lb = bvh(l); hv = [h.matrix_world @ v.co for v in h.data.vertices][::max(1, len(h.data.vertices) // 2000)]
    lost = sum((lb.find_nearest(v)[3] or 0) > 0.01 for v in hv) / max(1, len(hv))
    ts = tex_size(h)
    rows.append([n, cat, mat(h), hi_t, lo_t, 'présente', mat(l), f'{100 * flip / max(area, 1e-9):.0f}',
                 f'{100 * lost:.0f}', 'texture détaillée' if ts > 64 else 'couleur unie (forme = géométrie)'])
with open(out, 'w', newline='', encoding='utf-8') as f:
    w = csv.writer(f, delimiter=';')
    w.writerow(['pièce', 'catégorie', 'matériau origine', 'tri. origine', 'tri. D2', 'état', 'matériau D2',
                '% faces retournées', '% surface perdue (>1 cm)', 'apparence'])
    w.writerows(rows)
print('AUDIT', len(rows), 'pièces ->', out)
