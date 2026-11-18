#!/usr/bin/env python3
"""Install one Dubai route in Blur_test: its map (b2track.install: flat_earth slot, copies checked, originals kept
once) AND its b2gravity zones (natif/b2gravity/<route>/b2gravity.txt + .bin -> Blur_test/amax/dlls). The 4 routes
share the flat_earth slot: installing one replaces the previous one, map and gravity together.

usage: b2install.py ROUTE      (1 Business Bay, 2 Dubai Island, 3 Construction, 4 Marina)
"""
import os, shutil, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import b2track, config  # noqa: E402


def blur_running():
    out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq Blur.exe"], capture_output=True, text=True).stdout
    return "Blur.exe" in out


def main():
    r = int(sys.argv[1])
    m = b2track.MAPS["dubai%d" % r]
    if blur_running():
        sys.exit("Blur est ouvert : rien installé (les fichiers du jeu sont verrouillés)")
    if not os.path.isdir(os.path.join(m["out"], "files")):
        sys.exit("pas de map construite dans %s" % m["out"])
    print(b2track.install(m)[:200])
    src = os.path.join(HERE, "natif", "b2gravity", m["name"].lower().replace(" ", "_"))
    dst = os.path.join(config.BLUR_TEST, "amax", "dlls")
    for f in ("b2gravity.txt", "b2gravity.bin"):
        shutil.copy2(os.path.join(src, f), os.path.join(dst, f))
    print("zones de gravité de %s copiées dans %s" % (m["name"], dst))


if __name__ == "__main__":
    main()
