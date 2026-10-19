import struct
from blurxt import XT

x = XT(r"C:\Users\sanqu\Jeux_WII\blur_extracted\gamedata\gamedata\xt\amax.bin")
items = x.items()
for ref in (0x979, 0x97a, 0x97b):
    print("item", hex(ref), [hex(v) for v in items[ref]])
it = items[0x97a]
d = x.data
print("data len", len(d))
for base in (it[2],):
    print(d[base:base + 256].hex(" "))
# types table: 12B entries -> print type 7 and neighbours
off, cnt = x.sec[0]
for t in range(cnt):
    e = struct.unpack_from("<HHHHHH", x.b, off + 12 * t)
    if t in (6, 7, 8, 11): print("type", t, e)
