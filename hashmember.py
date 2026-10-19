import struct, glob, os
from hashwiki import pairs

Hs = {}
for f in glob.glob(r"C:\Users\sanqu\Jeux_WII\blur_extracted\gamedata\gamedata\**\*", recursive=True):
    if not os.path.isfile(f): continue
    b = open(f, "rb").read()
    if b[:4] != b"KSLF": continue
    h = struct.unpack_from("<18I", b, 0)
    off, cnt = h[10], h[11]
    for i in range(cnt):
        Hs.setdefault(struct.unpack_from("<I", b, off + 8 * i)[0], []).append(os.path.basename(f))
for n, le, be in pairs:
    print(n.ljust(16), "LE", hex(le), Hs.get(le), "| BE", hex(be), Hs.get(be))
