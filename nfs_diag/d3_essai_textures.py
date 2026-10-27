"""Diagnostic 3 : même géométrie + mêmes UV, plusieurs textures candidates -> planche de comparaison.

python d3_essai_textures.py LIEU.stm MAILLAGE MATERIAU_HEX SORTIE.png [texture.tex ...]
Sans textures données : candidates = table du .pvs autour de l'index MATERIAU (-3..+3), texture attribuée
aujourd'hui, et ordre alphabétique des .tex autour du même rang. Rendu logiciel simple (z-buffer, couleur
échantillonnée par pixel aux UV interpolés), vue de face selon la normale moyenne.
"""
import os
import sys

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import stm2obj  # noqa: E402

W = H = 256


def render(P, UV, tris, tex):
    """projection orthographique sur le plan perpendiculaire à la direction moyenne des normales (vue de face)"""
    N = np.array([np.cross(P[b] - P[a], P[c] - P[a]) for a, b, c in tris])
    area = np.linalg.norm(N, axis=1)
    N = N / np.maximum(area, 1e-9)[:, None]
    # direction de façade la plus représentée (pondérée par l'aire) ; seules les faces tournées vers elle
    best = max(range(len(N)), key=lambda i: (area * (N @ N[i] > 0.9)).sum())
    n = N[best]
    c0 = P[list(tris[best])].mean(0)
    tris = [t for t, k in zip(tris, N @ n) if k > 0.7 and np.linalg.norm(P[list(t)].mean(0) - c0) < 40]
    up = np.array([0.0, 1.0, 0.0]) if abs(n[1]) < 0.9 else np.array([0.0, 0.0, 1.0])
    x = np.cross(up, n)
    x /= np.linalg.norm(x)
    y = np.cross(n, x)
    Q = np.c_[P @ x, P @ y, P @ n]
    lo, hi = Q[:, :2].min(0), Q[:, :2].max(0)
    s = (min(W, H) - 8) / max(hi - lo)
    S = (Q[:, :2] - lo) * s + 4
    S[:, 1] = H - S[:, 1]
    img = np.full((H, W, 3), 255, np.uint8)
    zb = np.full((H, W), -1e9)
    T = np.asarray(tex.convert("RGB"))
    th, tw = T.shape[:2]
    for a, b, c in tris:
        p = S[[a, b, c]]
        x0, y0 = np.floor(p.min(0)).astype(int)
        x1, y1 = np.ceil(p.max(0)).astype(int)
        x0, y0, x1, y1 = max(x0, 0), max(y0, 0), min(x1, W - 1), min(y1, H - 1)
        if x1 < x0 or y1 < y0:
            continue
        gx, gy = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
        d = (p[1, 1] - p[2, 1]) * (p[0, 0] - p[2, 0]) + (p[2, 0] - p[1, 0]) * (p[0, 1] - p[2, 1])
        if abs(d) < 1e-9:
            continue
        l0 = ((p[1, 1] - p[2, 1]) * (gx - p[2, 0]) + (p[2, 0] - p[1, 0]) * (gy - p[2, 1])) / d
        l1 = ((p[2, 1] - p[0, 1]) * (gx - p[2, 0]) + (p[0, 0] - p[2, 0]) * (gy - p[2, 1])) / d
        l2 = 1 - l0 - l1
        m = (l0 >= 0) & (l1 >= 0) & (l2 >= 0)
        z = l0 * Q[a, 2] + l1 * Q[b, 2] + l2 * Q[c, 2]
        u = l0 * UV[a, 0] + l1 * UV[b, 0] + l2 * UV[c, 0]
        v = l0 * UV[a, 1] + l1 * UV[b, 1] + l2 * UV[c, 1]
        tx = (np.floor(u % 1 * tw)).astype(int) % tw
        ty = (np.floor((1 - v) % 1 * th)).astype(int) % th
        yy, xx = gy.astype(int), gx.astype(int)
        m &= z > zb[yy, xx]
        zb[yy[m], xx[m]] = z[m]
        img[yy[m], xx[m]] = T[ty[m], tx[m]]
    return Image.fromarray(img)


def main(stm, mesh_name, mat, out, cands):
    d = open(stm, "rb").read()
    b = next(b for t, n, b in stm2obj.entries(d) if t == 6 and n == mesh_name)
    pos, uvs, faces = stm2obj.mesh(b, mat)
    tris, P, UV = [], [], []
    for f in faces:
        ids = []
        for a, c in f:
            ids.append(len(P))
            P.append(pos[a])
            UV.append(uvs[c])
        tris.append(ids)
    P, UV = np.array(P), np.array(UV)
    tex_entries = [n for t, n, _ in stm2obj.entries(d) if t == 4]
    if not cands:
        table = stm2obj.texture_table(d)

        def entry(name):
            n = name.lower()
            return next((e for e in tex_entries if e.lower() == n or (len(e) >= 26 and n.startswith(e.lower()))), None)
        cands = [("actuelle", stm2obj.material_name(d, mat))]
        cands += [("table %+d" % k, entry(table[mat + k])) for k in range(-3, 4) if 0 <= mat + k < len(table)]
        cands += [("alpha %+d" % k, tex_entries[mat + k]) for k in (-1, 0, 1) if 0 <= mat + k < len(tex_entries)]
    else:
        cands = [(c, c) for c in cands]
    tiles = []
    for label, name in cands:
        if not name:
            continue
        tiles.append((label, name, render(P, UV, tris, stm2obj.texture_image(d, name))))
    sheet = Image.new("RGB", (len(tiles) * (W + 6), H + 30), "white")
    dr = ImageDraw.Draw(sheet)
    for k, (label, name, im) in enumerate(tiles):
        sheet.paste(im, (k * (W + 6), 0))
        dr.text((k * (W + 6), H + 2), label, fill="black")
        dr.text((k * (W + 6), H + 15), name[:30], fill="blue")
    sheet.save(out)
    print(mesh_name, hex(mat), len(tris), "triangles ->", out)


if __name__ == "__main__":
    a = sys.argv
    main(a[1], a[2], int(a[3], 16), a[4], a[5:])
