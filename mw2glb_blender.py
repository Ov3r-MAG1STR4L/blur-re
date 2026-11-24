"""Blender (-b -P): OBJ issu de mwgeom.to_obj + PNG de mwgeom.textures -> .glb allégés pour Map Builder (voiture perso).
Arguments après -- : obj  dossier_png  dossier_sortie  pièces(séparées par ,)  cibles_triangles(séparées par ,)"""
import bpy, sys, os, glob
args = sys.argv[sys.argv.index('--') + 1:]
SPLIT = '--split' in args          # découpe en pièces de Blur (e_bonnet, e_door_left...), voir split_blur
obj, texdir, outdir, keep, targets = [a for a in args if a != '--split']
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
    if SPLIT: split_blur()
    return sum(len(o.data.polygons) for o in bpy.data.objects)

# Découpe en pièces aux noms des éléments d'une voiture de Blur (ceux de la Bowler Nemesis).
# Repère de la voiture NFS : +x avant, +y gauche, z haut, en mètres.
# ponytail: boîtes réglées sur la Ryback Vulcan ; une autre voiture demande ses propres boîtes.
def blur_part(mats, mn, mx):
    c = [(a + b) / 2 for a, b in zip(mn, mx)]
    side = 'left' if c[1] > 0 else 'right'
    paint = 'paint' in mats
    if 0.6 <= mn[0] and mx[0] <= 1.0 and min(abs(mn[1]), abs(mx[1])) > 0.75 and 0.55 <= mn[2] and mx[2] <= 0.75:
        return 'e_mirror_front' + side
    if paint and mn[0] >= 1.0 and mn[2] >= 0.25 and max(abs(mn[1]), abs(mx[1])) <= 0.75:
        return 'e_bonnet'
    if paint and mx[0] <= -1.4 and mn[2] >= 0.5 and max(abs(mn[1]), abs(mx[1])) <= 0.4:
        return 'e_boot'
    if -0.25 <= mn[0] and mx[0] <= 1.15 and min(abs(mn[1]), abs(mx[1])) >= 0.6 and mx[2] <= 0.65:
        return 'e_door_' + side
    return None

def split_blur():
    import bmesh
    parts = {}
    for o in list(bpy.data.objects):
        base = 'e_interior' if o.name.startswith('interior') else 'e_exterior'
        bm = bmesh.new(); bm.from_mesh(o.data); bm.faces.ensure_lookup_table()
        seen, comps = set(), []
        for f in bm.faces:
            if f.index in seen: continue
            stack, fs = [f], []; seen.add(f.index)
            while stack:
                g = stack.pop(); fs.append(g.index)
                for e in g.edges:
                    for h in e.link_faces:
                        if h.index not in seen: seen.add(h.index); stack.append(h)
            vs = [v.co for i in fs for v in bm.faces[i].verts]
            mn = tuple(min(v[k] for v in vs) for k in range(3)); mx = tuple(max(v[k] for v in vs) for k in range(3))
            mats = {o.data.materials[bm.faces[i].material_index].name for i in fs}
            comps.append((fs, mn, mx, mats))
        # la conversion NFS double certaines pièces (même forme en peinture et en noir) : on garde la peinture
        painted = {(len(fs), tuple(round(x, 2) for x in mn + mx)) for fs, mn, mx, m in comps if 'paint' in m}
        target = {}
        for fs, mn, mx, mats in comps:
            if 'paint' not in mats and (len(fs), tuple(round(x, 2) for x in mn + mx)) in painted: continue
            name = blur_part(mats, mn, mx) if base == 'e_exterior' else None
            for i in fs: target[i] = name or base
        bm.free()
        for name in set(target.values()):
            p = o.copy(); p.data = o.data.copy(); bpy.context.scene.collection.objects.link(p)
            b2 = bmesh.new(); b2.from_mesh(p.data); b2.faces.ensure_lookup_table()
            bmesh.ops.delete(b2, geom=[f for f in b2.faces if target.get(f.index) != name], context='FACES')
            b2.to_mesh(p.data); b2.free()
            parts.setdefault(name, []).append(p)
        bpy.data.objects.remove(o)
    for name, objs in parts.items():   # une pièce = un objet au nom de l'élément de Blur
        bpy.ops.object.select_all(action='DESELECT')
        for p in objs: p.select_set(True)
        bpy.context.view_layer.objects.active = objs[0]
        if len(objs) > 1: bpy.ops.object.join()
        objs[0].name = name; objs[0].data.name = name
    print('PARTS', {n: len(bpy.data.objects[n].data.polygons) for n in sorted(parts)})

total = build()
print('FULL', total)
for t in targets:
    build()
    for o in bpy.data.objects:
        mod = o.modifiers.new('dec', 'DECIMATE')
        mod.ratio = min(1.0, t / total * (0.35 if o.name.startswith('interior') else 1.15))
        bpy.context.view_layer.objects.active = o; bpy.ops.object.modifier_apply(modifier='dec')
    n = sum(len(o.data.polygons) for o in bpy.data.objects)
    out = os.path.join(outdir, f'ryback_vulcan_{t // 1000}k{"_pieces" if SPLIT else ""}.glb')
    bpy.ops.export_scene.gltf(filepath=out, export_format='GLB', export_apply=True)
    print('GLB', out, n)
