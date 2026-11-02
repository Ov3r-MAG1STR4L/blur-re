"""Diagnostic P1 (lecture seule) : décodage du .stm de Dubaï par stm2obj, tel que l'utilisent NFS Studio et nfs_atlas.
usage : python p1_diag.py BLUR_TOOLS STM"""
import collections
import struct
import sys

import numpy as np

sys.path.insert(0, sys.argv[1])
import stm2obj as S  # noqa: E402

d = open(sys.argv[2], "rb").read()
ents = list(S.entries(d))
print("types d'entrées :", dict(collections.Counter(t for t, _, _ in ents)))

fail = collections.Counter()
failed_names = []
smalls = collections.Counter()
stop_ops = collections.Counter()
oob_pos = oob_uv = 0
tris = 0
spikes = []
meshes = 0
for t, n, b in ents:
    if t != 6:
        continue
    meshes += 1
    try:
        vb = struct.unpack_from(">I", b, 0x14)[0]
        smalls[bytes(b[vb + 12:vb + 15]).hex()] += 1
        pos, uvs, faces = S.mesh(b)
    except Exception as e:  # même attrape que nfs_web.export / nfs_atlas.jobs
        fail[type(e).__name__] += 1
        failed_names.append(n)
        continue
    # arrêt du décodage GX sur un opcode inconnu avant la fin de la liste
    subs = S.submeshes(b)
    ends = sorted({o for _, o, _ in subs}) + [vb]
    for _, p in sorted({(m, o) for m, o, _ in subs}, key=lambda x: x[1]):
        end = ends[ends.index(p) + 1]
        q = p
        sizes = [1 if s else 2 for s in b[vb + 12:vb + 15]]
        while q < end:
            op = b[q]
            if op == 0:
                q += 1
                continue
            if op not in (0x90, 0x98, 0xA0):
                stop_ops["%02x" % op] += 1
                break
            cnt = struct.unpack_from(">H", b, q + 1)[0]
            q += 3 + cnt * sum(sizes)
    P = np.array(pos) if pos else np.zeros((0, 3))
    if not len(P):
        continue
    ext = float(np.linalg.norm(P.max(0) - P.min(0))) or 1
    for f in faces:
        tris += 1
        if max(a for a, _ in f) >= len(pos):
            oob_pos += 1
            continue
        if max(c for _, c in f) >= len(uvs):
            oob_uv += 1
        v = P[[a for a, _ in f]]
        e = max(np.linalg.norm(v[0] - v[1]), np.linalg.norm(v[1] - v[2]), np.linalg.norm(v[2] - v[0]))
        area = np.linalg.norm(np.cross(v[1] - v[0], v[2] - v[0])) / 2
        if e > 0.5 * ext and e > 30 and area < 0.02 * e * e:   # long et fin : « éclat »
            spikes.append((n, round(float(e), 1)))

print("maillages type 6 :", meshes, "; abandonnés (trou entier) :", sum(fail.values()), dict(fail))
print("  exemples :", failed_names[:12])
print("formats d'index (pos, normale, uv ; 00=u16, sinon u8) :", dict(smalls))
print("listes GX coupées par un opcode inconnu :", dict(stop_ops))
print("triangles :", tris, "; index position hors limites :", oob_pos, "; index UV hors limites (UV écrêtée) :", oob_uv)
print("triangles longs et fins (éclats probables) :", len(spikes), collections.Counter(n for n, _ in spikes).most_common(10))

# textures : part des pixels sous le seuil alphaTest 0.3 de NFS Studio
mats = S.materials(d)
used = collections.Counter()
for t, n, b in ents:
    if t != 6:
        continue
    try:
        for m, _, _ in S.submeshes(b):
            used[m] += 1
    except Exception:
        pass
cut = []
for m in used:
    tex = S.material_name(d, m)
    if not tex:
        continue
    try:
        a = np.asarray(S.texture_image(d, tex))[:, :, 3]
    except Exception as e:
        cut.append((m, mats.get(m, ("?",))[0], tex, "ERREUR " + type(e).__name__))
        continue
    frac = float((a < 0.3 * 255).mean())
    if frac > 0.02:
        cut.append((m, mats.get(m, ("?",))[0], tex, round(frac, 2)))
print("matériaux dont la texture est trouée par alphaTest 0.3 (> 2 % des pixels) :", len(cut), "sur", len(used))
for c in sorted(cut, key=lambda c: str(c[3]))[:60]:
    print("  ", c)
