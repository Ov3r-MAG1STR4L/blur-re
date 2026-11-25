"""Méthode D (hybride) : on garde les pièces d'origine et leurs textures, mais chaque pièce reçoit un budget
proportionnel à sa SURFACE (pas à son nombre de triangles). Les grandes tôles gardent leurs courbes ; les pièces
très détaillées mais petites (ampoules de feux, vis, chromes) sont fortement réduites.
blender -b -P method_D_blender.py -- entree.obj sortie.glb triangles"""
import os, sys
import bmesh
import bpy

a = sys.argv[sys.argv.index('--') + 1:]
src, out, budget = os.path.abspath(a[0]), os.path.abspath(a[1]), int(a[2])
MIN_TRIS = 2   # une pièce plus petite que sa part tombe à ce minimum (ponytail: les plus petites peuvent disparaître)

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.obj_import(filepath=src)
objs = [o for o in bpy.data.objects if o.type == 'MESH']
tris = lambda o: sum(len(p.vertices) - 2 for p in o.data.polygons)
for o in objs:   # soudure par pièce + doublons (voir glb_reduce_blender.py)
    bm = bmesh.new(); bm.from_mesh(o.data)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.0001)
    keys, dup = set(), []
    for f in bm.faces:
        k = frozenset(v.index for v in f.verts)
        if k in keys: dup.append(f)
        else: keys.add(k)
    bmesh.ops.delete(bm, geom=dup, context='FACES'); bm.to_mesh(o.data); bm.free()
area = {o: sum(p.area for p in o.data.polygons) for o in objs}
total = sum(area.values())
for o in objs:
    want = max(MIN_TRIS, round(budget * area[o] / total))
    for _ in range(4):
        n = tris(o)
        if n <= want * 1.05 or n == 0: break
        m = o.modifiers.new('d', 'DECIMATE'); m.ratio = want / n
        bpy.context.view_layer.objects.active = o; bpy.ops.object.modifier_apply(modifier='d')
        if tris(o) > 0.97 * n: break
if '--normales' in sys.argv:   # D2 : normales d'origine (OBJ) mal interpolées après réduction -> recalculées
    for o in objs:
        bpy.ops.object.select_all(action='DESELECT'); o.select_set(True); bpy.context.view_layer.objects.active = o
        if o.data.has_custom_normals: bpy.ops.mesh.customdata_custom_splitnormals_clear()
        bpy.ops.object.shade_smooth_by_angle(angle=0.52)   # 30°
print('D tris', sum(tris(o) for o in objs))
bpy.ops.export_scene.gltf(filepath=out, export_format='GLB', export_apply=True)
