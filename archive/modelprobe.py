import re, struct, sys, glob
p = sys.argv[1] if len(sys.argv) > 1 else r"C:\Users\sanqu\Jeux_WII\blur_extracted\root\models\vehicles\bmw_m3e92_tuner.model"
b = open(p, "rb").read()
print(len(b))
# top-level chunk scan: names are 8-char padded tags
for m in re.finditer(rb"DDS ", b):
    o = m.start()
    hdr = struct.unpack_from("<IIIIIII", b, o + 4)      # size, flags, height, width, pitch, depth, mips
    fourcc = b[o + 84:o + 88]
    print("DDS at", hex(o), "h", hdr[2], "w", hdr[3], "mips", hdr[6], fourcc, "prev", b[o - 24:o])
# strings that look like texture/material names
strs = re.findall(rb"[\x20-\x7e]{4,80}", b[:0x8000])
print(strs[:80])
