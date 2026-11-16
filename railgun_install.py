#!/usr/bin/env python3
"""Install the Railgun prototype (natif/railgun) in the TEST copy only; --remove puts the Bolt back.

- railgun.dll -> Blur_test\\amax\\dlls (AMAX's d3d9.dll loads every .dll / .asi there): 1 shot, through walls and cars;
- pickups.bin (Blur_test\\gamedata\\xt): the Bolt's Normal PickupLevel (uid 0xDD8A965A, the only level the
  projectile reads: C_PickupBlindfireProjectile's constructor and the damage code take mNormal) gets the values of
  SETTINGS. Original kept once in blur_extracted\\mods\\railgun_backup\\pickups.bin.
Refused unless Blur_test has COPIE_DE_TEST_HORS_LIGNE.txt and Blur.exe is not running.
usage: railgun_install.py [--remove]
"""
import os, shutil, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import config  # noqa: E402
from blurxt import XT  # noqa: E402

BOLT_NORMAL = 0xDD8A965A
# original: Speed 300, Radius 0.2, FallRate 1, DamageInflicted 50, Health 50 (3 shots per pickup)
SETTINGS = {"Speed": 600.0,            # m/s; range = speed x Perks.Blindfire.LiveTime (10 s) = 6 km
            "Radius": 0.4,             # swept ray radius (the Modified Bolt's); 0.2 is hard to land in one shot
            "FallRate": 2.0,           # follows downhill ground faster (steps of 10 m per frame at 60 fps)
            "DamageInflicted": 150,    # the 3 shots in one
            "Health": 9999.0}          # mines / other projectiles do not stop it


def bolt(x):
    """(record name, BalancingData) of the Bolt's Normal level; the name must be unique (locate() takes the first)."""
    recs = list(x.records())
    hit = [(n, v["BalancingData"]) for n, t, v, h in recs if h == BOLT_NORMAL]
    assert len(hit) == 1 and [n for n, *_ in recs].count(hit[0][0]) == 1, hit
    return hit[0]


def main(remove=False):
    game = config.BLUR_TEST
    assert os.path.isfile(os.path.join(game, "COPIE_DE_TEST_HORS_LIGNE.txt")), "not the test copy"
    run = subprocess.run(["tasklist", "/FI", "IMAGENAME eq Blur.exe"], capture_output=True, text=True).stdout
    assert "Blur.exe" not in run, "Blur is running: close it first"
    dll = os.path.join(game, "amax", "dlls", "railgun.dll")
    pk = os.path.join(game, "gamedata", "xt", "pickups.bin")
    bak = os.path.join(config.BLUR_EXTRACTED, "mods", "railgun_backup", "pickups.bin")
    if remove:
        if os.path.exists(dll):
            os.remove(dll)
        if os.path.exists(bak):
            shutil.copyfile(bak, pk)
        print("railgun removed; Bolt:", bolt(XT(pk))[1])
        return
    if not os.path.exists(bak):
        os.makedirs(os.path.dirname(bak), exist_ok=True)
        shutil.copyfile(pk, bak)
    tmp = os.path.join(tempfile.gettempdir(), "railgun_pickups.bin")
    shutil.copyfile(bak, tmp)                          # always from the original: running twice is harmless
    name = bolt(XT(tmp))[0]
    for field, value in SETTINGS.items():
        data = XT(tmp).patched(name, "BalancingData." + field, value)
        open(tmp, "wb").write(data)
    changed = [n for (n, _, v, _), (_, _, w, _) in zip(XT(bak).records(), XT(tmp).records()) if v != w]
    assert changed == [name], changed                  # nothing else moved
    got = bolt(XT(tmp))[1]
    assert all(abs(got[k] - v) < 1e-3 for k, v in SETTINGS.items()), got
    shutil.copyfile(tmp, pk)
    shutil.copyfile(os.path.join(HERE, "natif", "railgun", "railgun.dll"), dll)
    print("railgun installed:", dll, "| Bolt", name, {k: round(got[k], 3) for k in SETTINGS})


if __name__ == "__main__":
    main("--remove" in sys.argv)
