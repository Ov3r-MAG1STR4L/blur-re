"""Coût de restauration des détails : pour chaque pièce, triangles nécessaires pour tenir un écart max donné
(même réduction que reduce_d2_blender.py : soudure par pièce, doublons retirés, Decimate en passes). Ne construit rien.
blender -b -P audit_cost_blender.py -- original.obj pieces_D2.csv sortie.csv"""
import csv, os, sys
import bmesh
import bpy
from mathutils.bvhtree import BVHTree

a = sys.argv[sys.argv.index('--') + 1:]
src, d2_csv, out = (os.path.abspath(x) for x in a[:3])
d2 = {r['pièce']: int(r['tri. réduits']) for r in csv.DictReader(open(d2_csv, encoding='utf-8'), delimiter=';')}
TOLS = (1.0, 3.0, 5.0)   # mm
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.obj_import(filepath=src)
tris = lambda me: sum(len(p.vertices) - 2 for p in me.polygons)
rows = []
for o in sorted([o for o in bpy.data.objects if o.type == 'MESH'], key=lambda o: o.name):
    bm = bmesh.new(); bm.from_mesh(o.data); bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.0001)
    keys, dup = set(), []
    for f in bm.faces:
        k = frozenset(v.index for v in f.verts)
        (dup.append(f) if k in keys else keys.add(k))
    bmesh.ops.delete(bm, geom=dup, context='FACES'); bm.to_mesh(o.data); bm.free()
    orig = o.data.copy(); hi_t = tris(orig)
    hb = BVHTree.FromPolygons([v.co.copy() for v in orig.vertices], [p.vertices[:] for p in orig.polygons])
    hv = orig.vertices; step = max(1, len(hv) // 2000)

    def dev(want):
        me = orig.copy(); o.data = me
        for _ in range(4):
            n = tris(me)
            if n <= want * 1.05 or n == 0: break
            m = o.modifiers.new('d', 'DECIMATE'); m.ratio = want / n
            bpy.context.view_layer.objects.active = o; bpy.ops.object.modifier_apply(modifier='d'); me = o.data
            if tris(me) > 0.97 * n: break
        if not me.polygons: return tris(me), 1e9
        lb = BVHTree.FromPolygons([v.co.copy() for v in me.vertices], [p.vertices[:] for p in me.polygons])
        d = [hb.find_nearest(v.co)[3] or 0 for v in me.vertices] + [lb.find_nearest(hv[i].co)[3] or 0 for i in range(0, len(hv), step)]
        return tris(me), 1000 * max(d)

    need, w = {}, 4
    while len(need) < len(TOLS):
        w = min(w, hi_t); t, mx = dev(w)
        for tol in TOLS:
            if tol not in need and (mx <= tol or w >= hi_t): need[tol] = t
        if w >= hi_t: break
        w *= 2
    rows.append([o.name, hi_t, d2.get(o.name, ''), need[1.0], need[3.0], need[5.0]])
with open(out, 'w', newline='', encoding='utf-8') as f:
    w = csv.writer(f, delimiter=';')
    w.writerow(['pièce', 'tri. origine', 'tri. D2', 'tri. pour 1 mm', 'tri. pour 3 mm', 'tri. pour 5 mm'])
    w.writerows(rows)
print('COUT', len(rows), '->', out)
