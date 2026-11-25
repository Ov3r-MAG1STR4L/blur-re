"""Méthode D2 sur une voiture entière : pièces et textures d'origine, budget réparti par SURFACE (pas par densité),
normales recalculées. Validée sur une pièce : docs/ETUDE_RECONSTRUCTION_1000TIPLA.md.

blender -b -P reduce_d2_blender.py -- modele.obj dossier_sortie budgets(ex. 6000,7000,8000) [importants.txt]

- chaque pièce soudée SEULE, faces en double retirées (voir glb_reduce_blender.py) ;
- poids = surface x IMPORTANT (x3) pour vitres, feux, rétros, échappements (matériau ou nom, liste en argument) ;
- plancher : une pièce garde au moins min(ses triangles, PLANCHER) : rien ne disparaît pour tenir le budget ;
- facteur de répartition cherché par dichotomie pour que le total (vitres comprises) tienne dans chaque budget ;
- normales d'origine effacées puis recalculées (lissage 30°) : figées, elles tachent les tôles réduites ;
- rapport par pièce : triangles avant/après, écart moyen et max à l'original (mm), alertes.
"""
import csv
import math
import os
import sys

import bmesh
import bpy
from mathutils.bvhtree import BVHTree

args = sys.argv[sys.argv.index('--') + 1:]
opt = dict(x[2:].split('=', 1) for x in args if x.startswith('--'))
a = [x for x in args if not x.startswith('--')]
src, outdir = os.path.abspath(a[0]), os.path.abspath(a[1])
budgets = [int(b) for b in a[2].split(',')]
names_imp = open(a[3]).read().split() if len(a) > 3 else []
# Options issues de l'audit des détails (docs/etude_reconstruction/audit_details) :
#   --planchers=f.csv  pièce;triangles imposés (détails tenus à 5 mm : vitres, rétros, feux, échappements)
#   --plafonds=f.csv   pièce;triangles max (besoin à 1 mm : au-delà, gaspillage)
#   --cartes=f.txt     seules ces pièces deviennent des cartes (sinon : règle automatique)
read_map = lambda p: {l.split(';')[0]: int(l.split(';')[1]) for l in open(p, encoding='utf-8') if ';' in l}
fixed = read_map(opt['planchers']) if 'planchers' in opt else {}
caps = read_map(opt['plafonds']) if 'plafonds' in opt else {}
cards_only = set(open(opt['cartes']).read().split()) if 'cartes' in opt else None
IMPORTANT, PLANCHER = 3.0, 8
MAT_IMP = ('glass', 'light', 'mirror')            # vitres, feux (light_red, light_orange, Light), miroirs
os.makedirs(outdir, exist_ok=True)

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.obj_import(filepath=src)
objs = sorted([o for o in bpy.data.objects if o.type == 'MESH'], key=lambda o: o.name)
# l'export OBJ de Blender remplace les espaces des noms par « _ » : une entrée qui ne correspond à rien est ignorée en
# silence (clignotants sans plancher, 2026-11-26) -> arrêt
_names = {o.name for o in objs}
_bad = sorted(n for n in list(fixed) + list(caps) if n not in _names)
if _bad: raise SystemExit(f'planchers / plafonds sans pièce correspondante : {_bad}')
tris = lambda me: sum(len(p.vertices) - 2 for p in me.polygons)

orig, hi_bvh, info = {}, {}, {}
for o in objs:
    bm = bmesh.new(); bm.from_mesh(o.data)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.0001)
    keys, dup = set(), []
    for f in bm.faces:
        k = frozenset(v.index for v in f.verts)
        if k in keys: dup.append(f)
        else: keys.add(k)
    bmesh.ops.delete(bm, geom=dup, context='FACES'); bm.to_mesh(o.data); bm.free()
    orig[o.name] = o.data.copy()
    hi_bvh[o.name] = BVHTree.FromPolygons([v.co.copy() for v in o.data.vertices], [p.vertices[:] for p in o.data.polygons])
    mat = o.data.materials[0].name if o.data.materials else ''
    imp = any(k in mat.lower() for k in MAT_IMP) or o.name in names_imp
    info[o.name] = dict(mat=mat, imp=imp, area=sum(p.area for p in o.data.polygons), hi=tris(o.data))
def card(o):
    """Pièce que Decimate ne réduit pas (grille en nid d'abeille : 20 448 -> 13 305 au mieux, ses trous bloquent
    tout) : remplacée par une plaque fermée (épaissie + voxels) où sa couleur est cuite, alvéoles comprises.
    La plaque se réduit ensuite comme les autres pièces (les UV suivent Decimate)."""
    c = bpy.data.objects.new(o.name + '_carte', o.data.copy()); bpy.context.scene.collection.objects.link(c)
    c.data.materials.clear()
    for kind, kw in (('SOLIDIFY', dict(thickness=0.008, offset=0)), ('REMESH', dict(mode='VOXEL', voxel_size=0.006)),
                     ('DECIMATE', dict(ratio=1.0))):
        m = c.modifiers.new('m', kind)
        for k, v in kw.items(): setattr(m, k, v)
        if kind == 'DECIMATE': m.ratio = min(1.0, 4000 / max(1, tris(c.data)))
        bpy.ops.object.select_all(action='DESELECT'); c.select_set(True); bpy.context.view_layer.objects.active = c
        bpy.ops.object.modifier_apply(modifier='m')
    bpy.ops.object.mode_set(mode='EDIT'); bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.smart_project(angle_limit=math.radians(66), island_margin=0.004); bpy.ops.object.mode_set(mode='OBJECT')
    # nom sans point : l'export glTF coupe au point et fusionnait les images de deux cartes (Circle.015 / Circle.027)
    tag = o.name.replace('.', '_') + '_carte'
    img = bpy.data.images.new(tag, 512, 512)
    mat = bpy.data.materials.new(tag); mat.use_nodes = True
    node = mat.node_tree.nodes.new('ShaderNodeTexImage'); node.image = img; mat.node_tree.nodes.active = node
    mat.node_tree.links.new(node.outputs['Color'], mat.node_tree.nodes['Principled BSDF'].inputs['Base Color'])
    c.data.materials.append(mat)
    sc = bpy.context.scene; sc.render.engine = 'CYCLES'; sc.cycles.samples = 4; sc.cycles.device = 'CPU'
    o.data = orig[o.name]
    bpy.ops.object.select_all(action='DESELECT'); o.select_set(True); c.select_set(True)
    bpy.context.view_layer.objects.active = c
    bpy.ops.object.bake(type='DIFFUSE', pass_filter={'COLOR'}, use_selected_to_active=True, cage_extrusion=0.02,
                        max_ray_distance=0.05, margin=4)
    img.pack(); me = c.data; bpy.data.objects.remove(c)
    print(f'CARTE {o.name} : {info[o.name]["hi"]} -> plaque {tris(me)} triangles, couleur cuite 512 px')
    return me


# pièces rebelles : essai de réduction au plancher ; si elles gardent plus de 100 triangles, elles deviennent une carte
for o in objs:
    me = orig[o.name].copy(); o.data = me
    m = o.modifiers.new('d', 'DECIMATE'); m.ratio = min(1.0, PLANCHER / max(1, tris(me)))
    bpy.context.view_layer.objects.active = o; bpy.ops.object.modifier_apply(modifier='d')
    # pièce lourde seulement : Fiat_Multipla_28 (716 tri., bandes séparées) devenait une carte de 4 000 triangles
    rebel = tris(o.data) > 100 and info[o.name]['hi'] > 2000
    if (o.name in cards_only) if cards_only is not None else rebel:
        orig[o.name] = card(o); info[o.name]['carte'] = True
        # écart d'une carte mesuré par rapport à la carte : face à l'original ajouré (montants d'aileron), une
        # plaque pleine n'est jamais sous la tolérance (Circle.015 réclamait 3 588 triangles)
        hi_bvh[o.name] = BVHTree.FromPolygons([v.co.copy() for v in orig[o.name].vertices],
                                              [p.vertices[:] for p in orig[o.name].polygons])
    o.data = orig[o.name]
weight = {n: d['area'] * (IMPORTANT if d['imp'] else 1.0) for n, d in info.items()}
W = sum(weight.values())

cache = {}   # (pièce, triangles voulus) -> maillage réduit


def reduced(o, want):
    # jamais plus que l'origine (une grande pièce plate recevait plus que ses 716 triangles), jamais moins que le plancher
    top = min(info[o.name]['hi'], caps.get(o.name, info[o.name]['hi']))
    low_ = max(floor.get(o.name, min(info[o.name]['hi'], PLANCHER)), fixed.get(o.name, 0))
    want = max(low_, min(want, top))
    key = (o.name, want)
    if key not in cache:
        # Une réduction forte replie des triangles d'une pièce fine : retournés, ils sont invisibles dans Blur (qui
        # n'affiche qu'un côté ; 29 % de la barre latérale Fiat_Multipla_90 à 14 triangles). Refusée au-delà de 1 % de
        # la surface : +50 % de triangles (au-delà du plafond s'il le faut) jusqu'à une pièce propre.
        w = want
        while True:
            me = decimate(o, w)
            if w >= info[o.name]['hi'] or flipped(o, me) <= 0.01: break
            w = min(info[o.name]['hi'], int(w * 1.5) + 1)
        cache[key] = me
    return cache[key]


raw = {}


def decimate(o, want):
    if (o.name, want) not in raw:
        me = orig[o.name].copy(); o.data = me
        for _ in range(4):
            n = tris(me)
            if n <= want * 1.05 or n == 0: break
            m = o.modifiers.new('d', 'DECIMATE'); m.ratio = want / n
            bpy.context.view_layer.objects.active = o; bpy.ops.object.modifier_apply(modifier='d')
            me = o.data
            if tris(me) > 0.97 * n: break
        raw[(o.name, want)] = me
    return raw[(o.name, want)]


def flipped(o, me):
    """part de la surface réduite sans face d'origine de même orientation à moins de 1 cm (face retournée)."""
    bad = tot = 0.0
    for p in me.polygons:
        hits = hi_bvh[o.name].find_nearest_range(p.center, 0.01) or [hi_bvh[o.name].find_nearest(p.center)]
        tot += p.area
        if not any(h[1] is not None and h[1].dot(p.normal) > 0.3 for h in hits): bad += p.area
    return bad / max(tot, 1e-12)


def build(s):
    for o in objs: o.data = reduced(o, round(s * weight[o.name] / W))
    return sum(tris(o.data) for o in objs)


def deviation(o):
    """écart en mm : sommets réduits -> surface d'origine (déformation), sommets d'origine -> surface réduite (perte)."""
    if not o.data.polygons: return 0.0, float('inf')
    lo = BVHTree.FromPolygons([v.co.copy() for v in o.data.vertices], [p.vertices[:] for p in o.data.polygons])
    d1 = [hi_bvh[o.name].find_nearest(v.co)[3] or 0 for v in o.data.vertices]
    hv = orig[o.name].vertices; step = max(1, len(hv) // 3000)
    d2 = [lo.find_nearest(hv[i].co)[3] or 0 for i in range(0, len(hv), step)]
    d = d1 + d2
    return 1000 * sum(d) / max(1, len(d)), 1000 * max(d + [0])


# Plancher par pièce : le plus petit nombre de triangles (8, 16, 32...) qui la garde à moins de TOL de l'original.
# Un plancher fixe ne suffit pas : les baguettes chromées qui font le tour de la voiture (Circle.026, 12 008 tri.,
# 361 cm²) tombaient à 8 triangles étirés sur 3 m.
# Tolérance : la plus stricte qui tient dans le budget (2 cm, sinon 3 ; 4,5 ; 6), indiquée dans le rapport.
TOLS = (20.0, 30.0, 45.0, 60.0)   # mm, écart max toléré
floor, dev_cache = {}, {}


def floors(tol):
    out = {}
    for o in objs:
        w = min(info[o.name]['hi'], PLANCHER)
        while True:
            o.data = reduced(o, w)
            key = (o.name, w)
            if key not in dev_cache: dev_cache[key] = deviation(o)[1]
            if w >= info[o.name]['hi'] or dev_cache[key] <= tol: break
            w = min(info[o.name]['hi'], w * 2)
        out[o.name] = w
    return out


for budget in budgets:
    for TOL in TOLS:
        floor = {}; f = floors(TOL); floor.update(f)
        need = sum(tris(reduced(o, f[o.name])) for o in objs)
        print(f'PLANCHERS {budget} : tolérance {TOL:.0f} mm -> {need} triangles au minimum')
        if need <= budget: break
    for n in sorted(floor, key=lambda n: -floor[n])[:8]: print(f'  {floor[n]:5d}  {n}')
    lo_s, hi_s = 0.0, budget * 8.0
    for _ in range(14):           # dichotomie sur le facteur de répartition
        mid = (lo_s + hi_s) / 2
        if build(mid) <= budget: lo_s = mid
        else: hi_s = mid
    total = build(lo_s)
    if total > budget: raise SystemExit(f'budget {budget} impossible : {total} triangles au minimum (pièces rebelles ?)')
    for o in objs:                # normales recalculées sur une copie (le cache garde l'état réduit brut)
        o.data = o.data.copy()
        bpy.ops.object.select_all(action='DESELECT'); o.select_set(True); bpy.context.view_layer.objects.active = o
        if o.data.has_custom_normals: bpy.ops.mesh.customdata_custom_splitnormals_clear()
        bpy.ops.object.shade_smooth_by_angle(angle=math.radians(30))
    path = os.path.join(outdir, f'1000tipla_D2_{budget}.glb')
    bpy.ops.export_scene.gltf(filepath=path, export_format='GLB', export_apply=True)
    rows = []
    for o in objs:
        d = info[o.name]; lo = tris(o.data); mean, mx = deviation(o)
        alerte = []
        if d.get('carte'): alerte.append('remplacée par une carte (couleur cuite)')
        if flipped(o, o.data) > 0.01: alerte.append('FACES RETOURNÉES')
        if lo == 0: alerte.append('SUPPRIMÉE')
        elif lo <= PLANCHER and d['hi'] > PLANCHER: alerte.append('au plancher')
        if mean > 5: alerte.append('déformée (moy > 5 mm)')
        if mx > TOL: alerte.append(f'écart max > tolérance {TOL:.0f} mm')
        rows.append([o.name, d['mat'], 'oui' if d['imp'] else '', round(d['area'] * 1e4), d['hi'], lo,
                     f'{mean:.1f}', f'{mx:.1f}', ', '.join(alerte)])
    rows.sort(key=lambda r: -r[5])
    with open(os.path.join(outdir, f'pieces_{budget}.csv'), 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f, delimiter=';')
        w.writerow(['pièce', 'matériau', 'importante', 'surface cm²', 'tri. origine', 'tri. réduits',
                    'écart moy mm', 'écart max mm', 'alerte'])
        w.writerows(rows)
    print(f'BUDGET {budget} : {total} triangles, tolérance {TOL:.0f} mm, facteur {lo_s:.0f}, {path}')
