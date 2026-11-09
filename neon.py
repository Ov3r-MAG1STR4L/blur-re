#!/usr/bin/env python3
"""Blue neon bars along the top edges of our invisible walls (addramp.wall_object), for one reversed route.

Three parts (2026-11-05):
- model: one 4 m bar (box 4 x 0.12 x 0.12 m, solid blue, glow 255) written by blurmodel_write from the NFS template;
  one model for every bar (Map Builder models of different sizes from one template crash the load);
- amax.bin: a GameModel (its file name) + a DynamicObjDef (no physics, far draw distance, in the mirror), cloned
  the Map Builder way (kslf_write.clone_object_any of DynamicWaterLevel's records);
- actorpack: DynamicObjActors added to the route's own cloned lists only (a copy of an existing DynamicObjActor
  struct in a new chunk, its pointers appended to LevelActors, its name appended to the record strings, its
  DynamicObjType = an external index slot of our def). Never done before: [risk, untested in game].

usage: neon.py BUILD_DIR      (edits that build: models/, gamedata/xt/amax.bin, the city's actorpack.xt)
"""
import math, os, struct, sys, tempfile
import config
from blurxt import XT, decode_names, encode_names
from kslfwrite import KSLF

MB = config.MAP_BUILDER_DIR
sys.path[:0] = [os.path.join(MB, p) for p in ("kslf", "flat_earth")] + [MB]
import dump, kslf, kslf_write  # noqa: E402

LEVEL, LISTS = "usa_amboy", ["#354", "#357"]               # Route 66 reverse (Amboy 1R) lists 0xffff0c01 / 0c04
TEMPLATE_LIST = "#15"                                      # an Amboy list holding DynamicObjActors
# (GameModel uid, DynamicObjDef uid, file, box size x y z, texture, glow). The user's design (Gemini image, 2026-11-05):
# dark 4 m panels, a top band with a chevron group, a neon line at the top and under the band, double neon posts
# between panels. Same vertex / index / texture counts for all: models from one template must have the same size
# (load crash 0x6DB2EB)
GLOW = 90                    # 255 bloomed to cyan, 150 still too contrasted (user)
F = r"models\objects\usa_amboy\neon_%s.model"
CHEV = (0.22, 0.2)           # half length along the wall, half height of a chevron
MODELS = {"bar": (0xFFFFFE00, 0xFFFFFE01, F % "blue", (4.4, 0.2, 0.06), "neon", GLOW),   # 4.4: overlap at joints
          "stroke": (0xFFFFFE02, 0xFFFFFE03, F % "post", (2 * math.hypot(*CHEV), 0.12, 0.06), "neon", GLOW)}
# 2026-11-05 (user): no black band (this shader draws a see-through pixel black) -> chevrons drawn as neon strokes;
# no posts down to the ground; no panel: between the neons the wall is collision only
SRC_GAMEMODEL, SRC_DYNDEF = "1F3F42A6", "01ADFCF8"         # Map Builder's sources (DynamicWaterLevel)
PIECE, THICK, HEIGHT, BAND = 4.0, 1.0, 3.0, 0.5
NEON = (45, 75, 205)          # deep Blur-menu blue; 2026-11-05 (20, 70, 255) at glow 255 washed out to sky blue
DRAW = 700.0
TW, TH = 128, 32             # band texture: sharper chevrons (32 x 32 was pixelated); same for every model


def texture(kind):
    """TW x TH RGBA (1-bit alpha in DXT1): neon = plain blue; band = see-through with 5 chevrons '<' (they point
    the way the reversed route runs: the first '>' were the wrong way round) in its middle"""
    px = bytearray()
    for y in range(TH):
        for x in range(TW):
            on = kind == "neon"
            if kind == "band" and 34 <= x < 94 and 3 <= y < TH - 3:
                d = (x - 34 - abs(y - (TH - 1) / 2) * 0.9) % 12           # '<': the tip on the left
                on = d < 4.5
            px += bytes(NEON) + (b"\xff" if on else b"\x00")
    return bytes(px)


def model_bytes(size, kind, glow, salt):
    import blurmodel_write
    V, I = [], []
    half = [c / 2 for c in size]
    for ax in range(3):
        for s in (-1, 1):
            n = [0, 0, 0]; n[ax] = s
            u_, v_ = (ax + 1) % 3, (ax + 2) % 3
            base = len(V)
            for a, b in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
                p = [0.0] * 3
                p[ax], p[u_], p[v_] = half[ax] * s, half[u_] * a, half[v_] * b
                # u along x (the piece length), v along y (height): the chevrons read along the road
                V.append((*p, *n, (p[0] + half[0]) / size[0], 1 - (p[1] + half[1]) / size[1]))
            q = [base, base + 1, base + 2, base, base + 2, base + 3]
            I += q + q[::-1]                                 # both faces: winding does not matter
    t = open(os.path.join(config.BLUR_EXTRACTED, "nfs_models", "sign_wetfloor.model"), "rb").read()
    return blurmodel_write.build(t, V, I, texture(kind), TW, TH, glow=glow, salt=salt)


def amax_defs(amax):
    tmp = os.path.join(tempfile.gettempdir(), "neon_amax.bin")
    open(tmp, "wb").write(amax)
    A = dump.File(tmp)
    have = {u for u, t, oi in A.refs}
    obj = {"%08X" % u: oi for u, t, oi in A.refs if oi != 0xFFFF}
    for gm_uid, def_uid, fname, *_ in MODELS.values():
        assert gm_uid not in have and def_uid not in have

        def gm_patch(data, pool, blocks, fname=fname):
            struct.pack_into("<I", data, blocks[0], len(pool))
            pool += fname.encode() + b"\0"
        _, amax = kslf_write.clone_object_any(obj[SRC_GAMEMODEL], None, gm_uid, gm_patch, data_in=amax)
        k4 = kslf.Kslf(amax)
        o4, n4 = k4.sections[4]
        gm_ref = next(i for i in range(n4) if struct.unpack_from("<I", amax, o4 + 8 * i)[0] == gm_uid)

        def def_patch(data, pool, blocks, gm_ref=gm_ref):
            b0 = blocks[0]
            struct.pack_into("<I", data, b0 + 0, gm_ref)       # Model
            struct.pack_into("<f", data, b0 + 12, DRAW)        # DrawDistance
            struct.pack_into("<I", data, b0 + 24, 1)           # DisplayInMirror
            struct.pack_into("<I", data, b0 + 32, 0)           # PhysType None
            struct.pack_into("<I", data, b0 + 68, 0)           # Alignment None
        _, amax = kslf_write.clone_object_any(obj[SRC_DYNDEF], None, def_uid, def_patch, data_in=amax)
    return amax


def _stations(w):
    """centre line of a wall [(x, bottom y, top y, z)] cut in PIECE m pieces: [(start, centre, end, top y, ax)]"""
    line = [(x, yt, z) for x, yb, yt, z in w]
    L = [0.0]
    for p, q in zip(line, line[1:]):
        L.append(L[-1] + math.hypot(q[0] - p[0], q[2] - p[2]))
    def at(c):
        k = max(i for i in range(len(L) - 1) if L[i] <= c) if c < L[-1] else len(L) - 2
        f = (c - L[k]) / ((L[k + 1] - L[k]) or 1)
        return [line[k][i] + (line[k + 1][i] - line[k][i]) * f for i in range(3)]
    out, n = [], max(1, round(L[-1] / PIECE))
    step = L[-1] / n
    for j in range(n):
        a, c, e = at(j * step), at((j + 0.5) * step), at((j + 1) * step)
        h = math.hypot(e[0] - a[0], e[2] - a[2]) or 1
        out.append((a, c, e, max(a[1], e[1]), ((e[0] - a[0]) / h, 0.0, (e[2] - a[2]) / h)))
    return out


def layout(walls):
    """[(model key, Mat43 rows (ax, ay, az, aw))], in the wall's middle plane only (2026-11-05: chevrons on both
    faces of the see-through wall overlapped as X): per 4 m piece, a neon line on the top edge and one BAND m lower,
    each tilted to the piece's slope and 10 % longer (no step between pieces), and between them 3 chevrons pointing
    against the recorded direction (the race direction)"""
    out = []
    L = math.hypot(*CHEV)
    for w in walls:
        for a, c, e, top, ax in _stations(w):
            az = (-ax[2], 0.0, ax[0])
            dy = (e[1] - a[1]) / PIECE                          # slope of the piece (top y per m)
            n = math.sqrt(1 + dy * dy)
            tx = (ax[0] / n, dy / n, ax[2] / n)                  # along the wall, following its top
            ty = (-ax[0] * dy / n, 1 / n, -ax[2] * dy / n)
            ym = (a[1] + e[1]) / 2
            for y in (ym, ym - BAND):
                out.append(("bar", (tx, ty, az, (c[0], y, c[2]))))
            for along in (-0.8, 0.0, 0.8):
                for up in (-1, 1):                         # tip at -CHEV[0], arms to +CHEV[0], +-CHEV[1]
                    u = (CHEV[0] / L, up * CHEV[1] / L)
                    sx = (ax[0] * u[0], u[1], ax[2] * u[0])
                    sy = (-ax[0] * u[1], u[0], -ax[2] * u[1])
                    p = (c[0] + ax[0] * along, ym + dy * along - BAND / 2 + up * CHEV[1] / 2, c[2] + ax[2] * along)
                    out.append(("stroke", (sx, sy, az, p)))
    return out


def add_actors(ap, lists, items):
    """New DynamicObjActors, items [(model key, Mat43)], in each record of `lists`."""
    x = XT(ap)
    tpl = None
    used = set()
    for n, t, v, h in x.records():
        used |= {a["SerialisableUid"] for a in v.get("LevelActors", []) if a and "SerialisableUid" in a}
        if n == TEMPLATE_LIST:
            c = next(i for i, ch in enumerate(x._ch) if x._names[ch[0]] == "DynamicObjActor")
            ct, cn, co, esz = x._ch[c]
            tpl, tdyn = bytes(x._d[co:co + esz]), ct
    assert tpl and len(tpl) == 140
    k = KSLF(ap)
    top = max(h for h, _, _ in k.index)
    slot = {key: k.add_external(m[1], "DynamicObjDef") for key, m in sorted(MODELS.items(), key=lambda e: e[1][1])}
    assert top < min(m[1] for m in MODELS.values())
    uid = 0x4E000000
    for lst in lists:
        r = k._record_pos(lst)
        idx, chunks, data, strings = k.records[r]
        plain = bytearray(decode_names(strings) if strings else b"\0")
        c_new = len(chunks)
        add = bytearray()
        for i, (key, m) in enumerate(items):
            while uid in used:
                uid += 1
            used.add(uid)
            a = bytearray(tpl)
            name_ofs = len(plain)
            plain += b"Neon%s%03d\0" % (key.encode(), i)
            struct.pack_into("<III", a, 0, uid, name_ofs, 0)        # SerialisableUid, Name, IsCommented
            struct.pack_into("<12f", a, 12, *[c for row in m for c in row])
            struct.pack_into("<I", a, 60, slot[key])               # DynamicObjType
            add += a
        while len(plain) % 4:
            plain += b"\0"
        k.records[r] = [idx, list(chunks) + [(tdyn, len(items), 0)], data + bytes(add), encode_names(bytes(plain))]
        k.append_to_array(lst, "LevelActors", [(i << 16) | c_new for i in range(len(items))])
    open(ap, "wb").write(k.build())


def main(build):
    import make_reverse as mr
    items = layout(mr.WALLS[LEVEL])
    sizes = set()
    for salt, (key, (gm, du, fname, size, kind, glow)) in enumerate(MODELS.items()):
        mp = os.path.join(build, fname.replace("\\", os.sep))
        os.makedirs(os.path.dirname(mp), exist_ok=True)
        data = model_bytes(size, kind, glow, 0x4E30 + salt)
        sizes.add(len(data))
        open(mp, "wb").write(data)
    assert len(sizes) == 1, sizes                          # one size for all (see MODELS)
    am = os.path.join(build, "gamedata", "xt", "amax.bin")
    data = amax_defs(open(am, "rb").read())                # read before open("wb") truncates it
    open(am, "wb").write(data)
    ap = os.path.join(build, "gamedata", "levels", LEVEL, "actorpack.xt")
    add_actors(ap, LISTS, items)
    # self-check: the new actors read back with our defs, positions and names
    defs = {"@%08x" % m[1] for m in MODELS.values()}
    for n, t, v, h in XT(ap).records():
        if n in LISTS:
            neon = [a for a in v["LevelActors"] if a and a.get("DynamicObjType") in defs]
            assert len(neon) == len(items), (n, len(neon))
            assert abs(neon[0]["WorldMatrix"]["aw"]["vx"] - items[0][1][3][0]) < 1e-3
            assert str(neon[-1]["Name"]).startswith("Neon"), neon[-1]["Name"]
    print(len(items), "neon actors", {k: sum(i[0] == k for i in items) for k in MODELS}, "on", LEVEL, LISTS)


if __name__ == "__main__":
    main(sys.argv[1])
