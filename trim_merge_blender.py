"""Découpe des pièces à leurs faces gardées (visible_faces_blender.py) puis fusion avec un modèle de base, en OBJ.
blender -b -P trim_merge_blender.py -- pieces.obj faces.json base.obj occultants.obj sortie.obj
- les faces non gardées sont retirées (sommets orphelins compris) ;
- contrôle : les bords de coupe NOUVEAUX (absents de la pièce d'origine) vus de l'extérieur sont comptés ;
- matériaux : un matériau « X.001 » créé par le second import est ramené au matériau d'origine « X » ;
- export OBJ + MTL + textures copiées (même repère que kn5.py)."""
import json, math, os, sys
import bmesh
import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree

a = sys.argv[sys.argv.index('--') + 1:]
pieces_p, faces_p, base_p, occ_p, out = (os.path.abspath(x) for x in a[:5])
keep = json.load(open(faces_p))
CENTER = Vector((0, 0, 0.8))
cams = [CENTER + 7.0 * Vector((math.cos(math.radians(e)) * math.sin(math.radians(az)),
                               -math.cos(math.radians(e)) * math.cos(math.radians(az)), math.sin(math.radians(e))))
        for az in range(0, 360, 15) for e in (0, 15, 35)]

bpy.ops.wm.read_factory_settings(use_empty=True)
# occultants (pour le contrôle des bords), sans les vitres et sans les pièces traitées
bpy.ops.wm.obj_import(filepath=occ_p)
verts, faces = [], []
for o in list(bpy.data.objects):
    if o.type == 'MESH' and o.name not in keep and not any(m and 'glass' in m.name.lower() for m in o.data.materials):
        mw = o.matrix_world; off = len(verts)
        verts += [mw @ v.co for v in o.data.vertices]; faces += [[i + off for i in p.vertices] for p in o.data.polygons]
    bpy.data.objects.remove(o)
for m in list(bpy.data.materials): bpy.data.materials.remove(m)
occ = BVHTree.FromPolygons(verts, faces)

bpy.ops.wm.obj_import(filepath=pieces_p)
report = {}
for o in [o for o in bpy.data.objects if o.type == 'MESH']:
    bm = bmesh.new(); bm.from_mesh(o.data); bm.faces.ensure_lookup_table()
    key = lambda e: frozenset(tuple(round(c, 5) for c in v.co) for v in e.verts)   # par position : indices changent
    old_border = {key(e) for e in bm.edges if len(e.link_faces) == 1}
    ks = set(keep.get(o.name, []))
    bmesh.ops.delete(bm, geom=[f for f in bm.faces if f.index not in ks], context='FACES')
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context='VERTS')
    bm.verts.index_update()
    # bords de coupe nouveaux vus de l'extérieur (milieu de l'arête, depuis une caméra, rien devant)
    new_b = [e for e in bm.edges if len(e.link_faces) == 1 and key(e) not in old_border]
    seen = 0
    for e in new_b:
        c = (e.verts[0].co + e.verts[1].co) / 2
        for cam in cams:
            d = cam - c; dist = d.length; d.normalize()
            if occ.ray_cast(c + d * 0.003, d, dist)[0] is None: seen += 1; break
    tri = sum(len(f.verts) - 2 for f in bm.faces)
    bm.to_mesh(o.data); bm.free()
    report[o.name] = {'triangles gardés': tri, 'arêtes de coupe': len(new_b), 'dont visibles de l\'extérieur': seen}
    print('DECOUPE', o.name, report[o.name], flush=True)

bpy.ops.wm.obj_import(filepath=base_p)
base_mats = {m.name: m for m in bpy.data.materials}
for o in bpy.data.objects:
    if o.type != 'MESH': continue
    for i, m in enumerate(o.data.materials):
        if m and '.' in m.name and m.name.rsplit('.', 1)[0] in base_mats and m.name.rsplit('.', 1)[1].isdigit():
            o.data.materials[i] = base_mats[m.name.rsplit('.', 1)[0]]
os.makedirs(os.path.dirname(out), exist_ok=True)
bpy.ops.wm.obj_export(filepath=out, export_materials=True, path_mode='COPY', export_uv=True, export_normals=True,
                      export_triangulated_mesh=True)
json.dump(report, open(out.replace('.obj', '_decoupe.json'), 'w'), ensure_ascii=False, indent=1)
print('FUSION', out, sum(1 for o in bpy.data.objects if o.type == 'MESH'), 'pièces')
