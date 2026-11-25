"""Relevé par rayons de la bande des fenêtres : pour chaque rayon tiré de l'extérieur (flanc gauche puis droit), la
première pièce touchée. Compare ce qui remplit les fenêtres dans plusieurs modèles sans rien modifier.
blender -b -P window_raymap_blender.py -- sortie.csv modele1.(obj|glb) [modele2 ...]
Repère après import : avant vers -Y, flanc gauche vers +X, haut +Z. Grille : Y -1,95..1,95, Z 0,80..1,60, pas 1 cm.
Une face touchée par son dos (invisible dans Blur, qui n'affiche qu'un côté) est notée « dos »."""
import csv, os, sys
import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree

a = sys.argv[sys.argv.index('--') + 1:]
out, models = os.path.abspath(a[0]), [os.path.abspath(x) for x in a[1:]]
STEP = 0.01
ys = [-1.95 + i * STEP for i in range(int(3.9 / STEP) + 1)]
zs = [0.80 + i * STEP for i in range(int(0.80 / STEP) + 1)]
rows = []
for mpath in models:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    if mpath.lower().endswith('.obj'): bpy.ops.wm.obj_import(filepath=mpath)
    else: bpy.ops.import_scene.gltf(filepath=mpath)
    objs = [o for o in bpy.data.objects if o.type == 'MESH']
    trees = []
    for o in objs:
        mw = o.matrix_world
        trees.append((o.name, BVHTree.FromPolygons([mw @ v.co for v in o.data.vertices], [p.vertices[:] for p in o.data.polygons]),
                      o.data.materials[0].name if o.data.materials else ''))
    for side, x0, d in (('gauche', 3.0, Vector((-1, 0, 0))), ('droite', -3.0, Vector((1, 0, 0)))):
        for y in ys:
            for z in zs:
                best = None
                for name, t, mat in trees:
                    h = t.ray_cast(Vector((x0, y, z)), d, 6.0)
                    if h[0] is not None and (best is None or h[3] < best[0]):
                        best = (h[3], name, mat, h[1].dot(d) < 0)
                rows.append([os.path.basename(os.path.dirname(mpath)) + '/' + os.path.basename(mpath), side, f'{y:.2f}', f'{z:.2f}',
                             best[1] if best else '', best[2] if best else '', ('face' if best[3] else 'dos') if best else '',
                             f'{abs(x0) - best[0]:.3f}' if best else ''])
    print('MODELE', mpath, flush=True)
with open(out, 'w', newline='', encoding='utf-8') as f:
    w = csv.writer(f, delimiter=';'); w.writerow(['modèle', 'flanc', 'y', 'z', 'pièce', 'matériau', 'côté', 'x touché'])
    w.writerows(rows)
print('RAYONS', len(rows), '->', out)
