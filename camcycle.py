"""Caméras d'intro des circuits (.cycle, root.pak animations/cameras/) : lecture, pour l'aperçu dans Reverse Studio.

Format (version 15, 3 os AftkRoot / camera / camera.fov) décrit par Blur Map Builder (MDPRO, MIT,
flat_earth/intro_cam.py, qui ne fait que les écrire) :
  en-tête 0xCD o (u32 images en 0x5C, f32 dernière image 0x60, f32 images/s 0x64), u16 2, table 10 x u16, u16 0x30, puis
  1re image : position 3 f32, fov f32, rotation 6 o
  u32 nb positions, u16 nb fov, u16 nb rotations, u32 0
  3 listes u8 nombre + u8 numéros d'image (positions, fov, rotations)
  les clés (3 f32 / f32 / 6 o), dernière image : position, fov, rotation
Rotation = quaternion 48 bits ; la caméra regarde selon son +z, +y en haut ; fov en radians.
Une route d'origine désigne ses caméras : Route.VistaCameraSequence / PackCameraSequence* -> AnimatedCameraSequence
{Animation, StageTime} -> CycleResourceDef.FilenameMinusExt.

python camcycle.py      relit tous les fichiers de caméra extraits et vérifie qu'ils se lisent jusqu'au bout
"""
import glob, json, math, os, struct

E = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "blur_extracted")
R = 0.70710677
SLOTS = ((1, 2, 3), (2, 3, 0), (3, 0, 1), (0, 1, 2))
HEAD = 0xCD + 24


def quat(rb):
    w0, w1, w2 = struct.unpack("<3H", rb)
    v = (w0 << 32) | (w1 << 16) | w2
    sign, idx = v & 1, (v >> 1) & 3
    vals = [(((v >> sh) & 0x7FFF) * 2.0 / 32767 - 1.0) * R for sh in (3, 18, 33)]
    q = [0.0] * 4
    for s, x in zip(SLOTS[idx], vals):
        q[s] = x
    big = math.sqrt(max(0.0, 1.0 - sum(x * x for x in vals)))
    q[idx] = -big if sign else big
    return q                                   # (x, y, z, w)


def read(b):
    """{fps, frames: [{pos, quat, fov}] une par image (clés interpolées linéairement)}"""
    n, _, fps = struct.unpack_from("<Iff", b, 0x5C)
    o = HEAD

    def full(o):
        p = struct.unpack_from("<3f", b, o)
        return o + 22, (list(p), struct.unpack_from("<f", b, o + 12)[0], quat(b[o + 16:o + 22]))
    o, first = full(o)
    npos, nfov, nrot, _ = struct.unpack_from("<IHHI", b, o)
    o += 12
    lists = []
    for _ in range(3):
        c = b[o]
        lists.append(list(b[o + 1:o + 1 + c]))
        o += 1 + c
    assert [len(x) for x in lists] == [npos, nfov, nrot], "listes de clés incohérentes"
    pos = [struct.unpack_from("<3f", b, o + 12 * i) for i in range(npos)]
    o += 12 * npos
    fov = [struct.unpack_from("<f", b, o + 4 * i)[0] for i in range(nfov)]
    o += 4 * nfov
    rot = [quat(b[o + 6 * i:o + 6 * i + 6]) for i in range(nrot)]
    o += 6 * nrot
    o, last = full(o)
    assert o <= len(b), "fichier trop court"
    L = n - 1
    keys = [[(0, first[0])] + list(zip(lists[0], map(list, pos))) + [(L, last[0])],
            [(0, first[1])] + list(zip(lists[1], fov)) + [(L, last[1])],
            [(0, first[2])] + list(zip(lists[2], rot)) + [(L, last[2])]]

    def at(ks, f, lerp):
        for (f0, v0), (f1, v1) in zip(ks, ks[1:]):
            if f0 <= f <= f1:
                return lerp(v0, v1, 0 if f1 == f0 else (f - f0) / (f1 - f0))
        return ks[-1][1]
    num = lambda a, c, t: a + (c - a) * t
    vec = lambda a, c, t: [num(x, y, t) for x, y in zip(a, c)]

    def slerp(a, c, t):                        # nlerp sur le plus court chemin : assez juste entre clés proches
        if sum(x * y for x, y in zip(a, c)) < 0:
            c = [-x for x in c]
        q = vec(a, c, t)
        ln = math.sqrt(sum(x * x for x in q)) or 1
        return [x / ln for x in q]
    return dict(fps=fps, frames=[dict(pos=at(keys[0], f, vec), fov=at(keys[1], f, num), quat=at(keys[2], f, slerp))
                                 for f in range(n)])


# ---------- écriture : reprise telle quelle de Blur Map Builder (MDPRO, MIT, flat_earth/intro_cam.py) ----------
TEMPLATE_HEAD = bytes.fromhex(
    "0f000000000000000000000000000000000000000000803f0000000000000000000000000000803f0000803f0000803f00000000"
    "00000000000000000000803f0000000000000000000000000000803f0000803f0000803f00000000690000000000d0420000f041"
    "0300000000000303000000080000004166746b526f6f740600000063616d6572610a00000063616d6572612e666f760200030001"
    "00000001000100000001000100000000000100000041008300400012000000000000000000000000000000fe7ffdfffeff")
FPS = 30.0
SHOT_FRAMES = {"vista": 180, "pack": 105}     # images des plans du jeu (4,5 s / 3,5 s à 30 i/s)
FOV = 0.9


def quat_encode(q):
    """6 bytes of quaternion q = (x, y, z, w)"""
    n = math.sqrt(sum(x * x for x in q)) or 1.0
    q = [x / n for x in q]
    idx = max(range(4), key=lambda k: abs(q[k]))
    v = (1 if q[idx] < 0 else 0) | (idx << 1)
    for s, sh in zip(SLOTS[idx], (3, 18, 33)):
        x = max(-R, min(R, q[s]))
        v |= max(0, min(0x7FFF, int(round((x / R + 1.0) * 32767 / 2.0)))) << sh
    return struct.pack("<3H", (v >> 32) & 0xFFFF, (v >> 16) & 0xFFFF, v & 0xFFFF)


def look_quat(eye, target):
    """(x, y, z, w) turning the camera's +z towards target, no roll (+y stays up)"""
    fx, fy, fz = (target[k] - eye[k] for k in range(3))
    ln = math.sqrt(fx * fx + fy * fy + fz * fz) or 1.0
    yaw = math.atan2(fx, fz)
    pitch = math.asin(max(-1.0, min(1.0, fy / ln)))
    cy, sy = math.cos(yaw / 2), math.sin(yaw / 2)
    cp, sp = math.cos(-pitch / 2), math.sin(-pitch / 2)
    return (cy * sp, sy * cp, -sy * sp, cy * cp)


def table_size(npos, nfov, nrot):
    return (37 + 13 * npos + 5 * nfov + (6 * nrot + 3) // 4 * 4 + nrot + 15) // 16 * 16


def write_cycle(frames, rot_every=2, fov_keys=(), fps=FPS):
    """.cycle bytes: frames = [(position (x, y, z), quaternion (x, y, z, w), fov)] one per frame (2..255)"""
    n = len(frames)
    assert 2 <= n <= 255, n
    last = n - 1
    inner = list(range(1, last))
    pos_f = inner
    rot_f = [f for f in inner if f % rot_every == 0]
    fov_f = [f for f in fov_keys if 0 < f < last] or [last // 2]
    body = bytearray()

    def full(f):
        p, q, fov = frames[f]
        return struct.pack("<3ff", p[0], p[1], p[2], fov) + quat_encode(q)
    body += full(0)
    body += struct.pack("<IHHI", len(pos_f), len(fov_f), len(rot_f), 0)
    for lst in (pos_f, fov_f, rot_f):
        body += bytes([len(lst)] + lst)
    for f in pos_f:
        body += struct.pack("<3f", *frames[f][0])
    for f in fov_f:
        body += struct.pack("<f", frames[f][2])
    for f in rot_f:
        body += quat_encode(frames[f][1])
    body += full(last)
    b = table_size(len(pos_f), len(fov_f), len(rot_f))
    head = bytearray(TEMPLATE_HEAD)
    struct.pack_into("<Iff", head, 0x5C, n, float(last), fps)
    table = struct.pack("<H10HH", 2, 0, b + 0x30, 0, 0, 0, last, b, last, 0, 0, 0x30)
    return bytes(head) + table + bytes(body)


def _smooth(t):
    return t * t * (3 - 2 * t)


def _catmull(p0, p1, p2, p3, t):
    t2, t3 = t * t, t * t * t
    return tuple(0.5 * (2 * p1[k] + (p2[k] - p0[k]) * t + (2 * p0[k] - 5 * p1[k] + 4 * p2[k] - p3[k]) * t2 +
                        (3 * p1[k] - p0[k] - 3 * p2[k] + p3[k]) * t3) for k in range(3))


def keyed_frames(views, n):
    """n images passant en douceur par les points de vue {eye, look} (un seul = plan fixe)"""
    eyes = [tuple(v["eye"]) for v in views]
    looks = [tuple(v["look"]) for v in views]
    out = []
    for f in range(n):
        if len(views) == 1:
            eye, look = eyes[0], looks[0]
        else:
            u = _smooth(f / (n - 1)) * (len(views) - 1)
            i = min(int(u), len(views) - 2)
            t = u - i

            def at(ps):
                return _catmull(ps[max(i - 1, 0)], ps[i], ps[i + 1], ps[min(i + 2, len(ps) - 1)], t)
            eye, look = at(eyes), at(looks)
        out.append((eye, look_quat(eye, look), FOV))
    return out


def own_cycles(cams):
    """{"vista": bytes, "pack": bytes} des plans définis dans Reverse Studio ({plan: [{eye, look}, ...]})"""
    return {shot: write_cycle(keyed_frames(views, SHOT_FRAMES[shot]))
            for shot, views in cams.items() if views and shot in SHOT_FRAMES}


def route_shots(orig):
    """Caméras d'intro d'une route du jeu : ([{field, file, stage, fps, frames}], [fichiers non lus]) ; .cycle extraits
    de root.pak. Le jeu montre le survol puis le plan de grille (en course perso : PackCameraSequenceMP)."""
    a = json.load(open(os.path.join(E, "xt_json", "amax.json")))
    r, out, seen, unread = a["Route"][orig], [], set(), []
    for field in ("VistaCameraSequence", "PackCameraSequenceMP", "PackCameraSequence"):
        ref = r.get(field)
        if not ref or ref in seen:
            continue
        seen.add(ref)
        seq = a["AnimatedCameraSequence"][ref.split("/")[-1]]
        f = a["CycleResourceDef"][seq["Animation"].split("/")[-1]]["FilenameMinusExt"]
        path = os.path.join(E, "root", *f.split("/")) + ".cycle"
        try:
            out.append(dict(field=field, file=f, stage=seq["StageTime"], **read(open(path, "rb").read())))
        except Exception:  # noqa: BLE001  (72 des 171 fichiers ont une autre disposition : pas encore lue)
            unread.append(f.split("/")[-1])
    return out, unread


if __name__ == "__main__":
    files = glob.glob(os.path.join(E, "root", "animations", "cameras", "*.cycle"))
    bad = []
    for p in files:
        try:
            read(open(p, "rb").read())
        except Exception as ex:  # noqa: BLE001
            bad.append((os.path.basename(p), ex))
    print(len(files) - len(bad), "/", len(files), "fichiers lus")
    for x in bad[:10]:
        print(" ", *x)
    for s in route_shots("USA_NY_Dumbo_2")[0]:
        f = s["frames"]
        print(s["field"], s["file"], s["stage"], "s,", len(f), "images, début", [round(v) for v in f[0]["pos"]],
              "fin", [round(v) for v in f[-1]["pos"]])
