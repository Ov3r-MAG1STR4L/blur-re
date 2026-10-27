"""Diagnostic 2 : audit des matériaux d'un .stm Hot Pursuit Wii (CSV).

python d2_materiaux.py LIEU.stm DOSSIER_SORTIE
- materiaux.csv : un matériau par ligne : id, nb de sous-maillages / triangles / maillages, part de faces plates et
  verticales, étendue des UV, texture attribuée aujourd'hui (stm2obj.material_name), et (fiche n° m - 1),
  l'offset de la fiche dans le .pvs, son nom, les 8 u32 de l'en-tête (+0x40) et, par emplacement, le nom lu et
  les 8 u32 de paramètres.
- sousmaillages.csv : chaque sous-maillage (maillage, offset de l'entrée de nœud, id, offset de la liste GX, n).
"""
import collections
import csv
import os
import struct
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import stm2obj  # noqa: E402


def submesh_entries(b):
    """comme stm2obj.submeshes, avec l'offset de l'entrée de 16 o"""
    vb = struct.unpack_from(">I", b, 0x14)[0]
    out, o, first = [], 0x40, vb
    while o + 16 <= first:
        w = struct.unpack_from(">4I", b, o)
        if w[0] == 0 and w[1] & 0xFFFF == 0 and 0x40 < w[2] < vb and b[w[2]] in (0x90, 0x98, 0xA0) and 0 < w[3] < 5000:
            out.append((o, w[1] >> 16, w[2], w[3]))
            first = min(first, w[2])
            o += 16
        else:
            o += 4
    return out


def main(stm, out):
    os.makedirs(out, exist_ok=True)
    d = open(stm, "rb").read()
    pvs = next(b for t, n, b in stm2obj.entries(d) if t == 1)
    pvs_at = d.find(pvs[:256])
    first = pvs.find(bytes.fromhex("0000411cdcdd0000")) - 0x40 - 0x160     # fiche 0 (sans nom)
    stats = collections.defaultdict(lambda: dict(sous=0, tris=0, maillages=set(), plat=0, vert=0, umin=9e9, umax=-9e9,
                                                 vmin=9e9, vmax=-9e9))
    subrows = []
    for t, n, b in stm2obj.entries(d):
        if t not in (6, 7, 8):
            continue
        try:
            for o, m, dl, cnt in submesh_entries(b):
                subrows.append(dict(maillage=n, lod=t - 5, offset_entree=hex(o), materiau=hex(m), offset_gx=hex(dl),
                                    n=cnt))
            if t != 6:
                continue
            pos, uvs, _ = stm2obj.mesh(b)
            P, U = np.array(pos), np.array(uvs)
            for m in {s[0] for s in stm2obj.submeshes(b)}:
                s = stats[m]
                s["sous"] += 1
                s["maillages"].add(n)
                for f in stm2obj.mesh(b, m)[2]:
                    a = [x for x, _ in f]
                    c = [y for _, y in f]
                    nn = np.cross(P[a[1]] - P[a[0]], P[a[2]] - P[a[0]])
                    ln = np.linalg.norm(nn)
                    s["tris"] += 1
                    if ln:
                        s["plat"] += abs(nn[1]) / ln > 0.9
                        s["vert"] += abs(nn[1]) / ln < 0.3
                    uv = U[c]
                    s["umin"], s["umax"] = min(s["umin"], uv[:, 0].min()), max(s["umax"], uv[:, 0].max())
                    s["vmin"], s["vmax"] = min(s["vmin"], uv[:, 1].min()), max(s["vmax"], uv[:, 1].max())
        except (struct.error, ValueError, IndexError):
            continue
    rows = []
    for m in sorted(stats):
        s = stats[m]
        r = dict(materiau=hex(m), sous_maillages=s["sous"], triangles=s["tris"], maillages=len(s["maillages"]),
                 exemple=sorted(s["maillages"])[0], plat="%.2f" % (s["plat"] / max(1, s["tris"])),
                 vertical="%.2f" % (s["vert"] / max(1, s["tris"])),
                 u="%.2f..%.2f" % (s["umin"], s["umax"]), v="%.2f..%.2f" % (s["vmin"], s["vmax"]),
                 texture_attribuee=stm2obj.material_name(d, m) or "")
        if m >= 1:
            o = first + (m - 1) * 0x160                                       # matériau m = fiche m - 1
            r["fiche_offset_pvs"] = hex(o)
            r["fiche_offset_fichier"] = hex(pvs_at + o)
            r["fiche_nom"] = pvs[o:o + 0x40].split(b"\0")[0].decode("latin1", "replace")
            r["entete"] = " ".join("%08x" % v for v in struct.unpack_from(">8I", pvs, o + 0x40))
            for k in range(4):
                so = o + 0x60 + k * 0x40
                r["empl%d_nom" % k] = pvs[so + 1:so + 0x20].split(b"\0")[0].decode("latin1", "replace")
                r["empl%d_brut" % k] = pvs[so:so + 4].hex()
                r["empl%d_params" % k] = " ".join("%08x" % v for v in struct.unpack_from(">8I", pvs, so + 0x20))
        rows.append(r)
    keys = list(dict.fromkeys(k for r in rows for k in r))
    with open(os.path.join(out, "materiaux.csv"), "w", newline="", encoding="utf-8") as f:
        wr = csv.DictWriter(f, fieldnames=keys)
        wr.writeheader()
        wr.writerows(rows)
    with open(os.path.join(out, "sousmaillages.csv"), "w", newline="", encoding="utf-8") as f:
        wr = csv.DictWriter(f, fieldnames=list(subrows[0]))
        wr.writeheader()
        wr.writerows(subrows)
    print(len(rows), "matériaux,", len(subrows), "sous-maillages ; fiches à partir de", hex(first), "dans le .pvs")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
