#!/usr/bin/env python3
"""Install natif/b2gravity (dll + zones) in the TEST copy only, and lower the Hand of God "flipped" threshold there.

- b2gravity.dll + b2gravity.txt -> Blur_test\\amax\\dlls (AMAX's d3d9.dll loads every .dll / .asi of that folder);
- rldatabase.bin (Blur_test\\gamedata\\xt): HandOfGodParameters.MinDotUp 0.45 -> 0.0 (the other set is already -0.1).
  With 0.45 the game resets a car whose up axis is less than ~63 deg from vertical for 0.3 s (FlippedTimer):
  every wall ride (Marina: ~80 deg) would end in a reset even with the car-local gravity. Original kept once in
  blur_extracted\\mods\\b2gravity_backup\\rldatabase.bin.
Refused unless Blur_test has COPIE_DE_TEST_HORS_LIGNE.txt and Blur.exe is not running.
"""
import os, shutil, struct, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import config  # noqa: E402

MIN_DOT_UP = 0.0


def min_dot_up_offsets(path):
    import neon
    A = neon.dump.File(path)
    out = []
    for u, t, oi in A.refs:
        if oi != 0xFFFF and A.T[t]["name"] == "HandOfGodParameters":
            f = next(f for f in A.all_fields(t) if f["name"] == "MinDotUp")
            out.append(A.O[oi]["blocks"][0]["offset"] + f["offset"])
    return out


def main():
    game = config.BLUR_TEST
    assert os.path.isfile(os.path.join(game, "COPIE_DE_TEST_HORS_LIGNE.txt")), "not the test copy"
    run = subprocess.run(["tasklist", "/FI", "IMAGENAME eq Blur.exe"], capture_output=True, text=True).stdout
    assert "Blur.exe" not in run, "Blur is running: close it first"
    src = os.path.join(HERE, "natif", "b2gravity")
    dlls = os.path.join(game, "amax", "dlls")
    for f in ("b2gravity.dll", "b2gravity.txt", "b2gravity.bin"):
        shutil.copyfile(os.path.join(src, f), os.path.join(dlls, f))
        assert open(os.path.join(src, f), "rb").read() == open(os.path.join(dlls, f), "rb").read()
    rl = os.path.join(game, "gamedata", "xt", "rldatabase.bin")
    bak = os.path.join(config.BLUR_EXTRACTED, "mods", "b2gravity_backup", "rldatabase.bin")
    if not os.path.exists(bak):
        os.makedirs(os.path.dirname(bak), exist_ok=True)
        shutil.copyfile(rl, bak)
    d = bytearray(open(rl, "rb").read())
    offs = min_dot_up_offsets(rl)
    before = [round(struct.unpack_from("<f", d, o)[0], 3) for o in offs]
    for o in offs:
        if struct.unpack_from("<f", d, o)[0] > MIN_DOT_UP:
            struct.pack_into("<f", d, o, MIN_DOT_UP)
    open(rl, "wb").write(bytes(d))
    after = [round(struct.unpack_from("<f", open(rl, "rb").read(), o)[0], 3) for o in min_dot_up_offsets(rl)]
    print("dll + zones installed in", dlls, "| MinDotUp", before, "->", after)


if __name__ == "__main__":
    main()
