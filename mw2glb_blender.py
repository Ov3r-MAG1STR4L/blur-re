"""Blender (-b -P): OBJ issu de mwgeom.to_obj + PNG de mwgeom.textures -> .glb allégés pour Map Builder (voiture perso).
Arguments après -- : obj  dossier_png  dossier_sortie  pièces(séparées par ,)  cibles_triangles(séparées par ,)"""
import bpy, sys, os, glob
obj, texdir, outdir, keep, targets = sys.argv[sys.argv.index('--') + 1:]
keep = keep.split(','); targets = [int(t) for t in targets.split(',')]
PAINT, GLASS = '6E77236D', '7B220DDF'          # VULCAN_SKIN1 (peinture du jeu), WINDOW_FRONT (vitre globale)
PAINT_RGB = (0.55, 0.57, 0.60, 1)              # ponytail: couleur fixe, la peinture des carrosseries importées est grisée dans Map Builder 2.7.1

def build():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.wm.obj_import(filepath=obj, forward_axis='Y', up_axis='Z')
    only_paint = [k[:-6] for k in keep if k.endswith(':paint')]   # NOM:paint = garder seulement la peinture (pièce en double)
    names = [k.split(':')[0] for k in keep]
    for o in list(bpy.data.objects):
        if not any(o.name.startswith(k) for k in names): bpy.data.objects.remove(o)
        elif any(o.name.startswith(k) for k in only_paint):
            import bmesh
            bm = bmesh.new(); bm.from_mesh(o.data)
            slot = [i for i, m in enumerate(o.data.materials) if m and PAINT in m.name]
            bmesh.ops.delete(bm, geom=[f for f in bm.faces if f.material_index not in slot], context='FACES')
            bm.to_mesh(o.data); bm.free()
    pngs = {os.path.basename(p)[:8]: p for p in glob.glob(os.path.join(texdir, '*.png'))}
    for m in bpy.data.materials:
        h = m.name.replace('tex_', '')[:8]
        m.use_nodes = True; bsdf = m.node_tree.nodes.get('Principled BSDF')
        if h == PAINT:
            m.name = 'paint'; bsdf.inputs['Base Color'].default_value = PAINT_RGB
            bsdf.inputs['Metallic'].default_value = 0.6; bsdf.inputs['Roughness'].default_value = 0.3
        elif h == GLASS:
            m.name = 'glass'; bsdf.inputs['Base Color'].default_value = (0.05, 0.06, 0.07, 1)
            bsdf.inputs['Alpha'].default_value = 0.35; m.surface_render_method = 'BLENDED'
        elif h in pngs:
            img = bpy.data.images.load(pngs[h]); tn = m.node_tree.nodes.new('ShaderNodeTexImage'); tn.image = img
            m.node_tree.links.new(tn.outputs['Color'], bsdf.inputs['Base Color'])
            name = os.path.basename(pngs[h])[9:-4].lower()
            m.name = name
            if 'interior' in name: bsdf.inputs['Roughness'].default_value = 0.9
            if img.depth == 32 or 'light' in name or 'neon' in name:
                m.node_tree.links.new(tn.outputs['Alpha'], bsdf.inputs['Alpha']); m.surface_render_method = 'BLENDED'
        else:
            m.name = 'black_trim'; bsdf.inputs['Base Color'].default_value = (0.02, 0.02, 0.02, 1)
    for o in bpy.data.objects:   # noms parlants pour Map Builder (intérieur mat d'après le nom)
        if 'INTERIOR' in o.name: o.name = 'interior'
    return sum(len(o.data.polygons) for o in bpy.data.objects)

total = build()
print('FULL', total)
for t in targets:
    build()
    for o in bpy.data.objects:
        mod = o.modifiers.new('dec', 'DECIMATE')
        mod.ratio = min(1.0, t / total * (0.35 if o.name.startswith('interior') else 1.15))
        bpy.context.view_layer.objects.active = o; bpy.ops.object.modifier_apply(modifier='dec')
    n = sum(len(o.data.polygons) for o in bpy.data.objects)
    out = os.path.join(outdir, f'ryback_vulcan_{t // 1000}k.glb')
    bpy.ops.export_scene.gltf(filepath=out, export_format='GLB', export_apply=True)
    print('GLB', out, n)
