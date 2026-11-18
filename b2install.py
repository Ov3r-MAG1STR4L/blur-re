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


NAMES = {1: "Business Bay", 2: "Dubai Island", 3: "Construction", 4: "Marina"}


def installed():
    """route whose gravity zones are in Blur_test (header line of b2gravity.txt), or None"""
    import re
    try:
        head = open(os.path.join(config.BLUR_TEST, "amax", "dlls", "b2gravity.txt"), encoding="utf-8",
                    errors="replace").readline()
    except OSError:
        return None
    m = re.search(r"Dubai route (\d+)", head)
    return int(m.group(1)) if m else None


def main():
    if sys.argv[1:] == ["--etat"]:
        r = installed()
        print("Route installée : %s" % ("%d - %s" % (r, NAMES[r]) if r in NAMES else "aucune route de Dubaï reconnue"))
        for k, n in NAMES.items():
            built = os.path.isdir(os.path.join(b2track.MAPS["dubai%d" % k]["out"], "files"))
            print("  %d  %-13s %s" % (k, n, "construite" if built else "pas construite"))
        return
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
    dll, old = os.path.join(HERE, "natif", "b2gravity", "b2gravity.dll"), os.path.join(dst, "b2gravity.dll")
    if os.path.exists(dll) and (not os.path.exists(old) or open(dll, "rb").read() != open(old, "rb").read()):
        if os.path.exists(old):
            shutil.copy2(old, old + ".precedente.bak")
        shutil.copy2(dll, old)
        print("DLL de gravité mise à jour (l'ancienne : b2gravity.dll.precedente.bak)")


if __name__ == "__main__":
    main()
