#!/usr/bin/env python3
"""Build the reversed-routes mod (projet C) from the extracted game data, off-game, every route in ONE pass
(amax.bin, multiplayer.bin, a city's actorpack and ui_frontend.bpr are shared by all routes).

Per route (ROUTES below):
  gamedata/levels/<city>/<new>.aid        reversed AI / logic route, gates moved back onto the painted lines
  gamedata/levels/<city>/actorpack.xt     + clones of the route's start lists (grid + start/finish texts)
  gamedata/xt/amax.bin                    + Route <new> (copy of the original, pointing to the clones)
  gamedata/xt/multiplayer.bin             + <new> in MultiplayerConfig.routes (custom race menu)
  ui/data/ui_frontend.bpr                 picture <new> (original + U-turn sign) in a spare duplicate slot
Also (multiplayer.bin): max_ai_per_console 4 -> 19, so a player alone gets the menu's 18 AI, not 4;
and AMAX plugins from mod_static/ (ai19: Max AI menu up to 19), enabled in the copy's plugins.lua.
The game folder rules (pak before loose files, header of .bpr...) are in docs/CONNAISSANCES.md.
usage: make_reverse.py OUT_DIR
"""
import collections, json, os, struct, sys
import aidreverse, blurbpr, blurroute, gridreverse, thumbreverse
from blurxt import XT
from kslfwrite import KSLF

MAX_AI_PER_CONSOLE = 19        # multiplayer.bin MultiplayerConfig, original 4; 19 = 20 cars (49 tested: clamped to 20)
# AI experiments on a difficulty file: {file: {row of a stage: value for every AI}}. Stage rows: 0 i32, 1 distances
# (+4), 2 factors 1 / 0.84..0.87 (+8, corrected by difficulty), 3 0.55 (+0xC), 4 i32 flags, 5 i32, 6 AIPerkSkillz
# Index, 7 AIPerkPrefs Index. Experiment 1 ({6: 70}, Tier 10 Skills): same race times as the original.
# Experiment 2: factors 1.2 -> median AI 13 s faster (the row is the speed cap). Experiment 3: 1.5. {} = original.
# "no handicap" Hard (2026-10-20): no speed cap + Shannon profile for all. Rival pack test (2026-10-20): every AI in the
# rival group (row 4 = 1) with a target gap around the player (row 1, m, -18..+18), instead of 4 rivals + 15 fillers.
AI_ROWS = {"multiplayer_hard.csv": {1: [2 * i - 18 for i in range(19)], 2: 2.0, 3: 1.0, 4: 1, 6: 900}}   # factor 2.0 = 1.2 (measured); row 3 (0.55, unknown) test
# DoubleTap experiment (2026-10-19): the combine-two-pickups trigger is orphaned code; instead every pickup with a
# DoubleTap level (Nitro rift, Shield 12 s, Mine, Shunt, Shock) uses it as its Normal level. Test 1 (all five): the
# AI use them fine, but the game crashes as soon as the PLAYER fires a pickup -> one pickup at a time.
# Pickup Type names: "Bomb", "Shunt", "Shock", "Shield", "Nitrous". Empty = original.
PICKUPS_DOUBLETAP = set()   # set aside 2026-10-19. Player results: Shield OK (12 s); Bomb OK (3 s); Shock OK (no visible change); Nitrous no effect; Shunt CRASH
AI_FRICTION = None            # AI grip test (2026-10-20): AI.Air_Default FrictionCoefficient, original 1.212; None = original
# AI steering test (2026-10-20): the AI weave slightly (PID P ~32, D ~3.7). Every AISteering profile gets these values.
AI_STEERING = {"SteeringParams.PID.D": 7.0, "SteeringParams.ForwardsDist": 20.0}   # {} = original
# Career AI grip test (2026-10-20): AmaxEvent OverrideAISurface on every career event; the value scales the AI target
# speed (clamped 0.8..1.5 by the game, AI only). None = original. Custom races have no such field.
CAREER_AI_SURFACE = None   # 1.5 tested 2026-10-20: applied, post-nitro braking unchanged
EVIL_SHANNON = True            # custom races: Shannon with the evil avatar + ultimate profile (see step 9)
GAME = r"C:\Program Files (x86)\Activision\Blur(TM)"   # read only (installed plugins.lua)
E = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "blur_extracted")
G = os.path.join(E, "gamedata", "gamedata")


def loc_hash(key, file="cityandroutenames.loc"):
    """Hash of a text key (a Route's LocString is that hash)."""
    b = open(os.path.join(G, "xt", "loc", file), "rb").read()
    kb = 0x1C + 24 * struct.unpack_from("<I", b, 0x14)[0]
    for i in range(struct.unpack_from("<I", b, kb)[0]):
        h, o = struct.unpack_from("<II", b, kb + 8 + 8 * i)
        if b[kb + o:b.index(b"\0", kb + o)].decode() == key:
            return h
    raise KeyError(key)


# new: Route name (the .aid is found by name); RouteNumber is kept (it picks the levelphysics road collision).
# hashes: above every existing hash (max 0xFFFE3216); Haruna keeps the ones it was tested with.
ROUTES = [
    dict(orig="JPN_MHaruna_1", new="JPN_MHaruna_7", index=3, hash=0xFFFF0001,
         loc=226956641,                          # CRN_MOUNT_HARUNA_2 "Ascent" / "Montée", unused dev string
         grid=gridreverse.HARUNA,
         gates={"start": -15.9, "finish": 4.0}),  # m from the painted line to the gate's first node (original)
    dict(orig="UK_Brighton_1", new="UK_Brighton_1R", index=None, hash=0xFFFF0010,
         loc="CRN_ROUTE_1_REVERSE",              # "Route 1 Reverse" / "Route 1 Miroir", unused dev string
         grid=dict(loop=True), gates=None),       # loop: line and gate relation read from the original
    dict(orig="USA_SanFran_RussianHill_1", new="USA_SanFran_RussianHill_R", index=None, hash=0xFFFF0020,
         loc="CRN_ROUTE_1_REVERSE",              # "Route 1 Reverse" (shared with Brighton); name <= 25: picture slot
         grid=dict(loop=True), gates=None,
         drop=("Carpark", "JunctionCarpark")),   # car-park shortcut: AI no longer use it (2026-10-21)
]


def load_aid(path, drop=()):
    """Parsed .aid (raw) without the blocks named in `drop` (a shortcut and its junction: aidreverse refuses junctions;
    the AI then ignore the shortcut, the player can still take it) nor their logic-table references."""
    d = blurroute.parse(open(path, "rb").read(), raw=True)
    d["blocks"] = [b for b in d["blocks"] if b["name"] not in drop]
    d["logic_table"] = [[ref for ref in refs if ref[1] not in drop] for refs in d["logic_table"]]
    return d


def build_aid(r, orig_aid, out_aid, start_xz):
    """Reverse, then slide the start (and finish) gates so each first node keeps the original distance to its line."""
    d = aidreverse.reverse(load_aid(orig_aid, r.get("drop", ())))
    roles = aidreverse.roles(d)
    mc = aidreverse._centres(roles["main"]["nodes"])
    loop = bool(roles["main"]["type"] & 1)
    arc = [0.0]
    for (x0, z0), (x1, z1) in zip(mc, mc[1:]):
        arc.append(arc[-1] + ((x1 - x0) ** 2 + (z1 - z0) ** 2) ** 0.5)

    def idx(xz):                                  # file frame: z negated
        return min(range(len(mc)), key=lambda k: (mc[k][0] - xz[0]) ** 2 + (mc[k][1] + xz[1]) ** 2)

    def at(target):
        if loop:
            target %= arc[-1]
        return min(range(len(arc)), key=lambda k: abs(arc[k] - target))

    if r["gates"]:                                 # point-to-point: measured offsets, painted lines in cfg
        lines = r["grid"]["lines"]
        moves = [("start", lines["start"], r["gates"]["start"]), ("finish", lines["finish"], r["gates"]["finish"])]
    else:                                          # loop: same offset as the original, the other way
        o = load_aid(orig_aid, r.get("drop", ()))
        oroles = aidreverse.roles(o)
        omc = aidreverse._centres(oroles["main"]["nodes"])
        oarc = [0.0]
        for (x0, z0), (x1, z1) in zip(omc, omc[1:]):
            oarc.append(oarc[-1] + ((x1 - x0) ** 2 + (z1 - z0) ** 2) ** 0.5)
        oi = lambda xz: min(range(len(omc)), key=lambda k: (omc[k][0] - xz[0]) ** 2 + (omc[k][1] + xz[1]) ** 2)
        g0 = aidreverse._centres(oroles["start"]["nodes"][:1])[0]
        ahead = oarc[oi(start_xz)] - oarc[oi((g0[0], -g0[1]))]       # gate starts `ahead` m before the line
        moves = [("start", start_xz, -ahead)]
    for role, xz, after in moves:
        print(f"  {role} gate moved by", aidreverse.move_gate(d, roles[role]["name"], at(arc[idx(xz)] + after)),
              "nodes")
    open(out_aid, "wb").write(blurroute.build(d))


def renew_uids(ap, names):
    """Clones keep the original SerialisableUids; the game then used the ORIGINAL grid (tested 2026-10-19)."""
    x = XT(ap)
    used, paths = set(), []

    def walk(v, path, out):
        if isinstance(v, dict):
            for k, w in v.items():
                walk(w, f"{path}.{k}" if path else k, out)
        elif isinstance(v, list):
            for i, w in enumerate(v):
                walk(w, f"{path}[{i}]", out)
        elif path.endswith("SerialisableUid"):
            out.append((path, v))

    for n, _, v, _ in x.records():
        found = []
        walk(v, "", found)
        used.update(u for _, u in found)
        if n in names:
            paths += [(n, p) for p, _ in found]
    b, uid = bytearray(open(ap, "rb").read()), 0xB1E00000
    for n, p in paths:
        while uid in used:
            uid += 1
        used.add(uid)
        struct.pack_into("<I", b, x.locate(n, p)[0], uid)
    open(ap, "wb").write(b)
    return len(paths)


def main(out):
    routes_json = json.load(open(os.path.join(E, "xt_json", "amax.json")))["Route"]
    xt = os.path.join(out, "gamedata", "xt")
    os.makedirs(xt, exist_ok=True)
    by_city = collections.defaultdict(list)
    for r in ROUTES:
        src = routes_json[r["orig"]]
        r["city"] = src["City"].split("/")[-1].lower()
        r["src"] = src
        by_city[r["city"]].append(r)

    # 1. per city: .aid of each route, then one actorpack with every route's cloned start lists
    for city, rs in by_city.items():
        lvl = os.path.join(out, "gamedata", "levels", city)
        os.makedirs(lvl, exist_ok=True)
        pack = os.path.join(G, "levels", city, "actorpack.xt")
        pack_json = os.path.join(E, "xt_json", f"{city}.actorpack.json")
        A = json.load(open(pack_json, encoding="utf-8"))["LevelActorList"]
        k = KSLF(pack)
        for r in rs:
            # start lists = lists of this pack, used by the route, holding a grid or start/finish texts
            r["clones"] = []
            for field in ("ActorLists", "MultiplayerActorLists"):
                for i, ref in enumerate(r["src"][field]):
                    pk, _, lst = ref.split("/")
                    acts = [a for a in A.get(lst, {}).get("LevelActors", []) if a]
                    if pk == f"{city}.actorpack" and any(gridreverse.is_start_position(a) or
                                                         a.get("Name", "").startswith("Start_Text") for a in acts):
                        r["clones"].append((field, i, lst))
            if not r["grid"].get("lines"):         # loop: the painted line = the original Start text
                xz = next(filter(None, (gridreverse.start_line(A[l]["LevelActors"]) for _, _, l in r["clones"])))
                r["grid"] = dict(r["grid"], lines={"orig_start": xz, "start": xz, "finish": xz})
            print(r["new"], "start lists", [l for _, _, l in r["clones"]])
            orig_aid = os.path.join(G, "levels", city, r["orig"].lower() + ".aid")
            r["aid"] = os.path.join(lvl, r["new"].lower() + ".aid")
            build_aid(r, orig_aid, r["aid"], r["grid"]["lines"]["start"])
            r["clone_names"], r["list_hash"] = {}, {}
            for n, lst in enumerate(dict.fromkeys(l for _, _, l in r["clones"])):   # a list used solo + multi: once
                h = r["hash"] + 1 + n
                k.clone(lst, None, h)
                r["clone_names"][lst] = f"#{len(k.index) - 1}"   # nameless records are named after their slot
                r["list_hash"][lst] = h
        ap = os.path.join(lvl, "actorpack.xt")
        open(ap, "wb").write(k.build())
        for r in rs:
            orig_aid = os.path.join(G, "levels", city, r["orig"].lower() + ".aid")
            lists = sorted({l for _, _, l in r["clones"]})
            moves = gridreverse.compute(orig_aid, r["aid"], pack_json, lists, r["grid"])
            for lst, mv in moves.items():
                for i, _, m in mv:
                    for row in ("ax", "ay", "az", "aw"):
                        for c, v in zip(("vx", "vy", "vz"), m[row]):
                            b = XT(ap).patched(r["clone_names"][lst], f"LevelActors[{i}].WorldMatrix.{row}.{c}", float(v))
                            open(ap, "wb").write(b)
        print(city, renew_uids(ap, {n for r in rs for n in r["clone_names"].values()}), "cloned actor uids renewed")

    # 2. amax.bin: each new Route = copy of the original pointing to its clones
    p = os.path.join(xt, "amax.bin")
    a = KSLF(os.path.join(G, "xt", "amax.bin"))
    for r in ROUTES:
        a.clone(r["orig"], r["new"], r["hash"])
        r["ext"] = {lst: a.add_external(h, "LevelActorList") for lst, h in r["list_hash"].items()}
    open(p, "wb").write(a.build())
    a = KSLF(p)
    for r in ROUTES:
        for field, i, lst in r["clones"]:
            a.set_array_ref(r["new"], field, i, r["ext"][lst])
    open(p, "wb").write(a.build())
    for r in ROUTES:
        loc = r["loc"] if isinstance(r["loc"], int) else loc_hash(r["loc"])
        index = r["index"] if r["index"] is not None else r["src"]["Index"] + 1
        for field, v in (("RouteNumber", r["src"]["RouteNumber"]), ("Index", index), ("LocString", loc)):
            b = XT(p).patched(r["new"], field, v)     # read before opening for writing
            open(p, "wb").write(b)

    # 3. pictures: found by Route Name; only a spare duplicate slot may change (the header gives the data start)
    bpr = blurbpr.Bpr(os.path.join(E, "root", "ui", "data", "ui_frontend.bpr"))
    taken = set()
    for r in ROUTES:
        (_, _, _, _, _, _, fmt, mips, w, h), _ = bpr.raw(r["orig"])
        slot = bpr.spare_slot(fmt, mips, w, h, min_name=len(r["new"]), skip=taken)
        taken.add(slot)
        bpr = blurbpr.Bpr(data=bpr.reuse(slot, r["new"], blurbpr.encode(thumbreverse.make(bpr.image(r["orig"])),
                                                                          fmt, mips)))
        print(r["new"], "picture in slot", slot)
    ui = os.path.join(out, "ui", "data")
    os.makedirs(ui, exist_ok=True)
    open(os.path.join(ui, "ui_frontend.bpr"), "wb").write(bpr.b)

    # 4. custom race menu
    m = KSLF(os.path.join(G, "xt", "multiplayer.bin"))
    for r in ROUTES:
        m.append_to_array("#735", "routes", m.add_external(r["hash"], "Route"))
    mp = os.path.join(xt, "multiplayer.bin")
    open(mp, "wb").write(m.build())
    # 5. AI in custom races: the game allows max_ai_per_console AI per player in the lobby (4: alone = 4 AI);
    # the menu's "Max AI" goes up to 18 (20 cars - 2 players assumed). 19: alone, up to the menu's 18 AI.
    b = XT(mp).patched("#735", "max_ai_per_console", MAX_AI_PER_CONSOLE)
    open(mp, "wb").write(b)
    # 6. AI experiments: one stage row of a difficulty file set to one value for every AI, at every stage
    for name, changes in AI_ROWS.items():
        src = os.path.join(G, "events", name)
        rows = [l.rstrip("\r\n").split(",") for l in open(src, encoding="latin-1", newline="")]
        n_stages = int(float(rows[1][0]))
        for k in range(n_stages):                    # header 4 rows, then 9 rows per stage (8 + a blank one)
            for row, value in changes.items():
                r = rows[4 + 9 * k + row]
                vals = value if isinstance(value, list) else [value] * (len(r) - 1)   # one value or one per AI
                rows[4 + 9 * k + row] = [r[0]] + [f"{v:g}" for v in vals]           # column 0 = the player
        ev = os.path.join(out, "gamedata", "events")
        os.makedirs(ev, exist_ok=True)
        open(os.path.join(ev, name), "w", encoding="latin-1", newline="").write("".join(",".join(r) + "\r\n" for r in rows))

    # 7. DoubleTap experiment: every PickupType that has a DoubleTap level uses it as its Normal level
    if PICKUPS_DOUBLETAP:
        pk = os.path.join(G, "xt", "pickups.bin")
        x = XT(pk)
        b = bytearray(x.b)
        done = []
        for name, typ, v, _ in x.records():
            if typ == "PickupType" and v.get("DoubleTap") and v["Type"] in PICKUPS_DOUBLETAP:
                n_at, d_at = x.locate(name, "Normal")[0], x.locate(name, "DoubleTap")[0]
                b[n_at:n_at + 4] = b[d_at:d_at + 4]           # reference = index slot of the PickupLevel
                done.append(v["Type"])
        open(os.path.join(xt, "pickups.bin"), "wb").write(b)
        print("DoubleTap as Normal:", done)

    # 9. "Evil Shannon": Shannon and ShannonEvil are the same driver (same model, AI template, cars, displayed name);
    # only the avatar differs (16 / 22). Custom races list Shannon: give her the evil avatar, and make her profile
    # (AIPerkSkillz T9 Shannon, Index 900, the only one at 1.0 for every pickup) "ultimate": Racing, Aggression,
    # Blocking, Slamming 1.0 and Mistakes 0 (every profile of the game has 0.5 / 0.5 / 0 / 0 / 0). In custom races
    # the profile is per grid slot, not per driver: the no-handicap Hard (AI_ROWS) gives it to every AI.
    if EVIL_SHANNON:
        p_air = os.path.join(xt, "air.bin")
        open(p_air, "wb").write(open(os.path.join(G, "xt", "air.bin"), "rb").read())
        for field, v in (("Racing", 1.0), ("Aggression", 1.0), ("Blocking", 1.0), ("Slamming", 1.0), ("Mistakes", 0.0)):
            b = XT(p_air).patched("T9 Shannon", field, v)
            open(p_air, "wb").write(b)
        p_rb = os.path.join(xt, "finalracebook.bin")
        open(p_rb, "wb").write(XT(os.path.join(G, "xt", "finalracebook.bin")).patched("Shannon", "AvatarID", 22))
        print("Evil Shannon: avatar 22, T9 Shannon profile ultimate")
    if AI_FRICTION:                                   # every AI driver uses the Air_Default template
        p_air = os.path.join(xt, "air.bin")
        if not os.path.exists(p_air):
            open(p_air, "wb").write(open(os.path.join(G, "xt", "air.bin"), "rb").read())
        b = XT(p_air).patched("Air_Default", "PersonalityParams.Speed.FrictionCoefficient", AI_FRICTION)   # read before truncating
        open(p_air, "wb").write(b)
        print("AI grip: Air_Default FrictionCoefficient", AI_FRICTION)
    if AI_STEERING:
        p_air = os.path.join(xt, "air.bin")
        if not os.path.exists(p_air):
            open(p_air, "wb").write(open(os.path.join(G, "xt", "air.bin"), "rb").read())
        for name in [r[0] for r in XT(p_air).records() if r[1] == "AISteering"]:
            for path, v in AI_STEERING.items():
                b = XT(p_air).patched(name, path, v)
                open(p_air, "wb").write(b)
        print("AI steering:", AI_STEERING)
    if CAREER_AI_SURFACE:
        p_sp = os.path.join(xt, "singleplayer.bin")
        x = XT(os.path.join(G, "xt", "singleplayer.bin"))
        events = [r[0] for r in x.records() if r[1] == "AmaxEvent"]
        for name in events:
            for path, v in (("OverrideAISurface", True), ("OverrideAISurfaceValue", CAREER_AI_SURFACE)):
                x.b = x.patched(name, path, v)
        open(p_sp, "wb").write(x.b)
        print("career AI surface", CAREER_AI_SURFACE, "on", len(events), "events")

    # 10. AMAX Lua plugins shipped with the mod (test copy only): mod_static/amax/plugins/<name>/<name>.lua, plus
    # the copy's plugins.lua = the installed one (read only) + a require line per plugin
    static = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mod_static")
    for root, _, files in os.walk(static):
        for f in files:
            dst = os.path.join(out, os.path.relpath(os.path.join(root, f), static))
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            open(dst, "wb").write(open(os.path.join(root, f), "rb").read())
    plugs = sorted(os.listdir(os.path.join(static, "amax", "plugins")))
    lst = open(os.path.join(GAME, "amax", "plugins", "plugins.lua"), encoding="utf-8").read()
    for name in plugs:
        if f'require("{name}.{name}")' not in lst:
            lst = lst.replace("\n}", f'\n\trequire("{name}.{name}"),\n}}', 1)
    open(os.path.join(out, "amax", "plugins", "plugins.lua"), "w", encoding="utf-8", newline="\n").write(lst)
    print("written to", out)


if __name__ == "__main__":
    main(sys.argv[1])
