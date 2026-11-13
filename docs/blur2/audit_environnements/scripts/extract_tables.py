"""Audit A : extrait (lecture seule des paks) et décode les tables d'environnement Blur 2 X360.

Tables : lighting.bin, environmentalsettings.bin, enviroment_animations.bin, amax.bin (10 et 4 nov).
Sorties : ../data/<build>/<table>.bin (copie brute, < 80 Ko chacune) et .json (décodé par blurxt_be).
Usage : python -I extract_tables.py
"""
import json
import os
import sys

JEUX = r"C:\Users\sanqu\Jeux_WII"
sys.path.insert(0, os.path.join(JEUX, "blur_tools", "x360"))
sys.path.insert(0, os.path.join(JEUX, "blur_tools"))
import blurpak_be  # noqa: E402
import blurxt_be   # noqa: E402

PAKS = {
    "nov10": os.path.join(JEUX, r"blur_extracted\b2_x360_nov\gamedata.pak"),
    "nov04": os.path.join(JEUX, r"blur_extracted\b2_x360_nov04\!Blur 2 (Nov 04, 2010) [Unreleased]\cache\gamedata.pak"),
}
TABLES = ("lighting.bin", "environmentalsettings.bin", "enviroment_animations.bin", "amax.bin")
HERE = os.path.dirname(os.path.abspath(__file__))

# ponytail: garde de profondeur ajoutée ici (blurxt_be boucle sur certaines tables X360) ; vrai correctif = décodeur
_orig_struct = blurxt_be.XT._struct


def _guarded(self, t, o, depth):
    if depth > 12:
        return "<profondeur>"
    return _orig_struct(self, t, o, depth)


blurxt_be.XT._struct = _guarded
# pointeurs internes non suivis (explosion combinatoire sur les graphes PostFx) : on garde la référence brute
blurxt_be.XT._elem = lambda self, ref, depth: f"->{ref:#x}"


def decode(path):
    x = blurxt_be.XT(path)
    schema = {nm: {"kind": blurxt_be.KIND.get(kind, kind), "size": size,
                   "fields": [[f, ft, fo, fl] for f, ft, fo, fl in flds]}
              for i, nm, kind, prim, size, nf, flds in x.schema() if kind in (1, 2, 3)}
    recs, errors = {}, []
    it = x.records()
    while True:
        try:
            rname, tname, val, _ = next(it)
        except StopIteration:
            break
        except Exception as ex:                       # un enregistrement illisible arrête le générateur
            errors.append(repr(ex)[:200])
            break
        grp = recs.setdefault(tname, {})
        key, k = rname, 2
        while key in grp:
            key, k = f"{rname} ({k})", k + 1
        grp[key] = blurxt_be._round(val)
    return {"schema": schema, "records": recs, "errors": errors}


def main():
    for build, pak in PAKS.items():
        p = blurpak_be.Pak(pak)
        out = os.path.join(HERE, "..", "data", build)
        os.makedirs(out, exist_ok=True)
        for e in p.files:
            name = os.path.basename(e.path.replace("\\", "/")).lower()
            if name not in TABLES:
                continue
            raw = p.read(e)
            assert len(raw) == e.usize, (e.path, len(raw), e.usize)
            dst = os.path.join(out, name)
            open(dst, "wb").write(raw)
            res = decode(dst)
            json.dump(res, open(dst[:-4] + ".json", "w", encoding="utf-8"), indent=1, ensure_ascii=False)
            print(build, e.path, e.usize, {t: len(v) for t, v in res["records"].items()}, res["errors"])


if __name__ == "__main__":
    main()
