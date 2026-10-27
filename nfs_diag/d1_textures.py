"""Diagnostic 1 : catalogue des textures d'un .stm Hot Pursuit Wii (planche de contact + CSV).

python d1_textures.py LIEU.stm DOSSIER_SORTIE
Pour chaque entrée .tex (type 4) : n° d'entrée, rang parmi les .tex, rang dans la table de noms du .pvs, nom,
dimensions, format, mips, taille palette, offsets, et un contrôle du décodage (taille attendue, image non uniforme).
"""
import csv
import os
import struct
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import stm2obj  # noqa: E402
from PIL import Image, ImageDraw  # noqa: E402

FORMATS = {0xFB: "CMPR", 5: "C8"}


def level_bytes(fmt, w, h):
    return w * h // 2 if fmt == 0xFB else w * h


def main(stm, out):
    os.makedirs(out, exist_ok=True)
    d = open(stm, "rb").read()
    table = [t.lower() for t in stm2obj.texture_table(d)]
    rows, thumbs = [], []
    k = 0
    for i, (t, n, b) in enumerate(stm2obj.entries(d)):
        if t != 4:
            continue
        w, h, _, _, mips, fmt, pal_fmt, pal, _, pix, poff = struct.unpack_from(">11I", b, 0)
        rank = next((j for j, x in enumerate(table) if x == n.lower() or (len(n) >= 26 and x.startswith(n.lower()))),
                    "")
        need = pix + level_bytes(fmt, w, h)
        status, img = "ok", None
        try:
            img = stm2obj.texture_image(d, n)
            ext = img.convert("L").getextrema()
            if ext[0] == ext[1]:
                status = "uniforme"
        except Exception as ex:  # noqa: BLE001 - noté dans le CSV
            status = "erreur: %s" % ex
        if need > len(b):
            status += " / données trop courtes"
        rows.append(dict(entree=i, rang_tex=k, rang_table_pvs=rank, nom=n, largeur=w, hauteur=h,
                         format=FORMATS.get(fmt, hex(fmt)), mips=mips, format_palette=hex(pal_fmt), taille_palette=pal,
                         offset_pixels=hex(pix), offset_palette=hex(poff), octets=len(b), decodage=status))
        thumbs.append((k, i, rank, n, w, h, FORMATS.get(fmt, hex(fmt)), img))
        k += 1
    with open(os.path.join(out, "textures.csv"), "w", newline="", encoding="utf-8") as f:
        wr = csv.DictWriter(f, fieldnames=list(rows[0]))
        wr.writeheader()
        wr.writerows(rows)
    T, per, cols = 128, 48, 8
    for page in range(0, len(thumbs), per):
        part = thumbs[page:page + per]
        sheet = Image.new("RGB", (cols * (T + 8), ((len(part) + cols - 1) // cols) * (T + 40)), "white")
        dr = ImageDraw.Draw(sheet)
        for j, (k, i, rank, n, w, h, fmt, img) in enumerate(part):
            x, y = (j % cols) * (T + 8), (j // cols) * (T + 40)
            if img is not None:
                sheet.paste(img.convert("RGB").resize((T, T)), (x, y))
            dr.text((x, y + T + 1), "tex%d e%d p%s" % (k, i, rank), fill="black")
            dr.text((x, y + T + 13), n[:21], fill="black")
            dr.text((x, y + T + 25), "%dx%d %s" % (w, h, fmt), fill="blue")
        sheet.save(os.path.join(out, "textures_%02d.png" % (page // per)))
    bad = [r for r in rows if r["decodage"] != "ok"]
    print(len(rows), "textures,", len(bad), "à vérifier :", [(r["nom"], r["decodage"]) for r in bad][:10])


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
