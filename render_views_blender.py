"""Vues de contrôle d'une voiture (même cadrage pour l'original et les versions réduites).
blender -b -P render_views_blender.py -- modele.(obj|glb) prefixe [vues=avant,arriere,gauche,droite,av34,ar34] [gris]
Repère après import (kn5.py -> OBJ ou glb) : avant vers -Y, flanc gauche vers +X (volant à x>0, conduite à gauche).
Workbench, lumière studio ; « gris » = sans texture, brillant (courbure, arêtes, reflets)."""
import math, os, sys
import bpy
from mathutils import Vector

a = sys.argv[sys.argv.index('--') + 1:]
src, out = os.path.abspath(a[0]), os.path.abspath(a[1])
views = a[2].split(',') if len(a) > 2 else ['avant', 'arriere', 'gauche', 'droite', 'av34', 'ar34']
grey = 'gris' in a
# angle de la caméra autour de Z : 0 = caméra en -Y (face à l'avant), 90 = en +X (flanc gauche)
AZ = {'avant': 0, 'arriere': 180, 'gauche': 90, 'droite': 270, 'av34': 45, 'ar34': 135}

bpy.ops.wm.read_factory_settings(use_empty=True)
if src.lower().endswith('.obj'): bpy.ops.wm.obj_import(filepath=src)
else: bpy.ops.import_scene.gltf(filepath=src)
sc = bpy.context.scene
sc.render.engine = 'BLENDER_WORKBENCH'; sc.render.resolution_x, sc.render.resolution_y = 1200, 800
sh = sc.display.shading; sh.light = 'STUDIO'; sh.show_specular_highlight = True
sh.color_type = 'SINGLE' if grey else 'TEXTURE'; sh.single_color = (0.55, 0.55, 0.57)
sc.world = bpy.data.worlds.new('w'); sc.world.color = (0.62, 0.66, 0.70)
cam = bpy.data.objects.new('cam', bpy.data.cameras.new('cam')); sc.collection.objects.link(cam); sc.camera = cam
cam.data.lens = 50
target = Vector((0, 0, 0.75))
for v in views:
    az, el, d = math.radians(AZ[v]), math.radians(12), 8.0
    cam.location = target + Vector((d * math.cos(el) * math.sin(az), -d * math.cos(el) * math.cos(az), d * math.sin(el)))
    cam.rotation_euler = (target - cam.location).to_track_quat('-Z', 'Y').to_euler()
    sc.render.filepath = f"{out}_{v}{'_gris' if grey else ''}.png"; bpy.ops.render.render(write_still=True)
