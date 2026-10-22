#!/usr/bin/env python3
"""Blur KSLF writer: rebuild a .bin/.xt from its parts, clone records, append references.

Layout facts used (checked on all 49 KSLF files, see docs/CONNAISSANCES.md):
- 'KSLF', u32 version, 8 x (u32 offset, u32 count) at +8, then sections 0..7 back to back from 0x48;
  only section 7 (data) is aligned to 4 (zero padding). Counts are elements (sections 3 and 7: bytes).
- item = (index slot, nChunks, dataSize, stringSize); item.idx is ALWAYS the index slot of that item.
- each record = its chunks back to back (dataSize = sum of chunk sizes), then its scrambled strings
  (stringSize multiple of 4); records are 4-aligned and packed.
- index (section 4) is sorted by hash: (u32 hash, u16 type, u16 local item or 0xFFFF = other file).
New records get a hash ABOVE every existing hash of every file, so they are appended at the end of each
index and no existing slot moves. The game's own name->hash function is unknown: a record added this way
can be found by hash (references), not by a name lookup that would hash the name. [risk, untested in game]
"""
import struct
from blurxt import XT, decode_names, encode_names

ESIZE = [12, 4, 8, 1, 8, 16, 6, 1]


def ts_size(x, t):
    return x.types()[t][5]


class KSLF:
    def __init__(self, path):
        x = self.x = XT(path)
        self.version = x.ver
        raw = lambda i: x.b[x.sec[i][0]:x.sec[i][0] + x.sec[i][1] * ESIZE[i]]
        self.types, self.parents, self.fields, self.pool = raw(0), raw(1), raw(2), raw(3)
        self.index = [struct.unpack("<IHH", e) for e in x.section(4, 8)]
        self.chunks = [struct.unpack("<3H", e) for e in x.section(6, 6)]
        # records: (idx, [chunks], data bytes, string bytes)
        self.records, d, p, c = [], x.data, 0, 0
        for idx, nch, ds, ss in x.items():
            self.records.append([idx, self.chunks[c:c + nch], d[p:p + ds], d[p + ds:p + ds + ss]])
            c += nch
            p += ds + ss

    # ---- helpers ----
    def _record_pos(self, name):
        """record number of the record called `name` (records() yields them in file order)."""
        for k, (n, _, _, _) in enumerate(self.x.records()):
            if n == name:
                return k
        raise KeyError(name)

    def _rel(self, abs_off, k):
        """file offset -> offset inside record k's data."""
        start = self.x.sec[7][0] + sum(len(r[2]) + len(r[3]) for r in self.records[:k])
        return abs_off - start

    def type_index(self, type_name):
        names = [self.x.name(t[0]) for t in self.x.types()]
        return names.index(type_name)

    # ---- edits ----
    def clone(self, src, new_name, new_hash):
        """Append a copy of record `src` named `new_name`, reachable by `new_hash`. Returns its record number."""
        k = self._record_pos(src)
        idx, chunks, data, strings = self.records[k]
        name_off = None
        for field in ("Name", "name"):
            try:
                name_off = self._rel(self.x.locate(src, field)[0], k)
                break
            except KeyError:
                pass
        if name_off is not None and new_name:         # nameless records (e.g. LevelActorList) keep no name
            plain = decode_names(strings) if strings else b""
            new_ofs = len(plain)
            plain += new_name.encode("latin-1") + b"\0"
            plain += b"\0" * ((-len(plain)) % 4)
            data = bytearray(data)
            struct.pack_into("<I", data, name_off, new_ofs)
            strings = encode_names(plain)
        root_type = self.index[idx][1]
        self.index.append((new_hash, root_type, len(self.records)))
        self.records.append([len(self.index) - 1, list(chunks), bytes(data), strings])
        return len(self.records) - 1

    def get_array_refs(self, owner, field):
        """Index slots (u32) of a top-level reference array of `owner`, in order."""
        k = self._record_pos(owner)
        x = self.x
        ft, fo, fl = x._field(x._ch[0][0], field)
        idx, chunks, data, strings = self.records[k]
        ref, n = struct.unpack_from("<II", data, fo)
        c, start = ref & 0xFFFF, ref >> 16
        at = sum((4 if z else ts_size(x, t2)) * n2 for t2, n2, z in chunks[:c]) + start * 4
        return list(struct.unpack_from("<%dI" % n, data, at))

    def set_array_ref(self, owner, field, i, slot):
        """Replace element i of a top-level reference array of `owner` by index slot `slot`."""
        k = self._record_pos(owner)
        x = self.x
        ft, fo, fl = x._field(x._ch[0][0], field)
        idx, chunks, data, strings = self.records[k]
        ref, n = struct.unpack_from("<II", data, fo)
        if not (fl & 0x100 and i < n):
            raise IndexError(f"{field}[{i}]")
        c, start = ref & 0xFFFF, ref >> 16
        if not chunks[c][2]:
            raise TypeError(f"{field} is not an array of references")
        at = sum((4 if z else ts_size(x, t2)) * n2 for t2, n2, z in chunks[:c]) + (start + i) * 4
        data = bytearray(data)
        struct.pack_into("<I", data, at, slot)
        self.records[k] = [idx, chunks, bytes(data), strings]

    def add_external(self, hash_, type_name):
        """Index slot for a record living in another file (appended: hash must be above all others)."""
        self.index.append((hash_, self.type_index(type_name), 0xFFFF))
        return len(self.index) - 1

    def _refs(self, t, o, out, seen):
        """Collect ('arr'|'ptr', blob offset) of every array descriptor / intra pointer reachable in the
        current record of self.x (offsets are in the data blob)."""
        x = self.x
        while t is not None:
            for no, ft, fo, fl in x._flds[t]:
                low = fl & 0xFF
                if fl & 0x100:
                    out.append(("arr", o + fo))
                    ref, n = struct.unpack_from("<II", x._d, o + fo)
                    if n and (ref & 0xFFFF) < len(x._ch):
                        ct, _, co, sz = x._ch[ref & 0xFFFF]
                        for k in range(n):
                            e = co + ((ref >> 16) + k) * sz
                            if low == 3:
                                self._refs(ct, e, out, seen)
                            elif low == 4:
                                self._ptr(e, out, seen)
                elif low == 3 or (low == 0 and x._ts[ft][3] == 3):
                    self._refs(ft, o + fo, out, seen)
                elif low == 4:
                    self._ptr(o + fo, out, seen)
            t = self.x._parent[t]

    def _ptr(self, at, out, seen):
        out.append(("ptr", at))
        u = struct.unpack_from("<I", self.x._d, at)[0]
        if u == 0xFFFFFFFF or (u & 0xFFFF) >= len(self.x._ch) or u in seen:
            return
        seen.add(u)
        ct, n, co, sz = self.x._ch[u & 0xFFFF]
        if (u >> 16) < n and self.x._ts[ct][3] == 3:
            self._refs(ct, co + (u >> 16) * sz, out, seen)

    def append_to_array(self, owner, field, slot):
        """Append u32 `slot` (an index slot = reference) at the end of a top-level array of `owner`.
        Arrays / intra pointers of the record that point later into the same chunk are shifted."""
        k = self._record_pos(owner)                   # also leaves self.x positioned on that record
        x = self.x
        t, rec0 = x._ch[0][0], x._ch[0][2]            # root type, blob offset of the record
        ft, fo, fl = x._field(t, field)
        if not fl & 0x100:
            raise TypeError(f"{field} is not an array")
        idx, chunks, data, strings = self.records[k]
        data = bytearray(data)
        desc = fo                                     # root struct starts at record offset 0
        ref, n = struct.unpack_from("<II", data, desc)
        c, pos = ref & 0xFFFF, (ref >> 16) + n        # insertion element index inside chunk c
        found = []
        self._refs(t, rec0, found, set())
        for kind, at in found:
            r = at - rec0
            if kind == "arr" and r != desc:
                a, m = struct.unpack_from("<II", data, r)
                if (a & 0xFFFF) == c and (a >> 16) >= pos:
                    struct.pack_into("<I", data, r, a + 0x10000)
            elif kind == "ptr":
                u = struct.unpack_from("<I", data, r)[0]
                if u != 0xFFFFFFFF and (u & 0xFFFF) == c and (u >> 16) >= pos:
                    struct.pack_into("<I", data, r, u + 0x10000)
        struct.pack_into("<II", data, desc, ref, n + 1)
        ct, cn, cz = chunks[c]
        esz = 4 if cz else ts_size(x, ct)
        if esz != 4:
            raise NotImplementedError("only arrays of references (4-byte elements)")
        at = sum((4 if z else ts_size(x, t2)) * n2 for t2, n2, z in chunks[:c]) + pos * esz
        data[at:at] = struct.pack("<I", slot)
        chunks = list(chunks)
        chunks[c] = (ct, cn + 1, cz)
        self.records[k] = [idx, chunks, bytes(data), strings]

    def build(self):
        index = b"".join(struct.pack("<IHH", *e) for e in self.index)
        items = b"".join(struct.pack("<4I", r[0], len(r[1]), len(r[2]), len(r[3])) for r in self.records)
        chunks = b"".join(struct.pack("<3H", *ch) for r in self.records for ch in r[1])
        data = b"".join(r[2] + r[3] for r in self.records)
        parts = [self.types, self.parents, self.fields, self.pool, index, items, chunks]
        counts = [len(self.types) // 12, len(self.parents) // 4, len(self.fields) // 8, len(self.pool),
                  len(self.index), len(self.records), sum(len(r[1]) for r in self.records)]
        body, offs, o = b"", [], 0x48
        for part in parts:
            offs.append(o)
            body += part
            o += len(part)
        pad = (-o) % 4
        offs.append(o + pad)
        counts.append(len(data))
        head = b"KSLF" + struct.pack("<I", self.version) + b"".join(struct.pack("<II", a, n) for a, n in zip(offs, counts))
        return head + body + b"\0" * pad + data
