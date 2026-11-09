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
usage: make_reverse.py OUT_DIR [--routes-only]
"""
import collections, json, os, struct, sys
import numpy as np
import addramp, aidreverse, camcycle, maplock, blurbaf, blurbpr, blurloc, bluripf, blurroute, gridreverse, thumbreverse
from blurxt import XT
from kslfwrite import KSLF

HARDCORE = True                # custom races: levels moved up one step (see step 6b)
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
# Invisible ramps (collision only) {level: [(bottom centre, top centre, width)]}, game coordinates (trackrec.py).
# New York Dumbo 3 reversed (East River Run): the dock platform, a ~3 m step down in the original direction (player
# stuck at (1006, 3.8, 43), back on the platform at (1012, 5.8..6.6, 35)); 25 m long, 3 m rise, 16 m wide.
# 2026-10-22 second version: the whole step, measured by driving along it: left end (1010, 46), right end (986, 30)
# (28.8 m), platform top y 5.7..6.0 -> 35 m wide (3 m margin each side), from 18 m before the step to 3 m onto it.
# 3rd version (2026-10-23, player: AI took off and crashed): 45 m wide, 35 m long (30 m before the step, 5 m onto the
# platform), smoothstep profile in 12 bands (flat at both ends), ends at 6.0 = the platform top.
# 4th (2026-10-23, player: small step between the road and the ramp start): starts 40 m before the step, sunk to
# y 3.2 under the road (the recorded y 3.8 is the car, not the ground): it comes out of the ground with no edge.
# invisible walls (addramp.wall_object): level -> walls, each [(x, bottom y, top y, z)] in game coordinates
# Route 66 reverse (Amboy 1R, MainLoop nodes 759-768): road edge on the left, from 2 positions read live 2026-11-05,
# top at guardrail height (a jump follows: no higher)
WALLS = {"usa_amboy": [[(186.4, -0.4, 3.8, 846.6), (166.5, 0.2, 3.9, 846.0), (150.4, 0.7, 4.1, 845.4),
                        (146.4, 0.8, 4.2, 845.3)]]}   # 2026-11-05: 3 m above the road (decorated neon wall, user's design)
# 2026-11-05: path closed by a wall along the player's recorded path (edits/route66r_path1.json, car y - 1.5 .. + 2.5 = road + 3 m)
# 2026-11-07: wall continuing the game's wall on the player's right (edits/route66r_wall2.json = recorded path
# route66r_wall2_path_raw.json moved 1.5 m to the right, 4 m longer at both ends: no gap with the game walls)
WALL_PATHS = {"usa_amboy": ["edits/route66r_path1.json", "edits/route66r_wall2.json"]}
WALL_HEIGHT = {"edits/route66r_wall2.json": 6.0,      # m above the road (car y - 0.5); 2026-11-07 user: 6 m, big animations
               "edits/route66r_path1.json": 7.5}      # 2026-11-07 user: 7.5 m
for _lv, _files in WALL_PATHS.items():
    for _f in _files:
        _p = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), _f)))
        # smooth (user 2026-11-05: odd car reactions): moving average of 7 (ends kept), then one point every 3 m
        _p = [_p[0]] + [[sum(q[k] for q in _p[max(i - 3, 0):i + 4]) / len(_p[max(i - 3, 0):i + 4]) for k in range(3)]
                        for i in range(1, len(_p) - 1)] + [_p[-1]]
        _r, _acc = [_p[0]], 0.0
        for _a, _b in zip(_p, _p[1:]):
            _acc += ((_b[0] - _a[0]) ** 2 + (_b[2] - _a[2]) ** 2) ** 0.5
            if _acc >= 3.0: _r.append(_b); _acc = 0.0
        _p = _r if _r[-1] == _p[-1] else _r + [_p[-1]]
        for _i in range(0, len(_p) - 1, 30):                   # <= 255 triangles per mesh object (8 per segment): 31 points
            WALLS.setdefault(_lv, []).append([(x, y - 1.5, y - 0.5 + WALL_HEIGHT.get(_f, 3.0), z)
                                              for x, y, z in _p[_i:_i + 31]])
   # 2026-11-05: 1 m high was jumped over, now ~2.5 m (just under the ramp end)
RAMPS = {"usa_ny_dumbo": [((975.8, 3.2, 71.3), (1000.8, 6.0, 33.8), 45.0)]}   # Route 66 reverse ramp removed 2026-11-05 (user: path closed by a wall instead)
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
         loc="CRN_BRIGHTON_MULTIPLAYER",         # "Ocean Pier" / "Jetée océanique", unused dev name (was Route 1 Reverse)
         grid=dict(loop=True), gates=None),       # loop: line and gate relation read from the original
    dict(orig="USA_SanFran_RussianHill_1", new="USA_SanFran_RussianHill_R", index=None, hash=0xFFFF0020,
         loc="CRN_SANFRAN_RUSSIANHILL_3",        # "Cable Car Chase" / "Poursuite du tram", unused dev name; name <= 25: picture slot
         grid=dict(loop=True), gates=None,
         drop=("Carpark", "JunctionCarpark")),   # car-park shortcut: AI no longer use it (2026-10-21)
    # New York: alternative routes dropped (AI on the main loop only; kept on 2026-11-03: player fell through). Names fit the last free
    # picture slots (USA_Amboy_Bowl 14 chars, USA_LA_LongBeachDocks_2 23 chars).
    dict(orig="USA_NY_Dumbo_2", new="USA_NY_Dumbo2R", index=None, hash=0xFFFF0030,
         loc="CRN_NY_DUMBO_1",                   # "Fulton Loop" / "Boucle de Fulton", unused dev name (was Route 2 Reverse)
         grid=dict(loop=True), gates=None, main_only=True),
    dict(orig="USA_NY_Dumbo_3", new="USA_NY_Dumbo_3R", index=None, hash=0xFFFF0040,
         loc="CRN_NY_DUMBO_4",                   # "East River Run" / "Course sur l'East River", unused dev route name
         grid=dict(loop=True), gates=None, main_only=True),
]

# Reverse every other playable route without a jump on its main loop. Routes with jump-only shortcuts keep the
# original geometry for players, but their branch sections are omitted from the reversed AI .aid. Brighton 2 and
# Downtown 1/6 are excluded (main-loop jump / unresolved jump-related risk). Hashes are above the old routes and
# spaced so the cloned actor-list entries fit between route hashes.
EXTRA_ROUTES = [
    ("JPN_Tokyo_Shutoko_2", "JPN_Tokyo_Shutoko_2R", "CRN_TOKYO_SHUTOKO_R1"),
    ("JPN_Tokyo_Shutoko_4", "JPN_Tokyo_Shutoko_4R", "CRN_ROUTE_2_REVERSE"),
    ("SPA_Barcelona_Gracia_1", "SPA_Barcelona_Gracia_1R", "CRN_ROUTE_1_REVERSE"),
    ("SPA_Barcelona_Gracia_2", "SPA_Barcelona_Gracia_2R", "CRN_ROUTE_2_REVERSE"),
    ("SPA_Barcelona_Gracia_5", "SPA_Barcelona_Gracia_5R", "CRN_BARCELONA_GRACIA_3"),
    ("SPA_Barcelona_Oval_1", "SPA_Barcelona_Oval_1R", "CRN_ROUTE_1_REVERSE"),
    ("SPA_Barcelona_Oval_2", "SPA_Barcelona_Oval_2R", "CRN_ROUTE_2_REVERSE"),
    ("UK_Brighton_3", "UK_Brighton_3R", "CRN_ROUTE_1_REVERSE"),
    ("UK_London_Hackney_1", "UK_London_Hackney_1R", "CRN_ROUTE_1_REVERSE"),
    ("UK_London_Hackney_2", "UK_London_Hackney_2R", "CRN_ROUTE_2_REVERSE"),
    ("UK_London_Hackney_4", "UK_London_Hackney_4R", "CRN_HACKNEY_6"),
    ("USA_Amboy_1", "USA_Amboy_1R", "CRN_AMBOY_2"),
    ("USA_Amboy_3", "USA_Amboy_3R", "CRN_AMBOY_BOWL"),
    ("USA_LA_Downtown_4", "USA_LA_Downtown_4R", "CRN_LA_DOWNTOWN_HIGHRISE"),
    ("USA_LA_LongBeachDocks_2", "USA_LA_LongBeachDocks_2R", "CRN_LA_DOCKS_1"),
    ("USA_LA_LongBeachDocks_3", "USA_LA_LongBeachDocks_3R", "CRN_LA_DOCKS_MULTIPLAYER"),
    ("USA_LA_Observatory_1", "USA_LA_Observatory_1R", "CRN_LA_OBSERVATORY_R1"),
    ("USA_LA_Observatory_2", "USA_LA_Observatory_2R", "CRN_LA_OBSERVATORY_R2"),
    ("USA_LA_River_3", "USA_LA_River_3R", "CRN_LA_RIVER_5"),
    ("USA_LA_River_6", "USA_LA_River_6R", "CRN_ROUTE_2_REVERSE"),
    ("USA_SanFran_Sausalito_1", "USA_SanFran_Sausalito_1R", "CRN_ROUTE_1_REVERSE"),
    ("USA_SanFran_Sausalito_2", "USA_SanFran_Sausalito_2R", "CRN_ROUTE_2_REVERSE"),
    # 2026-10-26, asked by the player despite the risk: Brighton 2 has its jump on the main loop (jump triggers and
    # fail reset), Downtown 1 / 6 pass near Building_TopofJump. To check and fix one by one in game.
    ("UK_Brighton_2", "UK_Brighton_2R", "CRN_ROUTE_2_REVERSE"),
    ("USA_LA_Downtown_1", "USA_LA_Downtown_1R", "CRN_ROUTE_1_REVERSE"),
    ("USA_LA_Downtown_6", "USA_LA_Downtown_6R", "CRN_ROUTE_2_REVERSE"),
]
# set aside by the player (2026-11-02): Cargo Run Reverse, Seafront Strip Reverse; 2026-11-04: Badlands Traverse, Shoreditch Sweep and the other docks route Reverse. Skipped here, not removed from the
# list, so every other route keeps its hash (i) and its cloned lists keep theirs
EXCLUDED = {"USA_LA_LongBeachDocks_3R", "USA_LA_LongBeachDocks_2R", "UK_Brighton_2R", "UK_London_Hackney_1R", "USA_Amboy_3R"}
# shortcuts kept in the reversed .aid (junctions rebuilt by aidreverse): validated in game on both Tokyos 2026-11-03.
# Applied to every route on 2026-11-03, the player fell through the ground on several maps: back to Tokyo only
KEEP_BRANCHES = {"JPN_Tokyo_Shutoko_2", "JPN_Tokyo_Shutoko_4"}
for i, (orig, new, loc) in enumerate(EXTRA_ROUTES):
    if new in EXCLUDED:
        continue
    grid = dict(loop=True)
    if orig == "JPN_Tokyo_Shutoko_2":
        grid["surface_from_lines"] = True
    # ground recorded by driving the original route (trackrec.py --all, cars moving): blur_extracted/ground/<orig>.csv
    ground = os.path.join(E, "ground", orig + ".csv")
    if os.path.isfile(ground):
        grid["ground"] = np.loadtxt(ground, delimiter=",", skiprows=1)
    # slots off the driven area brought back to its edge ("clip": best on 4 of the 5 routes, 2026-10-26); Speedway R's
    # recording is narrower than its grid (clip put cars on top of each other): columns spread instead ("spread")
    grid["ground_lateral"] = "spread" if orig == "SPA_Barcelona_Oval_2" else "clip"
    ROUTES.append(dict(orig=orig, new=new, index=None, hash=0xFFFF0100 + i * 0x100, loc=loc,
                       grid=grid, gates=None, main_only=orig not in KEEP_BRANCHES, allocate_index=True))


# glowing animated corner chevrons (SpecialFX with Corner_Arrows.model, e.g. #281) live in a list no route references
# (loaded for the whole level). Test 2026-11-05: that list is commented out, every original route of the city gets an
# identical copy, every reversed route a copy with the chevrons turned 180 deg. [untested in game]
CORNER_ARROWS = {}  # 2026-11-05 test with Tokyo #63: player fell into the void, chevrons unchanged


def is_arrow(a):
    """Projected direction arrows (special effects: corner1Arrows_3 on Dumbo, Arrow0 on LA River), in per-route lists:
    turned 180 deg like the pickups. Arrow signs (Ext_TempArrowSignA on Tokyo, per-route lists #188 / #109) are models
    still facing the driver from the curve's outside: mirrored instead (is_sign), so the chevrons point the new way."""
    n = a.get("Name", "")
    return "SpecialEffect" in a and "Arrow" in n and "Sign" not in n or is_sign(a)


def is_sign(a):
    # ponytail: mirror (det -1) may flip back-face culling; test in game, then rotate the mesh if it shows inside out
    return "ArrowSign" in a.get("Name", "") and "DynamicObjType" in a


def load_aid(path, drop=(), main_only=False):
    """Parsed .aid (raw) without the blocks named in `drop` (a shortcut and its junction: aidreverse refuses junctions;
    the AI then ignore the shortcut, the player can still take it) nor their logic-table references."""
    d = blurroute.parse(open(path, "rb").read(), raw=True)
    if main_only:
        main_name = aidreverse.roles(d)["main"]["name"]
        drop = set(drop)
        drop.update(j["name"] for j in d["junctions"])
        drop.update(s["name"] for s in d["sections"]
                    if s["name"] != main_name and not s["type"] & 0x3E)
    drop = set(drop) | {j["name"] for j in d["junctions"] if j["from"] in drop or j["to"] in drop}  # orphaned junctions
    d["blocks"] = [b for b in d["blocks"] if b["name"] not in drop]
    d["logic_table"] = [[ref for ref in refs if ref[1] not in drop] for refs in d["logic_table"]]
    return d


def build_aid(r, orig_aid, out_aid, start_xz):
    """Reverse, then slide the start (and finish) gates so each first node keeps the original distance to its line."""
    drop = r.get("drop", ())
    main_only = r.get("main_only", False)
    d = aidreverse.reverse(load_aid(orig_aid, drop, main_only))
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
        o = load_aid(orig_aid, drop, main_only)
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


KEY_SOUND_SECONDS = 1.7     # musicctl next-track sound: race_fail_fill cut at 1.7 s from the file start (player)


def music_key_sounds(out):
    """Sound of the musicctl plugin's next-track key. The Lua can only play UIEnums.SoundEffect events. BossRaceLose
    was tried first: the game also plays the 6.4 s career defeat jingle (menumusic_ns race_fail_fill, music graph)
    on it; the player liked its start. So MotorMashCount (cut Motor Mash mode, plays only its own wave in ingameui)
    gets the first KEY_SOUND_SECONDS of race_fail_fill: its wave replaced in ingameui.baf (used by that event only;
    mono like the original: MonoToStereoMixer), 150 ms fade out, peak -3 dBFS."""
    b = open(os.path.join(E, "root", "audio", "menumusic_ns.baf"), "rb").read()
    w = next(w for w in blurbaf.parse(b)["waves"] if w["name"] == "race_fail_fill")
    x = np.asarray(blurbaf.decode(b, w), dtype=float).reshape(-1, w["channels"]).mean(axis=1)
    x = x[:int(w["rate"] * KEY_SOUND_SECONDS)]           # measured from the file start, as the player listened
    if w["rate"] != 48000:
        x = np.interp(np.arange(0, len(x) - 1, w["rate"] / 48000), np.arange(len(x)), x)
    x[-7200:] *= np.linspace(1, 0, 7200)
    x = (x / np.abs(x).max() * 0.7 * 32767).astype(np.int16)[:, None]
    b = open(os.path.join(E, "root", "audio", "ingameui.baf"), "rb").read()
    b = blurbaf.replace_wave(b, "HUD_MotorMashCount", x, 48000)
    os.makedirs(os.path.join(out, "audio"), exist_ok=True)
    open(os.path.join(out, "audio", "ingameui.baf"), "wb").write(b)
    print("musicctl sound: ingameui.baf HUD_MotorMashCount (next track)")


def main(out, routes_only=False):
    routes_json_all = json.load(open(os.path.join(E, "xt_json", "amax.json")))
    routes_json = routes_json_all["Route"]
    xt = os.path.join(out, "gamedata", "xt")
    os.makedirs(xt, exist_ok=True)
    by_city = collections.defaultdict(list)
    for r in ROUTES:
        src = routes_json[r["orig"]]
        r["city"] = src["City"].split("/")[-1].lower()
        r["src"] = src
        by_city[r["city"]].append(r)
    for city, rs in by_city.items():
        next_index = max((v["Index"] for v in routes_json.values()
                          if v["City"].split("/")[-1].lower() == city and "Index" in v), default=-1) + 1
        for r in rs:
            if r.get("allocate_index"):
                r["resolved_index"] = next_index
                next_index += 1
            else:
                r["resolved_index"] = r["index"] if r["index"] is not None else r["src"]["Index"] + 1
    if routes_only:
        print("routes-only: AI balance, steering, perks, and driver experiments disabled")

    # 1. per city: .aid of each route, then one actorpack with every route's cloned start lists
    for city, rs in by_city.items():
        lvl = os.path.join(out, "gamedata", "levels", city)
        os.makedirs(lvl, exist_ok=True)
        pack = os.path.join(G, "levels", city, "actorpack.xt")
        pack_json = os.path.join(E, "xt_json", f"{city}.actorpack.json")
        A = json.load(open(pack_json, encoding="utf-8"))["LevelActorList"]
        k = KSLF(pack)
        for r in rs:
            # start lists = lists of this pack, used by the route, holding a grid or start/finish texts; pickup lists
            # too (2026-10-26: pickups faced the old way), cloned because the original route uses the same lists
            r["clones"] = []
            for field in ("ActorLists", "MultiplayerActorLists"):
                for i, ref in enumerate(r["src"][field]):
                    pk, _, lst = ref.split("/")
                    acts = [a for a in A.get(lst, {}).get("LevelActors", []) if a]
                    if pk == f"{city}.actorpack" and any(gridreverse.is_start_position(a) or "PickupType" in a or
                                                         a.get("Name", "").startswith("Start_Text") or is_arrow(a)
                                                         for a in acts):
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
        arrows = CORNER_ARROWS.get(city)
        if arrows:
            k.clone(arrows, None, rs[0]["hash"] + 7)       # the originals' copy
            for r in rs:
                k.clone(arrows, None, r["hash"] + 6)
                r["arrow_clone"], r["arrow_orig_hash"] = f"#{len(k.index) - 1}", rs[0]["hash"] + 7
        ap = os.path.join(lvl, "actorpack.xt")
        open(ap, "wb").write(k.build())
        if arrows:
            x = XT(ap)
            buf = bytearray(x.b)
            for i, a in enumerate(A[arrows]["LevelActors"]):
                if not a:
                    continue
                buf[x.locate(arrows, f"LevelActors[{i}].IsCommented")[0]] = 1
                if "SpecialEffect" in a and a.get("WorldMatrix"):
                    for r in rs:
                        for row in ("ax", "az"):
                            for c in ("vx", "vy", "vz"):
                                off = x.locate(r["arrow_clone"], f"LevelActors[{i}].WorldMatrix.{row}.{c}")[0]
                                struct.pack_into("<f", buf, off, -float(a["WorldMatrix"][row][c]))
            open(ap, "wb").write(buf)
            print(city, "corner chevrons", arrows, "commented out, copied for the originals and turned for", len(rs), "reversed routes")
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
            # pickups: same place, turned 180 deg about the vertical (ax and az negated, like the line texts)
            # (written into one buffer: XT.patched copies the whole file per value, a 2 h build on 2026-10-26)
            x = XT(ap)
            buf = bytearray(x.b)
            n_pick = 0
            for lst in lists:
                for i, a in enumerate(A[lst]["LevelActors"]):
                    if a and ("PickupType" in a or is_arrow(a)) and a.get("WorldMatrix"):
                        for row in (("ax",) if is_sign(a) else ("ax", "az")):
                            for c in ("vx", "vy", "vz"):
                                off = x.locate(r["clone_names"][lst], f"LevelActors[{i}].WorldMatrix.{row}.{c}")[0]
                                struct.pack_into("<f", buf, off, -float(a["WorldMatrix"][row][c]))
                        n_pick += 1
            open(ap, "wb").write(buf)
            print(r["new"], n_pick, "pickups and direction arrows turned")
            if maplock.edited(r["new"]):          # moves made in Reverse Studio (grids, pickups, texts)
                maplock.apply_edits(r["new"], ap, r["hash"])
            if maplock.locked(r["new"]):          # validated in game: back to its locked .aid, grids and pickups
                maplock.restore(r["new"], r["aid"], ap, r["hash"])
        print(city, renew_uids(ap, {n for r in rs for n in r["clone_names"].values()}), "cloned actor uids renewed")

    # 2. amax.bin: each new Route = copy of the original pointing to its clones
    p = os.path.join(xt, "amax.bin")
    a = KSLF(os.path.join(G, "xt", "amax.bin"))
    for r in ROUTES:
        a.clone(r["orig"], r["new"], r["hash"])
        r["ext"] = {lst: a.add_external(h, "LevelActorList") for lst, h in r["list_hash"].items()}
        if "arrow_clone" in r:                         # hashes ascending: + 6, then + 7 (first route of the city)
            r["arrow_ext"] = a.add_external(r["hash"] + 6, "LevelActorList")
            if r["arrow_orig_hash"] == r["hash"] + 7:
                r["arrow_orig_ext"] = a.add_external(r["arrow_orig_hash"], "LevelActorList")
    open(p, "wb").write(a.build())
    a = KSLF(p)
    for r in ROUTES:
        for field, i, lst in r["clones"]:
            a.set_array_ref(r["new"], field, i, r["ext"][lst])
    orig_ext = {r["arrow_orig_hash"]: r["arrow_orig_ext"] for r in ROUTES if "arrow_orig_ext" in r}
    for r in ROUTES:
        if "arrow_ext" in r:
            for field in ("ActorLists", "MultiplayerActorLists"):
                a.append_to_array(r["new"], field, r["arrow_ext"])
                a.append_to_array(r["orig"], field, orig_ext[r["arrow_orig_hash"]])
    # 2b. intro cameras made in Reverse Studio (edits/<route>.cams.json): our own .cycle files, written loose like the
    # rest of root.pak, + a copy of the original's CycleResourceDef (new file name) and AnimatedCameraSequence
    # (StageTime kept) per shot; the reversed Route points at them (pack: solo, multi, single and boss slots).
    # Hashes route + 0x0C..0x0F (cloned lists use route + 1..5)
    for r in ROUTES:
        cf = os.path.join(maplock.EDITS, r["new"] + ".cams.json")
        if not os.path.isfile(cf):
            continue
        cycles = camcycle.own_cycles(json.load(open(cf)))
        k_route = a._record_pos(r["new"])
        for j, (shot, data) in enumerate(cycles.items()):
            fields = (("VistaCameraSequence",) if shot == "vista" else
                      ("PackCameraSequence", "PackCameraSequenceMP", "PackCameraSequenceSingle", "PackCameraSequenceBoss"))
            seq_src = r["src"][fields[-1] if shot == "pack" else fields[0]].split("/")[-1]
            cyc_src = routes_json_all["AnimatedCameraSequence"][seq_src]["Animation"].split("/")[-1]
            name = f"animations/cameras/rev_{r['new'].lower()}_{shot}"
            os.makedirs(os.path.join(out, "animations", "cameras"), exist_ok=True)
            open(os.path.join(out, *name.split("/")) + ".cycle", "wb").write(data)
            kc = a.clone(cyc_src, None, r["hash"] + 0x0C + j)
            a.set_string(cyc_src, kc, "FilenameMinusExt", name)
            ks = a.clone(seq_src, None, r["hash"] + 0x0E + j)
            a.set_ref(seq_src, ks, "Animation", a.records[kc][0])
            for f in fields:
                a.set_ref(r["new"], k_route, f, a.records[ks][0])
            print(r["new"], "intro camera:", shot, name)
    open(p, "wb").write(a.build())
    # names (2026-10-26, the player's choice): "<original name> Reverse" in every language, new texts added to
    # cityandroutenames.loc (blurloc.add_text, new hashes: the key -> hash function is unknown, the Route's LocString
    # holds the hash); Haruna keeps "Ascent" (an unused dev string)
    lp = os.path.join(G, "xt", "loc", "cityandroutenames.loc")
    loc_file = blurloc.parse_raw(open(lp, "rb").read())
    for i, r in enumerate(ROUTES):
        if isinstance(r["loc"], int):
            continue
        orig = r["src"]["LocString"]
        texts = {code.rstrip(b"\0").decode(): t[orig] + " Reverse" for code, t in loc_file["langs"]}
        r["loc"] = 0xB1E10000 + i
        blurloc.add_text(loc_file, "CRN_REVERSE_" + r["orig"].upper(), r["loc"], texts)
    os.makedirs(os.path.join(out, "gamedata", "xt", "loc"), exist_ok=True)
    open(os.path.join(out, "gamedata", "xt", "loc", "cityandroutenames.loc"), "wb").write(blurloc.build(loc_file))
    for r in ROUTES:
        loc = r["loc"] if isinstance(r["loc"], int) else loc_hash(r["loc"])
        index = r["resolved_index"]
        for field, v in (("RouteNumber", r["src"]["RouteNumber"]), ("Index", index), ("LocString", loc)):
            b = XT(p).patched(r["new"], field, v)     # read before opening for writing
            open(p, "wb").write(b)

    # 3. pictures: append new Route Name entries while retaining the complete original BPR.
    bpr = blurbpr.Bpr(os.path.join(E, "root", "ui", "data", "ui_frontend.bpr"))
    old_bpr_paths = (os.path.join(E, "mods", "reverse_first_batch_heightfix", "files", "ui", "data", "ui_frontend.bpr"),
                     os.path.join(E, "mods", "reverse_first_batch_final", "files", "ui", "data", "ui_frontend.bpr"),
                     os.path.join(E, "mods", "reverse", "files", "ui", "data", "ui_frontend.bpr"))
    old_bpr_path = next((p for p in old_bpr_paths if os.path.isfile(p)), None)
    old_bpr = blurbpr.Bpr(old_bpr_path) if old_bpr_path else None
    additions = []
    for r in ROUTES:
        rec, _ = bpr.raw(r["orig"])
        if old_bpr and r["new"] in old_bpr.names:
            previous, raw = old_bpr.raw(r["new"])
            assert previous[6:10] == rec[6:10] and len(raw) == rec[4], r["new"]
            print(r["new"], "reused existing thumbnail")
        else:
            raw = blurbpr.encode(thumbreverse.make(bpr.image(r["orig"])), rec[6], rec[7])
        additions.append((r["new"], r["orig"], raw))
    bpr = bpr.rebuild(additions)
    print("pictures appended:", len(additions), "new route thumbnails")
    ui = os.path.join(out, "ui", "data")
    os.makedirs(ui, exist_ok=True)
    open(os.path.join(ui, "ui_frontend.bpr"), "wb").write(bpr.b)
    # 3b. glowing route outline of the menu / loading screen (ui/data/ipf/minimap/<city>_ui.ipf, one group per
    # route named like it): a copy of the original's, drawn the other way (bluripf.add_reversed). Haruna's start
    # line mark stays at the top (point to point: not moved).
    mm = os.path.join(ui, "ipf", "minimap")
    os.makedirs(mm, exist_ok=True)
    ipf = {}
    for r in ROUTES:
        f = r["city"] + "_ui.ipf"
        if f not in ipf:
            ipf[f] = open(os.path.join(E, "root", "ui", "data", "ipf", "minimap", f), "rb").read()
        ipf[f] = bluripf.add_reversed(ipf[f], r["orig"], r["new"])
        g = r["city"] + "_game.ipf"            # in-race HUD minimap: same outline under the reversed name
        if g not in ipf:
            ipf[g] = open(os.path.join(E, "root", "ui", "data", "ipf", "minimap", g), "rb").read()
        ipf[g] = bluripf.add_reversed_game(ipf[g], r["orig"], r["new"])
    for f, b in ipf.items():
        open(os.path.join(mm, f), "wb").write(b)
    print("route outlines:", len(ROUTES), "added in", len(ipf), "files")

    # 4. custom race menu
    m = KSLF(os.path.join(G, "xt", "multiplayer.bin"))
    orig_hashes = [int(h[1:], 16) for h in
                   next(v for n, t, v, _ in XT(os.path.join(G, "xt", "multiplayer.bin")).records() if n == "#735")["routes"]]
    for r in ROUTES:
        m.append_to_array("#735", "routes", m.add_external(r["hash"], "Route"))
    # menu order: each reversed route right after its original (2026-10-23), the others as in the game
    slots = m.get_array_refs("#735", "routes")
    slot_of = dict(zip(orig_hashes + [r["hash"] for r in ROUTES], slots))
    amax_hash = {n: h for n, t, v, h in XT(os.path.join(G, "xt", "amax.bin")).records() if t == "Route"}
    order = []
    for h in orig_hashes:
        order.append(h)
        order += [r["hash"] for r in ROUTES if amax_hash[r["orig"]] == h]
    order += [r["hash"] for r in ROUTES if r["hash"] not in order]
    for i, h in enumerate(order):
        m.set_array_ref("#735", "routes", i, slot_of[h])
    mp = os.path.join(xt, "multiplayer.bin")
    open(mp, "wb").write(m.build())
    print("menu :", len(order), "routes, chaque inversée après son original")
    # 5. AI in custom races: the game allows max_ai_per_console AI per player in the lobby (4: alone = 4 AI);
    # the menu's "Max AI" goes up to 18 (20 cars - 2 players assumed). 19: alone, up to the menu's 18 AI.
    b = XT(mp).patched("#735", "max_ai_per_console", MAX_AI_PER_CONSOLE)
    open(mp, "wb").write(b)
    # 6. AI experiments: one stage row of a difficulty file set to one value for every AI, at every stage
    for name, changes in ({} if routes_only else AI_ROWS).items():
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

    # 6b. Hardcore (2026-11-05): the game has 3 custom-race levels, each a file named in Blur.exe (Multiplayer_Easy /
    # _Medium / _Hard.csv, MpAI Off / Easy / Medium / Hard in MpCustomRaceAdvanced.lua): moved up one step without
    # touching the exe. Easy = the original Medium ("Normal"), Medium = the original Hard, Hard = AI_ROWS ("Hardcore").
    if HARDCORE and not routes_only:
        ev = os.path.join(out, "gamedata", "events")
        os.makedirs(ev, exist_ok=True)
        for dst, src in (("multiplayer_easy.csv", "multiplayer_medium.csv"), ("multiplayer_medium.csv", "multiplayer_hard.csv")):
            open(os.path.join(ev, dst), "wb").write(open(os.path.join(G, "events", src), "rb").read())
        for field, v in (("ai_average_mp_rank_easy", 24), ("ai_average_mp_rank_medium", 44), ("ai_average_mp_rank_hard", 50)):
            data = XT(mp).patched("#735", field, v)   # read before open("wb") truncates the file
            open(mp, "wb").write(data)
        # labels kept as in the game (user, 2026-11-05: "ni vu ni connu"); multiplayer.loc not written
        print("Hardcore: custom-race levels Normal / Hard / Hardcore")

    # 7. DoubleTap experiment: every PickupType that has a DoubleTap level uses it as its Normal level
    if PICKUPS_DOUBLETAP and not routes_only:
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
    if EVIL_SHANNON and not routes_only:
        p_air = os.path.join(xt, "air.bin")
        open(p_air, "wb").write(open(os.path.join(G, "xt", "air.bin"), "rb").read())
        for field, v in (("Racing", 1.0), ("Aggression", 1.0), ("Blocking", 1.0), ("Slamming", 1.0), ("Mistakes", 0.0)):
            b = XT(p_air).patched("T9 Shannon", field, v)
            open(p_air, "wb").write(b)
        p_rb = os.path.join(xt, "finalracebook.bin")
        open(p_rb, "wb").write(XT(os.path.join(G, "xt", "finalracebook.bin")).patched("Shannon", "AvatarID", 22))
        print("Evil Shannon: avatar 22, T9 Shannon profile ultimate")
    if AI_FRICTION and not routes_only:               # every AI driver uses the Air_Default template
        p_air = os.path.join(xt, "air.bin")
        if not os.path.exists(p_air):
            open(p_air, "wb").write(open(os.path.join(G, "xt", "air.bin"), "rb").read())
        b = XT(p_air).patched("Air_Default", "PersonalityParams.Speed.FrictionCoefficient", AI_FRICTION)   # read before truncating
        open(p_air, "wb").write(b)
        print("AI grip: Air_Default FrictionCoefficient", AI_FRICTION)
    if AI_STEERING and not routes_only:
        p_air = os.path.join(xt, "air.bin")
        if not os.path.exists(p_air):
            open(p_air, "wb").write(open(os.path.join(G, "xt", "air.bin"), "rb").read())
        for name in [r[0] for r in XT(p_air).records() if r[1] == "AISteering"]:
            for path, v in AI_STEERING.items():
                b = XT(p_air).patched(name, path, v)
                open(p_air, "wb").write(b)
        print("AI steering:", AI_STEERING)
    if CAREER_AI_SURFACE and not routes_only:
        p_sp = os.path.join(xt, "singleplayer.bin")
        x = XT(os.path.join(G, "xt", "singleplayer.bin"))
        events = [r[0] for r in x.records() if r[1] == "AmaxEvent"]
        for name in events:
            for path, v in (("OverrideAISurface", True), ("OverrideAISurfaceValue", CAREER_AI_SURFACE)):
                x.b = x.patched(name, path, v)
        open(p_sp, "wb").write(x.b)
        print("career AI surface", CAREER_AI_SURFACE, "on", len(events), "events")

    # 9b. invisible ramps added to a level's collision (addramp.py): steps a reversed route can only go down
    for level, ramps in {**{k: [] for k in WALLS}, **RAMPS}.items():
        src = os.path.join(GAME, "levels", level, "Level.levelphysics")     # read only
        data = open(src, "rb").read()
        tmp = os.path.join(out, "levels", level, "Level.levelphysics")
        os.makedirs(os.path.dirname(tmp), exist_ok=True)
        for bottom, top, width, *kick in ramps:
            open(tmp, "wb").write(data)
            data = addramp.add_ramp(tmp, bottom, top, width, *kick)
        for wall in WALLS.get(level, []):
            data = addramp.insert_objects(data, addramp.wall_object(wall, thick=1.0))
        open(tmp, "wb").write(data)
        print(f"{level}: {len(ramps)} rampe(s), {len(WALLS.get(level, []))} mur(s) invisible(s) dans la collision")

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
    music_key_sounds(out)
    print("written to", out)


if __name__ == "__main__":
    routes_only = "--routes-only" in sys.argv[1:]
    args = [arg for arg in sys.argv[1:] if arg != "--routes-only"]
    if len(args) != 1:
        raise SystemExit("usage: make_reverse.py OUT_DIR [--routes-only]")
    main(args[0], routes_only=routes_only)
