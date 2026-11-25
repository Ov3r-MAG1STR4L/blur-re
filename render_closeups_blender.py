"""Vues rapprochées des détails extérieurs (même cadrage pour l'original et les versions réduites).
blender -b -P render_closeups_blender.py -- modele.(obj|glb) prefixe [gris]
Repère après import : avant vers -Y, flanc gauche vers +X, haut +Z (voir render_views_blender.py)."""
import os, sys
import bpy
from mathutils import Vector

a = sys.argv[sys.argv.index('--') + 1:]
src, out = os.path.abspath(a[0]), os.path.abspath(a[1]); grey = 'gris' in a
# zone : (cible, caméra) en mètres
ZONES = {
    'vitres_laterales': ((0.80, 0.25, 1.15), (3.4, -0.4, 1.55)),
    'montant_parebrise': ((0.55, -1.15, 1.15), (2.2, -3.0, 1.75)),
    'retro': ((0.95, -0.62, 1.00), (2.2, -2.0, 1.35)),
    'phares': ((0.55, -1.55, 0.85), (1.8, -3.6, 1.15)),
    'feu_arriere': ((0.70, 1.78, 0.78), (2.0, 3.4, 1.05)),
    'bas_de_caisse': ((0.95, 0.0, 0.35), (3.2, -0.9, 0.65)),
    'arche_arriere': ((0.90, 1.20, 0.50), (3.0, 2.2, 0.85)),
    'arche_avant': ((0.90, -1.23, 0.45), (3.0, -2.1, 0.8)),
    'bouclier_avant': ((0.0, -2.0, 0.45), (1.2, -4.3, 0.95)),
    'diffuseur': ((0.0, 2.0, 0.35), (1.0, 4.3, 0.55)),
    'chromes': ((0.90, -0.2, 0.95), (2.7, -1.3, 1.2)),
    'fenetre_avant': ((0.80, -0.55, 1.20), (2.3, -1.3, 1.45)),
    'fenetre_arriere': ((0.80, 1.10, 1.20), (2.4, 1.9, 1.45)),
    'fenetre_haut': ((0.75, 0.30, 1.42), (2.4, 0.3, 2.1)),
    'fenetre_bas': ((0.82, 0.30, 0.97), (2.6, 0.0, 0.75)),
}
ONLY = [z for z in os.environ.get('ZONES', '').split(',') if z]   # ZONES=a,b : seulement ces zones
bpy.ops.wm.read_factory_settings(use_empty=True)
if src.lower().endswith('.obj'): bpy.ops.wm.obj_import(filepath=src)
else: bpy.ops.import_scene.gltf(filepath=src)
sc = bpy.context.scene
sc.render.engine = 'BLENDER_WORKBENCH'; sc.render.resolution_x, sc.render.resolution_y = 1000, 700
sh = sc.display.shading; sh.light = 'STUDIO'; sh.show_specular_highlight = True
sh.show_backface_culling = True   # comme Blur : une face retournée disparaît
sh.color_type = 'SINGLE' if grey else 'TEXTURE'; sh.single_color = (0.55, 0.55, 0.57)
sc.world = bpy.data.worlds.new('w'); sc.world.color = (0.62, 0.66, 0.70)
cam = bpy.data.objects.new('cam', bpy.data.cameras.new('cam')); sc.collection.objects.link(cam); sc.camera = cam
cam.data.lens = 50
for z, (t, c) in ZONES.items():
    if ONLY and z not in ONLY: continue
    cam.location = Vector(c); cam.rotation_euler = (Vector(t) - cam.location).to_track_quat('-Z', 'Y').to_euler()
    sc.render.filepath = f"{out}_{z}{'_gris' if grey else ''}.png"; bpy.ops.render.render(write_still=True)
