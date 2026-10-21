#!/usr/bin/env python3
"""Music mod: race-music playlists for Blur (test copy only).

usage: make_music.py PLAYLIST_DIR [PLAYLIST_DIR ...]     build + install the chosen playlists into the test copy
       (music_menu.py / "Choisir la musique.bat" pick the folders in MUSIC_DIR)

A playlist = a folder of audio files (mp3, wav, flac, ogg, m4a). A folder with no audio file whose name contains
"original" = the game's own 23 race tracks. Each new file:
  - converted with ffmpeg to 48 kHz stereo at LUFS, encoded PS-ADPCM ONCE (cache in CACHE, keyed by the file's
    content), appended to ingamemusic.baf (blurbaf.add_wave);
  - music_controller.dat (JBOA): a sound object copied from InGameMusic22 is APPENDED at the end of the object list
    (index = old count, so no existing reference moves) with its mixer input (type 73, 17 words) and stop-script line.
Then playlist() rebuilds the race-music choice from the chosen sound objects: groups of at most 32 (selectors above
32 entries misbehave in game), one selector per group (type 33) + a group selector, the play script (switch), and the
draws in NextTrackScript and RaceStartScript. finalsubmix.dat: muffled mix while wrecked (wreck_muffle).
Layouts measured 2026-10-20/21 (docs/CONNAISSANCES.md, "Audio et musique").
"""
import hashlib, json, os, shutil, struct, subprocess, sys, tempfile, wave
import numpy as np
import blurbaf

HERE = os.path.dirname(os.path.abspath(__file__))
E = os.path.join(HERE, "..", "blur_extracted")
MUSIC_DIR = os.path.join(HERE, "..", "Blur_musiques")          # one sub-folder per playlist (not in the repository)
CACHE = os.path.join(E, "music_cache")                          # encoded tracks, reused between builds
OUT = os.path.join(E, "mods", "music", "files")
TEST = os.path.join(HERE, "..", "Blur_test")
AUDIO_EXT = (".mp3", ".wav", ".flac", ".ogg", ".m4a")
FF = 0xFFFF
F1 = 0x3F800000                                                 # 1.0f
GROUP_MAX = 32
LUFS = -9.0           # added tracks: a bit above the originals (median -10.2, full tracks -12.2 .. -8.7) to cut through engines


def f32(v):
    return struct.unpack("<I", struct.pack("<f", v))[0]


def pcm48(src):
    """48 kHz stereo int16 of src, gain set to LUFS integrated loudness (limiter at -1 dBFS)."""
    m = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", src, "-af", "ebur128", "-f", "null", "-"],
                       capture_output=True, encoding="utf-8", errors="replace").stderr   # file names like 『BLUR』
    gain = LUFS - float(m.rsplit("I:", 1)[1].split("LUFS")[0])
    print(f"  volume {gain:+.1f} dB vers {LUFS} LUFS")
    with tempfile.TemporaryDirectory() as d:
        out = os.path.join(d, "a.wav")
        subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", src, "-ar", "48000", "-ac", "2",
                        "-af", f"volume={gain}dB,alimiter=limit=0.89:level=false", out], check=True)
        with wave.open(out) as w:
            return np.frombuffer(w.readframes(w.getnframes()), "<i2").reshape(-1, 2).copy()


def encoded(src):
    """(PS-ADPCM bytes, samples) of src, from the cache when the same file was already encoded at this LUFS."""
    h = hashlib.sha1(open(src, "rb").read() + f"|{LUFS}|v1".encode()).hexdigest()
    data_p, meta_p = os.path.join(CACHE, h + ".adpcm"), os.path.join(CACHE, h + ".json")
    if not (os.path.exists(data_p) and os.path.exists(meta_p)):
        print("  encodage (une seule fois) :", os.path.basename(src))
        pcm = pcm48(src)
        os.makedirs(CACHE, exist_ok=True)
        open(data_p, "wb").write(blurbaf.encode_psx(pcm))
        json.dump({"samples": len(pcm), "source": os.path.basename(src)}, open(meta_p, "w", encoding="utf-8"))
    return open(data_p, "rb").read(), json.load(open(meta_p, encoding="utf-8"))["samples"]


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

    def code(self, name):
        """(word index of the script object, its code words)."""
        s = self.find(189, name)
        return s, self.w[s + 3:s + 3 + (self.w[s + 2] & 0xFFFF)]

    def set_code(self, s, old, new):
        self.w[s + 2] = (self.w[s + 2] & 0xFFFF0000) | len(new)
        self.w[s + 3:s + 3 + len(old)] = new

    def build(self):
        body = struct.pack("<%dI" % len(self.w), *self.w)
        struct.pack_into("<I", self.head, 8, 0x14 + len(body))
        struct.pack_into("<I", self.head, 0x10, self.count)
        return bytes(self.head) + body + bytes(self.names)


# script opcode -> length in words (measured on the music scripts; unknown opcode = stop, layout not understood):
# 0x1000 obj arg = trigger, 0x1002 obj = store, 0x1004 val = push, 0x1101 target = jump if true, 0x1200 script = call,
# 0x1202 = end, 0x1317 obj val = compare (4887), 4610 = 0x1202
OPS = {0x1000: 3, 0x1002: 2, 0x1004: 2, 0x1101: 2, 0x1200: 2, 0x1202: 1, 0x1317: 3}


def script_ops(code):
    """(position, opcode) of every instruction of a script."""
    out, p = [], 0
    while p < len(code):
        assert code[p] in OPS, f"opcode inconnu {code[p]:#x} en {p}"
        out.append((p, code[p]))
        p += OPS[code[p]]
    return out


def original_tracks(j):
    """Sound objects of the 23 original race tracks, in selector order (bodies of the untouched play script)."""
    _, code = j.code("InGameLicensedMusicPlayScript")
    n = (len(code) - 1) // 9
    assert len(code) == 9 * n + 1 and code[5 * n] == 0x1202
    return [code[5 * n + 1 + 4 * k + 1] >> 16 for k in range(n)]


def add_track(j, suffix, wave_name):
    """Sound object InGameMusic<suffix> (copy of InGameMusic22) + its mixer input + its stop line. Returns its index."""
    s = j.find(60, "InGameMusic22")
    obj = j.w[s:s + 14]
    assert obj[2] == j.name("InGameMusic") and obj[10] == 29, obj
    obj[1], obj[3] = j.name("InGameMusic" + suffix), j.name(wave_name)
    new = j.count
    j.w += obj
    j.count += 1
    # mixer: [73, name, FF, 0, FF, 1.0, count<<16] + count * 17 words, the last one = (19 << 16) | track object
    s = j.find(73, "InGameLicensedMusicMixer")
    m = j.w[s + 6] >> 16
    last = s + 7 + 17 * (m - 1)
    entry = j.w[last:last + 17]
    assert entry[0] == 88 and entry[12] == 88 and entry[16] >> 16 == 19, entry
    entry[16] = (19 << 16) | new
    j.w[s + 6] = (m + 1) << 16
    j.w[last + 17:last + 17] = entry
    # stop script: [189, name, len|len<<16] + n * [4096, obj, 1] + [4610]
    s = j.find(189, "InGameLicensedMusicStopScript")
    ln = j.w[s + 2] & 0xFFFF
    assert j.w[s + 2] >> 16 == ln and j.w[s + 2 + ln] == 0x1202, hex(j.w[s + 2])
    j.w[s + 2 + ln:s + 2 + ln] = [0x1000, new << 16, 1]
    j.w[s + 2] = (ln + 3) | ((ln + 3) << 16)
    return new


def playlist(j, objs):
    """Race music = a random pick among the sound objects `objs` (each the same chance, up to group rounding).
    Groups of <= GROUP_MAX: group 0 reuses the game's selector (InGameMusicSelectorIndex), others are new selectors,
    plus a group selector when there is more than one group. Selector = [33, name, FF, 0, n] + n * [FF, k.0, FF, 1.0,
    FF, 0, FF, 1.0]. Play script = (group tests) + per group (cases on its selector) + one body per track.
    ponytail: groups differ by at most one track (37 tracks: 1/38 vs 1/36), weighted group pick if that matters."""
    entry = lambda k: [FF, f32(k), FF, F1, FF, 0, FF, F1]
    g = -(-len(objs) // GROUP_MAX)
    groups = [objs[k * len(objs) // g:(k + 1) * len(objs) // g] for k in range(g)]
    s_nt, nt = j.code("InGameLicensedMusicNextTrackScript")
    assert nt[0] == 0x1000 and nt[-3] == 0x1200 and nt[-1] == 0x1202, nt
    sel0, play = nt[1] >> 16, nt[-2] >> 16
    s = j.find(33, "InGameMusicSelectorIndex")
    n0 = j.w[s + 4]
    j.w[s + 4] = len(groups[0])
    j.w[s + 5:s + 5 + 8 * n0] = sum((entry(k) for k in range(len(groups[0]))), [])
    sels = [sel0]
    for k, grp in enumerate(groups[1:], 1):
        sels.append(j.count)
        j.w += [33, j.name("InGameMusicSelectorIndex%d" % k), FF, 0, len(grp)] + sum((entry(i) for i in range(len(grp))), [])
        j.count += 1
    group_sel = None
    if g > 1:
        group_sel = j.count
        j.w += [33, j.name("InGameMusicGroupSelector"), FF, 0, g] + sum((entry(i) for i in range(g)), [])
        j.count += 1
    # play script layout: [tests of groups 1..g-1, 5 words each; no match falls through into group 0's block]
    # then per group [cases 5 * len] [end], then the bodies (4 words per track, in objs order)
    tests = 5 * (g - 1)
    starts, p = [], tests
    for grp in groups:
        starts.append(p)
        p += 5 * len(grp) + 1
    body0, b = p, 0
    code = sum(([0x1317, group_sel << 16, f32(k), 0x1101, starts[k]] for k in range(1, g)), [])
    for k, grp in enumerate(groups):
        for i in range(len(grp)):
            code += [0x1317, sels[k] << 16, f32(i), 0x1101, body0 + 4 * (b + i)]
        code += [0x1202]
        b += len(grp)
    code += sum(([0x1000, o << 16, 0, 0x1202] for grp in groups for o in grp), [])
    s_play, old = j.code("InGameLicensedMusicPlayScript")
    j.set_code(s_play, old, code)
    # the draws: NextTrack and RaceStart draw the game's selector then call play; draw the others too
    extra = sum(([0x1000, x << 16, 0] for x in sels[1:] + ([group_sel] if group_sel is not None else [])), [])
    s_nt, nt = j.code("InGameLicensedMusicNextTrackScript")          # again: the selector edit moved the words
    j.set_code(s_nt, nt, nt[:3] + extra + nt[3:])
    s_rs, rs = j.code("RaceStartScript")
    at = [p_ for p_, op in script_ops(rs) if rs[p_:p_ + 3] == [0x1000, sel0 << 16, 0]]
    assert len(at) == 1, at
    ins = at[0] + 3
    rs2 = rs[:ins] + extra + rs[ins:]
    for p_, op in script_ops(rs2):
        if op == 0x1101 and rs2[p_ + 1] >= ins:
            rs2[p_ + 1] += len(extra)
    j.set_code(s_rs, rs, rs2)
    return [len(grp) for grp in groups]


def shuffle_loop(j, objs, seed=None):
    """Race music = Spotify-like shuffle that loops: one random order (drawn here, at each build), every track once, then
    the same order again. State = a new variable InGameMusicShuffleIndex (type 20, starts at 0). Play script: switch on
    it, each body plays its track then stores the next index ([0x1000 obj 0][0x1004 next.0][0x1002 var][0x1202]).
    Advancing at play time: a new race starts the next track even when the previous race stopped one half-way.
    NextTrack = just call play; RaceStart no longer draws the selector (its 3 words removed, jumps moved back)."""
    import random
    order = list(objs)
    random.Random(seed).shuffle(order)
    var = j.count
    j.w += [20, j.name("InGameMusicShuffleIndex"), 0]
    j.count += 1
    n = len(order)
    code = sum(([0x1317, var << 16, f32(k), 0x1101, 5 * n + 1 + 8 * k] for k in range(n)), []) + [0x1202]
    code += sum(([0x1000, o << 16, 0, 0x1004, f32((k + 1) % n), 0x1002, var << 16, 0x1202]
                 for k, o in enumerate(order)), [])
    s_play, old = j.code("InGameLicensedMusicPlayScript")
    j.set_code(s_play, old, code)
    s_nt, nt = j.code("InGameLicensedMusicNextTrackScript")
    assert nt[0] == 0x1000 and nt[-3] == 0x1200 and nt[-1] == 0x1202, nt
    sel0 = nt[1] >> 16
    j.set_code(s_nt, nt, nt[-3:])
    s_rs, rs = j.code("RaceStartScript")
    at = [p_ for p_, op in script_ops(rs) if rs[p_:p_ + 3] == [0x1000, sel0 << 16, 0]]
    assert len(at) == 1, at
    cut = at[0]
    rs2 = rs[:cut] + rs[cut + 3:]
    for p_, op in script_ops(rs2):
        if op == 0x1101 and rs2[p_ + 1] > cut:
            rs2[p_ + 1] -= 3
    j.set_code(s_rs, rs, rs2)
    return order


def shuffle_sequence(j, steps):
    """Simulation of the shuffle play script from index 0: the sound objects played, in order (check)."""
    _, code = j.code("InGameLicensedMusicPlayScript")
    fl = lambda w: struct.unpack("<f", struct.pack("<I", w))[0]
    idx, out = 0.0, []
    for _ in range(steps):
        p = 0
        while code[p] == 0x1317 and fl(code[p + 2]) != idx:
            p += 5
        assert code[p] == 0x1317, "index sans morceau"
        b = code[p + 4]
        assert code[b] == 0x1000 and code[b + 3] == 0x1004 and code[b + 5] == 0x1002
        out.append(code[b + 1] >> 16)
        idx = fl(code[b + 4])
    return out


def play_targets(j):
    """Simulation of the play script for every (group, value): the sound objects reached (check of playlist())."""
    _, code = j.code("InGameLicensedMusicPlayScript")
    sels = sorted({code[p + 1] >> 16 for p, op in script_ops(code) if op == 0x1317})
    seen = set()

    def run(vals):
        p = 0
        while True:
            op = code[p]
            if op == 0x1317:
                if vals.get(code[p + 1] >> 16) == struct.unpack("<f", struct.pack("<I", code[p + 2]))[0]:
                    p = code[p + 4]
                    continue
                p += 5
            elif op == 0x1202:
                return None
            elif op == 0x1000:
                return code[p + 1] >> 16

    for a in sels:                                  # any track needs at most 2 selectors: its group's and the group pick
        for b in sels:
            for va in range(GROUP_MAX):
                for vb in range(GROUP_MAX):
                    seen.add(run({a: float(va), b: float(vb)}))
    seen.discard(None)
    return seen


WRECK_CUTOFF = 0.02   # wrecked: final-mix low-pass at 0.02 x 48 kHz (~1 kHz) on music, AI, world (not the player car)


def wreck_muffle(j):
    """finalsubmix.dat: muffle the mix while the player is wrecked. Control objects only, appended at the end:
    WreckMusicVariable (1 normal, 0 wrecked) -> WreckMusicCutOff curve (0 -> WRECK_CUTOFF, 1 -> 1) -> one more term of
    PerkFilterCutOff (type 42, min of the perk cut-offs that drive PerkSurroundLowPass, enabled below 1 by
    PerkLPFilterGateSwitch). WreckedInput used to run RaceFinishedScript: it now runs a copy that also sets the
    variable to 0; ResetLevelScript (level start, and back above health -0.5 via WreckedStopSwitch) sets it to 1."""
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


def obj_index(j, name):
    """Index of an ORIGINAL object (object i is named names[i + 1]; objects we append break this rule)."""
    names = bytes(j.names).split(b"\0")
    k = names.index(name.encode()) - 1
    assert 0 <= k < j.count
    return k


def no_perk_duck(j):
    """finalsubmix.dat: the music no longer ducks when power-ups fire. MusicMixerVolume (type 37) = product of
    (obj, 0) pairs; its MusicMixerPerkDuckVolume term is removed (the game-pause term stays). The nitro low-pass
    acts on the whole final mix (PerkSurroundLowPass), not only on the music: left as it is."""
    duck = obj_index(j, "MusicMixerPerkDuckVolume")
    s = j.find(37, "MusicMixerVolume")
    n = j.w[s + 2] & 0xFFFF
    pairs = [j.w[s + 3 + 2 * k:s + 5 + 2 * k] for k in range(n)]
    assert [duck, 0] in pairs, pairs
    pairs.remove([duck, 0])
    j.w[s + 2] -= 1
    j.w[s + 3:s + 3 + 2 * n] = sum(pairs, [])


def wave_name(path, used):
    """Bank sound name from the file name: letters and digits only, at most 31 bytes, unique."""
    base = "".join(c for c in os.path.splitext(os.path.basename(path))[0] if c.isascii() and c.isalnum())[:28] or "Track"
    name, k = base, 2
    while name.lower() in used:
        name, k = base[:28] + str(k), k + 1
    used.add(name.lower())
    return name


def build(folders, out=OUT, shuffle=True, effects=True):
    """Bank + controller + final mix for the chosen playlist folders. Returns a summary.
    shuffle: Spotify-like looping shuffle (new order at each build), else independent random picks.
    effects: game effects on the music (duck on power-ups, muffled when wrecked)."""
    bank = open(os.path.join(E, "root_streaming", "ingamemusic.baf"), "rb").read()
    j = Jboa(open(os.path.join(E, "root", "audio", "dat", "music_controller.dat"), "rb").read())
    originals = original_tracks(j)
    used = {w["name"].lower() for w in blurbaf.parse(bank)["waves"]}
    objs, files, seen = [], [], set()
    for d in folders:
        audio = sorted(f for f in os.listdir(d) if f.lower().endswith(AUDIO_EXT))
        if not audio and "original" in os.path.basename(d).lower():
            objs += [o for o in originals if o not in objs]
        for f in audio:
            path = os.path.join(d, f)
            key = hashlib.sha1(open(path, "rb").read()).hexdigest()
            if key not in seen:
                seen.add(key)
                files.append(path)
    for k, path in enumerate(files):
        name = wave_name(path, used)
        print("morceau", "InGameMusic%02d" % (23 + k), "=", os.path.basename(path))
        data, samples = encoded(path)
        bank = blurbaf.add_wave(bank, name, None, 48000, data=data, samples=samples)
        objs.append(add_track(j, "%02d" % (23 + k), name))
    if not objs:
        raise SystemExit("playlist vide : aucun morceau choisi")
    if shuffle:
        order = shuffle_loop(j, objs)
        assert shuffle_sequence(j, 2 * len(objs)) == order * 2, "simulation de l'ordre aléatoire"
        mode = f"aléatoire en boucle, nouvel ordre à chaque préparation"
    else:
        sizes = playlist(j, objs)
        reached = play_targets(j)
        assert reached == set(objs), ("simulation", sorted(set(objs) - reached), sorted(reached - set(objs)))
        mode = f"tirage au hasard, groupes {' + '.join(map(str, sizes))}"
    fs = Jboa(open(os.path.join(E, "root", "audio", "dat", "finalsubmix.dat"), "rb").read())
    if effects:
        wreck_muffle(fs)
    else:
        no_perk_duck(fs)
    os.makedirs(os.path.join(out, "audio", "dat"), exist_ok=True)
    open(os.path.join(out, "audio", "ingamemusic.baf"), "wb").write(bank)
    open(os.path.join(out, "audio", "dat", "music_controller.dat"), "wb").write(j.build())
    open(os.path.join(out, "audio", "dat", "finalsubmix.dat"), "wb").write(fs.build())
    return f"{len(objs)} morceaux en course ({mode}) ; effets du jeu sur la musique : {'oui' if effects else 'non'}"


def install(out=OUT, test=TEST):
    """Copy the built files into the test copy (Blur must be closed)."""
    if b"Blur.exe" in subprocess.run(["tasklist", "/fi", "imagename eq Blur.exe"], capture_output=True).stdout:
        raise SystemExit("Blur est lancé : ferme-le puis recommence.")
    for rel in ("audio/ingamemusic.baf", "audio/dat/music_controller.dat", "audio/dat/finalsubmix.dat"):
        src, dst = os.path.join(out, rel), os.path.join(test, rel)
        if not os.path.exists(dst) or open(src, "rb").read() != open(dst, "rb").read():
            shutil.copyfile(src, dst)
            print("installé :", rel)


if __name__ == "__main__":
    print(build(sys.argv[1:]))
    install()
