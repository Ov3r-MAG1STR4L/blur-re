#!/usr/bin/env python3
"""Music mod: add licensed race tracks to Blur (test copy only).

usage: make_music.py OUTDIR        (OUTDIR mirrors the game root: audio/ingamemusic.baf, audio/dat/music_controller.dat)

TRACKS: (object name suffix, wave name, source audio file). Each track:
  - audio converted with ffmpeg to 48 kHz stereo, encoded PS-ADPCM, appended to ingamemusic.baf (blurbaf.add_wave);
  - music_controller.dat (JBOA): a sound object copied from InGameMusic22 is APPENDED at the end of the object list
    (index = old count, so no existing reference moves), then the race-music selector (type 33, 8 words per entry),
    the licensed-music mixer (type 73, 17 words per input), the play script (switch on the selector: 5 words per case,
    4 per body, jump targets = word index in the script) and the stop script (3 words per track) get one entry more.
Layouts measured 2026-10-20 (docs/CONNAISSANCES.md, "Audio et musique").
"""
import os, struct, subprocess, sys, tempfile, wave
import numpy as np
import blurbaf

E = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "blur_extracted")
TRACKS = [("23", "ShutUpAndDrive", r"C:\Users\sanqu\Downloads\Rihanna - Shut Up And Drive(Lyrics)🎶.mp3")]
FF = 0xFFFF
FORCE_LAST = False    # test: every selector entry plays the last added track (False = random among all)
F1 = 0x3F800000                                           # 1.0f


LUFS = -10.2          # median loudness of the 24 original race tracks (measured 2026-10-20: -11.7 .. -8.6)


def pcm48(src):
    """48 kHz stereo int16, gain set so the integrated loudness matches the original tracks (limiter at -1 dBFS)."""
    m = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", src, "-af", "ebur128", "-f", "null", "-"],
                       capture_output=True, text=True).stderr
    gain = LUFS - float(m.rsplit("I:", 1)[1].split("LUFS")[0])
    print(f"  volume {gain:+.1f} dB vers {LUFS} LUFS")
    with tempfile.TemporaryDirectory() as d:
        out = os.path.join(d, "a.wav")
        subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", src, "-ar", "48000", "-ac", "2",
                        "-af", f"volume={gain}dB,alimiter=limit=0.89:level=false", out], check=True)
        with wave.open(out) as w:
            return np.frombuffer(w.readframes(w.getnframes()), "<i2").reshape(-1, 2).copy()


class Jboa:
    def __init__(self, b):
        assert b[:4] == b"JBOA"
        self.size, self.count = struct.unpack_from("<I", b, 8)[0], struct.unpack_from("<I", b, 0x10)[0]
        self.w = list(struct.unpack_from("<%dI" % ((self.size - 0x14) // 4), b, 0x14))   # object stream as words
        self.head = bytearray(b[:0x14])
        self.names = bytearray(b[self.size:])

    def name(self, s):
        """Offset of s in the name table (added at the end if missing)."""
        k = self.names.find(s.encode() + b"\0")
        while k > 0 and self.names[k - 1] != 0:                 # must be a whole string, not a suffix
            k = self.names.find(s.encode() + b"\0", k + 1)
        if k < 0:
            k = len(self.names)
            self.names += s.encode() + b"\0"
        return k

    def find(self, typ, name):
        """Word index of the object (type word) whose name is `name`."""
        n = self.name(name)
        hits = [i for i in range(len(self.w) - 1) if self.w[i] == typ and self.w[i + 1] == n]
        assert len(hits) == 1, (typ, name, hits)
        return hits[0]

    def build(self):
        body = struct.pack("<%dI" % len(self.w), *self.w)
        struct.pack_into("<I", self.head, 8, 0x14 + len(body))
        struct.pack_into("<I", self.head, 0x10, self.count)
        return bytes(self.head) + body + bytes(self.names)


def add_track(j, suffix, wave_name):
    f32 = lambda v: struct.unpack("<I", struct.pack("<f", v))[0]
    ref = lambda i: i << 16
    # sound object: copy of InGameMusic22 (14 words), new name / wave, appended at the end of the object list
    s = j.find(60, "InGameMusic22")
    obj = j.w[s:s + 14]
    assert obj[2] == j.name("InGameMusic") and obj[10] == 29, obj
    obj[1], obj[3] = j.name("InGameMusic" + suffix), j.name(wave_name)
    new = j.count
    j.w += obj
    j.count += 1
    # selector: [33, name, FF, 0, count] + count * [FF, k.0, FF, 1.0, FF, 0, FF, 1.0]
    s = j.find(33, "InGameMusicSelectorIndex")
    n = j.w[s + 4]
    j.w[s + 4] = n + 1
    j.w[s + 5 + 8 * n:s + 5 + 8 * n] = [FF, f32(n), FF, F1, FF, 0, FF, F1]
    # mixer: [73, name, FF, 0, FF, 1.0, count<<16] + count * 17 words, the last one = (19 << 16) | track object
    s = j.find(73, "InGameLicensedMusicMixer")
    m = j.w[s + 6] >> 16
    assert m == n, (m, n)
    last = s + 7 + 17 * (m - 1)
    entry = j.w[last:last + 17]
    assert entry[0] == 88 and entry[12] == 88 and entry[16] >> 16 == 19, entry
    entry[16] = (19 << 16) | new
    j.w[s + 6] = (m + 1) << 16
    j.w[last + 17:last + 17] = entry
    # play script: [189, name, len] + n cases [4887, sel, k.0, 4353, target] + [4610] + n bodies [4096, obj, 0, 4610]
    s = j.find(189, "InGameLicensedMusicPlayScript")
    code = j.w[s + 3:s + 3 + j.w[s + 2]]
    assert len(code) == 5 * n + 1 + 4 * n and code[5 * n] == 4610
    cases = [code[5 * k:5 * k + 5] for k in range(n)]
    bodies = [code[5 * n + 1 + 4 * k:5 * n + 5 + 4 * k] for k in range(n)]
    cases.append([4887, cases[0][1], f32(n), 4353, 0])
    bodies.append([4096, ref(new), 0, 4610])
    for k, c in enumerate(cases):
        c[4] = 5 * (n + 1) + 1 + 4 * k
    code2 = sum(cases, []) + [4610] + sum(bodies, [])
    j.w[s + 2] = len(code2)
    j.w[s + 3:s + 3 + len(code)] = code2
    # stop script: [189, name, len|len<<16] + n * [4096, obj, 1] + [4610]
    s = j.find(189, "InGameLicensedMusicStopScript")
    ln = j.w[s + 2] & 0xFFFF
    assert ln == 3 * n + 1 and j.w[s + 2] >> 16 == ln, hex(j.w[s + 2])
    j.w[s + 3 + 3 * n:s + 3 + 3 * n] = [4096, ref(new), 1]
    j.w[s + 2] = (ln + 3) | ((ln + 3) << 16)


def main(out):
    bank = open(os.path.join(E, "root_streaming", "ingamemusic.baf"), "rb").read()
    j = Jboa(open(os.path.join(E, "root", "audio", "dat", "music_controller.dat"), "rb").read())
    for suffix, wave_name, src in TRACKS:
        bank = blurbaf.add_wave(bank, wave_name, pcm48(src), 48000)
        add_track(j, suffix, wave_name)
        print("piste", "InGameMusic" + suffix, "=", wave_name)
    if FORCE_LAST:
        s = j.find(33, "InGameMusicSelectorIndex")
        for k in range(j.w[s + 4]):
            j.w[s + 6 + 8 * k] = j.w[s + 6 + 8 * (j.w[s + 4] - 1)]
        print("test : toutes les entrées du sélecteur jouent la dernière piste")
    os.makedirs(os.path.join(out, "audio", "dat"), exist_ok=True)
    open(os.path.join(out, "audio", "ingamemusic.baf"), "wb").write(bank)
    open(os.path.join(out, "audio", "dat", "music_controller.dat"), "wb").write(j.build())
    print("écrit dans", out)


if __name__ == "__main__":
    main(sys.argv[1])
