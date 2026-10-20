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
# (wave name in the bank, source file, start, end) ; start / end "mm:ss" cut a long mix, None = whole file.
# Object names follow: InGameMusic23, 24, ...
MIX = r"C:\Users\sanqu\Downloads\『BLUR』reimagined SOUNDTRACK.mp3"     # unofficial fan selection, 20 tracks
_MIX_CUTS = [("Wonderdawgs", "00:00"), ("Primal", "01:54"), ("FreshToDeath", "04:12"), ("StarGuitarRemake", "06:06"),
             ("RightAway", "10:51"), ("TheDeep", "13:40"), ("DirtyBoxing", "15:56"), ("SwagDCBreaks", "18:57"),
             ("RabbitInYourHeadlights", "22:05"), ("Freefall", "24:08"), ("OrbitofrontalEntourage", "26:01"),
             ("BlackOutDays", "27:46"), ("Pressure", "30:19"), ("Doubt", "33:15"), ("NeonBeams", "35:28"),
             ("TheDifference", "38:15"), ("RubixCube", "41:35"), ("Spooked", "44:12"), ("NarcoTourists", "46:26"),
             ("Tomorrow", "51:23")]
# removed after listening in game (2026-10-21, player's choice: too calm / too strange / too long)
_DROPPED = {"RightAway", "SwagDCBreaks", "OrbitofrontalEntourage", "Pressure", "NeonBeams", "TheDifference",
            "RubixCube", "Tomorrow"}
TRACKS = [("ShutUpAndDrive", r"C:\Users\sanqu\Downloads\Rihanna - Shut Up And Drive(Lyrics)🎶.mp3", None, None)] + \
         [(n, MIX, t, _MIX_CUTS[k + 1][1] if k + 1 < len(_MIX_CUTS) else None) for k, (n, t) in enumerate(_MIX_CUTS)
          if n not in _DROPPED]
FF = 0xFFFF
FORCE_LAST = False    # test: every selector entry plays the last added track (False = random among all)
F1 = 0x3F800000                                           # 1.0f


LUFS = -9.0           # added tracks: a bit above the originals (median -10.2, full tracks -12.2 .. -8.7) to cut through engines


def pcm48(src, start=None, end=None):
    """48 kHz stereo int16 of src[start:end], gain set so the integrated loudness matches the original tracks
    (limiter at -1 dBFS)."""
    cut = (["-ss", start] if start else []) + (["-to", end] if end else [])
    m = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", *cut, "-i", src, "-af", "ebur128", "-f", "null", "-"],
                       capture_output=True, encoding="utf-8", errors="replace").stderr   # file names like 『BLUR』
    gain = LUFS - float(m.rsplit("I:", 1)[1].split("LUFS")[0])
    print(f"  volume {gain:+.1f} dB vers {LUFS} LUFS")
    with tempfile.TemporaryDirectory() as d:
        out = os.path.join(d, "a.wav")
        subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *cut, "-i", src, "-ar", "48000", "-ac", "2",
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


def split_selector(j):
    """Selectors above 32 entries misbehave in game (2026-10-20, 44 entries: entry 32 played 3 races out of 4, entries
    33+ never; no original selector has more than 23). Split the race-music selector in two halves A / B (<= 32 each)
    plus a 2-entry group selector (heads or tails), so every track keeps the same chance.
    NextTrackScript: [0x1000 sel 0, 0x1200 play, 0x1202] -> also picks B and the group.
    PlayScript: if group == 0 -> A cases, else B cases; bodies unchanged (one per track, same order)."""
    f32 = lambda v: struct.unpack("<I", struct.pack("<f", v))[0]
    s = j.find(33, "InGameMusicSelectorIndex")
    n = j.w[s + 4]
    if n <= 32:
        return
    a = (n + 1) // 2
    entries = j.w[s + 5:s + 5 + 8 * n]
    nt = j.find(189, "InGameLicensedMusicNextTrackScript")
    sel_a = j.w[nt + 4] >> 16                               # object index of the selector (31), from its first use
    j.w[s + 4] = a
    del j.w[s + 5 + 8 * a:s + 5 + 8 * n]
    sel_b, group = j.count, j.count + 1
    j.w += [33, j.name("InGameMusicSelectorIndexB"), FF, 0, n - a] + entries[8 * a:]
    j.w += [33, j.name("InGameMusicGroupSelector"), FF, 0, 2] + entries[:16]           # entries 0.0 and 1.0
    j.count += 2
    s = j.find(189, "InGameLicensedMusicNextTrackScript")
    code = j.w[s + 3:s + 3 + j.w[s + 2]]
    assert code[:3] == [0x1000, sel_a << 16, 0] and code[-1] == 0x1202, code
    code2 = code[:3] + [0x1000, sel_b << 16, 0, 0x1000, group << 16, 0] + code[3:]
    j.w[s + 2] = len(code2)
    j.w[s + 3:s + 3 + len(code)] = code2
    s = j.find(189, "InGameLicensedMusicPlayScript")
    code = j.w[s + 3:s + 3 + j.w[s + 2]]
    assert len(code) == 5 * n + 1 + 4 * n and code[5 * n] == 4610
    bodies = code[5 * n + 1:]
    head = 5 + 5 * (n - a) + 1 + 5 * a + 1                    # group test, B cases, end, A cases, end
    b_cases = sum(([4887, sel_b << 16, f32(k), 4353, head + 4 * k] for k in range(a, n)), [])
    a_cases = sum(([4887, sel_a << 16, f32(k), 4353, head + 4 * k] for k in range(a)), [])
    a_start = 5 + len(b_cases) + 1
    code2 = [4887, group << 16, 0, 4353, a_start] + b_cases + [4610] + a_cases + [4610] + bodies
    assert len(code2) == head + 4 * n
    j.w[s + 2] = len(code2)
    j.w[s + 3:s + 3 + len(code)] = code2
    print(f"sélecteur coupé en {a} + {n - a} morceaux (+ pile ou face)")


WRECK_CUTOFF = 0.02   # wrecked: final-mix low-pass at 0.02 x 48 kHz (~1 kHz) on music, AI, world (not the player car)


def wreck_muffle(j):
    """finalsubmix.dat: muffle the mix while the player is wrecked. Control objects only, appended at the end:
    WreckMusicVariable (1 normal, 0 wrecked) -> WreckMusicCutOff curve (0 -> WRECK_CUTOFF, 1 -> 1) -> one more term of
    PerkFilterCutOff (type 42, min of the perk cut-offs that drive PerkSurroundLowPass, enabled below 1 by
    PerkLPFilterGateSwitch). WreckedInput used to run RaceFinishedScript: it now runs a copy that also sets the
    variable to 0; ResetLevelScript (level start, and back above health -0.5 via WreckedStopSwitch) sets it to 1."""
    f32 = lambda v: struct.unpack("<I", struct.pack("<f", v))[0]
    var = j.count
    j.w += [20, j.name("WreckMusicVariable"), F1]
    curve = j.count + 1
    j.w += [21, j.name("WreckMusicCutOff"), var, FF, F1, 2, 0, FF, f32(WRECK_CUTOFF), F1, FF, F1]
    j.count += 2
    s = j.find(42, "PerkFilterCutOff")
    n = j.w[s + 2] & 0xFFFF
    j.w[s + 2] += 1
    j.w[s + 3 + 2 * n:s + 3 + 2 * n] = [curve, 0]
    # wreck script = RaceFinishedScript + "var = 0"
    s = j.find(189, "RaceFinishedScript")
    code = j.w[s + 3:s + 3 + j.w[s + 2]]
    assert code[-1] == 0x1202 and j.w[s + 2] >> 16 == 0
    code = code[:-1] + [0x1004, 0, 0x1002, var << 16, 0x1202]
    script = j.count
    j.w += [189, j.name("WreckedMusicScript"), len(code)] + code
    j.count += 1
    s = j.find(8, "WreckedInput")
    assert j.w[s + 2] == 132, j.w[s + 2]
    j.w[s + 2] = script
    # reset script: "var = 1" before the end
    s = j.find(189, "ResetLevelScript")
    ln = j.w[s + 2]
    assert ln >> 16 == 0 and j.w[s + 2 + ln] == 0x1202
    j.w[s + 2 + ln:s + 2 + ln] = [0x1004, F1, 0x1002, var << 16]
    j.w[s + 2] = ln + 4


def main(out, graphs_only=False):
    """graphs_only: keep the already built OUTDIR/audio/ingamemusic.baf (encoding takes ~20 min), redo the graphs."""
    bank = open(os.path.join(E, "root_streaming", "ingamemusic.baf"), "rb").read()
    j = Jboa(open(os.path.join(E, "root", "audio", "dat", "music_controller.dat"), "rb").read())
    for k, (wave_name, src, start, end) in enumerate(TRACKS):
        suffix = "%02d" % (23 + k)
        print("piste", "InGameMusic" + suffix, "=", wave_name, start or "", end or "")
        if not graphs_only:
            bank = blurbaf.add_wave(bank, wave_name, pcm48(src, start, end), 48000)
        add_track(j, suffix, wave_name)
    if not FORCE_LAST:
        split_selector(j)
    fs = Jboa(open(os.path.join(E, "root", "audio", "dat", "finalsubmix.dat"), "rb").read())
    wreck_muffle(fs)
    if FORCE_LAST:
        s = j.find(33, "InGameMusicSelectorIndex")
        for k in range(j.w[s + 4]):
            j.w[s + 6 + 8 * k] = j.w[s + 6 + 8 * (j.w[s + 4] - 1)]
        print("test : toutes les entrées du sélecteur jouent la dernière piste")
    os.makedirs(os.path.join(out, "audio", "dat"), exist_ok=True)
    if not graphs_only:
        open(os.path.join(out, "audio", "ingamemusic.baf"), "wb").write(bank)
    open(os.path.join(out, "audio", "dat", "music_controller.dat"), "wb").write(j.build())
    open(os.path.join(out, "audio", "dat", "finalsubmix.dat"), "wb").write(fs.build())
    print("épave : mixage étouffé à", WRECK_CUTOFF)
    print("écrit dans", out)


if __name__ == "__main__":
    main(sys.argv[1], "--graphes" in sys.argv)
