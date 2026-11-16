import struct, re
from blurxt import XT

x = XT(r"C:\Users\sanqu\Jeux_WII\blur_extracted\gamedata\gamedata\xt\amax.bin")
d = x.data
pat = struct.pack("<I", 0x895082bf)
pos = [m.start() for m in re.finditer(re.escape(pat), d)]
print("R8 hash in data at", pos)
for p in pos[:3]:
    print(hex(p), d[p - 64:p + 96].hex(" "))
# where else in the file
b = x.b
print([hex(m.start()) for m in re.finditer(re.escape(pat), b)])
