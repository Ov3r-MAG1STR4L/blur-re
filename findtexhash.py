import struct, glob, os, re, sys
model = r"C:\Users\sanqu\Jeux_WII\blur_extracted\root\models\vehicles\%s.model" % (sys.argv[1] if len(sys.argv) > 1 else "bmw_m3e92_tuner")
b = open(model, "rb").read()
ext = []
for m in re.finditer(rb"DXT[1-5]", b):
    p = m.start()
    length, h, w, _, mips = struct.unpack_from("<5i", b, p - 20)
    if length != 0x1c: continue
    hsh = struct.unpack_from("<I", b, p - 28)[0]
    mk = b.rfind(b"RA\x01\x00", p - 140, p)
    name = "?"
    for L in range(1, 65):
        o = mk - L - 4
        if o >= 0 and struct.unpack_from("<i", b, o)[0] == L and all(32 <= c < 127 for c in b[o + 4:o + 4 + L]):
            name = b[o + 4:o + 4 + L].decode(); break
    ext.append((name, hsh, m.group().decode(), w, h, mips))
print(len(ext), "external texture records")
for e in ext: print(e[0].ljust(28), "%08x" % e[1], e[2:])
open(r"C:\Users\sanqu\Jeux_WII\blur_tools\ext_tex.txt", "w").write("\n".join("%s %08x" % (n, h) for n, h, *_ in ext))
