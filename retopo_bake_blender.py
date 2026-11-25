"""Recrée une carrosserie légère et propre à partir d'un modèle détaillé, couleurs cuites dans une texture.

blender -b -P retopo_bake_blender.py -- modele.obj sortie.glb [triangles=5500] [texture=2048] [voxel=0.012]

Au lieu de réduire le modèle détaillé (pièces déchirées à 98 % de réduction), on refait une coque :
1. carrosserie épaissie puis remaillée en voxels : une seule surface fermée et régulière ;
2. on ne garde que les faces visibles de l'extérieur (l'envers des tôles est retiré) ;
3. Decimate sur cette surface propre, lissage ;
4. dépliage UV et cuisson de la couleur du modèle détaillé (livrée, autocollants, calandre, feux) ;
5. vitres gardées à part, réduites, matériau « glass » (reconnu par Map Builder).
"""
import math
import os
import sys

import bmesh
import bpy
from mathutils.bvhtree import BVHTree

args = sys.argv[sys.argv.index('--') + 1:]
src, out = os.path.abspath(args[0]), args[1]
target = int(args[2]) if len(args) > 2 else 5500
tex = int(args[3]) if len(args) > 3 else 2048
voxel = float(args[4]) if len(args) > 4 else 0.012
GLASS_TRIS = 400

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.obj_import(filepath=src)
hi = [o for o in bpy.data.objects if o.type == 'MESH']
is_glass = lambda o: any(m and 'glass' in m.name.lower() for m in o.data.materials)
glass = [o for o in hi if is_glass(o)]
body_hi = [o for o in hi if not is_glass(o)]
tris = lambda o: sum(len(p.vertices) - 2 for p in o.data.polygons)


def select(objs, active):
    bpy.ops.object.select_all(action='DESELECT')
    for o in objs: o.select_set(True)
    bpy.context.view_layer.objects.active = active


def apply(o, kind, **kw):
    m = o.modifiers.new('m', kind)
    for k, v in kw.items(): setattr(m, k, v)
    select([o], o); bpy.ops.object.modifier_apply(modifier='m')


def copy_joined(objs, name):
    cs = []
    for o in objs:
        c = o.copy(); c.data = o.data.copy(); bpy.context.scene.collection.objects.link(c); cs.append(c)
    select(cs, cs[0])
    if len(cs) > 1: bpy.ops.object.join()
    o = bpy.context.view_layer.objects.active; o.name = o.data.name = name
    return o


# 1. coque fermée
low = copy_joined(body_hi, 'body')
low.data.materials.clear()
apply(low, 'SOLIDIFY', thickness=voxel * 1.5, offset=0)
apply(low, 'REMESH', mode='VOXEL', voxel_size=voxel)
print('remesh', tris(low))
apply(low, 'DECIMATE', ratio=min(1.0, 300000 / max(1, tris(low))))

# 2. faces visibles de l'extérieur : un rayon parmi 13 (normale + cône de 60°) doit sortir sans rien toucher.
# ponytail: 13 directions, une face visible seulement en rasant peut partir ; plus de directions si des trous
bvh = BVHTree.FromObject(low, bpy.context.evaluated_depsgraph_get())
bm = bmesh.new(); bm.from_mesh(low.data); bm.faces.ensure_lookup_table()
hidden = []
for f in bm.faces:
    n = f.normal; c = f.calc_center_median() + n * 0.002
    t = n.orthogonal().normalized(); b = n.cross(t)
    dirs = [n] + [(n * math.cos(math.radians(60)) + (t * math.cos(a) + b * math.sin(a)) * math.sin(math.radians(60)))
                  for a in (i * math.pi / 6 for i in range(12))]
    if all(bvh.ray_cast(c, d, 20)[0] is not None for d in dirs): hidden.append(f)
bmesh.ops.delete(bm, geom=hidden, context='FACES')
bm.to_mesh(low.data); bm.free()
print('visible', tris(low), 'retirées', len(hidden))

# 3. réduction + lissage
gl = copy_joined(glass, 'glass') if glass else None
if gl:
    bm = bmesh.new(); bm.from_mesh(gl.data); bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.0005)
    bm.to_mesh(gl.data); bm.free()
    apply(gl, 'DECIMATE', ratio=min(1.0, GLASS_TRIS / max(1, tris(gl))))
budget = target - (tris(gl) if gl else 0)
for _ in range(4):
    n = tris(low)
    if n <= budget * 1.03: break
    apply(low, 'DECIMATE', ratio=budget / n)
select([low], low); bpy.ops.object.shade_smooth_by_angle(angle=math.radians(40))

# 4. UV + cuisson de la couleur
select([low], low); bpy.ops.object.mode_set(mode='EDIT'); bpy.ops.mesh.select_all(action='SELECT')
bpy.ops.uv.smart_project(angle_limit=math.radians(66), island_margin=0.004)
bpy.ops.object.mode_set(mode='OBJECT')
img = bpy.data.images.new('body_baked', tex, tex)
mat = bpy.data.materials.new('body'); mat.use_nodes = True
node = mat.node_tree.nodes.new('ShaderNodeTexImage'); node.image = img
mat.node_tree.nodes.active = node
bsdf = mat.node_tree.nodes['Principled BSDF']
mat.node_tree.links.new(node.outputs['Color'], bsdf.inputs['Base Color'])
bsdf.inputs['Roughness'].default_value = 0.35
low.data.materials.append(mat)
sc = bpy.context.scene; sc.render.engine = 'CYCLES'; sc.cycles.samples = 4; sc.cycles.device = 'CPU'
select(body_hi + [low], low)
bpy.ops.object.bake(type='DIFFUSE', pass_filter={'COLOR'}, use_selected_to_active=True,
                    cage_extrusion=voxel * 4, max_ray_distance=voxel * 12, margin=8)
img.pack()

if gl:
    gl.data.materials.clear()
    gm = bpy.data.materials.new('glass'); gm.use_nodes = True
    p = gm.node_tree.nodes['Principled BSDF']
    p.inputs['Base Color'].default_value = (0.05, 0.06, 0.07, 1); p.inputs['Alpha'].default_value = 0.35
    gl.data.materials.append(gm)

# 5. export : seulement la coque et les vitres
for o in hi: bpy.data.objects.remove(o)
bpy.ops.export_scene.gltf(filepath=out, export_format='GLB', export_apply=True)
print(f'GLB {out} : coque {tris(low)} + vitres {tris(gl) if gl else 0} triangles, texture {tex} px')
