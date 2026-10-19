import struct, sys
from blurtex import records
b = open(sys.argv[1], "rb").read()
want = sys.argv[2]
for r in records(b):
    if r["name"] == want or (r["kind"] == "level" and abs(r["p"] - int(sys.argv[3], 16)) < 40000 if len(sys.argv) > 3 else False):
        p = r["p"]
        print(r["kind"], r["name"], r["w"], r["h"], "mips", r["mips"], "p", hex(p), "off", hex(r["off"]), "size", len(r["data"]),
              "hdr", b[p + 12:p + 28].hex(" "))
