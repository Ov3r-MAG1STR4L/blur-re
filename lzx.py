#!/usr/bin/env python3
"""LZX decoder for Xbox 360 XMemCompress "native" streams (Blur 2 X360 .pak entries).

Stream = frames, each [0xFF, u16 BE usize, u16 BE csize] or [u16 BE csize] (usize = 0x8000), then csize bytes
of LZX bitstream (16-bit LE words, read MSB first). Decoder state (window, trees, R0-R2) carries over frames;
the bit reader restarts on each frame. Algorithm follows libmspack lzxd.c. Window 128 KB (XMem default).

usage: lzx.py IN OUT
"""
import struct, sys

MIN_MATCH, NUM_CHARS, PRETREE, LENTREE, ALIGNED = 2, 256, 20, 249, 8
EXTRA = [0, 0, 0, 0] + [min((i - 2) // 2, 17) for i in range(4, 52)]
BASE = [0]
for e in EXTRA[:-1]:
    BASE.append(BASE[-1] + (1 << e))


class Bits:
    def __init__(self, b):
        self.b, self.p, self.buf, self.n = b, 0, 0, 0

    def _fill(self):
        while self.n <= 16:
            w = self.b[self.p] | self.b[self.p + 1] << 8 if self.p + 1 < len(self.b) else 0
            self.p += 2
            self.buf |= w << (16 - self.n)   # 32-bit buffer, MSB first
            self.n += 16

    def peek(self, k):
        self._fill()
        return (self.buf >> (32 - k)) & ((1 << k) - 1)

    def skip(self, k):
        self.buf = (self.buf << k) & 0xFFFFFFFF
        self.n -= k

    def read(self, k):
        if k == 0:
            return 0
        if k > 16:
            return self.read(k - 16) << 16 | self.read(16)
        v = self.peek(k)
        self.skip(k)
        return v


class Huff:
    """Canonical Huffman: decode by walking code lengths (codes are assigned shortest first)."""
    def __init__(self, lens):
        self.lut = {}
        code = 0
        for L in range(1, 17):
            for s, l in enumerate(lens):
                if l == L:
                    self.lut[(L, code)] = s
                    code += 1
            code <<= 1
        self.maxlen = max(lens) if any(lens) else 0

    def sym(self, bits):
        bits._fill()
        for L in range(1, self.maxlen + 1):
            s = self.lut.get((L, bits.peek(L)))
            if s is not None:
                bits.skip(L)
                return s
        raise ValueError("bad huffman code")


class LZX:
    def __init__(self, window_bits=17):
        self.wsize = 1 << window_bits
        self.win = bytearray(self.wsize)
        self.wp = 0
        self.slots = {15: 30, 16: 32, 17: 34, 18: 36, 19: 38, 20: 42, 21: 50}[window_bits]
        self.main_len = [0] * (NUM_CHARS + self.slots * 8)
        self.len_len = [0] * LENTREE
        self.R = [1, 1, 1]
        self.header = False
        self.btype, self.bremain, self._odd = 0, 0, 0

    def _lengths(self, bits, real, first, last):
        lens = real + [0] * 32                    # runs may overshoot `last` (libmspack tolerates it)
        pre = Huff([bits.read(4) for _ in range(PRETREE)])
        x = first
        while x < last:
            z = pre.sym(bits)
            if z == 17:
                for _ in range(bits.read(4) + 4): lens[x] = 0; x += 1
            elif z == 18:
                for _ in range(bits.read(5) + 20): lens[x] = 0; x += 1
            elif z == 19:
                n = bits.read(1) + 4
                z = (lens[x] - pre.sym(bits)) % 17
                for _ in range(n): lens[x] = z; x += 1
            else:
                lens[x] = (lens[x] - z) % 17; x += 1
        real[first:last] = lens[first:last]

    def _put(self, c, out):
        self.win[self.wp] = c
        self.wp = (self.wp + 1) & (self.wsize - 1)
        out.append(c)

    def frame(self, data, usize):
        bits, out = Bits(data), bytearray()
        if not self.header:                      # E8 translation flag, once per stream
            if bits.read(1):
                raise NotImplementedError("E8 translation")
            self.header = True
        while len(out) < usize:
            if self.bremain == 0:
                if self.btype == 3 and self._odd:
                    bits.p += 1                        # uncompressed block padding (byte stream)
                self.btype = bits.read(3)
                self.bremain = bits.read(24)           # classic (CAB) LZX: 24-bit block size, no default-size bit
                if self.btype == 2:
                    self.aligned = Huff([bits.read(3) for _ in range(ALIGNED)])
                if self.btype in (1, 2):
                    self._lengths(bits, self.main_len, 0, 256)
                    self._lengths(bits, self.main_len, 256, len(self.main_len))
                    self.main = Huff(self.main_len)
                    self._lengths(bits, self.len_len, 0, LENTREE)
                    self.lent = Huff(self.len_len) if any(self.len_len) else None
                elif self.btype == 3:
                    bits._fill()
                    if bits.n > 16:
                        bits.p -= 2
                    bits.buf = bits.n = 0              # byte-aligned from here
                    self.R = list(struct.unpack_from("<3I", data, bits.p)); bits.p += 12
                    self._odd = self.bremain & 1
                else:
                    raise ValueError("bad block type %d" % self.btype)
            if self.btype == 3:
                n = min(self.bremain, usize - len(out))
                for c in data[bits.p:bits.p + n]:
                    self._put(c, out)
                bits.p += n; self.bremain -= n
                continue
            while self.bremain > 0 and len(out) < usize:
                s = self.main.sym(bits)
                if s < NUM_CHARS:
                    self._put(s, out); self.bremain -= 1
                    continue
                s -= NUM_CHARS
                ml = s & 7
                if ml == 7:
                    ml += self.lent.sym(bits)
                ml += MIN_MATCH
                slot = s >> 3
                if slot < 3:
                    off = self.R[slot]
                    self.R[slot] = self.R[0]; self.R[0] = off
                else:
                    ex = EXTRA[slot]
                    off = BASE[slot] - 2
                    if self.btype == 2 and ex >= 3:
                        off += (bits.read(ex - 3) << 3) + self.aligned.sym(bits)
                    else:
                        off += bits.read(ex)
                    self.R = [off, self.R[0], self.R[1]]
                for _ in range(ml):
                    self._put(self.win[(self.wp - off) & (self.wsize - 1)], out)
                self.bremain -= ml
        return bytes(out)


def decompress(raw, usize=None):
    d, p, out = LZX(), 0, bytearray()
    while p < len(raw) and (usize is None or len(out) < usize):
        if raw[p] == 0xFF:
            fu, fc = struct.unpack_from(">HH", raw, p + 1); p += 5
        else:
            fu, fc = 0x8000, struct.unpack_from(">H", raw, p)[0]; p += 2
        if fc == 0:
            break
        out += d.frame(raw[p:p + fc], fu)
        p += fc
    return bytes(out[:usize] if usize else out)


if __name__ == "__main__":
    open(sys.argv[2], "wb").write(decompress(open(sys.argv[1], "rb").read()))
