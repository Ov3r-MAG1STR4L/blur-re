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
        ch *= tracks or 1
        if codec == 3 and size == 0x50:          # PCM16 entry: +0x3C rate, +0x40 bits, +0x44 channels
            rate, bits, ch = struct.unpack_from("<3I", b, off + 0x3C)
            samples, loop, tracks, unk = length // (2 * max(ch, 1)), 0, 0, 0
        waves.append(dict(name=name, codec=codec, start=start, size=length, rate=rate, samples=samples,
                          loop=loop, tracks=tracks, unk=unk, channels=ch, entry=off))
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


def _encode_channel(x):
    """PS-ADPCM encoder for one channel (int array) -> (frames, 0x21) uint8; exact mirror of decode_psx."""
    import numba

    @numba.njit(cache=True)
    def enc(x, coefs):
        n = len(x) // 64
        out = np.zeros((n, 0x21), np.uint8)
        h1 = h2 = 0
        for i in range(n):
            best_err, best = 1e30, (0, 0, 0, 0)
            for filt in range(5):
                c1, c2 = coefs[filt]
                for shift in range(13):
                    a1, a2, err = h1, h2, 0.0
                    for k in range(64):
                        pred = (a1 * c1 + a2 * c2 + 32) >> 6
                        q = ((x[i * 64 + k] - pred) * (1 << shift) + (1 << 11)) >> 12   # round to nibble
                        q = -8 if q < -8 else 7 if q > 7 else q
                        v = ((q << 12) >> shift) + pred
                        v = -32768 if v < -32768 else 32767 if v > 32767 else v
                        d = x[i * 64 + k] - v
                        err += d * d
                        if err >= best_err:
                            break
                        a2, a1 = a1, v
                    if err < best_err:
                        best_err, best = err, (filt, shift, a1, a2)
            filt, shift = best[0], best[1]
            c1, c2 = coefs[filt]
            out[i, 0] = (filt << 4) | shift
            for k in range(64):
                pred = (h1 * c1 + h2 * c2 + 32) >> 6
                q = ((x[i * 64 + k] - pred) * (1 << shift) + (1 << 11)) >> 12
                q = -8 if q < -8 else 7 if q > 7 else q
                v = ((q << 12) >> shift) + pred
                v = -32768 if v < -32768 else 32767 if v > 32767 else v
                h2, h1 = h1, v
                out[i, 1 + k // 2] |= (q & 0xF) << (4 * (k & 1))
        return out

    return enc(x.astype(np.int64), np.array(FILTERS, np.int64))


def encode_psx(pcm):
    """int16 (samples, channels) -> PS-ADPCM bytes, frames interleaved per channel (padded to 64 samples)."""
    pad = (-len(pcm)) % 64
    pcm = np.vstack([pcm, np.zeros((pad, pcm.shape[1]), pcm.dtype)])
    frames = [_encode_channel(pcm[:, c]) for c in range(pcm.shape[1])]
    return np.stack(frames, axis=1).tobytes()


def add_pcm_wave(b, name, pcm, rate):
    """Like add_wave, uncompressed: codec 3 = PCM16, entry 0x50 bytes as the game's own PCM sounds (the *_sync_loop
    tracks of ingamecustommusic.baf, streamed): +0x3C rate, +0x40 bits (16), +0x44 channels, +0x48 0, +0x4C 0xFF."""
    data = pcm.astype("<i2").tobytes()
    out = bytearray(add_wave(b, name, None, rate, data=data, samples=len(pcm), channels=pcm.shape[1], entry_size=0x50))
    bank = parse(bytes(out))
    e = bank["waves"][-1]["entry"]
    struct.pack_into("<I", out, e + 0x08, 3)
    struct.pack_into("<5I", out, e + 0x3C, rate, 16, pcm.shape[1], 0, 0xFF)
    return bytes(out)


def add_wave(b, name, pcm, rate, data=None, samples=None, channels=2, entry_size=0x4C):
    """Return bank bytes with one more codec-7 WAVE appended (entry written in the padding before the first data;
    data at the end, 0x800-aligned, preceded by 'DATA' + u32 size+8 like the existing ones).
    pcm = int16 (samples, channels), or pcm=None with data (already encoded, encode_psx) + samples."""
    bank = parse(b)
    first_data = min(w["start"] for w in bank["waves"])
    last = bank["waves"][-1]["entry"]
    end_entries = last + struct.unpack_from("<I", b, last + 4)[0]     # entries are 0x4C (ADPCM) or 0x50 (PCM)
    out = bytearray(b)
    if end_entries + entry_size > first_data - 8:                   # no room: shift every sound by one 0x800 page
        out[first_data - 8:first_data - 8] = b"\0" * 0x800
        for w in bank["waves"]:
            struct.pack_into("<I", out, w["entry"] + 0x2C, w["start"] + 0x800)
    if pcm is not None:
        data, samples, channels = encode_psx(pcm), len(pcm), pcm.shape[1]
    out += b"\0" * ((-(len(out) + 8)) % 0x800)
    out += b"DATA" + struct.pack("<I", len(data) + 8)
    start = len(out)
    out += data + b"\0" * ((-len(data)) % 0x800)
    sib = next(w["entry"] for w in reversed(bank["waves"]) if w["codec"] == 7)
    e = bytearray(b[sib:sib + 0x4C]).ljust(entry_size, b"\0")            # copy the flags of an ADPCM sibling
    struct.pack_into("<I", e, 4, entry_size)
    e[0x0C:0x2C] = name.encode().ljust(0x20, b"\0")
    struct.pack_into("<2I", e, 0x2C, start, len(data))
    struct.pack_into("<2I", e, 0x40, rate, samples)
    e[0x4B] = channels
    out[end_entries:end_entries + entry_size] = e
    struct.pack_into("<I", out, 0x0C, len(bank["waves"]) + 1)
    return bytes(out)


def replace_wave(b, name, pcm=None, rate=None, data=None):
    """Return bank bytes where the existing codec-7 WAVE `name` plays `pcm` (int16 (samples, channels)) instead.
    In-memory banks (ingameui, frontendui...) are packed: one 'DATA' + u32 (size + 8) block per sound, in entry order,
    back to back, the last one ending the file. Appending 0x800-aligned blocks there (the streamed music banks' layout)
    broke other sounds in game (2026-10-26): the bank is rebuilt in that packed layout instead.
    data = already encoded bytes (pcm only gives the sample count then); used to check the identical round trip."""
    bank = parse(b)
    w = bank["waves"]
    starts = [x["start"] for x in w]
    assert all(starts[i] + w[i]["size"] + 8 == starts[i + 1] for i in range(len(w) - 1)), "not a packed bank"
    assert starts[-1] + w[-1]["size"] == len(b), "not a packed bank"
    k = next(i for i, x in enumerate(w) if x["name"] == name)
    assert w[k]["codec"] == 7, name
    if data is None:
        data = encode_psx(pcm)
    out = bytearray(b[:starts[0] - 8])
    for i, x in enumerate(w):
        blob = data if i == k else b[x["start"]:x["start"] + x["size"]]
        out += b"DATA" + struct.pack("<I", len(blob) + 8)
        struct.pack_into("<2I", out, x["entry"] + 0x2C, len(out), len(blob))
        out += blob
    if pcm is not None:
        struct.pack_into("<2I", out, w[k]["entry"] + 0x40, rate, len(pcm))
        out[w[k]["entry"] + 0x4B] = pcm.shape[1]
    return bytes(out)


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
