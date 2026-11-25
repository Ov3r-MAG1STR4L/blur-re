"""Allège un modèle (.glb/.gltf/.fbx/.obj, ex. Sketchfab, kn5.py) pour une voiture perso de Map Builder.

blender -b -P glb_reduce_blender.py -- entree.glb sortie.glb [triangles=6000] [texture_max=1024]

Limite du conteneur (Bowler Nemesis) : ~16 000 points soudés ; Map Builder accepte si
sommets >= 1,1 x points et index >= 2,3 x triangles, d'où ~6 000 triangles par défaut.
"""
import os
import sys

import bmesh
import bpy

args = sys.argv[sys.argv.index('--') + 1:]
src, out = os.path.abspath(args[0]), args[1]   # chemin relatif : l'OBJ ne retrouve pas ses textures (glb sans image)
target = int(args[2]) if len(args) > 2 else 6000
tex_max = int(args[3]) if len(args) > 3 else 1024

bpy.ops.wm.read_factory_settings(use_empty=True)
ext = os.path.splitext(src)[1].lower()
if ext in ('.glb', '.gltf'):
    bpy.ops.import_scene.gltf(filepath=src)
elif ext == '.fbx':
    bpy.ops.import_scene.fbx(filepath=src)
else:
    bpy.ops.wm.obj_import(filepath=src)

meshes = [o for o in bpy.data.objects if o.type == 'MESH']
tris = lambda o: sum(len(p.vertices) - 2 for p in o.data.polygons)
count = lambda: sum(tris(o) for o in meshes)
total = count()

# Avant Decimate, chaque pièce est soudée SEULE (sommets coupés aux coutures d'UV) et ses faces en double (surfaces
# « deux côtés ») retirées. Sans soudure, chaque pièce est faite de mille îlots que Decimate ne réduit pas ;
# soudée avec ses voisines (autocollants posés sur la peinture), elle a des arêtes à 3 faces et Decimate s'arrête
# (essais 1000tipla : 6 000 visés, 24 000 puis 10 600 obtenus ; pièce par pièce : 5 917).
for o in meshes:
    bm = bmesh.new(); bm.from_mesh(o.data)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.0001)
    keys, dup = set(), []
    for f in bm.faces:
        k = frozenset(v.index for v in f.verts)
        if k in keys: dup.append(f)
        else: keys.add(k)
    bmesh.ops.delete(bm, geom=dup, context='FACES')
    bm.to_mesh(o.data); bm.free()

for _ in range(4):  # ponytail: même ratio pour toutes les pièces ; les plus petites peuvent disparaître
    n = count()
    if n <= target * 1.05: break
    for o in meshes:
        o.modifiers.new('dec', 'DECIMATE').ratio = min(1.0, target / n)
        bpy.context.view_layer.objects.active = o
        bpy.ops.object.modifier_apply(modifier='dec')
    if count() > 0.97 * n: break   # Decimate ne gagne plus rien

for img in bpy.data.images:  # textures 4K -> tex_max
    w, h = img.size
    if max(w, h) > tex_max:
        img.scale(max(1, w * tex_max // max(w, h)), max(1, h * tex_max // max(w, h)))

bpy.ops.export_scene.gltf(filepath=out, export_format='GLB', export_apply=True)
print(f'triangles {total} -> {count()}, textures <= {tex_max} px : {out}')
