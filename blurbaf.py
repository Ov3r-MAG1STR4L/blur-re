#!/usr/bin/env python3
"""Blur (PC) audio bank .baf ("BANK", version 4) - list and decode to WAV.

Layout (LE), after vgmstream meta/baf.c (Blur PS3 = same layout as PC):
  0x00 'BANK'  u32 header size (= offset of the first WAVE)  u32 version (4)  u32 wave count
  0x10 u8 1?  u8 padding flag?  0x12 bank name (0x22)
  WAVE entries back to back: 'WAVE' u32 entry size (0x4C) u32 codec, name (0x20 at +0x0C),
       +0x2C data offset (absolute), +0x30 data size, +0x34 f32 volume? (1.0), +0x38 u32 0x19, +0x3C u32 0,
       +0x40 sample rate, +0x44 samples per channel, +0x48 u8 loop, +0x49 u8 tracks, +0x4A u8 ?, +0x4B u8 channels
  then 'DATA' u32 size, sound data (offsets point inside).
Codec 7 = PS-ADPCM in 0x21-byte frames (1 header byte: high nibble filter, low nibble shift; 32 bytes = 64 nibbles,
low nibble first), frames interleaved per channel (frame ch0, frame ch1, ...). Codec 3 = PCM16.

usage: blurbaf.py BANK.baf                 list
       blurbaf.py BANK.baf NAME OUT.wav    decode one sound
"""
import struct, sys, wave
import numpy as np

FILTERS = [(0, 0), (60, 0), (115, -52), (98, -55), (122, -60)]


def parse(b):
    assert b[:4] == b"BANK", "not a BANK file"
    off, version, count = struct.unpack_from("<3I", b, 4)
    waves = []
    for _ in range(count):
        assert b[off:off + 4] == b"WAVE", hex(off)
        size, codec = struct.unpack_from("<2I", b, off + 4)
        name = b[off + 0x0C:off + 0x2C].split(b"\0")[0].decode()
        start, length = struct.unpack_from("<2I", b, off + 0x2C)
        rate, samples = struct.unpack_from("<2I", b, off + 0x40)
        loop, tracks, unk, ch = b[off + 0x48:off + 0x4C]
        waves.append(dict(name=name, codec=codec, start=start, size=length, rate=rate, samples=samples,
                          loop=loop, tracks=tracks, unk=unk, channels=ch * (tracks or 1), entry=off))
        off += size
    return dict(version=version, name=b[0x12:0x34].split(b"\0")[0].decode(), waves=waves)


def decode_psx(data, channels, samples):
    """PS-ADPCM, 0x21-byte frames interleaved per channel -> int16 array (samples, channels)."""
    fr = np.frombuffer(data[:len(data) // (0x21 * channels) * 0x21 * channels], np.uint8).reshape(-1, channels, 0x21)
    out = np.zeros((fr.shape[0] * 64, channels), np.int16)
    for c in range(channels):
        f = fr[:, c]
        hdr = f[:, 0]
        shift, filt = hdr & 0x0F, np.minimum(hdr >> 4, 4)
        nib = np.empty((f.shape[0], 64), np.int32)
        nib[:, 0::2], nib[:, 1::2] = f[:, 1:] & 0x0F, f[:, 1:] >> 4
        nib = np.where(nib >= 8, nib - 16, nib)
        raw = (nib << 12) >> shift[:, None].astype(np.int32)        # ponytail: python loop for the IIR filter, ~1 s/min of audio
        h1 = h2 = 0
        res = out[:, c]
        k = 0
        for i in range(f.shape[0]):
            c1, c2 = FILTERS[filt[i]]
            for s in raw[i]:
                v = s + ((h1 * c1 + h2 * c2 + 32) >> 6)
                v = -32768 if v < -32768 else 32767 if v > 32767 else v
                res[k] = v
                h2, h1 = h1, v
                k += 1
    return out[:samples]


def decode(b, w):
    data = b[w["start"]:w["start"] + w["size"]]
    if w["codec"] == 3:
        return np.frombuffer(data, "<i2").reshape(-1, w["channels"])
    if w["codec"] == 7:
        return decode_psx(data, w["channels"], w["samples"])
    raise NotImplementedError(f"codec {w['codec']}")


def write_wav(path, pcm, rate):
    with wave.open(path, "wb") as o:
        o.setnchannels(pcm.shape[1]); o.setsampwidth(2); o.setframerate(rate)
        o.writeframes(pcm.astype("<i2").tobytes())


if __name__ == "__main__":
    b = open(sys.argv[1], "rb").read()
    bank = parse(b)
    if len(sys.argv) == 2:
        print(f"bank {bank['name']!r} v{bank['version']} {len(bank['waves'])} sons")
        for w in bank["waves"]:
            print(f"  {w['name']:32} codec {w['codec']} {w['rate']} Hz {w['channels']} can. "
                  f"{w['samples'] / max(w['rate'], 1):6.1f} s  boucle {w['loop']} pistes {w['tracks']} ?{w['unk']}"
                  f"  @{w['start']:#x} {w['size']}")
    else:
        w = next(w for w in bank["waves"] if w["name"] == sys.argv[2])
        write_wav(sys.argv[3], decode(b, w), w["rate"])
        print("écrit", sys.argv[3])
