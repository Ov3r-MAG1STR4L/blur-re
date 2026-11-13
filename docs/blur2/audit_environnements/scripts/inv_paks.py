"""Audit A : inventaire (lecture seule) des entrées de pak liées à l'environnement.

Compare les paks Blur 2 X360 (10 nov, 4 nov) et Blur 1 PC. Sortie : ../data/paks_env.json
Usage : python -I inv_paks.py
"""
import json
import os
import sys

JEUX = r"C:\Users\sanqu\Jeux_WII"
sys.path.insert(0, os.path.join(JEUX, "blur_tools", "x360"))
sys.path.insert(0, os.path.join(JEUX, "blur_tools"))
import blurpak_be  # noqa: E402
import blurpak     # noqa: E402

BE = {
    "b2_nov10_gamedata": os.path.join(JEUX, r"blur_extracted\b2_x360_nov\gamedata.pak"),
    "b2_nov10_root": os.path.join(JEUX, r"blur_extracted\b2_x360_nov\full\Blur 2 (Nov 10, 2010)\cache\root.pak"),
    "b2_nov04_gamedata": os.path.join(JEUX, r"blur_extracted\b2_x360_nov04\!Blur 2 (Nov 04, 2010) [Unreleased]\cache\gamedata.pak"),
    "b2_nov04_root": os.path.join(JEUX, r"blur_extracted\b2_x360_nov04\!Blur 2 (Nov 04, 2010) [Unreleased]\cache\root.pak"),
}
LE = {
    "b1_pc_root": r"C:\Program Files (x86)\Activision\Blur(TM)\cache\root.pak",
    "b1_pc_gamedata": r"C:\Program Files (x86)\Activision\Blur(TM)\cache\gamedata.pak",
    "b1_pc_lut_rampak": r"C:\Program Files (x86)\Activision\Blur(TM)\cache\lut_rampak.pak",
}
KEYS = ("sky", "cube", "env", "hemi", "hdr", "sunset", "twilight", "cloud", "_lut", "lighting", "fog",
        "postprocess", "dubai", "weather", "light.bin")


def match(p):
    s = p.lower()
    return any(k in s for k in KEYS) and not s.endswith((".model", ".cycle", ".skeleton"))


def entries(path, mod):
    k = mod.Pak(path)
    return {e.path: e.usize for e in k.entries}


def main():
    out = {}
    for name, path in list(BE.items()) + list(LE.items()):
        if not os.path.exists(path):
            out[name] = {"absent": path}
            continue
        mod = blurpak_be if name.startswith("b2") else blurpak
        allp = entries(path, mod)
        out[name] = {"path": path, "count": len(allp),
                     "env": dict(sorted((p, n) for p, n in allp.items() if match(p) and n))}
    # présence croisée Blur 2 -> Blur 1 (par nom de fichier)
    b1_all = set()
    for n, path in LE.items():
        if os.path.exists(path):
            b1_all |= {os.path.basename(p.replace("\\", "/")).lower() for p in entries(path, blurpak)}
    out["cross"] = {p: (os.path.basename(p.replace("\\", "/")).lower() in b1_all)
                    for n in BE for p in out.get(n, {}).get("env", {})}
    dst = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "paks_env.json")
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    json.dump(out, open(dst, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    for n, v in out.items():
        if n != "cross":
            print(n, v.get("count"), len(v.get("env", {})))
    print("B2 env absents de Blur 1 :",
          sorted({os.path.basename(p.replace("\\", "/")) for p, ok in out["cross"].items() if not ok}))


if __name__ == "__main__":
    main()
