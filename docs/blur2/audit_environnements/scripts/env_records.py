"""Audit A : décodage direct (lecture seule) des enregistrements d'environnement Blur 2 X360.

blurxt_be.records() boucle sur environmentalsettings.bin (graphes PostFx) : ici, décodeur plat limité aux types
utiles (champs primitifs, structures en ligne, chaînes sz8, références externes = hash, tableaux = (n, réf)).
Entrées : ../data/<build>/{environmentalsettings,lighting}.bin (copiés par extract_tables.py, ou extraits ici).
Sortie : ../data/<build>/env_records.json
Usage : python -I env_records.py
"""
import json
import os
import struct
import sys

JEUX = r"C:\Users\sanqu\Jeux_WII"
sys.path.insert(0, os.path.join(JEUX, "blur_tools", "x360"))
sys.path.insert(0, os.path.join(JEUX, "blur_tools"))
import blurpak_be  # noqa: E402
import blurxt_be   # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
PAKS = {
    "nov10": os.path.join(JEUX, r"blur_extracted\b2_x360_nov\gamedata.pak"),
    "nov04": os.path.join(JEUX, r"blur_extracted\b2_x360_nov04\!Blur 2 (Nov 04, 2010) [Unreleased]\cache\gamedata.pak"),
    "aug31": None,   # tables en clair dans l'archive, extraites à la main dans ../data/aug31 (7z e, 4 fichiers)
}
TABLES = ("environmentalsettings.bin", "lighting.bin", "amax.bin", "enviroment_animations.bin", "tracks.bin",
          "tracks_archive.bin", "shaders.bin")
rot = blurxt_be.rot


class Flat(blurxt_be.XT):
    def setup(self):
        ts, fs = self.types(), self.fields()
        self.ts, self.tn = ts, [self.name(t[0]) for t in ts]
        self.flds, ff = [], 0
        for no, nf, base, kind, prim, size in ts:
            self.flds.append(fs[ff:ff + nf] if kind in (1, 2, 3) else [])
            ff += nf if kind in (1, 2, 3) else 0
        parents = iter(rot(struct.unpack(">I", e)[0]) for e in self.section(1, 4))
        self.parent = [next(parents) if t[2] else None for t in ts]
        self.ix = self.index()

    def val(self, t, o, fl, d, s, depth=0):
        fl = ((fl & 0xFF) << 8) | (fl >> 8)              # X360 : u16 de drapeaux aux octets inversés (0x300 = 3)
        low = fl & 0xFF
        kind, prim = self.ts[t][3], self.ts[t][4]
        if fl & 0x100:                                   # tableau : (réf chunk|début, n)
            ref, n = struct.unpack_from(">II", d, o)
            return {"_tableau": n}
        if low == 3 or (low == 0 and kind == 3):
            return self.struct(t, o, d, s, depth + 1)
        u = struct.unpack_from(">I", d, o)[0]
        if low in (4, 5) and u == 0xFFFFFFFF:
            return None
        if low == 4:
            return f"->{u:#x}"
        if low == 5:
            return f"@{self.ix[u][0]:08x}" if u < len(self.ix) else f"ref:{u:#x}"
        if low == 1 or kind == 1:
            ev = self.flds[t]
            return self.name(ev[u][0]) if u < len(ev) else u
        if kind == 2:
            return [self.name(e[0]) for n, e in enumerate(self.flds[t]) if u >> n & 1]
        if prim == 12:
            return s[u:s.index(b"\0", u)].decode("latin-1") if u < len(s) else None
        if prim == 1:
            return bool(u)
        if prim == 10:
            return round(struct.unpack_from(">f", d, o)[0], 6)
        return u

    def struct(self, t, o, d, s, depth=0):
        if depth > 6:
            return "<prof>"
        out = {}
        if self.parent[t] is not None:
            out.update(self.struct(self.parent[t], o, d, s, depth))
        for no, ft, fo, fl in self.flds[t]:
            out[self.name(no)] = self.val(ft, o + fo, fl, d, s, depth)
        return out

    def recs(self):
        self.setup()
        chunks = [struct.unpack(">3H", e) for e in self.section(6, 6)]
        hash_of = {i: h for h, t, i in self.ix if i != 0xFFFF}
        data, p, c = self.data, 0, 0
        for k, (idx, nch, dsize, ssize) in enumerate(self.items()):
            t0 = chunks[c][0]
            c += nch
            s = blurxt_be.decode_names(data[p + dsize:p + dsize + ssize]) if ssize else b""
            v = self.struct(t0, p, data, s)
            yield k, f"{hash_of.get(k, 0):08x}", self.tn[t0], v
            p += dsize + ssize


def main():
    for build, pak in PAKS.items():
        out = os.path.join(HERE, "..", "data", build)
        os.makedirs(out, exist_ok=True)
        P = blurpak_be.Pak(pak) if pak else None
        for e in (P.files if P else []):
            n = os.path.basename(e.path.replace("\\", "/")).lower()
            if n in TABLES and not os.path.exists(os.path.join(out, n)):
                open(os.path.join(out, n), "wb").write(P.read(e))
        tables = [n for n in TABLES if os.path.exists(os.path.join(out, n))]
        res = {}
        for n in tables:
            x = Flat(os.path.join(out, n))
            recs = {}
            for k, h, tname, v in x.recs():
                recs.setdefault(tname, []).append({"item": k, "hash": h, **v})
            res[n] = recs
            print(build, n, {t: len(v) for t, v in recs.items()})
        json.dump(res, open(os.path.join(out, "env_records.json"), "w", encoding="utf-8"), indent=1,
                  ensure_ascii=False)


if __name__ == "__main__":
    main()
