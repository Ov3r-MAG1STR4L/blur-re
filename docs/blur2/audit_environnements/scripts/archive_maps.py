"""Audit A : maps présentes dans les 3 archives Blur 2 (listings `7z l -slt`, rien d'extrait).

Entrées : ../data/listing_*.txt. Sortie : ../data/archives_maps.json
  {build: {map: {"level": o, "levelrender": o, "levelstream": o, "levelphysics": o, "levelanim": o}},
   "_fichiers_env": {build: [chemins hors niveaux évoquant ciel / cubemap / lut / éclairage]}}
Usage : python -I archive_maps.py
"""
import glob
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
D = os.path.join(HERE, "..", "data")
BUILD = {"Aug31": "aug31", "Nov102010": "nov10", "Nov42010": "nov04"}
ENV = re.compile(r"sky|cube|_lut|light|envir|hdr|fog|postfx|postprocess", re.I)


def parse(path):
    recs, cur = [], {}
    for line in open(path, encoding="utf-8", errors="replace"):
        line = line.rstrip("\n")
        if not line.strip():
            if "Path" in cur:
                recs.append(cur)
            cur = {}
        elif " = " in line:
            k, v = line.split(" = ", 1)
            cur[k] = v
    if "Path" in cur:
        recs.append(cur)
    return recs


def main():
    out, env = {}, {}
    for f in sorted(glob.glob(os.path.join(D, "listing_*.txt"))):
        b = next(v for k, v in BUILD.items() if k in f)
        maps = out.setdefault(b, {})
        env[b] = []
        for r in parse(f):
            p = r["Path"].replace("\\", "/")
            size = int(r.get("Size") or 0)
            m = re.search(r"/levels/([^/]+)/level\.(\w+)$", p, re.I)
            if m:
                maps.setdefault(m.group(1).lower(), {})[m.group(2).lower()] = size
            elif ENV.search(os.path.basename(p)) and size:
                env[b].append([p, size])
    out["_fichiers_env"] = env
    json.dump(out, open(os.path.join(D, "archives_maps.json"), "w", encoding="utf-8"), indent=1)
    for b, maps in out.items():
        if b.startswith("_"):
            continue
        print(b, len(maps), "maps ;", sum(1 for m in maps.values() if m.get("levelrender", 0) > 1 << 20),
              "avec levelrender > 1 Mo")
    for b, l in env.items():
        print(b, l[:15])


if __name__ == "__main__":
    main()
