#!/usr/bin/env python3
"""Blur "Flask" (KSLF, .bin / .xt) reader.

Header (LE): 'KSLF' u32 ver(1|2) then 8 (offset,count) pairs starting at +8:
   0 types      12B x n   (u16 nameOfs, u16 nFields, u16 firstField, u16 kind, u16 prim, u16 size)
                          kind 3 = struct, 2 = bit flags, 1 = enum, 0 = primitive (prim = primitive code)
   1 u32 table  4B  x n
   2 fields     8B  x n   (u16 nameOfs, u16 typeIdx, u16 byteOfs, u16 flags)
   3 names      bytes     string pool, v2 = scrambled (decode_names), v1 = plain
   4 index      8B  x n   (u32 namehash, u16 rootType, u16 itemIdx)   sorted by hash
   5 items      16B x n   (u32 idx, u32 nChunks, u32 dataSize, u32 strSize)
   6 chunks     6B  x n   (u16 typeIdx, u16 count, u16 ptr: 0 objects, 1/2 = u32 intra/extern pointers) -- nChunks per item, in item order
   7 data blob  bytes     per item: dataSize bytes (its chunks back to back, chunk 0 = root
                          record) then strSize bytes of strings scrambled like the name pool.
Type 'base' u16 = has-parent flag; parents are taken in order from section 1 (u32 typeIdx).
Field value encoding (flags & 0xFF): 0 prim, 1 enum (ordinal), 3 inline struct,
   4 intra-record pointer u32 = chunk | elem<<16, 5 external ref (raw u32);
   flag 0x100 = array: u32 (chunk | start<<16), u32 count. sz8 = u32 offset in record strings.

Name decoding = Blur.exe 0x5871b0 (called from schema loader 0x5850d0 when ver == 2;
encoder is 0x5871f0). Loader entry 0x585660, validator 0x584700 ("Flask failed validation").
"""
import struct, sys


def decode_names(src):
    """Blur.exe 0x5871b0: chained byte cipher, key 0xCC / 0xB3. Last byte becomes NUL."""
    dl, out = 0xCC, bytearray()
    for i in range(len(src) - 1):
        al = (dl - (src[i] ^ 0xB3)) & 0xFF
        out.append(al)
        dl = (dl + al - i) & 0xFF
    return bytes(out) + b"\0"


def encode_names(plain):
    """Inverse of decode_names (Blur.exe 0x5871f0). Round trip is byte-identical on all 49 KSLF files."""
    dl, out = 0xCC, bytearray()
    for i, p in enumerate(plain):
        out.append(((dl - p) & 0xFF) ^ 0xB3)
        dl = (dl + p - i) & 0xFF
    return bytes(out)


class XT:
    def __init__(self, path):
        self.b = open(path, "rb").read()
        b = self.b
        assert b[:4] == b"KSLF"
        self.ver = struct.unpack_from("<I", b, 4)[0]
        v = struct.unpack_from("<16I", b, 8)
        self.sec = [(v[2 * i], v[2 * i + 1]) for i in range(8)]     # (offset, count)
        o, c = self.sec[3]
        raw = b[o:o + c]
        self.pool = decode_names(raw) if self.ver == 2 else raw

    def name(self, ofs):
        return self.pool[ofs:self.pool.index(b"\0", ofs)].decode("latin-1")

    def section(self, i, esize):
        off, cnt = self.sec[i]
        return [self.b[off + k * esize: off + (k + 1) * esize] for k in range(cnt)]

    def types(self):
        return [struct.unpack("<6H", e) for e in self.section(0, 12)]

    def fields(self):
        return [struct.unpack("<4H", e) for e in self.section(2, 8)]

    def schema(self):
        ts, fs = self.types(), self.fields()
        out, ff = [], 0                                  # struct fields are stored back to back
        for i, (no, nf, base, kind, prim, size) in enumerate(ts):
            flds = []
            if kind in (1, 2, 3):                        # enum/flag values live in the field table too (type 0xFFFF)
                flds = [(self.name(fs[k][0]), self.name(ts[fs[k][1]][0]) if fs[k][1] < len(ts) else "value",
                         fs[k][2], fs[k][3]) for k in range(ff, ff + nf)]
                ff += nf
            out.append((i, self.name(no), kind, prim, size, nf, flds))
        return out

    def index(self):
        return [struct.unpack("<IHH", e) for e in self.section(4, 8)]      # hash, ?, idx

    def items(self):
        return [struct.unpack("<4I", e) for e in self.section(5, 16)]

    @property
    def data(self):
        off, cnt = self.sec[7]
        return self.b[off:off + cnt]

    # ---- record values ----
    PRIM = {1: "<I", 4: "<i", 5: "<I", 6: "<I", 7: "<I", 10: "<f", 14: "<I"}   # 12 = sz8 handled apart

    def records(self):
        """Yield (name, typeName, value dict) for every record."""
        ts, fs = self.types(), self.fields()
        self._ts, self._names = ts, [self.name(t[0]) for t in ts]
        self._flds, ff = [], 0
        for no, nf, base, kind, prim, size in ts:
            self._flds.append(fs[ff:ff + nf] if kind in (1, 2, 3) else [])
            ff += nf if kind in (1, 2, 3) else 0
        parents = iter(struct.unpack("<I", e)[0] for e in self.section(1, 4))
        self._parent = [next(parents) if t[2] else None for t in ts]
        chunks = [struct.unpack("<3H", e) for e in self.section(6, 6)]
        self._ix = self.index()
        hash_of = {i: h for h, t, i in self._ix if i != 0xFFFF}
        d, p, c = self.data, 0, 0
        self._seen = []
        for idx, nch, dsize, ssize in self.items():
            ch, o = [], p
            for t, n, z in chunks[c:c + nch]:     # z != 0: chunk of u32 pointers (1 intra, 2 external)
                esz = 4 if z else ts[t][5]
                ch.append((t, n, o, esz)); o += esz * n
            c += nch
            self._d, self._ch = d, ch
            self._str = decode_names(d[p + dsize:p + dsize + ssize]) if ssize else b""
            root = ch[0][0]
            val = self._struct(root, ch[0][2], 0)
            yield val.get("Name") or val.get("name") or f"#{idx}", self._names[root], val, hash_of.get(len(self._seen), 0)
            self._seen.append(idx)
            p += dsize + ssize

    def _s(self, ofs):
        if ofs >= len(self._str):
            return None
        return self._str[ofs:self._str.index(b"\0", ofs)].decode("latin-1")

    def _elem(self, ref, depth):
        chunk, elem = ref & 0xFFFF, ref >> 16
        if chunk >= len(self._ch):
            return f"?{ref:#x}"
        t, n, o, esz = self._ch[chunk]
        if elem >= n:
            return f"?{ref:#x}"
        return self._value(t, o + elem * esz, 3 if self._ts[t][3] == 3 else 0, depth)

    def _value(self, t, o, low, depth):
        d, kind, prim = self._d, self._ts[t][3], self._ts[t][4]
        if low == 3 or (low == 0 and kind == 3):
            return self._struct(t, o, depth + 1)
        u = struct.unpack_from("<I", d, o)[0]
        if low in (4, 5) and u == 0xFFFFFFFF:
            return None                               # null pointer
        if low == 4:
            return self._elem(u, depth + 1) if depth < 8 else f"->{u:#x}"
        if low == 5:                                  # index slot -> record hash (may live in another file)
            return f"@{self._ix[u][0]:08x}" if u < len(self._ix) else f"ref:{u:#x}"
        if low == 1 or kind == 1:
            ev = self._flds[t]
            return self.name(ev[u][0]) if u < len(ev) else u
        if kind == 2:                                 # bit flags, bit n = n-th value
            return [self.name(e[0]) for n, e in enumerate(self._flds[t]) if u >> n & 1]
        if prim == 12:
            return self._s(u)
        if prim == 1:
            return bool(u)
        return struct.unpack_from(self.PRIM.get(prim, "<I"), d, o)[0]

    def _struct(self, t, o, depth):
        out = {}
        if self._parent[t] is not None:
            out.update(self._struct(self._parent[t], o, depth))
        for no, ft, fo, fl in self._flds[t]:
            low = fl & 0xFF
            if fl & 0x100:
                ref, n = struct.unpack_from("<II", self._d, o + fo)
                chunk, start = ref & 0xFFFF, ref >> 16
                if n == 0 or chunk >= len(self._ch):
                    v = []
                else:
                    ct, _, co, sz = self._ch[chunk]
                    v = [self._value(ct, co + (start + k) * sz, low, depth) for k in range(n)]
            else:
                v = self._value(ft, o + fo, low, depth)
            out[self.name(no)] = v
        return out

    # ---- in-place edit (same size only: numbers, bools, enums; not strings / arrays length) ----
    def _field(self, t, fname):
        while t is not None:
            for no, ft, fo, fl in self._flds[t]:
                if self.name(no) == fname:
                    return ft, fo, fl
            t = self._parent[t]
        raise KeyError(fname)

    def locate(self, record, path):
        """'Record', 'engine.engineTorque_Rpm.dataPoints[3]' -> (file offset, type idx, field flags)."""
        import re
        for name, _, _, _ in self.records():
            if name == record:
                break
        else:
            raise KeyError(record)
        t, o, fl = self._ch[0][0], self._ch[0][2], 3
        for seg in path.split("."):
            fname, i = re.fullmatch(r"(\w+)(?:\[(\d+)\])?", seg).groups()
            ft, fo, fl = self._field(t, fname)
            if fl & 0x100:
                ref, n = struct.unpack_from("<II", self._d, o + fo)
                if i is None or int(i) >= n:
                    raise IndexError(f"{seg}: array of {n}")
                ct, _, co, sz = self._ch[ref & 0xFFFF]
                t, o = ct, co + ((ref >> 16) + int(i)) * sz
            else:
                t, o = ft, o + fo
            if fl & 0xFF == 4:                        # intra-record pointer: follow it
                u = struct.unpack_from("<I", self._d, o)[0]
                ct, _, co, sz = self._ch[u & 0xFFFF]
                t, o = ct, co + (u >> 16) * sz
        return self.sec[7][0] + o, t, fl

    def patched(self, record, path, value):
        """Return a copy of the file bytes with one number / bool / enum changed in place."""
        off, t, fl = self.locate(record, path)
        kind, prim = self._ts[t][3], self._ts[t][4]
        if fl & 0xFF == 1 or kind == 1:
            names = [self.name(e[0]) for e in self._flds[t]]
            raw = struct.pack("<I", names.index(value) if isinstance(value, str) else int(value))
        elif kind != 0 or prim == 12 or fl & 0xFF in (3, 5):
            raise TypeError(f"{path}: only numbers, bools and enums can be edited in place")
        elif prim == 1:
            raw = struct.pack("<I", 1 if value in (True, 1, "1", "true", "True") else 0)
        elif prim == 10:
            raw = struct.pack("<f", float(value))
        else:
            raw = struct.pack(self.PRIM.get(prim, "<I"), int(value))
        b = bytearray(self.b)
        b[off:off + 4] = raw
        return bytes(b)


KIND = {0: "prim", 1: "enum", 2: "flags", 3: "struct"}

def _round(v):
    if isinstance(v, float):
        return float(f"{v:.6g}")
    if isinstance(v, dict):
        return {k: _round(x) for k, x in v.items()}
    if isinstance(v, list):
        return [_round(x) for x in v]
    return v


def export_all(paths, outdir):
    """Decode every file, then replace "@hash" refs by "file/Type/Name" across all files."""
    import json, os, re
    files, label = {}, {}
    for pth in paths:
        fn = os.path.splitext(os.path.basename(pth))[0]
        if fn == "actorpack":
            fn = os.path.basename(os.path.dirname(pth)) + ".actorpack"
        recs = {}
        for name, tname, val, h in XT(pth).records():
            grp = recs.setdefault(tname, {})
            key, k = name, 2
            while key in grp:                         # duplicate record names exist (e.g. per content pack)
                key, k = f"{name} ({k})", k + 1
            grp[key] = _round(val)
            if h:
                label.setdefault(f"@{h:08x}", f"{fn}/{tname}/{key}")
        files[fn] = recs
    rx = re.compile(r"@[0-9a-f]{8}")
    fix = lambda v: ({k: fix(x) for k, x in v.items()} if isinstance(v, dict) else
                     [fix(x) for x in v] if isinstance(v, list) else
                     label.get(v, v) if isinstance(v, str) and rx.fullmatch(v) else v)
    os.makedirs(outdir, exist_ok=True)
    for fn, recs in files.items():
        with open(os.path.join(outdir, fn + ".json"), "w", encoding="utf-8") as f:
            json.dump(fix(recs), f, indent=1, ensure_ascii=False)
    return files, label


if __name__ == "__main__" and len(sys.argv) == 7 and sys.argv[1] == "--set":
    # blurxt.py --set IN.bin OUT.bin "Record" "path.to.field[0]" VALUE   (never overwrite game files)
    x = XT(sys.argv[2])
    open(sys.argv[3], "wb").write(x.patched(sys.argv[4], sys.argv[5], sys.argv[6]))
    print("written", sys.argv[3])
elif __name__ == "__main__" and len(sys.argv) > 3 and sys.argv[1] == "--all":
    import glob                                       # blurxt.py --all XTDIR OUTDIR [more .bin/.xt ...]
    export_all(sorted(glob.glob(sys.argv[2] + "/*.bin")) + sys.argv[4:], sys.argv[3])
elif __name__ == "__main__" and len(sys.argv) > 2 and sys.argv[1] == "--json":
    import json                                       # blurxt.py --json FILE.bin > out.json
    x = XT(sys.argv[2])
    recs = {}
    for name, tname, val, _ in x.records():
        grp = recs.setdefault(tname, {})
        key, k = name, 2
        while key in grp:                             # duplicate record names exist (e.g. per content pack)
            key, k = f"{name} ({k})", k + 1
        grp[key] = _round(val)
    print(json.dumps(recs, indent=1, ensure_ascii=False))
elif __name__ == "__main__":
    x = XT(sys.argv[1])
    print(f"# {sys.argv[1]}  ver {x.ver}  sections {[(hex(o), c) for o, c in x.sec]}")
    for i, nm, kind, prim, size, nf, flds in x.schema():
        print(f"T{i:<3} {KIND.get(kind, kind):6} {nm}  size={size} n={nf}" + (f" prim={prim}" if kind == 0 else ""))
        for fn, ft, fo, fl in flds:
            print(f"      +{fo:<4} {fn:32} {ft}  flags={fl:#x}")
