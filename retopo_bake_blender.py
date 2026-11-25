"""Recrée une carrosserie légère et propre à partir d'un modèle détaillé, couleurs cuites dans une texture.

blender -b -P retopo_bake_blender.py -- modele.obj sortie.glb [triangles=5500] [texture=2048] [voxel=0.012]

Au lieu de réduire le modèle détaillé (pièces déchirées à 98 % de réduction), on refait une coque :
1. carrosserie épaissie puis remaillée en voxels : une seule surface fermée et régulière ;
2. on ne garde que les faces visibles de l'extérieur (l'envers des tôles est retiré) ;
3. Decimate (ou Instant Meshes avec --instant, voir plus bas) ; lissage ;
4. dépliage UV et cuisson de la couleur du modèle détaillé (livrée, autocollants, calandre, feux) ;
5. vitres gardées à part, réduites, matériau « glass » (reconnu par Map Builder).
"""
import math
import os
import sys

import bmesh
import bpy
import numpy as np
from mathutils.bvhtree import BVHTree

args = sys.argv[sys.argv.index('--') + 1:]
src, out = os.path.abspath(args[0]), args[1]
target = int(args[2]) if len(args) > 2 else 5500
tex = int(args[3]) if len(args) > 3 else 2048
# 1,2 cm : le meilleur résultat. 8 mm garde plus de creux mais Decimate froisse les tôles (essai 2026-11-25)
voxel = float(args[4]) if len(args) > 4 else 0.012
GLASS_TRIS = 400
AO_DIST = 0.25    # portée de l'occlusion (m)
AO_MIN = 0.25     # couleur au fond d'un creux = 25 % de la couleur d'origine
# Instant Meshes (wjakob, release Windows officielle) : utilisé s'il est là, sinon Decimate
INSTANT = os.path.join(os.path.expanduser('~'), 'Jeux_WII', 'tools', 'instant-meshes', 'Instant Meshes.exe')
CREASE = 30       # angle (°) au-delà duquel une arête est gardée vive par Instant Meshes

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
# Instant Meshes seulement avec --instant : sur une tôle épaissie (deux faces à ~1 cm), il perce la coque de partout
# (essai 1000tipla 2026-11-25 : lambeaux, 10 042 triangles au lieu de 5 100). Il lui faut un volume plein.
if '--instant' in sys.argv and os.path.exists(INSTANT):
    # Instant Meshes : grille de quadrilatères régulière qui suit les arêtes (-c) et les bords des fenêtres et
    # arches (-b), au lieu de Decimate qui retire des triangles sans voir la forme (facettes, tôles cabossées).
    import subprocess, tempfile
    tmp = tempfile.mkdtemp(); a, b = os.path.join(tmp, 'shell.obj'), os.path.join(tmp, 'quads.obj')
    select([low], low)
    bpy.ops.wm.obj_export(filepath=a, export_selected_objects=True, export_uv=False, export_normals=False,
                          export_materials=False)
    subprocess.run([INSTANT, a, '-o', b, '-f', str(budget // 2), '-c', str(CREASE), '-b', '-r', '4', '-p', '4',
                    '-S', '3'], check=True, capture_output=True)
    bpy.data.objects.remove(low)
    bpy.ops.wm.obj_import(filepath=b)
    low = bpy.context.selected_objects[0]; low.name = low.data.name = 'body'
    apply(low, 'TRIANGULATE')
    print('instant meshes', tris(low))
else:
    # Réduction uniforme. Un groupe de sommets « détail » sur Decimate (essai 2026-11-25) fige les sommets à poids
    # faible : 32 000 triangles quel que soit le facteur, tôles cabossées. Le détail passe par l'ombrage cuit.
    for _ in range(4):
        n = tris(low)
        if n <= budget * 1.03: break
        apply(low, 'DECIMATE', ratio=budget / n)
# 25° : arêtes du capot, des ailes et des prises d'air restent vives (40° rendait tout mou, 2026-11-25)
select([low], low); bpy.ops.object.shade_smooth_by_angle(angle=math.radians(25))

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
bake = dict(use_selected_to_active=True, cage_extrusion=0.05, max_ray_distance=0.15, margin=8)
bpy.ops.object.bake(type='DIFFUSE', pass_filter={'COLOR'}, **bake)

# ombrage cuit : Map Builder ne lit pas les normal maps (ModelImport.cs : « bump map (NOT read) ») ; un creux
# (échappement, prise d'air, joint de porte) ne se voit que s'il est sombre dans la couleur. Occlusion calculée sur
# le modèle détaillé ; la coque, posée par-dessus, ne doit pas faire d'ombre.
for k in ('visible_diffuse', 'visible_glossy', 'visible_shadow', 'visible_transmission'): setattr(low, k, False)
sc.world = bpy.data.worlds.new('w'); sc.world.light_settings.distance = AO_DIST; sc.cycles.samples = 64
ao = bpy.data.images.new('ao', tex, tex); node.image = ao
bpy.ops.object.bake(type='AO', **bake)
col, occ = np.array(img.pixels[:]).reshape(-1, 4), np.array(ao.pixels[:]).reshape(-1, 4)
col[:, :3] *= AO_MIN + (1 - AO_MIN) * occ[:, :3]
img.pixels[:] = col.ravel(); node.image = img
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
