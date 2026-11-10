#!/usr/bin/env python3
"""Vertex / face streams of Blur .model (CPModel) files, read and vertex colours rewritten in place.

Independent of the Blender add-on (which fails on the "Model" header variant and on some section layouts):
the stream section is found by its signature and every stream is validated strictly.

Layout (little endian, "RA" = 52 41 00 00 marker), per vertex stream:
  02 | RA 01 00 | RA | u32 stride | RA | u32 n_elements | n x (RA | u32 type | u32 ? | u32 channel | u32 sub)
  | RA | u32 n | n x u16 (element offsets) | u32 count | RA | u32 length (= count x stride) | u32 16 | data
face streams follow: u32 n | n x (02 | RA 01 00 | u32 count | u32 0 | RA | u32 length | u32 16 | data (u16))
Element types: 6 float3 (position), 7 16 bytes (skin, stride arithmetic), 0xB 4 bytes (channel 3 normal, channel 9 colour), 8 half2, 9 half4, 0xA 4 bytes.
Colour element (0xB, channel 9): see docs/CONNAISSANCES.md, vertex colours.
"""
import struct
import sys

TYPE_SIZE = {6: 12, 7: 16, 0xB: 4, 8: 4, 9: 8, 0xA: 4}
RA = b"RA\0\0"
STREAM = b"\x02RA\x01\0"
COLOUR = (0xB, 9)


def _u32(d, o):
    return struct.unpack_from("<I", d, o)[0]


def _vertex_stream(d, o):
    """one vertex stream at o (its 02 byte) -> (stream dict, offset after its data) or None if it does not validate"""
    if d[o:o + 5] != STREAM or d[o + 5:o + 9] != RA or d[o + 13:o + 17] != RA:
        return None
    stride, n = _u32(d, o + 9), _u32(d, o + 17)
    if not 0 < n <= 16:
        return None
    p, off, elements = o + 21, 0, []
    for _ in range(n):
        if d[p:p + 4] != RA:
            return None
        t, unk, ch, sub = struct.unpack_from("<4I", d, p + 4)
        if t not in TYPE_SIZE:
            return None
        elements.append({"type": t, "unknown": unk, "channel": ch, "sub": sub, "offset": off})
        off, p = off + TYPE_SIZE[t], p + 20
    if off != stride or d[p:p + 4] != RA:
        return None
    k = _u32(d, p + 4)
    p += 8 + 2 * k
    count = _u32(d, p)
    if d[p + 4:p + 8] != RA:
        return None
    length = _u32(d, p + 8)
    start = p + 16
    if length != count * stride or start + length > len(d):
        return None
    return {"start": start, "count": count, "stride": stride, "length": length, "elements": elements,
            "header": o}, start + length


def _anchor(d, s, marker):
    """data sit just before the next marker, after zero padding (0..31 bytes, the u32 16 alignment): move start"""
    e = d.find(marker, s["start"] + s["length"])
    while 0 <= e:
        pad = e - s["length"] - s["start"]
        if pad > 31:
            break
        if not any(d[s["start"]:s["start"] + pad]):
            s["start"] += pad
            s["pad"] = pad
            return True
        e = d.find(marker, e + 1)
    return False


def _face_streams(d, o):
    """face streams after the vertex streams: the u32 count just before the first 02 RA 01 00"""
    j = d.find(STREAM, o)
    if j < 4:
        return None
    n, p, out = _u32(d, j - 4), j, []
    for _ in range(n):
        if d[p:p + 5] != STREAM:
            return None
        count = _u32(d, p + 5)
        length = _u32(d, p + 17)
        if d[p + 13:p + 17] != RA or length != 2 * count or p + 25 + length > len(d):
            return None
        out.append({"start": p + 25, "count": count, "length": length, "header": p})
        if not _anchor(d, out[-1], STREAM if len(out) < n else RA):
            return None
        p = out[-1]["start"] + length
    return out


def read(d):
    """{"vertex_streams": [...], "face_streams": [...]} ; raises ValueError if no consistent stream section"""
    j = 0
    while True:
        j = d.find(STREAM, j + 1)
        if j < 4:
            raise ValueError("no vertex stream section")
        n = _u32(d, j - 4)
        if not 0 < n <= 64:
            continue
        streams, p = [], j
        for _ in range(n):
            r = _vertex_stream(d, p)
            if r is None:
                break
            streams.append(r[0])
            if not _anchor(d, r[0], STREAM if len(streams) < n else RA):    # last: RA, u32 n, face streams
                break
            p = r[0]["start"] + r[0]["length"]
        if len(streams) == n and d[p:p + 4] == RA and d[p + 8:p + 13] == STREAM:
            break
    faces = _face_streams(d, p)
    if faces is None:
        raise ValueError("face streams not found after the vertex streams")
    top = max(s["count"] for s in streams)
    for f in faces:      # meshes pick their vertex stream elsewhere: every index must at least fit the largest
        hi = max(struct.unpack_from("<%dH" % f["count"], d, f["start"]), default=0)
        if hi >= top:
            raise ValueError("face index %d beyond every vertex stream" % hi)
    return {"vertex_streams": streams, "face_streams": faces}


def colour_offset(stream):
    """byte offset of the colour element in the vertex, or None"""
    return next((e["offset"] for e in stream["elements"] if (e["type"], e["channel"]) == COLOUR), None)


def colours(d, stream):
    """[4 raw bytes as a tuple] for every vertex of a stream that has a colour element"""
    o = colour_offset(stream)
    if o is None:
        raise ValueError("stream has no colour element")
    b = stream["start"] + o
    return [tuple(d[b + i * stream["stride"]:b + i * stream["stride"] + 4]) for i in range(stream["count"])]


def set_colours(d, stream, new):
    """copy of d with {vertex index: 4 raw bytes} written; checks that nothing else changed"""
    o = colour_offset(stream)
    if o is None:
        raise ValueError("stream has no colour element")
    out, touched = bytearray(d), set()
    for i, raw in new.items():
        if not 0 <= i < stream["count"]:
            raise IndexError(i)
        a = stream["start"] + i * stream["stride"] + o
        out[a:a + 4] = bytes(raw)          # bytes() refuses values outside 0..255, length checked below
        touched.update(range(a, a + 4))
    assert len(out) == len(d)
    a = memoryview(d)
    for k in range(0, len(d), 1 << 16):     # changed bytes must all be colour bytes we wrote
        if a[k:k + 65536] != out[k:k + 65536]:
            assert all(k + j in touched for j in range(min(65536, len(d) - k)) if d[k + j] != out[k + j])
    return bytes(out)


def describe(d):
    m = read(d)
    for i, s in enumerate(m["vertex_streams"]):
        el = " ".join("%X/%d@%d" % (e["type"], e["channel"], e["offset"]) for e in s["elements"])
        print("  vs%d %6d x %2d  %s%s" % (i, s["count"], s["stride"], el,
                                          "  COLOUR" if colour_offset(s) is not None else ""))
    for i, f in enumerate(m["face_streams"]):
        print("  fs%d %6d indices" % (i, f["count"]))


if __name__ == "__main__":
    for path in sys.argv[1:]:
        print(path)
        describe(open(path, "rb").read())
