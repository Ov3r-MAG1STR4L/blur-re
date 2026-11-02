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
