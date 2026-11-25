"""Allège un modèle (.glb/.gltf/.fbx/.obj, ex. Sketchfab) pour une voiture perso de Map Builder.

blender -b -P glb_reduce_blender.py -- entree.glb sortie.glb [triangles=6000] [texture_max=1024]

Limite du conteneur (Bowler Nemesis) : ~16 000 points soudés ; Map Builder accepte si
sommets >= 1,1 x points et index >= 2,3 x triangles, d'où ~6 000 triangles par défaut.
"""
import os
import sys

import bpy

args = sys.argv[sys.argv.index('--') + 1:]
src, out = args[0], args[1]
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
total = sum(tris(o) for o in meshes)
for o in meshes:  # même ratio partout : les petites pièces gardent leur part
    o.modifiers.new('dec', 'DECIMATE').ratio = min(1.0, target / total)

for img in bpy.data.images:  # textures 4K Sketchfab -> tex_max
    w, h = img.size
    if max(w, h) > tex_max:
        img.scale(max(1, w * tex_max // max(w, h)), max(1, h * tex_max // max(w, h)))

bpy.ops.export_scene.gltf(filepath=out, export_format='GLB', export_apply=True)
dg = bpy.context.evaluated_depsgraph_get()
after = sum(len(p.vertices) - 2 for o in meshes for p in o.evaluated_get(dg).data.polygons)
print(f'triangles {total} -> {after}, textures <= {tex_max} px : {out}')
