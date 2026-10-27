"""Diagnostic 4 : nos textures .stm comparées au dump de textures de Dolphin (Hot Pursuit Wii, SNHE69).

python d4_dolphin.py LIEU.stm DOSSIER_DUMP SORTIE.csv
Pour chaque texture du .stm : candidates du dump de même taille (nom Dolphin tex1_LxH_[m_]empreinte_format.png,
niveaux _mipN ignorés), écart moyen (0..255) sur une réduction 32x32 RGB ; la meilleure est gardée.
Écart faible = décodage confirmé et texture réellement chargée par le jeu.
"""
import csv
import os
import re
import struct
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import stm2obj  # noqa: E402

NAME = re.compile(r"tex1_(\d+)x(\d+)_(?:m_)?([0-9a-f]+)(?:_[0-9a-f]+)?_(\d+)\.png$")


def small(img):
    return np.asarray(img.convert("RGB").resize((32, 32), Image.BILINEAR), np.float32)


def main(stm, dump, out):
    by_size = {}
    for f in os.listdir(dump):
        m = NAME.match(f)
        if m and "_mip" not in f:
            by_size.setdefault((int(m.group(1)), int(m.group(2))), []).append(f)
    cache = {}
    d = open(stm, "rb").read()
    rows = []
    for t, n, b in stm2obj.entries(d):
        if t != 4:
            continue
        w, h = struct.unpack_from(">2I", b, 0)
        ours = small(stm2obj.texture_image(d, n))
        best = (999.0, "")
        for f in by_size.get((w, h), []):
            if f not in cache:
                try:
                    cache[f] = small(Image.open(os.path.join(dump, f)))
                except OSError:
                    continue
            e = float(np.abs(cache[f] - ours).mean())
            if e < best[0]:
                best = (e, f)
        rows.append(dict(texture=n, largeur=w, hauteur=h, candidates=len(by_size.get((w, h), [])),
                         ecart=round(best[0], 1), dolphin=best[1]))
    with open(out, "w", newline="", encoding="utf-8") as f:
        wr = csv.DictWriter(f, fieldnames=list(rows[0]))
        wr.writeheader()
        wr.writerows(rows)
    e = np.array([r["ecart"] for r in rows])
    print(len(rows), "textures ; écart < 8 :", int((e < 8).sum()), "; 8-20 :", int(((e >= 8) & (e < 20)).sum()),
          "; >= 20 :", int((e >= 20).sum()))


if __name__ == "__main__":
    main(*sys.argv[1:4])
