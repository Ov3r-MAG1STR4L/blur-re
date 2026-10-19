import struct, sys
from blurxt import XT

base = r"C:\Users\sanqu\Jeux_WII\blur_extracted\gamedata\gamedata\xt\%s.bin"
R8 = 0x895082bf
for f in ("amax", "singleplayer", "multiplayer", "finalracebook"):
    x = XT(base % f)
    off4, c4 = x.sec[4]
    raw = [x.b[off4 + 8 * i: off4 + 8 * i + 8] for i in range(c4)]
    for i, e in enumerate(raw):
        h = struct.unpack("<I", e[:4])[0]
        if h == R8:
            print(f, "index pos", i, e.hex(" "), struct.unpack("<II", e))
            for j in (i - 1, i + 1):
                print("   neighbour", j, raw[j].hex(" "))
    print(f, "sec sizes", [(hex(o), c) for o, c in x.sec])
