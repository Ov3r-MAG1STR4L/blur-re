"""Audit A : blocs d'environnement des level.levelrender (lecture seule, rien n'est écrit hors ../data).

Pour chaque fichier : blocs LSData (échantillons de lumière : nombre, taille d'un enregistrement), LSTree, Lights,
CubePt2 (Blur 1) / CubePt3 (Blur 2) avec nom, position et chemin du cubemap, présence des lightmaps et des samplers
g_tEnvironment / g_tLightmap0/1, chaînes citant ciel / cubemap.
Sources : Blur 1 PC (dossier du jeu, lecture), Blur 2 local (Dubaï 4 et 10 nov), et archives Blur 2 lues par
`7z e -so` directement en mémoire (aucune copie sur disque).
Sortie : ../data/levelrender_env.json
Usage : python -I levelrender_scan.py [--archives]
"""
import json
import os
import re
import struct
import subprocess
import sys

JEUX = r"C:\Users\sanqu\Jeux_WII"
Z7 = r"C:\Program Files\7-Zip\7z.exe"
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "data", "levelrender_env.json")
B1 = r"C:\Program Files (x86)\Activision\Blur(TM)\levels"
LOCAL = {
    "nov10/dubai": os.path.join(JEUX, r"blur_extracted\b2_x360_nov\full\Blur 2 (Nov 10, 2010)\levels\dubai\level.levelrender"),
    "nov04/dubai": os.path.join(JEUX, r"blur_extracted\b2_x360_nov04\!Blur 2 (Nov 04, 2010) [Unreleased]\levels\dubai\level.levelrender"),
}
ARCH = {
    "nov10": (r"C:\Users\sanqu\Downloads\Blur 2 (Nov 10, 2010 prototype).rar", "Blur 2 (Nov 10, 2010)\\levels\\"),
    "aug31": (r"C:\Users\sanqu\Downloads\Blur 2 (Aug 31, 2010 prototype).rar",
              "Blur 2 (Aug 31, 2010) [Fixed]\\KanzenDev\\levels\\"),
}
NAMES = (b"LSData", b"LSTree", b"Lights", b"CubePt2", b"CubePt3", b"PVSData")
STR = re.compile(rb"(?i)[\x20-\x7e]*(?:cubemap|envdefault|_env|sky)[\x20-\x7e]*")


def chunks(b, E):
    out = {}
    for n in NAMES:
        k = n.ljust(8, b"\0")
        for m in re.finditer(re.escape(k), b):
            o = m.start()
            sz, a, c = struct.unpack_from(E + "IHH", b, o + 8)
            if 0x41 in (a, c, a >> 8, c >> 8) and o + 16 + sz <= len(b):
                out.setdefault(n.decode(), []).append((o, sz))
    return out


def scan(b):
    be = b[:3] == b"360"
    E = ">" if be else "<"
    ch = chunks(b, E)
    r = {"endian": "BE (X360)" if be else "LE (PC)", "taille": len(b)}
    for o, sz in ch.get("LSData", [])[:1]:
        n = struct.unpack_from(E + "I", b, o + 16)[0]
        r["LSData"] = {"n": n, "octets_par_echantillon": round((sz - 4) / n, 3) if n else None}
    for o, sz in ch.get("LSTree", [])[:1]:
        r["LSTree"] = {"taille": sz}
    for o, sz in ch.get("Lights", [])[:1]:
        r["Lights"] = {"taille": sz, "n?": struct.unpack_from(E + "I", b, o + 16)[0]}
    for kind in ("CubePt2", "CubePt3"):
        for o, sz in ch.get(kind, []):
            body = b[o + 16:o + 16 + sz]
            rec = {"taille": sz,
                   "dds": [p.decode("latin-1") for p in re.findall(rb"[\x20-\x7e]{4,}\.dds", body)],
                   "noms": [p.decode("latin-1") for p in re.findall(rb"[A-Za-z][A-Za-z0-9_]{3,}", body[:64])]}
            if kind == "CubePt3":                      # lecture Probable : u32 n, 3 f32 position, u32 long, nom
                rec["n?"] = struct.unpack_from(E + "I", body, 0)[0]
                rec["position?"] = [round(v, 2) for v in struct.unpack_from(E + "3f", body, 4)]
            r.setdefault(kind, []).append(rec)
    r["g_tEnvironment"] = b"g_tEnvironment" in b
    r["g_tLightmap0/1"] = b"g_tLightmap0" in b
    r["pages_lightmap"] = len(set(re.findall(rb"lightmap_[a-z_]+_\d+-[ab]", b)))
    r["chaines_env"] = sorted({s.decode("latin-1")[:120] for s in STR.findall(b)})[:20]
    return r


def main():
    res = json.load(open(OUT, encoding="utf-8")) if os.path.exists(OUT) else {}
    for m in sorted(os.listdir(B1)):
        p = os.path.join(B1, m, "level.levelrender")
        if os.path.exists(p):
            res[f"b1_pc/{m}"] = scan(open(p, "rb").read())
    for k, p in LOCAL.items():
        if os.path.exists(p):
            res[k] = scan(open(p, "rb").read())
    if "--archives" in sys.argv:
        # archive RAR solide : une seule passe par archive (7z -so concatène les fichiers dans l'ordre de l'archive,
        # celui du listing), découpée selon les tailles du listing
        for build, (rar, prefix) in ARCH.items():
            order = []
            lst = os.path.join(HERE, "..", "data",
                               "listing_" + re.sub(r"[^A-Za-z0-9]", "", os.path.basename(rar)) + ".txt")
            path = None
            for line in open(lst, encoding="utf-8", errors="replace"):
                if line.startswith("Path = "):
                    path = line[7:].strip()
                elif line.startswith("Size = ") and path and path.lower().endswith("\\level.levelrender"):
                    size = int(line[7:].strip() or 0)
                    if size:
                        order.append((path.split("\\")[-2].lower(), size))
                    path = None
            p = subprocess.Popen([Z7, "e", "-so", rar, "-r", "level.levelrender"], stdout=subprocess.PIPE,
                                 stderr=subprocess.DEVNULL)
            for m, size in order:
                b = p.stdout.read(size)
                key = f"{build}/{m}"
                res[key] = scan(b) if len(b) == size else {"erreur": f"lu {len(b)} o au lieu de {size}"}
                print(key, {k: v for k, v in res[key].items() if k in ("LSData", "CubePt3", "erreur")}, flush=True)
            p.stdout.close()
            p.wait()
            json.dump(res, open(OUT, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    json.dump(res, open(OUT, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    print("écrit", OUT, len(res))


if __name__ == "__main__":
    main()
