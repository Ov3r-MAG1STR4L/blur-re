"""Courbe de coût de chaque pièce : triangles nécessaires pour tenir chaque tolérance d'écart max (0,5 à 30 mm),
avec la même réduction que reduce_d2_blender.py (soudure par pièce, doublons, Decimate en passes) et le même refus des
faces retournées (> 1 % de la surface). Ne construit rien. Sert à chiffrer des budgets (étude 16 000).
blender -b -P cost_curve_blender.py -- original.obj sortie.csv [cartes.txt]
Sortie : pièce;surface cm²;taille caractéristique mm (racine de la surface);tri. origine;besoin à <tol> mm..."""
import csv, math, os, sys
import bmesh
import bpy
from mathutils.bvhtree import BVHTree

a = sys.argv[sys.argv.index('--') + 1:]
src, out = os.path.abspath(a[0]), os.path.abspath(a[1])
cards = set(open(a[2]).read().split()) if len(a) > 2 else set()
TOLS = (0.5, 1, 1.5, 2, 3, 4, 5, 7, 10, 15, 20, 30)   # mm
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.obj_import(filepath=src)
tris = lambda me: sum(len(p.vertices) - 2 for p in me.polygons)


def flipped(hb, me):
    bad = tot = 0.0
    for p in me.polygons:
        hits = hb.find_nearest_range(p.center, 0.01) or [hb.find_nearest(p.center)]
        tot += p.area
        if not any(h[1] is not None and h[1].dot(p.normal) > 0.3 for h in hits): bad += p.area
    return bad / max(tot, 1e-12)


rows = []
for o in sorted([o for o in bpy.data.objects if o.type == 'MESH'], key=lambda o: o.name):
    bm = bmesh.new(); bm.from_mesh(o.data); bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.0001)
    keys, dup = set(), []
    for f in bm.faces:
        k = frozenset(v.index for v in f.verts)
        (dup.append(f) if k in keys else keys.add(k))
    bmesh.ops.delete(bm, geom=dup, context='FACES'); bm.to_mesh(o.data); bm.free()
    orig = o.data.copy(); hi_t = tris(orig); area = sum(p.area for p in orig.polygons)
    hb = BVHTree.FromPolygons([v.co.copy() for v in orig.vertices], [p.vertices[:] for p in orig.polygons])
    hv = orig.vertices; step = max(1, len(hv) // 2000)

    def at(want):
        me = orig.copy(); o.data = me
        for _ in range(4):
            n = tris(me)
            if n <= want * 1.05 or n == 0: break
            m = o.modifiers.new('d', 'DECIMATE'); m.ratio = want / n
            bpy.context.view_layer.objects.active = o; bpy.ops.object.modifier_apply(modifier='d'); me = o.data
            if tris(me) > 0.97 * n: break
        if not me.polygons: return tris(me), 1e9, 1.0
        lb = BVHTree.FromPolygons([v.co.copy() for v in me.vertices], [p.vertices[:] for p in me.polygons])
        d = [hb.find_nearest(v.co)[3] or 0 for v in me.vertices] + [lb.find_nearest(hv[i].co)[3] or 0 for i in range(0, len(hv), step)]
        return tris(me), 1000 * max(d), flipped(hb, me)

    need, w = {}, 4
    if o.name in cards:
        need = {t: None for t in TOLS}   # pièce en carte : coût hors courbe (voir rapport)
    while len(need) < len(TOLS):
        w = min(w, hi_t); t_, mx, fl = at(w)
        for tol in TOLS:
            if tol not in need and ((mx <= tol and fl <= 0.01) or w >= hi_t): need[tol] = t_
        if w >= hi_t: break
        w = int(w * 1.25) + 1
    rows.append([o.name, round(area * 1e4), round(1000 * math.sqrt(area)), hi_t] + [need[t] if need[t] is not None else '' for t in TOLS])
    print('PIECE', o.name, hi_t, [need[t] for t in TOLS], flush=True)
with open(out, 'w', newline='', encoding='utf-8') as f:
    w = csv.writer(f, delimiter=';')
    w.writerow(['pièce', 'surface cm²', 'taille mm', 'tri. origine'] + [f'{t} mm' for t in TOLS])
    w.writerows(rows)
print('COURBES', len(rows), '->', out)
