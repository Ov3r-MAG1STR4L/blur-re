#!/usr/bin/env python3
"""Shared animated wall skin (2026-11-06): the same few models for every wall of every map, drawn by the game's
ScrollUVNeon_NV.fx shader (UV scrolling + DXT5 alpha), the look set in theme.json only.

Template: models/objects/usa_amboy/misc/spline_plane.model (root.pak, read from blur_extracted, never modified):
- mesh 0 = the plane (default_NB_NL_NM_NV, stream 0, 1429 vertices): every position set to 0 (hidden);
- mesh 1 = the propeller disc (ScrollUVNeon_NV, stream 1, 84 vertices of 24 B: pos f32x3, normal u8x4, uv half4,
  102 strip indices), texture propeller_diff 256 x 256 DXT5 9 mips: rewritten in place (same counts and sizes).
Material 1 values (0x4C B at MAT1, offsets declared in the file 0, 4, 8, 0xC, 0x1C, 0x2C, 0x3C): g_tNeon, g_tAlbedo,
g_tMaterial (u32 texture indices), g_vScrollTextureX / Y, g_vScrollSpeedX / Y (float4); template 1, 2, 3, 0, 0,
(5, 0, 0, 0), 0. In game (B1 test, 2026-11-06): SpeedX.x 5 -> 2.5 halves the scroll; g_tNeon is not a layer of its
own (another texture there only tints the albedo band) -> one texture, one row per line.

Layers (theme.json): each layer = one strip over the wall height per face (z = +-face_offset, nothing in the middle)
sampling its own texture row, which holds several curves; its own repeat (= apparent speed) and direction (u
mirrored). A motif spans `span` pieces (long waves): one model per place in it. 84 vertices = 3 layers x 2 faces x
7 columns x 2 rows. Wall ends: mur_debut / mur_fin_K taper every strip to 0 (no vertex alpha in this shader).

usage: scrollneon.py BUILD_DIR            full build (BUILD_DIR holds copies of amax.bin and the level's actorpack.xt)
       scrollneon.py --models BUILD_DIR   models only (after a theme change: maps untouched)
"""
import json, math, os, re, struct, sys
import config
import neon
import blurmodel_write  # noqa: F401  (puts Map Builder on the path)
import cpmodel  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
TEMPLATE = os.path.join(config.BLUR_EXTRACTED, "root", "models", "objects", "usa_amboy", "misc", "spline_plane.model")
VS0, N0, VS1, FS = 176684, 1429, 205388, 207452          # read from the template (BlurImportExport reader)
MAT1 = 0x3452C
PIECE = 4.0                                               # model length; actors are scaled to their exact piece
COLS, MAXL, ROWS = 7, 3, 3                                # 3 x 2 x 7 x 2 = 84 vertices; texture = 1 row per layer
TEX = 256
SALT = 0x4E50
GROUND = -3.3       # model y of the road under a 3 m wall (origin = wall top); 2026-11-07 user: at the wall ends the
                    # streaks rise out of the ground / sink into it (they used to shrink to the band's middle)
MASK_TEST = False   # 2026-11-06 test: g_tMaterial = the hidden plane's texture (0) holding a mask read with the 2nd
                    # uv set (uv1 = place in the piece, v = the layer's mask row): layer 1 dark -> bright, 2 white, 3 bright -> dark                                             # one texture id for our models (identical texture)
F = r"models\objects\blur_re\%s.model"


def model_set(keys):
    """{key: (GameModel uid, DynamicObjDef uid, file, ...)} for the variants in use: mur_K (K = the piece's place
    from the wall start), mur_debut (first piece, K = 0), mur_fin_K (last piece)"""
    keys = sorted(keys, key=lambda k: (k.startswith("mur_fin"), k == "mur_debut", int(k.rsplit("_", 1)[1]) if k[-1].isdigit() else 0))
    return {key: (0xFFFFFE10 + 2 * i, 0xFFFFFE11 + 2 * i, F % key, None, None, None) for i, key in enumerate(keys)}


def merged(walls):
    """collision walls cut in 31-point chunks (make_reverse WALL_PATHS: a chunk starts on the last point of the
    previous one) joined back: the strips fade only at the real wall ends"""
    out = []
    for w in walls:
        if out and tuple(w[0]) == tuple(out[-1][-1]):
            out[-1] = out[-1] + list(w[1:])
        else:
            out.append(list(w))
    return out


def wall_span(walls):
    """span "auto" (2026-11-06): one motif covers the longest wall, so it never starts again inside a wall (no cut
    where a non-integer repeat wraps; the user's choice over a cut every 12 pieces)"""
    return max(len(neon._stations(w)) for w in walls)


def load_theme():
    t = json.load(open(os.path.join(HERE, "theme.json"), encoding="utf-8"))
    assert len(t["wall"]["layers"]) <= MAXL
    return t


def _smooth(x):
    x = min(1.0, max(0.0, x))
    return x * x * (3 - 2 * x)


def texture(layers):
    """RGBA TEX x TEX, row i (TEX // ROWS px high) = layer i, all its curves; v = across (0 top), u = along (t, the
    way the pattern moves: +t). Curve: centre(t) = centre + amp sin(2 pi (freq t + phase)), soft body of `width`,
    optional thin core; curves blend over each other; everything fades to 0 before the row edges. User's drawing
    (2026-11-06): thin dark-blue lines and wide pale ribbons in long waves crossing over the wall height."""
    rh = TEX // ROWS
    px = bytearray(TEX * TEX * 4)
    for i, layer in enumerate(layers):
        for x in range(TEX):
            s = (x + 0.5) / TEX
            t = 1 - s if layer["direction"] > 0 else s       # mesh u is mirrored the same way (see model_bytes)
            cs = []
            for c in layer["curves"]:
                y0 = c["centre"] + c.get("amp", 0) * math.sin(2 * math.pi * (c.get("freq", 1) * t + c.get("phase", 0)))
                k = 1.0
                if "tail" in c:                              # streak: bright head at `head`, tail fading behind it
                    g = (c["head"] - t) % 1.0
                    if c.get("linear"):                      # opacity 1 at the head -> 0 at the tail end
                        k = max(0.0, 1 - g / c["tail"]) if g < 0.995 else math.exp(-(1 - g) / 0.002)
                    else:
                        k = math.exp(-g / c["tail"]) if g < 0.9 else math.exp(-(1 - g) / 0.012)   # soft nose
                    k = c.get("base", 0.0) + (1 - c.get("base", 0.0)) * k
                cs.append((c, y0, k))
            for yy in range(rh):
                v = (yy + 0.5) / rh
                win = _smooth(min(v, 1 - v) / 0.06)
                keep, rgb = 1.0, [0.0, 0.0, 0.0]
                for c, y0, kk in cs:
                    d = abs(v - y0)
                    body = math.exp(-(d / c["width"]) ** 2)
                    core = math.exp(-(d / (c["width"] * 0.35)) ** 2) * min(1.0, kk * 1.5) if c["core"] else 0.0
                    glow = 0.35 * math.exp(-(d / c["glow"]) ** 2) if c.get("glow") else 0.0
                    a = min(1.0, c["intensity"] * kk * (body * 0.9 + core * 0.5 + glow)) * win
                    col = [c["color"][k] * (1 - core) + (c["core"] or c["color"])[k] * core for k in range(3)]
                    rgb = [rgb[k] * (1 - a) + col[k] * a for k in range(3)]   # 'over' blending, front = last
                    keep *= 1 - a
                al = 1 - keep
                o = ((i * rh + yy) * TEX + x) * 4
                px[o:o + 4] = bytes([int(min(255, rgb[k] / al)) if al > 1e-3 else 0 for k in range(3)] + [int(al * 255)])
    return bytes(px)


def _mask(w, h):
    """MASK_TEST: 3 rows (one per layer), grey levels along u: dark -> bright, white, bright -> dark"""
    out = bytearray()
    for y in range(h):
        row = min(2, y * 3 // h)
        for x in range(w):
            g = (x + 0.5) / w
            g = {0: g, 1: 1.0, 2: 1 - g}[row]
            out += bytes([int(255 * g)] * 3)
    return bytes(out)


def dxt5(px, w, h):
    sys.path.insert(0, os.path.join(config.MAP_BUILDER_DIR, "tex"))
    import dxt
    rgb = bytes(b for i in range(0, len(px), 4) for b in px[i:i + 3])
    col = dxt.dxt1_encode(rgb, w, h)
    out = bytearray()
    for n, (by, bx) in enumerate((by, bx) for by in range(0, h, 4) for bx in range(0, w, 4)):
        al = [px[(min(by + k // 4, h - 1) * w + min(bx + k % 4, w - 1)) * 4 + 3] for k in range(16)]
        a0, a1 = max(al), min(al)
        bits = 0
        if a0 > a1:                                       # 8-level mode: index 0 = a0, 1 = a1, 2..7 between
            pal = [a0, a1] + [((7 - j) * a0 + j * a1) // 7 for j in range(1, 7)]
            for k, a in enumerate(al):
                bits |= min(range(8), key=lambda j: abs(pal[j] - a)) << (3 * k)
        out += bytes([a0, a1]) + bits.to_bytes(6, "little") + col[8 * n:8 * n + 8]
    return bytes(out)


def mips(px, w, n):
    out = bytearray()
    for i in range(n):
        out += dxt5(px, w, w) if w >= 4 else dxt5(_up(px, w), 4, 4)   # mips under 4 px: one 4 x 4 block
        if i < n - 1:
            px, w = _half(px, w), max(w // 2, 1)
    return bytes(out)


def _half(px, w):
    nw = max(w // 2, 1)
    return bytes(sum(px[((2 * y + dy) * w + 2 * x + dx) * 4 + c] for dy in (0, 1) for dx in (0, 1)) // 4
                 for y in range(nw) for x in range(nw) for c in range(4))


def _up(px, w):
    return bytes(px[((y * w // 4) * w + x * w // 4) * 4 + c] for y in range(4) for x in range(4) for c in range(4))


def model_bytes(theme, variant, tex_data):
    """variant: 'mur_K' (K-th piece of a motif), 'mur_debut' (strips grow from 0 at u = 0, K = 0), 'mur_fin_K'
    (strips shrink to 0 at u = 1)"""
    wall = theme["wall"]
    span = wall["span"]
    k_ = 0 if variant == "mur_debut" else int(variant.rsplit("_", 1)[1])
    d = bytearray(open(TEMPLATE, "rb").read())
    for i in range(N0):                                    # hide the plane
        struct.pack_into("<3f", d, VS0 + 20 * i, 0.0, 0.0, 0.0)
    nrm = [bytes(d[VS1 + 12:VS1 + 16]), bytes(d[VS1 + 24 * 42 + 12:VS1 + 24 * 42 + 16])]   # the two faces
    for k in range(84):                                    # unused vertices: one point
        struct.pack_into("<3f", d, VS1 + 24 * k, 0.0, 0.0, 0.0)
    idx = []
    yc, hh = -(wall["top"] + wall["bottom"]) / 2, wall["bottom"] - wall["top"]
    for li, layer in enumerate(wall["layers"]):
        r_ = layer["repeat"]
        v0, v1 = (li + 0.01) / ROWS, (li + 0.99) / ROWS
        for side in range(2):
            base = (li * 2 + side) * 2 * COLS
            for c in range(COLS):
                u = c / (COLS - 1)
                taper = 1.0
                if wall["fade"] and variant == "mur_debut":
                    taper = _smooth(u)
                elif wall["fade"] and variant.startswith("mur_fin"):
                    taper = _smooth(1 - u)
                uu = -layer["direction"] * r_ * (k_ + u) / span     # motif coordinate; minus: the traffic's sense
                for r in range(2):
                    k = base + 2 * c + (r if side == 0 else 1 - r)  # side 1: rows swapped = other winding
                    o = VS1 + 24 * k
                    z = (wall["face_offset"] + 0.012 * li) * (1 if side == 0 else -1)   # layers apart: no z-fight
                    struct.pack_into("<3f", d, o, (u - 0.5) * PIECE, GROUND + (yc - GROUND) * taper + (r - 0.5) * hh * taper, z)
                    d[o + 12:o + 16] = nrm[side]
                    vv = v1 if r == 0 else v0                       # r = 1 is the top: v0 (texture row top)
                    if MASK_TEST:
                        struct.pack_into("<4e", d, o + 16, uu, vv, u, (li + 0.5) / 3)
                    else:
                        struct.pack_into("<4e", d, o + 16, uu, vv, uu, vv)
            strip = list(range(base, base + 2 * COLS))
            idx += ([idx[-1], strip[0]] if idx else []) + strip
    idx += [idx[-1]] * (102 - len(idx))                    # degenerate padding: same index count
    assert len(idx) == 102
    struct.pack_into("<102H", d, FS + 2 * 2630, *idx)
    j = d.find(b"DXT5", re.search(rb"propeller_diffRA", d).end())
    w, h, _, nm = struct.unpack_from("<IIII", d, j - 16)
    assert (w, h, nm) == (TEX, TEX, 9) and len(tex_data) == 87408
    d[j + 12:j + 12 + len(tex_data)] = tex_data
    for name in (b"airplane01_diff", b"propeller_diff"):   # new texture ids (see cpmodel; DefaultColour: none)
        for old in {m.group(1) for m in re.finditer(re.escape(name) + b"(....)RA", d, re.S)}:
            d[:] = bytes(d).replace(old, struct.pack("<I", struct.unpack("<I", old)[0] ^ SALT))
    if MASK_TEST:
        j = d.find(b"DXT1", re.search(rb"airplane01_diffRA", d).end())
        w, h, _, nm = struct.unpack_from("<IIII", d, j - 16)
        assert (w, h, nm) == (512, 256, 10)                  # width first (the reader shows it swapped)
        data = cpmodel.encode_mips(_mask(w, h), w, h, nm)
        assert len(data) == 87400
        d[j + 12:j + 12 + len(data)] = data
    assert struct.unpack_from("<3I", d, MAT1) == (1, 2, 3) and struct.unpack_from("<f", d, MAT1 + 0x2C)[0] == 5.0
    struct.pack_into("<4f", d, MAT1 + 0x2C, theme["speed"], 0.0, 0.0, 0.0)
    if MASK_TEST:
        struct.pack_into("<I", d, MAT1 + 8, 0)                  # g_tMaterial -> texture 0 (the mask)
    assert len(d) == os.path.getsize(TEMPLATE)
    return bytes(d)


def write_models(build, theme, models):
    tex = mips(texture(theme["wall"]["layers"]), TEX, 9)
    for key, (_, _, fname, *_) in models.items():
        data = model_bytes(theme, key, tex)                 # computed before open("wb") truncates the file
        mp = os.path.join(build, fname.replace("\\", os.sep))
        os.makedirs(os.path.dirname(mp), exist_ok=True)
        open(mp, "wb").write(data)


def layout(walls, span):
    """one actor per piece (neon._stations), origin on the wall top, x scaled to the exact piece length (patterns
    run on without a seam); first / last piece of each wall = mur_debut / mur_fin_K, the others mur_K (K = place in the span-piece motif)"""
    out = []
    for w in walls:
        st = neon._stations(w)
        sy = sum(yt - yb for _, yb, yt, _ in w) / len(w) / 4.0     # 3 m walls (4 m incl. 1 m underground) = 1:
        # a higher wall stretches its strips (bands, streaks, halos) instead of needing its own models
        for i, (a, c, e, top, ax) in enumerate(st):
            az = (-ax[2], 0.0, ax[0])
            dy = (e[1] - a[1]) / math.hypot(e[0] - a[0], e[2] - a[2])
            n = math.sqrt(1 + dy * dy)
            s = math.dist(a, e) / PIECE
            tx = (ax[0] / n * s, dy / n * s, ax[2] / n * s)
            ty = (-ax[0] * dy / n * sy, 1 / n * sy, -ax[2] * dy / n * sy)
            key = "mur_debut" if i == 0 else ("mur_fin_%d" if i == len(st) - 1 else "mur_%d") % (i % span)
            out.append((key, (tx, ty, az, (c[0], (a[1] + e[1]) / 2, c[2]))))
    return out


def main(build, models_only=False):
    import make_reverse as mr
    theme = load_theme()
    walls = merged(mr.WALLS[neon.LEVEL])
    if theme["wall"]["span"] == "auto":
        theme["wall"]["span"] = wall_span(walls)
    items = layout(walls, theme["wall"]["span"])
    models = model_set({k for k, _ in items})
    write_models(build, theme, models)
    if models_only:
        print(len(models), "models written in", build, "(span %d)" % theme["wall"]["span"])
        return
    neon.MODELS = models
    am = os.path.join(build, "gamedata", "xt", "amax.bin")
    data = neon.amax_defs(open(am, "rb").read())            # read before open("wb") truncates it
    open(am, "wb").write(data)
    neon.add_actors(os.path.join(build, "gamedata", "levels", neon.LEVEL, "actorpack.xt"), neon.LISTS, items)
    print(len(items), "wall pieces,", len(models), "models, span", theme["wall"]["span"])


if __name__ == "__main__":
    a = sys.argv[1:]
    main(a[-1], models_only="--models" in a)
