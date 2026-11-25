"""Cuisson couleur + occlusion d'un modèle détaillé vers un modèle simplifié sans UV (méthodes B, C3, D).
blender -b -P bake_blender.py -- detaille.obj simplifie.obj sortie.glb [texture=1024]
Même cuisson que retopo_bake_blender.py (dépliage Smart UV, Cycles, occlusion 25 cm, fond de creux à 25 %)."""
import math, os, sys
import bpy
import numpy as np

a = sys.argv[sys.argv.index('--') + 1:]
hi_p, lo_p, out = (os.path.abspath(x) for x in a[:3]); tex = int(a[3]) if len(a) > 3 else 1024
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.obj_import(filepath=hi_p); hi = list(bpy.context.selected_objects)
bpy.ops.wm.obj_import(filepath=lo_p); lo = list(bpy.context.selected_objects)


def select(objs, active):
    bpy.ops.object.select_all(action='DESELECT')
    for o in objs: o.select_set(True)
    bpy.context.view_layer.objects.active = active


select(lo, lo[0])
if len(lo) > 1: bpy.ops.object.join()
low = bpy.context.view_layer.objects.active; low.name = 'body'; low.data.materials.clear()
bpy.ops.object.shade_smooth_by_angle(angle=math.radians(25))
bpy.ops.object.mode_set(mode='EDIT'); bpy.ops.mesh.select_all(action='SELECT')
bpy.ops.uv.smart_project(angle_limit=math.radians(66), island_margin=0.004)
bpy.ops.object.mode_set(mode='OBJECT')
img = bpy.data.images.new('body_baked', tex, tex)
mat = bpy.data.materials.new('body'); mat.use_nodes = True
node = mat.node_tree.nodes.new('ShaderNodeTexImage'); node.image = img; mat.node_tree.nodes.active = node
mat.node_tree.links.new(node.outputs['Color'], mat.node_tree.nodes['Principled BSDF'].inputs['Base Color'])
low.data.materials.append(mat)
sc = bpy.context.scene; sc.render.engine = 'CYCLES'; sc.cycles.samples = 4; sc.cycles.device = 'CPU'
select(hi + [low], low)
kw = dict(use_selected_to_active=True, cage_extrusion=0.05, max_ray_distance=0.15, margin=8)
bpy.ops.object.bake(type='DIFFUSE', pass_filter={'COLOR'}, **kw)
for k in ('visible_diffuse', 'visible_glossy', 'visible_shadow', 'visible_transmission'): setattr(low, k, False)
sc.world = bpy.data.worlds.new('w'); sc.world.light_settings.distance = 0.25; sc.cycles.samples = 64
ao = bpy.data.images.new('ao', tex, tex); node.image = ao
bpy.ops.object.bake(type='AO', **kw)
c, o = np.array(img.pixels[:]).reshape(-1, 4), np.array(ao.pixels[:]).reshape(-1, 4)
c[:, :3] *= 0.25 + 0.75 * o[:, :3]; img.pixels[:] = c.ravel(); node.image = img; img.pack()
for h in hi: bpy.data.objects.remove(h)
bpy.ops.export_scene.gltf(filepath=out, export_format='GLB', export_apply=True)
print('GLB', out, sum(len(p.vertices) - 2 for p in low.data.polygons))
