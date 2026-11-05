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
# (GameModel uid, DynamicObjDef uid, file, box size x y z): bars along the wall tops + vertical posts every POST_STEP m.
# Same vertex / index / texture counts: models from one template must have the same size (load crash 0x6DB2EB)
MODELS = {"bar": (0xFFFFFE00, 0xFFFFFE01, r"models\objects\usa_amboy\neon_blue.model", (4.0, 0.12, 0.12)),
          "post": (0xFFFFFE02, 0xFFFFFE03, r"models\objects\usa_amboy\neon_post.model", (0.12, 1.75, 0.12))}
SRC_GAMEMODEL, SRC_DYNDEF = "1F3F42A6", "01ADFCF8"         # Map Builder's sources (DynamicWaterLevel)
BAR, SIZE, POST_STEP = 4.0, 0.12, 8.0
# Blur menu deep blue (user 2026-11-05: the first sky blue was too light), lighter chevrons as the pattern
DARK, LIGHT = (4, 22, 150), (30, 85, 255)
DRAW = 700.0


def texture(n=16):
    """n x n chevron ">" lighter on the deep blue, repeated along each bar (u wraps)"""
    px = []
    for y in range(n):
        for x in range(n):
            d = abs(x - n // 2 - abs(y - n // 2 + 0.5))          # distance to a ">" shape
            px += LIGHT if d < 2.5 else DARK
    return bytes(px), n


def model_bytes(size, salt):
    import blurmodel_write
    V, I = [], []
    half = [c / 2 for c in size]
    long = max(range(3), key=lambda i: size[i])
    for ax in range(3):
        for s in (-1, 1):
            n = [0, 0, 0]; n[ax] = s
            u_, v_ = (ax + 1) % 3, (ax + 2) % 3
            base = len(V)
            for a, b in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
                p = [0.0] * 3
                p[ax], p[u_], p[v_] = half[ax] * s, half[u_] * a, half[v_] * b
                # u along the long axis: one chevron per 0.5 m
                u = (p[long] + half[long]) / 0.5 if long != ax else (a + 1) / 2
                V.append((*p, *n, u, (b + 1) / 2 if long != v_ else (a + 1) / 2))
            q = [base, base + 1, base + 2, base, base + 2, base + 3]
            I += q + q[::-1]                                 # both faces: winding does not matter
    rgb, w = texture()
    t = open(os.path.join(config.BLUR_EXTRACTED, "nfs_models", "sign_wetfloor.model"), "rb").read()
    return blurmodel_write.build(t, V, I, rgb, w, w, glow=230, salt=salt)


def amax_defs(amax):
    tmp = os.path.join(tempfile.gettempdir(), "neon_amax.bin")
    open(tmp, "wb").write(amax)
    A = dump.File(tmp)
    have = {u for u, t, oi in A.refs}
    obj = {"%08X" % u: oi for u, t, oi in A.refs if oi != 0xFFFF}
    for gm_uid, def_uid, fname, _ in MODELS.values():
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


def bars(walls, thick=1.0):
    """[(model key, Mat43 rows (ax, ay, az, aw))] of the bars: both top edges of each wall [(x, bottom y, top y, z)], one bar per
    BAR m (the last one may overlap)."""
    out = []
    for w in walls:
        for side in (-1, 1):
            line = []
            for i, (x, yb, yt, z) in enumerate(w):
                a, b = w[max(i - 1, 0)], w[min(i + 1, len(w) - 1)]
                dx, dz = b[0] - a[0], b[3] - a[3]
                n = math.hypot(dx, dz)
                line.append((x - dz / n * thick / 2 * side, yt + SIZE / 2, z + dx / n * thick / 2 * side))
            L = [0.0]
            for p, q in zip(line, line[1:]):
                L.append(L[-1] + math.dist(p, q))
            k = 0
            for j in range(max(1, round(L[-1] / BAR))):
                c = min(BAR / 2 + BAR * j, L[-1] - BAR / 2) if L[-1] > BAR else L[-1] / 2
                while k < len(L) - 2 and L[k + 1] < c:
                    k += 1
                f = (c - L[k]) / ((L[k + 1] - L[k]) or 1)
                p = [line[k][i] + (line[k + 1][i] - line[k][i]) * f for i in range(3)]
                d = [line[k + 1][i] - line[k][i] for i in range(3)]
                h = math.hypot(d[0], d[2]) or 1
                ax = (d[0] / h, 0.0, d[2] / h)
                out.append(("bar", (ax, (0.0, 1.0, 0.0), (-ax[2], 0.0, ax[0]), tuple(p))))
                if j % round(POST_STEP / BAR) == 0:             # post under the bar start, top flush with it
                    post = (p[0] - ax[0] * BAR / 2, p[1] + SIZE / 2 - MODELS["post"][3][1] / 2, p[2] - ax[2] * BAR / 2)
                    out.append(("post", (ax, (0.0, 1.0, 0.0), (-ax[2], 0.0, ax[0]), post)))
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
    items = bars(mr.WALLS[LEVEL])
    for salt, (key, (gm, du, fname, size)) in enumerate(MODELS.items()):
        mp = os.path.join(build, fname.replace("\\", os.sep))
        os.makedirs(os.path.dirname(mp), exist_ok=True)
        open(mp, "wb").write(model_bytes(size, 0x4E30 + salt))
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
