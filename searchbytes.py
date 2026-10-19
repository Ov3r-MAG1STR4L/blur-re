import sys, glob, os, struct, mmap
pat = struct.pack("<I", int(sys.argv[1], 16))
paths = sys.argv[2:]
for p in paths:
    for f in glob.glob(p, recursive=True):
        if not os.path.isfile(f): continue
        with open(f, "rb") as fh:
            try:
                mm = mmap.mmap(fh.fileno(), 0, access=mmap.ACCESS_READ)
            except ValueError:
                continue
            i = mm.find(pat); n = 0; first = []
            while i >= 0 and n < 200:
                n += 1; first.append(hex(i)); i = mm.find(pat, i + 1)
            if n: print(n, f, first[:4])
            mm.close()
