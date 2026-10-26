#!/usr/bin/env python3
"""List the sounds of the .baf banks that no audio graph (audio/dat/*.dat, JBOA) names: never played by the game.

A sound object (types 60 / 64) names its bank and its sound as strings in the graph's name table, so a sound whose
name appears in no .dat is unused. Writes a Markdown table (bank, sound, duration).
usage: unused_sounds.py EXTRACTED_DIR OUT.md     (EXTRACTED_DIR = blur_extracted, with root/ and root_streaming/)
"""
import glob, os, re, sys
import blurbaf


def main(e, out):
    names = set()
    for p in glob.glob(os.path.join(e, "root", "audio", "dat", "*.dat")):
        names.update(s.decode("latin-1") for s in re.findall(rb"[\x20-\x7e]{2,}", open(p, "rb").read()))
    banks = sorted(glob.glob(os.path.join(e, "root", "audio", "*.baf")) +
                   glob.glob(os.path.join(e, "root_streaming", "**", "*.baf"), recursive=True))
    rows, total = [], 0
    for p in banks:
        for w in blurbaf.parse(open(p, "rb").read())["waves"]:
            total += 1
            if w["name"] not in names:
                rows.append((os.path.basename(p), w["name"], w["samples"] / w["rate"] if w["rate"] else 0))
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        f.write("# Sons jamais utilisés par le jeu\n\n"
                f"{len(rows)} sons sur {total} ne sont nommés par aucun graphe audio (`audio/dat/*.dat`) : "
                "le jeu ne les joue jamais. Généré par `unused_sounds.py`. Écouter un son :\n"
                "`blurbaf.py BANQUE.baf NOM sortie.wav`.\n\n| Banque | Son | Durée (s) |\n|---|---|---|\n")
        f.writelines(f"| `{b}` | `{n}` | {d:.1f} |\n" for b, n, d in rows)
    print(len(rows), "/", total, "->", out)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    main(*sys.argv[1:])
