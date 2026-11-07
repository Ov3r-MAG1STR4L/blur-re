"""No auto-respawn when stuck or driving backwards (Blur_test only).
HandOfGodParameters (rldatabase.bin, records #5 and #24): StuckTimer / MovingBackwardsTimer = seconds before reset.
Usage: norespawn.py [--undo]"""
import os, sys
sys.path.insert(0, r"C:\Users\sanqu\Jeux_WII\blur_tools")
import config
from blurxt import XT

SRC = os.path.join(config.BLUR_EXTRACTED, "gamedata", "gamedata", "xt", "rldatabase.bin")
DST = os.path.join(config.BLUR_TEST, "gamedata", "xt", "rldatabase.bin")
OFF = {"StuckTimer": 9999.0, "MovingBackwardsTimer": 9999.0}

b = open(SRC, "rb").read()
if "--undo" not in sys.argv:
    tmp = DST + ".tmp"
    for rec in ("#5", "#24"):
        for k, v in OFF.items():
            open(tmp, "wb").write(b)
            b = XT(tmp).patched(rec, k, v)
    os.remove(tmp)
open(DST, "wb").write(b)
print("undo" if "--undo" in sys.argv else "installed", DST)
