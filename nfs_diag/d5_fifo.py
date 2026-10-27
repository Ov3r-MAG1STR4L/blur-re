"""Diagnostic 5 : capture FIFO Dolphin (.dff) -> correspondance matériau -> texture PROUVÉE par le rendu du jeu.

python d5_fifo.py LIEU.stm CAPTURE.dff SORTIE.csv
Le flux GX de l'image est rejoué à la main : registres BP de texture (0x88 TX_SETIMAGE0 = taille/format,
0x94 TX_SETIMAGE3 = adresse >> 5), registres CP de format de sommets (VCD 0x50/0x60, VAT 0x70..0x9F) pour sauter les
dessins directs, et appels de liste (0x40 CALL_DL adresse, taille). Pour chaque appel : les octets de la liste et
les octets de la texture active sont pris dans les mises à jour mémoire de la capture, puis cherchés tels quels
dans le .stm : liste -> sous-maillage (donc id de matériau), texture -> entrée .tex. Rien n'est supposé : une
correspondance n'est retenue que si les deux recherches d'octets réussissent.
DFF (Dolphin, version 6, petit-boutiste, champs u64 alignés sur 4) : en-tête, FileFrameInfo à frameListOffset
(u64 fifo, u32 taille, u32 début, u32 fin, u64 mises à jour, u32 nombre, 32 o), FileMemoryUpdate de 24 o
(u32 position fifo, u32 adresse, u64 données, u32 taille, u8 type, 3 o).
"""
import collections
import csv
import os
import struct
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import stm2obj  # noqa: E402


def read_dff(path):
    d = open(path, "rb").read()
    assert struct.unpack_from("<I", d, 0)[0] == 0x0D01F1F0, "pas un fichier FIFO Dolphin"
    frame_list, frames = struct.unpack_from("<QI", d, 0x3C)
    out = []
    for k in range(frames):
        o = frame_list + k * 64
        fifo_off, fifo_size, _, _, upd_off, nupd = struct.unpack_from("<QIIIQI", d, o)
        ups = [struct.unpack_from("<IIQIB", d, upd_off + 24 * i) for i in range(nupd)]
        mem = [(addr & 0x1FFFFFFF, d[off:off + size], pos) for pos, addr, off, size, typ in ups]
        out.append((d[fifo_off:fifo_off + fifo_size], mem))
    return out


def fetch(mem, addr, size):
    addr &= 0x1FFFFFFF
    for a, data, _ in reversed(mem):
        if a <= addr and addr + size <= a + len(data):
            return data[addr - a:addr - a + size]
    return None


def vertex_size(cp, vat):
    lo, hi = cp.get(0x50, 0), cp.get(0x60, 0)
    a, b, c = cp.get(0x70 + vat, 0), cp.get(0x80 + vat, 0), cp.get(0x90 + vat, 0)
    size = bin(lo & 0x1FF).count("1")                     # matrices d'index (1 o chacun)
    comp = [1, 1, 2, 2, 4]

    def att(kind, direct):
        return 0 if kind == 0 else (direct if kind == 1 else (1 if kind == 2 else 2))
    size += att((lo >> 9) & 3, (3 if a & 1 else 2) * comp[min((a >> 1) & 7, 4)])
    size += att((lo >> 11) & 3, (9 if (a >> 9) & 1 else 3) * comp[min((a >> 10) & 7, 4)])
    for k, sh in ((0, 13), (1, 17)):
        size += att((lo >> (13 + 2 * k)) & 3, [2, 3, 4, 2, 3, 4][min((a >> (sh + 1)) & 7, 5)])
    tex_fields = [(a >> 21) & 0x1FF, b & 0x1FF, (b >> 9) & 0x1FF, (b >> 18) & 0x1FF,
                  ((b >> 27) & 0x1F) | ((c & 0xF) << 5), (c >> 5) & 0x1FF, (c >> 14) & 0x1FF, (c >> 23) & 0x1FF]
    for k in range(8):
        f = tex_fields[k]
        size += att((hi >> (2 * k)) & 3, (2 if f & 1 else 1) * comp[min((f >> 1) & 7, 4)])
    return size


def calls(fifo, dl_index=None):
    """[(adresse liste ou None, octets du dessin direct ou None, adresse texture 0, format, largeur, hauteur)]
    pour chaque CALL_DL et chaque dessin direct dont les 64 premiers octets sont une liste du .stm (Hot Pursuit
    recopie ses listes dans le flux au lieu de les appeler)"""
    cp, bp, out, p = {}, {}, [], 0
    unknown = 0
    while p < len(fifo):
        op = fifo[p]
        if op in (0x00, 0x48):
            p += 1
        elif op == 0x08:
            cp[fifo[p + 1]] = struct.unpack_from(">I", fifo, p + 2)[0]
            p += 6
        elif op == 0x10:
            n = (struct.unpack_from(">I", fifo, p + 1)[0] >> 16) + 1
            p += 5 + 4 * n
        elif op in (0x20, 0x28, 0x30, 0x38):
            p += 5
        elif op == 0x40:
            addr, size = struct.unpack_from(">II", fifo, p + 1)
            t0 = bp.get(0x88, 0)
            out.append((addr, None, (bp.get(0x94, 0) & 0xFFFFFF) << 5, (t0 >> 20) & 0xF, (t0 & 0x3FF) + 1,
                        ((t0 >> 10) & 0x3FF) + 1))
            p += 9
        elif op == 0x61:
            v = struct.unpack_from(">I", fifo, p + 1)[0]
            bp[v >> 24] = v & 0xFFFFFF
            p += 5
        elif op & 0x80:
            if dl_index is not None and fifo[p:p + 64] in dl_index:
                t0 = bp.get(0x88, 0)
                out.append((None, fifo[p:p + 64], (bp.get(0x94, 0) & 0xFFFFFF) << 5, (t0 >> 20) & 0xF,
                            (t0 & 0x3FF) + 1, ((t0 >> 10) & 0x3FF) + 1))
            n = struct.unpack_from(">H", fifo, p + 1)[0]
            p += 3 + n * vertex_size(cp, op & 7)
        else:
            unknown += 1
            p += 1
    return out, unknown


def main(stm, dff, out):
    d = open(stm, "rb").read()
    dl_index = {}
    for t, n, b in stm2obj.entries(d):
        if t not in (6, 7, 8):
            continue
        try:
            subs = stm2obj.submeshes(b)
        except (struct.error, ValueError):
            continue
        for m, o, _ in subs:
            dl_index.setdefault(b[o:o + 64], set()).add((n, m))
    tex_index = {}
    for t, n, b in stm2obj.entries(d):
        if t == 4:
            pix = struct.unpack_from(">I", b, 0x24)[0]
            tex_index[b[pix:pix + 64]] = n
    pairs = collections.Counter()
    seen = found_dl = found_tex = 0
    for fifo, mem in read_dff(dff):
        cl, unknown = calls(fifo, dl_index)
        for addr, inline, taddr, fmt, w, h in cl:
            seen += 1
            dl = inline if inline else fetch(mem, addr, 64)
            tx = fetch(mem, taddr, 64) if taddr else None
            owners = dl_index.get(dl) if dl else None
            tex = tex_index.get(tx) if tx else None
            found_dl += bool(owners)
            found_tex += bool(tex)
            for n, m in owners or ():
                pairs[(m, tex or "?", "%dx%d f%x" % (w, h, fmt))] += 1
    rows = [dict(materiau=hex(m), texture_vue=tex, texture_gx=g, appels=c,
                 texture_attribuee_avant=stm2obj.material_name(d, m) or "")
            for (m, tex, g), c in sorted(pairs.items())]
    with open(out, "w", newline="", encoding="utf-8") as f:
        wr = csv.DictWriter(f, fieldnames=list(rows[0]) if rows else ["materiau"])
        wr.writeheader()
        wr.writerows(rows)
    print(seen, "dessins reconnus ou appels de liste ; listes reconnues", found_dl, "; textures reconnues", found_tex,
          "; octets inconnus du flux", unknown, ";", len(rows), "couples ->", out)


if __name__ == "__main__":
    main(*sys.argv[1:4])
