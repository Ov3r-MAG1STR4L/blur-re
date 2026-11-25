"""Banc d'essai : rendu identique (même caméra, même lumière) d'une pièce de test.
blender -b -P bench_render.py -- modele.(obj|glb) sortie_prefixe
Écrit <prefixe>_tex.png (texture) et <prefixe>_gris.png (gris brillant : courbure, arêtes, reflets)."""
import math, os, sys
import bpy
from mathutils import Vector

src, out = sys.argv[sys.argv.index('--') + 1:][:2]; out = os.path.abspath(out)   # relatif : écrit à la racine C:
bpy.ops.wm.read_factory_settings(use_empty=True)
if src.lower().endswith('.obj'): bpy.ops.wm.obj_import(filepath=os.path.abspath(src))
else: bpy.ops.import_scene.gltf(filepath=os.path.abspath(src))
# .obj pour bench_measure (pymeshlab lit mal les .glb : 1 triangle) ; axes par défaut = repère de kn5.py
bpy.ops.wm.obj_export(filepath=out + '.obj', export_materials=False, export_uv=False)
sc = bpy.context.scene
sc.render.engine = 'BLENDER_WORKBENCH'; sc.render.resolution_x, sc.render.resolution_y = 1400, 900
sh = sc.display.shading; sh.light = 'STUDIO'; sh.show_specular_highlight = True
sc.world = bpy.data.worlds.new('w'); sc.world.color = (0.62, 0.66, 0.70)
cam = bpy.data.objects.new('cam', bpy.data.cameras.new('cam')); sc.collection.objects.link(cam); sc.camera = cam
cam.data.lens = 50
target = Vector((0.8, 1.25, 0.62))                     # centre de l'aile arrière gauche (repère Blender)
cam.location = Vector((3.6, 3.3, 1.35))
cam.rotation_euler = (target - cam.location).to_track_quat('-Z', 'Y').to_euler()
for kind, ct in (('tex', 'TEXTURE'), ('gris', 'SINGLE')):
    sh.color_type = ct; sh.single_color = (0.55, 0.55, 0.57)
    sc.render.filepath = f'{out}_{kind}.png'; bpy.ops.render.render(write_still=True)
