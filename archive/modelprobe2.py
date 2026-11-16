import re, struct, sys
p = sys.argv[1]
b = open(p, "rb").read()
RA = b"RA\x00\x00"
print("first RA markers:", [hex(m.start()) for m in re.finditer(re.escape(RA), b)][:40])
fx = [(hex(m.start()), m.group()) for m in re.finditer(rb"[A-Za-z0-9_\\/]+\.(?:fx|fxo|fxh)", b)]
print(fx[:10])
for m in list(re.finditer(rb"[\x20-\x7e]{5,60}", b[0x3290:0x40000]))[:40]:
    print(hex(0x3290 + m.start()), m.group())
