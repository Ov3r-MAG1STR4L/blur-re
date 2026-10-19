#!/usr/bin/env python3
"""Blur (2010, PC) .pak reader/extractor  --  format "2KAP" (Bizarre Creations "mercury.pakfs").

Layout (little-endian, page size = 0x800):
  0x00  '2KAP'  u32 version  u32 pagesize  u32 headersize
  0x10  header fields (flags, timestamp, build, sizes, short pak name)
  page1 u32 N, then N bytes of NAME TABLE (NUL-separated paths), XORed with
        the 14-byte key KEY below, key index = (i+1) % 14.
  next  (page aligned after 4+N) u32 count, u32 tablebytes, then count*40-byte entries:
        [pathhash, nameOfs, dirOfs, usize, crc, ?, startPage, flags, hash2, streamSize]
        (dir entries have usize == 0 / startPage == 0xffffffff style filler)
  data  file data at startPage*0x800: u32 blocksize (0x10000) then repeated
        [u32 csize][raw deflate block] until usize bytes have been produced.
"""
import struct, sys, os, zlib, argparse

KEY = b"xVXo40j3@$%\\%`"   # found in Blur_debug.exe @ 0xefab60
PAGE = 0x800


class Entry:
    __slots__ = ("raw", "path", "usize", "page", "csize", "flags", "crc")

    def __repr__(self):
        return "<%s usize=%d csize=%d page=%d flags=%d>" % (
            self.path, self.usize, self.csize, self.page, self.flags)


class Pak:
    def __init__(self, path):
        self.path = path
        self.f = open(path, "rb")
        h = self.f.read(0x30)
        if h[:4] != b"2KAP":
            raise ValueError("not a 2KAP pak: %r" % h[:4])
        self.version, self.pagesize, self.hdrsize = struct.unpack_from("<3I", h, 4)
        self.hdr = h
        self.f.seek(self.pagesize)
        n = struct.unpack("<I", self.f.read(4))[0]
        blob = bytearray(self.f.read(n))
        for i in range(n):
            blob[i] ^= KEY[(i + 1) % 14]
        self.names = bytes(blob)
        tab = (4 + n + self.pagesize - 1) // self.pagesize * self.pagesize
        self.f.seek(self.pagesize + tab)
        count, tbytes = struct.unpack("<II", self.f.read(8))
        self.count = count
        self.tab_off = self.pagesize + tab
        self.stride = tbytes // count if count else 40   # 40 (plain) or 64 (+24 bytes digest)
        raw = self.f.read(count * self.stride)
        self.entries = []
        for i in range(count):
            r = struct.unpack_from("<10I", raw, i * self.stride)
            e = Entry()
            e.raw = r
            j = self.names.index(b"\0", r[1])
            e.path = self.names[r[1]:j].decode("latin1")
            e.usize, e.crc, e.page, e.flags, e.csize = r[3], r[4], r[6], r[7], r[9]
            e.page = r[6]
            self.entries.append(e)
        self.files = [e for e in self.entries if e.csize or e.usize]

    def read(self, e):
        self.f.seek(e.page * self.pagesize)
        raw = self.f.read(e.csize)
        if e.csize == e.usize:                      # stored (root_streaming .baf ...)
            return raw
        if raw[:1] == b"\x78" and raw[1:2] in (b"\x01", b"\x5e", b"\x9c", b"\xda"):
            return zlib.decompress(raw)             # whole-file zlib (gamedata.pak)
        bs = struct.unpack_from("<I", raw, 0)[0]    # chunked raw-deflate (boot/root)
        p, out = 4, bytearray()
        while len(out) < e.usize:
            cs = struct.unpack_from("<I", raw, p)[0]
            out += zlib.decompressobj(-15).decompress(raw[p + 4:p + 4 + cs])
            p += 4 + cs
        return bytes(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pak")
    ap.add_argument("-l", action="store_true", help="list")
    ap.add_argument("-x", metavar="OUTDIR", help="extract all")
    ap.add_argument("--filter", default="")
    a = ap.parse_args()
    p = Pak(a.pak)
    print("# %s: version=%d files=%d entries=%d" % (a.pak, p.version, len(p.files), p.count))
    for e in p.files:
        if a.filter.lower() not in e.path.lower():
            continue
        if a.l:
            print("%10d %10d p%-8d f%d %s" % (e.usize, e.csize, e.page, e.flags, e.path))
        if a.x:
            dst = os.path.join(a.x, e.path.lstrip("\\/").replace("\\", os.sep))
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            try:
                data = p.read(e)
            except Exception as ex:
                print("FAIL", e.path, ex)
                continue
            open(dst, "wb").write(data)


if __name__ == "__main__":
    main()
