"""Match strings hashed by the game (Jenkins lookup2(str,len,0)) against KSLF hash tables."""
import pefile, struct, re, glob, os

M = 0xffffffff


def mix2(a, b, c):
    a = (a - b - c) & M; a ^= c >> 13
    b = (b - c - a) & M; b ^= (a << 8) & M
    c = (c - a - b) & M; c ^= b >> 13
    a = (a - b - c) & M; a ^= c >> 12
    b = (b - c - a) & M; b ^= (a << 16) & M
    c = (c - a - b) & M; c ^= b >> 5
    a = (a - b - c) & M; a ^= c >> 3
    b = (b - c - a) & M; b ^= (a << 10) & M
    c = (c - a - b) & M; c ^= b >> 15
    return a, b, c


def lookup2(k, init=0):
    l = len(k); a = b = 0x9e3779b9; c = init; i = 0; n = l
    while n >= 12:
        a = (a + struct.unpack_from("<I", k, i)[0]) & M
        b = (b + struct.unpack_from("<I", k, i + 4)[0]) & M
        c = (c + struct.unpack_from("<I", k, i + 8)[0]) & M
        a, b, c = mix2(a, b, c); i += 12; n -= 12
    c = (c + l) & M
    t = k[i:]
    for j in range(len(t) - 1, -1, -1):
        v = t[j]
        if j >= 8: c = (c + (v << (8 * (j - 7)))) & M
        elif j >= 4: b = (b + (v << (8 * (j - 4)))) & M
        else: a = (a + (v << (8 * j))) & M
    a, b, c = mix2(a, b, c)
    return c


if __name__ == "__main__":
    EXE = r"C:\Program Files (x86)\Activision\Blur(TM)\Blur_debug.exe"
    pe = pefile.PE(EXE); d = open(EXE, "rb").read()

    def rd(va):
        o = pe.get_offset_from_rva(va - 0x400000)
        return d[o:d.index(b"\0", o)]

    strs = set()
    text = [s for s in pe.sections if s.Name.startswith(b".text")][0]
    lo = text.PointerToRawData; hi = lo + text.SizeOfRawData
    i = lo
    while True:
        i = d.find(b"\xe8", i, hi - 5)
        if i < 0: break
        rel = struct.unpack_from("<i", d, i + 1)[0]
        va = pe.get_rva_from_offset(i) + 0x400000
        if va + 5 + rel == 0x495de0:            # call hash(str, len, 0)
            w = d[i - 40:i]
            for m in re.finditer(rb"\x6a(.)\x68(....)", w, re.S):   # push len ; push ptr
                ln = m.group(1)[0]; ptr = struct.unpack("<I", m.group(2))[0]
                try:
                    s = rd(ptr)
                    if len(s) >= ln: strs.add(s[:ln])
                except Exception:
                    pass
        i += 1
    print(len(strs), sorted(strs)[:20])

    Hs = {}
    for f in glob.glob(r"C:\Users\sanqu\Jeux_WII\blur_extracted\gamedata\gamedata\**\*", recursive=True):
        if not os.path.isfile(f): continue
        b = open(f, "rb").read()
        if b[:4] != b"KSLF": continue
        h = struct.unpack_from("<18I", b, 0); off, cnt = h[10], h[11]
        for i in range(cnt):
            Hs.setdefault(struct.unpack_from("<I", b, off + 8 * i)[0], set()).add(os.path.basename(f))
    hit = 0
    for s in strs:
        for v in (s, s.lower()):
            h = lookup2(v, 0)
            if h in Hs:
                print("HIT", v, hex(h), Hs[h]); hit += 1
    print("hits", hit)
