"""Test hash candidates on (name, id) pairs published on the Blur community wiki."""
import struct, zlib, itertools
from hashscan import lookup2

M = 0xffffffff
ev = {"T1E1": "A7 27 46 00", "T1E2": "B3 94 B9 BF", "T1E3": "4D 4E 8A C9", "T1E4": "B8 64 0D A1",
      "T2E1": "06 DE 2C 86", "T2E2": "20 A0 38 62", "T3E1": "1D F2 6F 1B", "T4E1": "91 07 41 E7"}
cars = {"R8": "BF 82 50 89", "CCX-R": "BD E8 9F 94", "Z-Tune": "96 C3 0F AA", "Ford GT": "54 A5 E6 7F",
        "BMW X5": "44 CC B3 90", "Bowler Nemesis": "F1 B9 2B B3", "Corvette ZR1": "47 E8 4C 12"}
pairs = []
for d in (ev, cars):
    for k, v in d.items():
        bs = bytes.fromhex(v.replace(" ", ""))
        pairs.append((k, struct.unpack("<I", bs)[0], struct.unpack(">I", bs)[0]))


def fnv1(s, off=0x811c9dc5):
    h = off
    for c in s: h = (h * 0x01000193) & M; h ^= c
    return h


def fnv1a(s, off=0x811c9dc5):
    h = off
    for c in s: h ^= c; h = (h * 0x01000193) & M
    return h


def djb2(s):
    h = 5381
    for c in s: h = (h * 33 + c) & M
    return h


def djb2x(s):
    h = 5381
    for c in s: h = ((h * 33) ^ c) & M
    return h


def sdbm(s):
    h = 0
    for c in s: h = (c + (h << 6) + (h << 16) - h) & M
    return h


def joaat(s):
    h = 0
    for c in s:
        h = (h + c) & M; h = (h + (h << 10)) & M; h ^= h >> 6
    h = (h + (h << 3)) & M; h ^= h >> 11; h = (h + (h << 15)) & M
    return h


F = {"crc32": lambda s: zlib.crc32(s), "crc32~": lambda s: ~zlib.crc32(s) & M, "fnv1": fnv1, "fnv1a": fnv1a,
     "fnv1_0": lambda s: fnv1(s, 0), "fnv1a_0": lambda s: fnv1a(s, 0), "djb2": djb2, "djb2x": djb2x, "sdbm": sdbm,
     "joaat": joaat, "lk2_0": lambda s: lookup2(s, 0), "lk2_1": lambda s: lookup2(s, 1),
     "lk2_golden": lambda s: lookup2(s, 0x9e3779b9), "adler": zlib.adler32}
convs = {"id": lambda s: s, "lower": bytes.lower, "upper": bytes.upper,
         "nul": lambda s: s + b"\0", "wide": lambda s: b"".join(bytes([c, 0]) for c in s)}
hits = []
for (name, le, be) in pairs:
    for cn, cv in convs.items():
        s = cv(name.encode())
        for fn, f in F.items():
            h = f(s) & M
            if h in (le, be) or (~h & M) in (le, be) or struct.unpack(">I", struct.pack("<I", h))[0] in (le, be):
                hits.append((name, cn, fn, hex(h)))
print(hits)
for n, le, be in pairs[:4]:
    print(n, hex(le), hex(be))
