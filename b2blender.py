#!/usr/bin/env python3
"""Scène Blender de Dubaï (Blur 2 porté) pour voir la collision et poser des « pansements ».

Deux temps, un seul fichier :
  python b2blender.py                       export (Python normal : UnityPy) -> blur_blender/dubai_data.npz + dubai_reperes.json
  blender -b --python b2blender.py          construit blur_blender/dubai.blend (dans Blender, numpy y est fourni)
                                            (refuse d'écraser un dubai.blend existant : tes pansements sont dedans)
Repère : celui des colliders Unity en axes du jeu (b2collision.colliders), SANS le décalage de hauteur propre à chaque
route (dy = 1 - y le plus bas du tour : Business Bay −0,82). Blender (X, Y, Z) = jeu (x, −z, y) : rotation pure,
le sens des faces est gardé -> overlay « Face Orientation » : bleu = face avant (côté qui bloque dans Blur), rouge = dos.
Sens montré = sens Unity (celui des données ; l'écriture actuelle le réenroule vers le haut, cf. CONNAISSANCES).
Collections :
  REFERENCE (non sélectionnable) : Routes_17f, Parois_roulables, Dessous_roulables, Murs_15d, Barrieres_route_N, Autres
     un objet par collider Unity (nom d'origine), pour retrouver l'objet en cause
  REPERES : Traces (courbe par route), Tours_roules, Grilles, Zones_gravite_<route>, Captures (un repère par capture)
  PANSEMENTS : MUR, ROUTE, PAROI, TRACE, ZONE (vides : à toi)
"""
import glob, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
IN_BLENDER = "bpy" in sys.modules
JEUX = os.path.dirname(HERE)
OUT = os.path.join(JEUX, "blur_blender")
NPZ, JSN, BLEND = (os.path.join(OUT, n) for n in ("dubai_data.npz", "dubai_reperes.json", "dubai.blend"))
ROUTES = {1: ("Business_Bay", "lap_route1_business_bay.csv", "dubai_route1_trace.json", "business_bay", (90, -174)),
          2: ("Dubai_Island", "lap_route2_dubai_island.csv", "dubai_route2_trace.json", "dubai_island", (-540, 482)),
          3: ("Construction", "lap_route3_construction.csv", "dubai_route3_trace.json", "construction", (429, -1014)),
          4: ("Marina", "lap_route4_marina.csv", "marina_trace.json", "marina", (-435, 473))}


# ---------------- export (Python normal) ----------------
def classify(name):
    import re
    m = re.match(r"physics_route_(\d+)", name)
    if m:
        return "Barrieres_route_" + m.group(1)
    suf = name.replace("_collision", "").rsplit("_", 1)[-1]
    return {"17f": "ROAD", "8017f": "ROAD", "15d": "Murs_15d"}.get(suf, "Autres")


def export():
    import csv
    import numpy as np
    sys.path.insert(0, HERE)
    import b2collision, config
    aid = os.path.join(config.JEUX, "blur2_aid", "dubai")
    arrays, objs = {}, []
    for name, (v, t) in sorted(b2collision.colliders(os.path.join(config.JEUX, "Blur2DubaiTest",
                                                                  "Blur2DubaiTest_Data")).items()):
        if not len(t):
            continue
        cls = classify(name)
        parts = [(cls, t)]
        if cls == "ROAD":                         # roulables : séparés par la normale (comme b2viewer)
            T = v[t]
            n = np.cross(T[:, 1] - T[:, 0], T[:, 2] - T[:, 0])
            ny = n[:, 1] / (np.linalg.norm(n, axis=1) + 1e-12)
            parts = [("Routes_17f", t[ny >= 0.5]), ("Parois_roulables", t[np.abs(ny) < 0.5]),
                     ("Dessous_roulables", t[ny <= -0.5])]
        for c, tt in parts:
            if not len(tt):
                continue
            used = np.unique(tt)
            remap = np.full(len(v), -1, np.int64)
            remap[used] = np.arange(len(used))
            k = len(objs)
            arrays["v%d" % k] = v[used].astype(np.float32)
            arrays["t%d" % k] = remap[tt].astype(np.int32)
            objs.append({"name": name.replace("_collision", ""), "collection": c, "triangles": int(len(tt))})
    rep = {"objects": objs, "routes": {}}
    for r, (nom, lap, trace, gdir, grid) in ROUTES.items():
        L = [(float(x["x"]), float(x["y"]), float(x["z"])) for x in csv.DictReader(open(os.path.join(aid, lap)))]
        low = min(p[1] for p in L)
        dy = 1.0 - low                            # make_b2_map : hauteur de jeu = hauteur Unity + dy
        tr = json.load(open(os.path.join(aid, trace), encoding="utf-8"))

        def line(pts):
            return [(p["x"], p["h"] + low, p["z"]) for p in pts if isinstance(p, dict)]
        zones = []
        gz = os.path.join(HERE, "natif", "b2gravity", gdir, "b2gravity.txt")
        for s in (open(gz, encoding="utf-8", errors="replace") if os.path.exists(gz) else []):
            p = s.split()
            if len(p) == 6 and not s.startswith("#"):
                try:
                    a = [float(x) for x in p]
                    zones.append([a[0], a[1] - dy, a[2], a[3], a[4] - dy, a[5]])   # zones en repère du jeu installé
                except ValueError:
                    pass
        caps = []
        for f in sorted(glob.glob(os.path.join(HERE, "captures", nom, "session_*", "capture_*.json"))):
            c = json.load(open(f, encoding="utf-8"))
            caps.append({"nom": "%s_%03d" % (c["session"].replace("session_", ""), c["numero"]),
                         "pos": [c["x"], c["y"] - dy, c["z"]], "avant": c["axes"]["avant"], "haut": c["axes"]["haut"],
                         "resultat": c["resultat"], "commentaire": c["commentaire"], "kmh": c["vitesse_kmh"],
                         "fichier": os.path.relpath(f, HERE)})
        g = min(line(tr["points"]), key=lambda p: (p[0] - grid[0]) ** 2 + (p[2] - grid[1]) ** 2)
        rep["routes"][nom] = {"dy": dy, "trace": line(tr["points"]),
                              "branches": [line(b.get("points", [])) for b in tr.get("branches") or []],
                              "tour": L[::4], "grille": [grid[0], g[1], grid[1]], "zones": zones, "captures": caps}
    os.makedirs(OUT, exist_ok=True)
    np.savez_compressed(NPZ, **arrays)
    json.dump(rep, open(JSN, "w", encoding="utf-8"), ensure_ascii=False)
    print("%d objets, %d triangles -> %s" % (len(objs), sum(o["triangles"] for o in objs), OUT))


# ---------------- scène (dans Blender) ----------------
def B(p):
    """jeu (x, y, z) -> Blender (x, -z, y)"""
    return (p[0], -p[2], p[1])


def build():
    import bpy
    import numpy as np
    if os.path.exists(BLEND):
        sys.exit("%s existe déjà : pas écrasé (tes pansements). Renomme-le pour en refaire un." % BLEND)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    data, rep = np.load(NPZ), json.load(open(JSN, encoding="utf-8"))

    def coll(name, parent=None):
        c = bpy.data.collections.new(name)
        (parent or sc.collection).children.link(c)
        return c

    def mat(name, rgba):
        m = bpy.data.materials.new(name)
        m.diffuse_color = rgba
        return m

    COL = {"Routes_17f": (0.45, 0.45, 0.45, 1), "Parois_roulables": (1.0, 0.55, 0.1, 1),
           "Dessous_roulables": (0.8, 0.2, 0.8, 1), "Murs_15d": (0.2, 0.5, 1.0, 1), "Autres": (0.4, 0.7, 0.4, 1)}
    ref, cols = coll("REFERENCE"), {}
    for k, o in enumerate(rep["objects"]):
        c = o["collection"]
        if c not in cols:
            cols[c] = (coll(c, ref), mat(c, COL.get(c, (0.9, 0.1, 0.1, 1))))
        v = data["v%d" % k].astype(float)
        bv = np.stack([v[:, 0], -v[:, 2], v[:, 1]], 1)
        t = data["t%d" % k]
        me = bpy.data.meshes.new(o["name"])
        me.vertices.add(len(bv))
        me.vertices.foreach_set("co", bv.ravel())
        me.loops.add(len(t) * 3)
        me.loops.foreach_set("vertex_index", t.ravel())
        me.polygons.add(len(t))
        me.polygons.foreach_set("loop_start", np.arange(0, len(t) * 3, 3))
        me.update()
        me.materials.append(cols[c][1])
        ob = bpy.data.objects.new("%s__%s" % (o["name"], c), me)
        ob["collider_unity"], ob["classe"] = o["name"], c
        cols[c][0].objects.link(ob)
    ref.hide_select = True

    rp = coll("REPERES")

    def curve(name, pts, parent, rgba, closed=False, r=0.6):
        cu = bpy.data.curves.new(name, "CURVE")
        cu.dimensions, cu.bevel_depth = "3D", r
        s = cu.splines.new("POLY")
        s.points.add(len(pts) - 1)
        s.use_cyclic_u = closed
        for i, p in enumerate(pts):
            s.points[i].co = (*B(p), 1)
        cu.materials.append(mat(name, rgba))
        ob = bpy.data.objects.new(name, cu)
        parent.objects.link(ob)
        return ob

    ctr, ctour, cgr, ccap = coll("Traces", rp), coll("Tours_roules", rp), coll("Grilles", rp), coll("Captures", rp)
    RES = {"bloquant": (0.1, 0.8, 0.1, 1), "traversable": (1, 0.1, 0.1, 1), "anormal": (1, 0.9, 0.1, 1)}
    for nom, r in rep["routes"].items():
        curve("Trace_" + nom, r["trace"], ctr, (0, 0.9, 1, 1), closed=True)
        for i, b in enumerate(r["branches"]):
            if len(b) > 1:
                curve("Trace_%s_embr%d" % (nom, i + 1), b, ctr, (0, 0.6, 0.7, 1))
        curve("Tour_" + nom, r["tour"], ctour, (1, 1, 1, 1), r=0.2)
        e = bpy.data.objects.new("Grille_" + nom, None)
        e.empty_display_type, e.empty_display_size = "ARROWS", 8
        e.location = B(r["grille"])
        cgr.objects.link(e)
        cz = coll("Zones_gravite_" + nom, rp)
        mz = mat("zone_" + nom, (0.6, 0.3, 1, 1))
        for i, z in enumerate(r["zones"]):
            a, b = B(z[:3]), B(z[3:])
            lo = [min(a[j], b[j]) for j in range(3)]
            hi = [max(a[j], b[j]) for j in range(3)]
            me = bpy.data.meshes.new("zone")
            vs = [(x, y, w) for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for w in (lo[2], hi[2])]
            me.from_pydata(vs, [], [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)])
            me.materials.append(mz)
            ob = bpy.data.objects.new("Zone_%s_%02d" % (nom, i + 1), me)
            ob.display_type = "WIRE"
            cz.objects.link(ob)
        cz.hide_viewport = True
        for c in r["captures"]:
            e = bpy.data.objects.new("Capture_%s_%s" % (nom, c["nom"]), None)
            e.empty_display_type, e.empty_display_size = "SPHERE", 2.5
            e.location = B(c["pos"])
            e.color = RES.get(c["resultat"], (1, 1, 1, 1))
            e.show_in_front = True
            for k in ("resultat", "commentaire", "kmh", "fichier"):
                e[k] = c[k]
            ccap.objects.link(e)

    pz = coll("PANSEMENTS")
    for n in ("MUR", "ROUTE", "PAROI", "TRACE", "ZONE"):
        coll(n, pz)
    sc.unit_settings.system = "METRIC"
    os.makedirs(OUT, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=BLEND)
    print("scène écrite :", BLEND)


def build_recale():
    """blender -b --python b2blender.py -- recale : blur_blender/traces_recalees.blend (régénérable, réécrit) avec,
    par route : tracé actuel (cyan), tracé recalé de b2recale (vert), tour roulé Unity (blanc), et un repère par point
    signalé (rouge sans_route, orange deplace, jaune zone_large ; propriétés : drapeaux, déplacement, largeur).
    Même repère que dubai.blend : Fichier > Ajouter (Append) > Collection pour le superposer à la collision."""
    import bpy
    import csv
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    aid = os.path.join(JEUX, "blur2_aid", "dubai")

    def curve(name, pts, coll, rgba, closed, r):
        cu = bpy.data.curves.new(name, "CURVE")
        cu.dimensions, cu.bevel_depth = "3D", r
        s = cu.splines.new("POLY")
        s.points.add(len(pts) - 1)
        s.use_cyclic_u = closed
        for i, p in enumerate(pts):
            s.points[i].co = (*B(p), 1)
        m = bpy.data.materials.new(name)
        m.diffuse_color = rgba
        cu.materials.append(m)
        coll.objects.link(bpy.data.objects.new(name, cu))

    COLORS = {"sans_route": (1, 0.1, 0.1, 1), "deplace": (1, 0.5, 0, 1), "zone_large": (1, 0.9, 0.1, 1)}
    for r, (nom, lap, trace, _, _) in ROUTES.items():
        rec = os.path.join(aid, trace.replace(".json", "_recale.json"))
        if not os.path.exists(rec):
            continue
        L = [(float(x["x"]), float(x["y"]), float(x["z"])) for x in csv.DictReader(open(os.path.join(aid, lap)))]
        low = min(p[1] for p in L)
        old, new = json.load(open(os.path.join(aid, trace), encoding="utf-8")), json.load(open(rec, encoding="utf-8"))
        c = bpy.data.collections.new("Recalage_" + nom)
        sc.collection.children.link(c)

        def line(pts):
            return [(p["x"], p["h"] + low, p["z"]) for p in pts]
        curve("Trace_actuelle_" + nom, line(old["points"]), c, (0, 0.9, 1, 1), True, 0.5)
        curve("Trace_recalee_" + nom, line(new["points"]), c, (0.1, 1, 0.2, 1), True, 0.8)
        curve("Tour_roule_" + nom, L[::2], c, (1, 1, 1, 1), True, 0.25)
        for bi, (ob, nb) in enumerate(zip(old.get("branches") or [], new.get("branches") or [])):
            curve("Embr%d_actuel_%s" % (bi + 1, nom), line(ob["points"]), c, (0, 0.6, 0.7, 1), False, 0.4)
            curve("Embr%d_recale_%s" % (bi + 1, nom), line(nb["points"]), c, (0.1, 0.7, 0.2, 1), False, 0.6)
        groups = [("", new["points"], new.get("controle", []))] + [
            ("embr%d_" % (bi + 1), b["points"], b.get("controle", [])) for bi, b in enumerate(new.get("branches") or [])]
        for pre, pts, ctrl in groups:
            for k in ctrl:
                f = [x for x in k["drapeaux"] if x in COLORS]
                if not f:
                    continue
                p = pts[k["i"]]
                e = bpy.data.objects.new("Point_%s%s_%03d_%s" % (pre, nom, k["i"], f[0]), None)
                e.empty_display_type, e.empty_display_size = "SPHERE", 2.0
                e.location = B((p["x"], p["h"] + low, p["z"]))
                e.color, e.show_in_front = COLORS[f[0]], True
                e["drapeaux"], e["deplacement_m"] = ", ".join(k["drapeaux"]), k["deplacement_m"]
                e["largeur_m"] = k["largeur_m"] or 0.0
                c.objects.link(e)
    out = os.path.join(OUT, "traces_recalees.blend")
    bpy.ops.wm.save_as_mainfile(filepath=out)
    print("écrit :", out)


if __name__ == "__main__":
    if IN_BLENDER:
        build_recale() if "recale" in sys.argv else build()
    else:
        export()
