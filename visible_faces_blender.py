"""Faces d'une ou plusieurs pièces visibles depuis l'extérieur de la voiture (rien n'est modifié).
blender -b -P visible_faces_blender.py -- pieces.obj occultants.obj sortie.json [rangées=2]
Une face est visible si, depuis au moins une caméra autour de la voiture (24 azimuts x 3 hauteurs, 7 m), elle est vue
par son côté avant (Blur n'affiche qu'un côté) et que rien ne la cache (les vitres, transparentes, ne cachent pas).
On garde ensuite N rangées de faces voisines : les bords de coupe tombent dans la partie cachée.
Sortie : {pièce: [indices des faces gardées, dans l'ordre du fichier OBJ]}."""
import json, math, os, sys
import bmesh
import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree

a = sys.argv[sys.argv.index('--') + 1:]
pieces_p, occ_p, out = (os.path.abspath(x) for x in a[:3])
RINGS = int(a[3]) if len(a) > 3 else 2
CENTER = Vector((0, 0, 0.8))
cams = [CENTER + 7.0 * Vector((math.cos(math.radians(e)) * math.sin(math.radians(az)),
                               -math.cos(math.radians(e)) * math.cos(math.radians(az)), math.sin(math.radians(e))))
        for az in range(0, 360, 15) for e in (0, 15, 35)]

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.obj_import(filepath=pieces_p)
targets = {o.name: o for o in bpy.data.objects if o.type == 'MESH'}
for o in targets.values(): o.name = 'T_' + o.name
bpy.ops.wm.obj_import(filepath=occ_p)
verts, faces = [], []
for o in bpy.data.objects:
    if o.type != 'MESH': continue
    if not o.name.startswith('T_') and any(m and 'glass' in m.name.lower() for m in o.data.materials): continue
    if not o.name.startswith('T_') and o.name in targets: continue   # la pièce elle-même vient du fichier pieces
    mw = o.matrix_world; off = len(verts)
    verts += [mw @ v.co for v in o.data.vertices]; faces += [[i + off for i in p.vertices] for p in o.data.polygons]
occ = BVHTree.FromPolygons(verts, faces)
res = {}
for name, o in targets.items():
    me = o.data; mw = o.matrix_world
    vis = set()
    for p in me.polygons:
        c = mw @ p.center; n = (mw.to_3x3() @ p.normal).normalized()
        for cam in cams:
            d = cam - c
            if d.dot(n) <= 0: continue
            dist = d.length; d.normalize()
            h = occ.ray_cast(c + d * 0.003, d, dist)
            if h[0] is None: vis.add(p.index); break
    bm = bmesh.new(); bm.from_mesh(me); bm.faces.ensure_lookup_table()
    keep = set(vis)
    for _ in range(RINGS):
        grow = set()
        for i in keep:
            for v in bm.faces[i].verts:
                for f in v.link_faces: grow.add(f.index)
        keep |= grow
    bm.free()
    res[name] = sorted(keep)
    print(f'VISIBLE {name} : {len(vis)} faces vues, {len(keep)} gardées sur {len(me.polygons)}', flush=True)
json.dump(res, open(out, 'w'))
