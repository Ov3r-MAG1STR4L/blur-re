#!/usr/bin/env python3
"""Atlas : placer la grille de départ (20 places) et les bonus d'une route de Dubaï dans Blender, avec les vrais
modèles de Blur (bonus : models/perks/pickups/<type>pickup.model ; voitures : car01.model), lus par l'add-on
BlurImportExport (TimberStalker, fourni avec Map Builder).

  blender -b ../blur_blender/dubai.blend --python b2atlas.py -- ROUTE
      -> blur_blender/atlas_<Route>.blend (copie de dubai.blend + collections ATLAS ; jamais écrasé)
  Ouvrir atlas_<Route>.blend dans Blender, autoriser les scripts (Auto Run), panneau latéral (N) onglet « Atlas » :
      Ajouter un bonus (au curseur 3D ; Maj + clic droit pose le curseur sur une surface), Poser au sol (sélection),
      Exporter -> blur2_aid/dubai/atlas/route_N.json
  make_b2_map.py lit ce fichier s'il existe : grille (StartPosition) et bonus (PickupPosition) à ces places exactes.
  python b2atlas.py          auto-test hors Blender (dispositions de départ des 4 routes, modèles présents)

Repère : celui de dubai.blend (axes du jeu SANS le dy de la route) ; Blender (X, Y, Z) = jeu (x, −z, y).
Cap : rotation Z de l'objet ; l'avant est la flèche jaune (axe local −Y) ; jeu : avant = (sin cap, cos cap).
Départ : grilles.json (poscapture grille) ou la grille officielle, 2 colonnes à ±5 m, rangées de 8 m (Map Builder) ;
bonus : atlas existant, sinon les officiels (Blur2DubaiTest) à moins de 40 m du tracé.
"""
import json, math, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
JEUX = os.path.dirname(HERE)
DUBAI = os.path.join(JEUX, "blur2_aid", "dubai")
ATLAS_DIR = os.path.join(DUBAI, "atlas")
PICKUPS = os.path.join(JEUX, "blur_extracted", "root", "models", "perks", "pickups")
CAR = os.path.join(JEUX, "blur_extracted", "root", "models", "objects", "jpn_shutoko", "vehicles", "car01.model")
ADDON = os.path.join(JEUX, "bmb_game", "Blur Map Builder", "base", "addon")
ROUTES = {1: ("Business_Bay", "dubai_route1_trace_v2.json", (90.18, -173.98)),
          2: ("Dubai_Island", "dubai_route2_trace_v2.json", (-540.31, 481.57)),
          3: ("Construction", "dubai_route3_trace_v2.json", (428.82, -1013.98)),
          4: ("Marina", "marina_trace_v2.json", (-435.33, 473.32))}
# types de b2pickups (noms Blur 1) -> modèle ; Bolt : aucun modèle de bonus dans le jeu, xppickup en attendant
MODELS = {"Shunt": "shuntpickup", "Barge": "bargepickup", "Shock": "shockpickup", "Mine": "minepickup",
          "Bolt": "xppickup", "Nitro": "nitropickup", "Shield": "shieldpickup", "Repair": "repairpickup",
          "Railgun": "shieldsuperpickup"}
BLUR2 = {"Blindfire": "Bolt", "Bomb": "Mine", "Nitrous": "Nitro", "Icewall": "Railgun", "Javelin": "Railgun"}
SLOTS = 20


def atlas_path(route):
    return os.path.join(ATLAS_DIR, "route_%d.json" % route)


def trace_xz(route):
    t = json.load(open(os.path.join(DUBAI, ROUTES[route][1]), encoding="utf-8"))
    return [(q["x"], q["z"]) for q in t["points"]]


def heading_at(P, x, z):
    """cap du tracé (avant = (sin a, cos a)) au point le plus proche de (x, z)"""
    i = min(range(len(P)), key=lambda k: (P[k][0] - x) ** 2 + (P[k][1] - z) ** 2)
    a, b = P[i], P[(i + 1) % len(P)]
    return math.atan2(b[0] - a[0], b[1] - a[1])


def default_layout(route):
    """{"grille": [...], "bonus": [...]} de départ, axes du jeu sans dy (y = None : à poser au sol)"""
    P = trace_xz(route)
    gf = os.path.join(DUBAI, "grilles.json")
    g = json.load(open(gf, encoding="utf-8")).get(str(route)) if os.path.exists(gf) else None
    gx, gz = (g["x"], g["z"]) if g else ROUTES[route][2]
    cum = [0.0]                                        # rangées le long du tracé (la route tourne derrière la ligne)
    for p, q in zip(P, P[1:] + P[:1]):
        cum.append(cum[-1] + math.hypot(q[0] - p[0], q[1] - p[1]))
    i0 = min(range(len(P)), key=lambda k: (P[k][0] - gx) ** 2 + (P[k][1] - gz) ** 2)
    s0 = cum[i0] + ((gx - P[i0][0]) * (P[(i0 + 1) % len(P)][0] - P[i0][0]) + (gz - P[i0][1]) *
                    (P[(i0 + 1) % len(P)][1] - P[i0][1])) / max(cum[i0 + 1] - cum[i0], 1e-6)
    side0 = None
    grid = []
    for k in range(SLOTS):
        s = (s0 - 8.0 * (k // 2) - (4.0 if k % 2 else 0.0)) % cum[-1]
        j = max(i for i in range(len(P)) if cum[i] <= s)
        p, q = P[j], P[(j + 1) % len(P)]
        f = (s - cum[j]) / max(cum[j + 1] - cum[j], 1e-6)
        cx, cz = p[0] + f * (q[0] - p[0]), p[1] + f * (q[1] - p[1])
        a = math.atan2(q[0] - p[0], q[1] - p[1])
        ux, uz = math.sin(a), math.cos(a)
        if side0 is None:                              # place 1 : écart réel de la case officielle au tracé
            side0 = (gx - cx) * uz - (gz - cz) * ux
        lat = side0 if k % 2 == 0 else (-side0 if abs(side0) >= 3.0 else side0 + 10.0)   # 2e colonne : en miroir
        grid.append({"x": cx + uz * lat, "y": None, "z": cz - ux * lat, "cap": a})
    off = json.load(open(os.path.join(DUBAI, "dubai_pickups_officiels.json"), encoding="utf-8"))["pickups"]
    bonus = []
    for pk in off:
        x, y, z = -pk["position"][0], pk["position"][1], -pk["position"][2]
        if min((p[0] - x) ** 2 + (p[1] - z) ** 2 for p in P) > 40.0 ** 2:
            continue
        bonus.append({"x": x, "y": y, "z": z, "cap": heading_at(P, x, z),
                      "type": BLUR2.get(pk["pickupType"], pk["pickupType"])})
    return {"route": route, "repere": "jeu sans dy", "grille": grid, "bonus": bonus}


def check_layout(d):
    """validation d'un atlas exporté (aussi utilisée par make_b2_map)"""
    assert len(d["grille"]) == SLOTS, "il faut %d places de grille (%d)" % (SLOTS, len(d["grille"]))
    for b in d["bonus"]:
        assert b["type"] in MODELS, "type de bonus inconnu : %s" % b["type"]
    return d


def apply(actorpack, d, low):
    """écrit l'atlas dans l'actorpack construit : 20 StartPosition (listes solo + multi) et les bonus (b2pickups) ;
    hauteur du jeu installé = y + 1 - low (comme make_b2_map), voitures 1 m au-dessus du sol (Map Builder)"""
    import struct
    import b2pickups                                   # chemins de Map Builder (flat_earth, kslf) posés à l'import
    import dump, gen_actorpack, kslf_write
    check_layout(d)
    dy = 1.0 - low
    sp = [(b["x"], b["y"] + dy, b["z"], b["cap"],
           b2pickups.RAILGUN if b["type"] == "Railgun" else b2pickups.TYPES[b["type"]]) for b in d["bonus"]]
    b2pickups.apply(actorpack, sp)

    def grid(ctx):
        k = 0
        for name, at in gen_actorpack.each_actor(ctx):
            if name != "StartPosition":
                continue
            p = d["grille"][min(k, SLOTS - 1)]
            ux, uz = math.sin(p["cap"]), math.cos(p["cap"])
            struct.pack_into("<12f", ctx.data, at, uz, 0.0, -ux, 0.0, 1.0, 0.0, ux, 0.0, uz,
                             p["x"], p["y"] + dy + gen_actorpack.CAR_ABOVE_GROUND, p["z"])
            k += 1
    for lst in gen_actorpack.GRID_LISTS:
        oi = {u: o for u, t, o in dump.File(actorpack).refs if o != 0xFFFF}[int(lst, 16)]
        tmp = actorpack + ".tmp"
        kslf_write.edit_object(actorpack, tmp, oi, grid)
        os.replace(tmp, actorpack)
    print("atlas : 20 places de grille, %d bonus" % len(sp))


# ---------------------------------------------------------------- Blender
PANEL = r'''
import bpy, json, math, os
ATLAS_JSON = %(json)r
ROUTE = %(route)d
TYPES = %(types)r


def _col(n):
    return bpy.data.collections[n]


def _game(o):
    x, y, z = o.matrix_world.translation
    return {"x": round(x, 3), "y": round(z, 3), "z": round(-y, 3), "cap": round(o.matrix_world.to_euler().z, 4)}


class ATLAS_OT_add(bpy.types.Operator):
    bl_idname = "atlas.add_bonus"
    bl_label = "Ajouter"
    kind: bpy.props.StringProperty()

    def execute(self, ctx):
        o = bpy.data.objects.new("Bonus_" + self.kind, None)
        o.instance_type, o.instance_collection = "COLLECTION", _col("Modele_" + self.kind)
        o["type"] = self.kind
        o.location = ctx.scene.cursor.location
        _col("ATLAS_Bonus").objects.link(o)
        for s in ctx.selected_objects:
            s.select_set(False)
        o.select_set(True)
        ctx.view_layer.objects.active = o
        return {"FINISHED"}


class ATLAS_OT_ground(bpy.types.Operator):
    bl_idname = "atlas.ground"
    bl_label = "Poser au sol (sélection)"

    def execute(self, ctx):
        dg = ctx.evaluated_depsgraph_get()
        n = 0
        for o in ctx.selected_objects:
            x, y, z = o.location
            start = (x, y, z + 30.0)
            for _ in range(20):             # passe à travers les modèles de l'Atlas
                hit, loc, nor, i, ob, m = ctx.scene.ray_cast(dg, start, (0, 0, -1))
                if not hit:
                    break
                cols = [c.name for c in ob.users_collection]
                if any(c.startswith(("Modele_", "ATLAS")) for c in cols):
                    start = (x, y, loc.z - 0.01)
                    continue
                o.location.z = loc.z
                n += 1
                break
        self.report({"INFO"}, "%%d objet(s) posé(s) au sol" %% n)
        return {"FINISHED"}


class ATLAS_OT_export(bpy.types.Operator):
    bl_idname = "atlas.export"
    bl_label = "Exporter pour la construction"

    def execute(self, ctx):
        places = sorted((o for o in _col("ATLAS_Grille").objects if o.name.startswith("Place_")), key=lambda o: o.name[:8])
        if len(places) != 20:
            self.report({"ERROR"}, "il faut 20 places (Place_01..Place_20), il y en a %%d" %% len(places))
            return {"CANCELLED"}
        bonus = [dict(_game(o), type=o["type"]) for o in _col("ATLAS_Bonus").objects if "type" in o]
        d = {"route": ROUTE, "repere": "jeu sans dy", "grille": [_game(o) for o in places], "bonus": bonus}
        os.makedirs(os.path.dirname(ATLAS_JSON), exist_ok=True)
        if os.path.exists(ATLAS_JSON):
            os.replace(ATLAS_JSON, ATLAS_JSON + ".precedent")
        json.dump(d, open(ATLAS_JSON, "w", encoding="utf-8"), indent=1)
        self.report({"INFO"}, "exporté : 20 places, %%d bonus -> %%s" %% (len(bonus), ATLAS_JSON))
        return {"FINISHED"}


class ATLAS_PT_panel(bpy.types.Panel):
    bl_label = "Atlas Blur (route %%d)" %% ROUTE
    bl_space_type, bl_region_type, bl_category = "VIEW_3D", "UI", "Atlas"

    def draw(self, ctx):
        L = self.layout
        L.label(text="Bonus au curseur 3D (Maj + clic droit) :")
        g = L.grid_flow(columns=3, align=True)
        for t in TYPES:
            g.operator("atlas.add_bonus", text=t).kind = t
        L.operator("atlas.ground")
        L.separator()
        L.label(text="Places : Place_01..20, flèche jaune = avant")
        L.operator("atlas.export", icon="EXPORT")


for c in (ATLAS_OT_add, ATLAS_OT_ground, ATLAS_OT_export, ATLAS_PT_panel):
    try:
        bpy.utils.unregister_class(c)
    except Exception:
        pass
    bpy.utils.register_class(c)
'''


def _import_model(bpy, path, name, parent):
    """importe un .model dans une collection « Modele_<name> » (exclue de la vue : seules ses instances se voient)"""
    if ADDON not in sys.path:
        sys.path.insert(0, ADDON)
    import BlurImportExport as B
    col = bpy.data.collections.new("Modele_" + name)
    parent.children.link(col)
    lc = bpy.context.view_layer.layer_collection.children["ATLAS"].children[parent.name].children[col.name]
    bpy.context.view_layer.active_layer_collection = lc
    before = set(bpy.data.objects)
    B.create_model_from_data(B.read_cpmodel_data(None, path), False)
    new = [o for o in bpy.data.objects if o not in before]
    for o in new:
        if o.parent is not None:
            o.matrix_parent_inverse = o.parent.matrix_world.inverted()
    lc.exclude = True
    return col, new


def build(route):
    import bpy
    name = ROUTES[route][0]
    out = os.path.join(JEUX, "blur_blender", "atlas_%s.blend" % name)
    if os.path.exists(out):
        sys.exit("%s existe déjà (ton travail est dedans) : le supprimer ou le renommer pour repartir de zéro" % out)
    bpy.ops.wm.save_as_mainfile(filepath=out)            # avant l'import : les textures vont dans blur_blender/textures
    root = bpy.data.collections.new("ATLAS")
    bpy.context.scene.collection.children.link(root)
    mods = bpy.data.collections.new("ATLAS_Modeles")
    root.children.link(mods)
    for t, f in MODELS.items():
        _import_model(bpy, os.path.join(PICKUPS, f + ".model"), t, mods)
    _, car = _import_model(bpy, CAR, "Voiture", mods)
    arrow = bpy.data.meshes.new("Fleche")                 # flèche jaune à plat, pointe vers −Y (l'avant)
    arrow.from_pydata([(-0.8, 1.5, 0.3), (0.8, 1.5, 0.3), (0.8, -1.0, 0.3), (-0.8, -1.0, 0.3),
                       (-1.8, -1.0, 0.3), (0, -3.5, 0.3), (1.8, -1.0, 0.3)], [], [(0, 1, 2, 3), (4, 5, 6)])
    mat = bpy.data.materials.new("Fleche_jaune")
    mat.diffuse_color = (1.0, 0.85, 0.0, 1.0)
    arrow.materials.append(mat)
    ao = bpy.data.objects.new("Fleche", arrow)
    bpy.data.collections["Modele_Voiture"].objects.link(ao)
    d = json.load(open(atlas_path(route), encoding="utf-8")) if os.path.exists(atlas_path(route)) else default_layout(route)
    grid_c, bonus_c = (bpy.data.collections.new(n) for n in ("ATLAS_Grille", "ATLAS_Bonus"))
    root.children.link(grid_c)
    root.children.link(bonus_c)

    def place(n, inst, col, p):
        o = bpy.data.objects.new(n, None)
        o.instance_type, o.instance_collection = "COLLECTION", bpy.data.collections[inst]
        o.location = (p["x"], -p["z"], p["y"] if p["y"] is not None else 200.0)
        o.rotation_euler = (0, 0, p["cap"])
        col.objects.link(o)
        return o

    for k, p in enumerate(d["grille"]):
        place("Place_%02d" % (k + 1), "Modele_Voiture", grid_c, p)
    for p in d["bonus"]:
        place("Bonus_" + p["type"], "Modele_" + p["type"], bonus_c, p)["type"] = p["type"]
    txt = bpy.data.texts.new("atlas_panel.py")
    txt.write(PANEL % {"json": atlas_path(route), "route": route, "types": list(MODELS)})
    txt.use_module = True                                  # s'enregistre à l'ouverture (scripts autorisés)
    exec(compile(txt.as_string(), "atlas_panel.py", "exec"), {"__name__": "atlas_panel"})
    unset = [o for o in grid_c.objects if o.location.z == 200.0]
    if unset:                                              # places sans hauteur : posées au sol tout de suite
        for o in bpy.context.view_layer.objects:
            o.select_set(o in unset)
        bpy.ops.atlas.ground()
        ok = [o.location.z for o in grid_c.objects if o.location.z != 200.0]
        for o in grid_c.objects:                           # rien dessous (route trop courte) : à la hauteur des
            if o.location.z == 200.0 and ok:               # autres, à déplacer à la main ; signalées par leur nom
                o.location.z = ok[-1]
                o.name += "_HORS_ROUTE"
    bpy.ops.wm.save_mainfile()
    print("Atlas route %d : %d places, %d bonus, %d objets voiture -> %s" % (route, len(d["grille"]), len(d["bonus"]),
                                                                          len(car), out))


def selftest():
    for r in ROUTES:
        d = default_layout(r)
        assert len(d["grille"]) == SLOTS and all(b["type"] in MODELS for b in d["bonus"]), r
        p0, p1 = d["grille"][0], d["grille"][2]                       # rangée suivante : 8 m derrière
        assert 6.0 < math.hypot(p0["x"] - p1["x"], p0["z"] - p1["z"]) < 8.5      # 8 m le long du tracé (corde)
        check_layout(d)
        print("route %d : 20 places, %d bonus officiels" % (r, len(d["bonus"])))
    for f in MODELS.values():
        assert os.path.exists(os.path.join(PICKUPS, f + ".model")), f
    assert os.path.exists(CAR) and os.path.isdir(os.path.join(ADDON, "BlurImportExport"))
    print("auto-test OK")


if __name__ == "__main__":
    if "bpy" in sys.modules:
        build(int(sys.argv[sys.argv.index("--") + 1]))
    else:
        selftest()
