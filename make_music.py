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
import hashlib, json, os, re, shutil, struct, subprocess, sys, tempfile, wave
import numpy as np
import blurbaf

HERE = os.path.dirname(os.path.abspath(__file__))
_env = lambda name, default: os.environ.get("BLUR_MUSIC_" + name, default)   # set by the community pack (music_pack)
E = _env("E", os.path.join(HERE, "..", "blur_extracted"))       # needs root\audio\... and root_streaming\...
MUSIC_DIR = _env("MUSIC_DIR", os.path.join(HERE, "..", "Blur_musiques"))   # one sub-folder per playlist (not in the repo)
CACHE = _env("CACHE", os.path.join(E, "music_cache"))           # encoded tracks, reused between builds
OUT = _env("OUT", os.path.join(E, "mods", "music", "files"))
TEST = _env("TEST", os.path.join(HERE, "..", "Blur_test"))      # where install() copies the files
HUD_LOC = _env("HUD_LOC", os.path.join(E, "gamedata", "gamedata", "xt", "loc", "hud.loc"))   # original, track titles added
PLUGIN_TEMPLATE = _env("PLUGIN", os.path.join(HERE, "mod_static", "amax", "plugins", "musicctl", "musicctl.lua"))
TITLE_HASH0 = 0x0B1E1000                                       # hud.loc hashes of the track titles (ours)
AUDIO_EXT = (".mp3", ".wav", ".flac", ".ogg", ".m4a")
FF = 0xFFFF
F1 = 0x3F800000                                                 # 1.0f
GROUP_MAX = 32
LUFS = -9.0           # added tracks: a bit above the originals (median -10.2, full tracks -12.2 .. -8.7) to cut through engines


class Unreadable(Exception):
    """An audio file ffmpeg cannot decode: build() skips it."""


def f32(v):
    return struct.unpack("<I", struct.pack("<f", v))[0]


def pcm48(src):
    """48 kHz stereo int16 of src, gain set to LUFS integrated loudness (limiter at -1 dBFS)."""
    m = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", src, "-af", "ebur128", "-f", "null", "-"],
                       capture_output=True, encoding="utf-8", errors="replace").stderr   # file names like 『BLUR』
    if "I:" not in m:      # not audio ffmpeg can read: broken download, renamed web page or video (player, 2026-11-20)
        raise Unreadable(m.strip().splitlines()[-1] if m.strip() else "ffmpeg found no audio")
    gain = LUFS - float(m.rsplit("I:", 1)[1].split("LUFS")[0])
    print(f"  volume {gain:+.1f} dB -> {LUFS} LUFS")
    with tempfile.TemporaryDirectory() as d:
        out = os.path.join(d, "a.wav")
        subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", src, "-ar", "48000", "-ac", "2",
                        "-af", f"volume={gain}dB,alimiter=limit=0.89:level=false", out], check=True)
        with wave.open(out) as w:
            return np.frombuffer(w.readframes(w.getnframes()), "<i2").reshape(-1, 2).copy()


def encoded(src, pcm16=False):
    """(bytes, samples) of src, from the cache when the same file was already prepared at this LUFS:
    PS-ADPCM (the game's format, 4 bits) or, pcm16, uncompressed 16 bits (4x bigger, no codec loss)."""
    kind = "pcm16" if pcm16 else "adpcm"
    h = hashlib.sha1(open(src, "rb").read() + f"|{LUFS}|v1".encode()).hexdigest()
    data_p, meta_p = os.path.join(CACHE, f"{h}.{kind}"), os.path.join(CACHE, h + ".json")
    if not (os.path.exists(data_p) and os.path.exists(meta_p)):
        print(f"  converting ({kind}, once):", os.path.basename(src))
        pcm = pcm48(src)
        os.makedirs(CACHE, exist_ok=True)
        open(data_p, "wb").write(pcm.astype("<i2").tobytes() if pcm16 else blurbaf.encode_psx(pcm))
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
    random_start(j, var, sel0, nt[-2] >> 16, n)
    return order


def random_start(j, var, sel, play, n):
    """The shuffle index starts at 0 at each game launch: same tracks in the same order every session (unless rebuilt,
    which needed a launcher; players start Blur through other tools, TextMod...). At the first track of a session, a new
    script MusicShuffleStartScript draws the game's own random selector (unused by the shuffle) and sets the index from
    it, then calls play; afterwards (MusicShuffleStarted = 1) it just calls play. Every `0x1200 play` call now goes
    through it (NextTrack, RaceStart). Selector = [33, name, FF, 0, m] + m * [FF, k.0, FF, 1.0, FF, 0, FF, 1.0].
    ponytail: m = min(n, GROUP_MAX) start points spread over the order (selectors above 32 entries misbehave)."""
    m = min(n, GROUP_MAX)
    starts = [k * n // m for k in range(m)]
    s = j.find(33, "InGameMusicSelectorIndex")
    assert j.w[s + 2:s + 4] == [FF, 0] and sel == obj_index(j, "InGameMusicSelectorIndex"), (j.w[s:s + 5], sel)
    old = j.w[s + 4]
    j.w[s + 4] = m
    j.w[s + 5:s + 5 + 8 * old] = sum(([FF, f32(k), FF, F1, FF, 0, FF, F1] for k in range(m)), [])
    started = j.count
    j.w += [20, j.name("MusicShuffleStarted"), 0]
    j.count += 1
    j.shuffle_ids = (var, started, play)                 # for position_start
    # [started == 1 -> CALL] [started = 1] [draw] [m cases] [end]  [m bodies: index = start, call play]  CALL: call play
    head = [0x1317, started << 16, F1, 0x1101, None, 0x1004, F1, 0x1002, started << 16, 0x1000, sel << 16, 0]
    body0 = len(head) + 5 * m + 1
    code = head + sum(([0x1317, sel << 16, f32(k), 0x1101, body0 + 7 * k] for k in range(m)), []) + [0x1202]
    code += sum(([0x1004, f32(st), 0x1002, var << 16, 0x1200, play << 16, 0x1202] for st in starts), [])
    code[4] = len(code)
    code += [0x1200, play << 16, 0x1202]
    init = j.count
    j.w += [189, j.name("MusicShuffleStartScript"), len(code)] + code
    j.count += 1
    calls = 0
    for name in ("InGameLicensedMusicNextTrackScript", "RaceStartScript"):
        s_c, c = j.code(name)
        new = c.copy()
        for p_, op in script_ops(c):
            if c[p_:p_ + 2] == [0x1200, play << 16]:
                new[p_ + 1] = init << 16
                calls += 1
        j.set_code(s_c, c, new)
    assert calls >= 2, calls


def random_start_check(j):
    """Simulation of MusicShuffleStartScript for every selector value: the shuffle index it sets (check)."""
    _, code = j.code("MusicShuffleStartScript")
    fl = lambda w: struct.unpack("<f", struct.pack("<I", w))[0]
    out = []
    p = 12
    while code[p] == 0x1317:
        b = code[code[p + 4]:code[p + 4] + 7]
        assert b[0] == 0x1004 and b[2] == 0x1002 and b[4] == 0x1200 and b[6] == 0x1202, b
        out.append(fl(b[1]))
        p += 5
    assert code[p] == 0x1202 and code[code[4]] == 0x1200, code
    return out


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
EFFECTS_MODES = ("oui", "partiel", "non")


def normalize_effects(effects):
    """Accept saved legacy booleans as well as the three current effect modes."""
    if isinstance(effects, bool):
        return "oui" if effects else "non"
    if isinstance(effects, str):
        value = effects.strip().lower()
        if value == "partiellement":
            value = "partiel"
        if value in EFFECTS_MODES:
            return value
    raise ValueError(f"mode d'effets invalide : {effects!r}")


def wreck_muffle(j, cutoff=WRECK_CUTOFF):
    """finalsubmix.dat: muffle the mix while the player is wrecked. Control objects only, appended at the end:
    WreckMusicVariable (1 normal, 0 wrecked) -> WreckMusicCutOff curve (0 -> WRECK_CUTOFF, 1 -> 1) -> one more term of
    PerkFilterCutOff (type 42, min of the perk cut-offs that drive PerkSurroundLowPass, enabled below 1 by
    PerkLPFilterGateSwitch). WreckedInput used to run RaceFinishedScript: it now runs a copy that also sets the
    variable to 0; ResetLevelScript (level start, and back above health -0.5 via WreckedStopSwitch) sets it to 1."""
    var = j.count
    j.w += [20, j.name("WreckMusicVariable"), F1]
    curve = j.count + 1
    j.w += [21, j.name("WreckMusicCutOff"), var, FF, F1, 2, 0, FF, f32(cutoff), F1, FF, F1]
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


PERK_VOLUMES = ("BargeFireVolume", "BargeLastGaspVolume", "BargeHitVolume", "BoltFireVolume", "BoltHitVolume",
                "BombFireVolume", "BombHitVolume", "NitrousVolume", "RepairHitVolume", "ShockFireVolume",
                "ShockHitVolume", "ShuntFireVolume", "ShuntHitVolume")


def no_perk_volumes(j):
    """finalsubmix.dat: each power-up fires a timer whose curve dips to PerkVolumeViewportsDucking (0 in solo) for
    about a second; these curves multiply the music, reverb, AI, listener and DOPO mixers ("non" only flattened the
    music: other power-ups still changed the sound, player 2026-10-23). Every point -> 1.0."""
    for name in PERK_VOLUMES:
        s = j.find(21, name)
        for i in range(j.w[s + 5]):
            j.w[s + 7 + 3 * i:s + 9 + 3 * i] = [FF, F1]


def set_trigger_args(j, objs, old, new):
    """Rewrite every `0x1000 obj old` instruction to `0x1000 obj new` in all scripts (pattern match: some opcodes of
    these scripts are not decoded). Returns the number of changes."""
    want = {obj_index(j, o) << 16 for o in objs}
    changed = 0
    for i in range(len(j.w) - 2):
        if j.w[i] == 0x1000 and j.w[i + 1] in want and j.w[i + 2] == old:
            j.w[i + 2] = new
            changed += 1
    return changed


def no_perk_submix_effects(j):
    """finalperksubmix.dat (second effect stage on the whole final mix): power-up hits enable a bit crusher, ring mod,
    flanger and the repair low-pass (trigger arg 0 = on, 1 = bypass; StartScript sets all to 1): they stay bypassed.
    The high-pass is always on, cut-off = max of the charge curves and of HealthFilterCutOff (low health effect,
    player 2026-10-23; ~0.01 x 48 kHz at critical health level). A constant term in HighPassFinal (type 41) did not
    work in game (sound still thin, 2026-11-13): the filter's cut-off input (HighPassFinal, 1.0) is set to the
    constant 0 instead, as for CollisionSurroundHighPass in finalsubmix."""
    n = set_trigger_args(j, ("PerkHitBitCrusher", "PerkHitRingMod", "PerkHitFlanger", "PerkSurroundLowPass"), 0, 1)
    assert n == 8, n
    s = j.find(147, "PerkSurroundHighPass")
    assert j.w[s + 6:s + 8] == [obj_index(j, "HighPassFinal"), F1]
    j.w[s + 6:s + 8] = [FF, 0]


def set_curve_outputs(j, name, values):
    """Replace selected constant y-values in a type-21 curve, keyed by the point's x-value."""
    s = j.find(21, name)
    n = j.w[s + 5]
    pending = {f32(x): f32(y) for x, y in values.items()}
    for i in range(n):
        point = s + 6 + 3 * i
        x, output, _ = j.w[point:point + 3]
        if x in pending:
            assert output == FF, (name, i, output)
            j.w[point + 2] = pending.pop(x)
    assert not pending, (name, sorted(pending))


def soften_shield(j):
    """Raise the shield low-pass values, including the values written by its control scripts."""
    s = j.find(20, "ShieldCutOffVariable")
    j.w[s + 2] = f32(0.4)
    for name in ("PerkShieldScript", "PerkShieldMODScript", "CameraChangeShieldResetScript"):
        s, old = j.code(name)
        code = old.copy()
        changed = 0
        for p in range(len(code) - 1):
            if code[p:p + 2] == [0x1004, f32(0.004)]:
                code[p + 1] = f32(0.4)
                changed += 1
        assert changed == 1, (name, changed)
        j.set_code(s, old, code)


def set_terms(j, typ, name, value):
    """Replace all terms of a min / max / product object (types 42 / 41 / 37: count word, then (obj, 0) pairs) by one
    constant (FFFF, value), the form the game itself uses (PerkHitRingModDry = (28, 0) (FFFF, 1.0))."""
    s = j.find(typ, name)
    n = j.w[s + 2] & 0xFFFF
    j.w[s + 2] = (j.w[s + 2] & 0xFFFF0000) | 1
    j.w[s + 3:s + 3 + 2 * n] = [FF, f32(value)]


def no_perk_lowpass(j):
    """Keep a single unity term so nitro, shield, and wreck filters cannot muffle the final mix."""
    set_terms(j, 42, "PerkFilterCutOff", 1.0)


def soften_perk_effects(j):
    """Reduce perk ducking and low-pass strength without changing the original control flow."""
    set_curve_outputs(j, "MusicMixerPerkDuckVolume", {1.0: 0.5})
    set_curve_outputs(j, "NitrousLowPass", {0.1: 0.25, 1.5: 0.25})
    soften_shield(j)


def no_collision_effects(j):
    """Remove the collision volume duck and high-pass from the added final-submix mixer."""
    s = j.find(79, "FinalSubMixCarAddedMixer")
    assert j.w[s + 2:s + 4] == [obj_index(j, "CollisionVolumeRMSDucking"), 0]
    j.w[s + 2:s + 4] = [FF, F1]
    s = j.find(147, "CollisionSurroundHighPass")
    assert j.w[s + 6:s + 8] == [105, F1]
    j.w[s + 6:s + 8] = [FF, 0]


def no_bitcrusher(j):
    """Set the bit-crusher depth input to its documented neutral value."""
    set_terms(j, 42, "RGBBitCrusherDepthFinal", 32.0)


KEY_SOUND_SECONDS = 1.7     # musicctl next-track sound: race_fail_fill cut at 1.7 s from the file start (player)


def music_key_sounds(out):
    """Sound of the musicctl plugin's next-track key. The Lua can only play UIEnums.SoundEffect events. BossRaceLose
    was tried first: the game also plays the 6.4 s career defeat jingle (menumusic_ns race_fail_fill, music graph)
    on it; the player liked its start. So MotorMashCount (cut Motor Mash mode, plays only its own wave in ingameui)
    gets the first KEY_SOUND_SECONDS of race_fail_fill: its wave replaced in ingameui.baf (used by that event only;
    mono like the original: MonoToStereoMixer), 150 ms fade out, peak -3 dBFS."""
    b = open(os.path.join(E, "root", "audio", "menumusic_ns.baf"), "rb").read()
    w = next(w for w in blurbaf.parse(b)["waves"] if w["name"] == "race_fail_fill")
    x = np.asarray(blurbaf.decode(b, w), dtype=float).reshape(-1, w["channels"]).mean(axis=1)
    x = x[:int(w["rate"] * KEY_SOUND_SECONDS)]           # measured from the file start, as the player listened
    if w["rate"] != 48000:
        x = np.interp(np.arange(0, len(x) - 1, w["rate"] / 48000), np.arange(len(x)), x)
    x[-7200:] *= np.linspace(1, 0, 7200)
    x = (x / np.abs(x).max() * 0.7 * 32767).astype(np.int16)[:, None]
    b = open(os.path.join(E, "root", "audio", "ingameui.baf"), "rb").read()
    b = blurbaf.replace_wave(b, "HUD_MotorMashCount", x, 48000)
    os.makedirs(os.path.join(out, "audio"), exist_ok=True)
    open(os.path.join(out, "audio", "ingameui.baf"), "wb").write(b)
    print("musicctl sound: ingameui.baf HUD_MotorMashCount (next track)")


def wave_name(path, used):
    """Bank sound name from the file name: letters and digits only, at most 31 bytes, unique."""
    base = "".join(c for c in os.path.splitext(os.path.basename(path))[0] if c.isascii() and c.isalnum())[:28] or "Track"
    name, k = base, 2
    while name.lower() in used:
        name, k = base[:28] + str(k), k + 1
    used.add(name.lower())
    return name


def original_title(wave):
    """Readable banner title of an original race track from its wave name (the bank holds no artist): CamelCase
    split ("DemNaLikeMe" -> "Dem Na Like Me"), BLUR_trackN -> "Blur - Track N"."""
    m = re.fullmatch(r"BLUR_track(\d+)", wave)
    if m:
        return f"Blur - Track {m.group(1)}"
    return re.sub(r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])", " ", wave)


def track_tags(path):
    """title / artist / album tags of an audio file (ffprobe; empty when missing or no ffprobe)."""
    try:
        r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format_tags=title,artist,album", "-of", "json", path],
                           capture_output=True, encoding="utf-8", errors="replace")
        return {k.lower(): v.strip() for k, v in json.loads(r.stdout or "{}").get("format", {}).get("tags", {}).items()}
    except (OSError, ValueError):
        return {}


def track_lines(path):
    """Banner lines (player, 2026-11-13): the title, then one line per extra info: the artist when the title does not
    already hold it, the album when it differs from the title. Empty tags give no line."""
    tags = track_tags(path)
    title = track_title(path, tags)
    artist, album = clean_text(tags.get("artist", "")), clean_text(tags.get("album", ""))
    lines = [title]
    if artist and artist.lower() not in title.lower():
        lines.append(artist)
    if album and album.lower() != tags.get("title", "").lower() and album.lower() not in title.lower():
        lines.append(album)
    return [shorten(lines[0], TITLE_MAX)] + [shorten(l, INFO_MAX) for l in lines[1:3]]


TITLE_MAX, INFO_MAX = 45, 40                              # banner text lengths (player, 2026-11-16): longer = cut "…"
# what downloaded file names / tags add and the banner does not need (player, 2026-11-16)
JUNK = re.compile(r"\s*[\(\[【]\s*(official\s*)?(music\s*)?(audio|video|lyrics?|lyric\s*video|visuali[sz]er|mv|m/v|hd|hq|4k)"
                  r"\s*[\)\]】]|\s*【|】|\s+(hd|hq)\s*$", re.I)


def clean_text(s):
    """Banner text without download junk ("(Official Audio)", "[MV]", "【 】"...) and doubled spaces."""
    return re.sub(r"\s{2,}", " ", JUNK.sub(" ", s)).strip(" -")


def shorten(s, n):
    """At most n characters: first drop a final bracket "(from ...)", then cut on a word with "..."."""
    if len(s) <= n:
        return s
    t = re.sub(r"\s*[\(\[][^\(\)\[\]]*[\)\]]\s*$", "", s)
    if len(t) <= n and t:
        return t
    t = t[:n - 1]
    return (t[:t.rfind(" ")] if " " in t[n // 2:] else t).rstrip(" -,") + "..."   # ASCII: the game font may lack "…"


def track_title(path, tags=None):
    """Banner title (player's rule, 2026-11-13): "artist - title" from the tags, the title alone when it already holds
    " - " (downloaded files often have the uploader as artist), else the file name without its extension."""
    tags = track_tags(path) if tags is None else tags
    title, artist = clean_text(tags.get("title", "")), clean_text(tags.get("artist", ""))
    if title and artist and " - " not in title:
        return f"{artist} - {title}"
    return title or clean_text(os.path.splitext(os.path.basename(path))[0])


def position_start(j, n):
    """RaceStartScript: if MusicType == p + 2 (set by the musicctl plugin), the shuffle starts at position p: started = 1,
    index = p, call play (it plays order[p] and stores p + 1, so the graph then goes on in order by itself and the plugin
    knows which track plays). MusicType 0 / 1 (the option's own values) keep the normal behaviour.
    Proven in game by music_probe (MusicType 2 / 3 played two chosen tracks, 2026-11-13)."""
    mt = obj_index(j, "MusicType")
    var, started, play = j.shuffle_ids
    s, rs = j.code("RaceStartScript")
    calls = [p for p, op in script_ops(rs) if op == 0x1200]
    assert len(calls) == 1, calls
    ins = calls[0]
    new = list(rs)
    for p, op in script_ops(rs):                          # jumps past the insertion point move with it
        if op == 0x1101 and rs[p + 1] >= ins:
            new[p + 1] = rs[p + 1] + 5 * n
    body0 = len(rs) + 5 * n
    new[ins:ins] = sum(([0x1317, mt << 16, f32(p + 2), 0x1101, body0 + 11 * p] for p in range(n)), [])
    new += sum(([0x1004, F1, 0x1002, started << 16, 0x1004, f32(p), 0x1002, var << 16, 0x1200, play << 16, 0x1202]
                for p in range(n)), [])
    j.set_code(s, rs, new)


def position_check(j, n):
    """Simulation of the RaceStartScript chain for every MusicType p + 2: the shuffle index each sets (check)."""
    mt = obj_index(j, "MusicType")
    var, started, play = j.shuffle_ids
    _, rs = j.code("RaceStartScript")
    fl = lambda w: struct.unpack("<f", struct.pack("<I", w))[0]
    out = []
    for p in range(n):
        q = next(q for q, op in script_ops(rs) if rs[q:q + 3] == [0x1317, mt << 16, f32(p + 2)])
        b = rs[rs[q + 4]:rs[q + 4] + 11]
        assert b[2:4] == [0x1002, started << 16] and b[6:10] == [0x1002, var << 16, 0x1200, play << 16] and b[10] == 0x1202, b
        out.append(fl(b[5]))
    return out


FORCE_BASE = 1000      # MusicType FORCE_BASE + p (set by musicctl): RaceStartScript stops what plays and starts position p


def managed_chain(j):
    """A race track that ends no longer starts the next one by itself while the plugin drives the music: each track
    sound object calls, at its end, InGameLicensedMusicNextTrackScript (word 12 of the object, read in the data);
    it now calls a new InGameMusicEndedScript: if MusicType = 1 (the option's own "on": menus, no plugin, plugin
    passive) -> the next track as before; else (plugin in a race: p + 2, FORCE_BASE + p, 0 during a skip) -> playing = 0
    and silence until the plugin starts the next track itself (a skip at the end it computed: the banner and the sound
    always change together; the old chain drifted from the plugin's timer, player 2026-11-20). Returns the objects."""
    nt = obj_index(j, "InGameLicensedMusicNextTrackScript")
    mt, playing = obj_index(j, "MusicType"), obj_index(j, "InGameMusicPlayingVariable")
    code = [0x1317, mt << 16, F1, 0x1101, 10, 0x1004, 0, 0x1002, playing << 16, 0x1202, 0x1200, nt << 16, 0x1202]
    ended = j.count
    j.w += [189, j.name("InGameMusicEndedScript"), len(code)] + code
    j.count += 1
    bank = j.name("InGameMusic")
    hits = [i for i in range(len(j.w) - 13) if j.w[i] == 60 and j.w[i + 2] == bank and j.w[i + 12] == nt]
    for i in hits:
        assert j.w[i + 13] == 0x10000, (i, j.w[i:i + 14])
        j.w[i + 12] = ended
    return hits


def ended_check(j):
    """Simulation of InGameMusicEndedScript: {MusicType: 'next' or 'stop'} (check)."""
    _, code = j.code("InGameMusicEndedScript")
    nt, playing = obj_index(j, "InGameLicensedMusicNextTrackScript"), obj_index(j, "InGameMusicPlayingVariable")
    out = {}
    for v in (0.0, 1.0, 2.0, 7.0, float(FORCE_BASE)):
        assert code[0] == 0x1317 and code[3] == 0x1101, code
        p = code[4] if struct.unpack("<f", struct.pack("<I", code[2]))[0] == v else 5
        if code[p:p + 2] == [0x1200, nt << 16]:
            out[v] = "next"
        elif code[p:p + 4] == [0x1004, 0, 0x1002, playing << 16]:
            out[v] = "stop"
    return out


def force_start(j, n):
    """RaceStartScript: if MusicType = FORCE_BASE + p, stop the track that plays (even one the previous race left
    going: the normal path keeps it) and start position p: playing = 1, started = 1, index = p, call play. Tests go
    right before the "already playing" test, after the volumes are set. The plugin uses it to start a race on a track
    it knows for sure (a new track, or after a destruction / checkpoint event where it stays out)."""
    mt, playing = obj_index(j, "MusicType"), obj_index(j, "InGameMusicPlayingVariable")
    stop = obj_index(j, "InGameLicensedMusicStopScript")
    var, started, play = j.shuffle_ids
    s, rs = j.code("RaceStartScript")
    at = [p for p, op in script_ops(rs) if rs[p:p + 3] == [0x1317, playing << 16, F1]]
    assert len(at) == 1, at
    ins = at[0]
    new = list(rs)
    for p, op in script_ops(rs):
        if op == 0x1101 and rs[p + 1] >= ins:
            new[p + 1] = rs[p + 1] + 5 * n
    body0 = len(rs) + 5 * n
    new[ins:ins] = sum(([0x1317, mt << 16, f32(FORCE_BASE + p), 0x1101, body0 + 17 * p] for p in range(n)), [])
    new += sum(([0x1200, stop << 16, 0x1004, F1, 0x1002, playing << 16, 0x1004, F1, 0x1002, started << 16,
                 0x1004, f32(p), 0x1002, var << 16, 0x1200, play << 16, 0x1202] for p in range(n)), [])
    j.set_code(s, rs, new)


def force_check(j, n):
    """Simulation of RaceStartScript for MusicType FORCE_BASE + p: the index each sets, after a stop (check)."""
    mt, playing = obj_index(j, "MusicType"), obj_index(j, "InGameMusicPlayingVariable")
    stop = obj_index(j, "InGameLicensedMusicStopScript")
    var, started, play = j.shuffle_ids
    _, rs = j.code("RaceStartScript")
    fl = lambda w: struct.unpack("<f", struct.pack("<I", w))[0]
    test = next(q for q, op in script_ops(rs) if rs[q:q + 3] == [0x1317, playing << 16, F1])
    out = []
    for p in range(n):
        q = next(q for q, op in script_ops(rs) if rs[q:q + 3] == [0x1317, mt << 16, f32(FORCE_BASE + p)])
        assert q < test, "forced start after the 'already playing' test"
        b = rs[rs[q + 4]:rs[q + 4] + 17]
        assert b[:2] == [0x1200, stop << 16] and b[4:6] == [0x1002, playing << 16] and b[8:10] == [0x1002, started << 16]
        assert b[12:16] == [0x1002, var << 16, 0x1200, play << 16] and b[16] == 0x1202, b
        out.append(fl(b[11]))
    return out


def build(folders, out=OUT, shuffle=True, effects=True, pcm16=False):
    """Bank + controller + final mix for the chosen playlist folders. Returns a summary.
    shuffle: Spotify-like looping shuffle (new order at each build), else independent random picks.
    effects: oui = original effects plus wreck muffle; partiel = softened perk/wreck effects without collision
    processing; non = no effects on the final mix. Legacy booleans remain accepted.
    pcm16: added tracks stored uncompressed (codec 3, like the game's own *_sync_loop sounds) instead of PS-ADPCM."""
    effects = normalize_effects(effects)
    bank = open(os.path.join(E, "root_streaming", "ingamemusic.baf"), "rb").read()
    j = Jboa(open(os.path.join(E, "root", "audio", "dat", "music_controller.dat"), "rb").read())
    originals = original_tracks(j)
    used = {w["name"].lower() for w in blurbaf.parse(bank)["waves"]}
    objs, files, seen = [], [], set()
    info = {}                                             # sound object -> (banner title, seconds)
    waves = {w["name"]: w for w in blurbaf.parse(bank)["waves"]}
    names = bytes(j.names).split(b"\0")
    for o in originals:                                   # original object i is named names[i + 1]
        w = j.w[j.find(60, names[o + 1].decode()) + 3]
        wave = bytes(j.names[w:j.names.index(b"\0", w)]).decode()
        info[o] = ([original_title(wave)], waves[wave]["samples"] / waves[wave]["rate"] if wave in waves else 180.0, None)
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
    k = 0
    for path in files:
        try:
            data, samples = encoded(path, pcm16)
        except Unreadable as e:
            print(f"  SKIPPED, unreadable audio file: {path}\n    ffmpeg: {e}\n"
                  "    (play it in VLC: if it does not play, download or convert it again, or remove it)")
            continue
        name = wave_name(path, used)
        print("track", "InGameMusic%02d" % (23 + k), "=", os.path.basename(path))
        if pcm16:
            bank = blurbaf.add_pcm_wave(bank, name, np.frombuffer(data, "<i2").reshape(-1, 2), 48000)
        else:
            bank = blurbaf.add_wave(bank, name, None, 48000, data=data, samples=samples)
        objs.append(add_track(j, "%02d" % (23 + k), name))
        info[objs[-1]] = (track_lines(path), samples / 48000, path)
        k += 1
    if not objs:
        raise SystemExit("empty playlist: no track chosen")
    if shuffle:
        order = shuffle_loop(j, objs)
        assert shuffle_sequence(j, 2 * len(objs)) == order * 2, "simulation de l'ordre aléatoire"
        mode = "looping shuffle, new order at each build"
        position_start(j, len(order))
        assert position_check(j, len(order)) == [float(p) for p in range(len(order))], "simulation du départ par position"
        force_start(j, len(order))
        assert force_check(j, len(order)) == [float(p) for p in range(len(order))], "simulation du départ forcé"
        assert position_check(j, len(order)) == [float(p) for p in range(len(order))], "départ par position après"
        assert len(managed_chain(j)) >= len(order), "objets morceaux sans fin de morceau connue"
        assert ended_check(j) == {0.0: "stop", 1.0: "next", 2.0: "stop", 7.0: "stop", float(FORCE_BASE): "stop"}
        tracks = [info[o][:2] for o in order]
        covers = [info[o][2] for o in order]
    else:
        sizes = playlist(j, objs)
        reached = play_targets(j)
        assert reached == set(objs), ("simulation", sorted(set(objs) - reached), sorted(reached - set(objs)))
        mode = f"random draw, groups {' + '.join(map(str, sizes))}"
        tracks, covers = [], []                           # no known order: no banner
    fs = Jboa(open(os.path.join(E, "root", "audio", "dat", "finalsubmix.dat"), "rb").read())
    fps = Jboa(open(os.path.join(E, "root", "audio", "dat", "finalperksubmix.dat"), "rb").read())
    if effects == "oui":
        wreck_muffle(fs)
    elif effects == "partiel":
        soften_perk_effects(fs)
        no_collision_effects(fs)
        no_bitcrusher(fs)
        wreck_muffle(fs, cutoff=0.06)
    else:
        no_perk_duck(fs)
        no_perk_volumes(fs)
        no_perk_lowpass(fs)
        no_collision_effects(fs)
        no_bitcrusher(fs)
        no_perk_submix_effects(fps)
    os.makedirs(os.path.join(out, "audio", "dat"), exist_ok=True)
    open(os.path.join(out, "audio", "ingamemusic.baf"), "wb").write(bank)
    open(os.path.join(out, "audio", "dat", "music_controller.dat"), "wb").write(j.build())
    open(os.path.join(out, "audio", "dat", "finalsubmix.dat"), "wb").write(fs.build())
    open(os.path.join(out, "audio", "dat", "finalperksubmix.dat"), "wb").write(fps.build())
    write_titles(tracks, out, write_covers(covers, out))
    return f"{len(objs)} race tracks ({mode}); game effects on the sound: {effects}; quality: {'high (uncompressed)' if pcm16 else 'normal'}"


UI_COMMON = os.path.join("ui", "data", "ui_common.bpr")   # the bundle of hud_main / light_paint_02: covers go in it
ART_NAME, ART_SIZE, ART_CELL = "blur_music_art", 1024, 256  # DXT1 atlases blur_music_art0, 1... of 4 x 4 cells
ART_RADIUS = 0.06                                        # corner radius, fraction of the side (HUD panels' look)
ART_TARGET, ART_KNEE = 0.30, 0.75                        # cover levelling: mean luminance, highlight knee (see art_level)
COVER_NAMES = ("cover", "folder", "front", "album")      # picture files next to the music that serve as a cover


def cover_image(path):
    """The cover of an audio file, as a square ART_CELL RGB image, or None: a picture with the same name as the file,
    else its embedded picture (tags, ffmpeg), else cover / folder / front / album .jpg / .png in its folder."""
    from PIL import Image
    base, d = os.path.splitext(path)[0], os.path.dirname(path)
    pics = [base + e for e in (".jpg", ".jpeg", ".png")]
    side = [os.path.join(d, n + e) for n in COVER_NAMES for e in (".jpg", ".jpeg", ".png")]
    vf = f"scale={ART_CELL}:{ART_CELL}:force_original_aspect_ratio=increase,crop={ART_CELL}:{ART_CELL}"
    with tempfile.TemporaryDirectory() as tmp:
        out = os.path.join(tmp, "c.png")
        for src in [p for p in pics if os.path.exists(p)] + [path] + [p for p in side if os.path.exists(p)]:
            r = subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", src, "-an", "-frames:v", "1", "-vf", vf, out],
                               capture_output=True)
            if r.returncode == 0 and os.path.exists(out):
                return Image.open(out).convert("RGB")
    return None


def art_level(img):
    """Per-cover brightness (the HUD's bloom burnt bright covers; one fixed brightness did not suit every cover, player
    2026-11-16): scale to ART_TARGET mean luminance (at most x1.3), then a soft knee on the highlights."""
    from PIL import Image
    a = np.asarray(img, dtype=np.float32) / 255.0
    lum = float((a @ np.array([0.2126, 0.7152, 0.0722], np.float32)).mean())
    a *= min(1.3, ART_TARGET / max(lum, 1e-3))
    hi = a > ART_KNEE
    a[hi] = ART_KNEE + (1 - ART_KNEE) * (1 - np.exp(-(a[hi] - ART_KNEE) / (1 - ART_KNEE)))
    return Image.fromarray((np.clip(a, 0, 1) * 255 + 0.5).astype("uint8"))


def write_covers(covers, out):
    """covers = audio path (or None) per shuffle position. Writes out/ui/data/ui_common.bpr = the original + one atlas
    per 16 covers (confirmed in game 2026-11-16: an added texture is found by name, pos / size pick the cell).
    Returns {position: (atlas name, u, v)}; a track without a cover has no entry (no square in game)."""
    from PIL import Image
    import blurbpr
    found = {}
    for p, path in enumerate(covers):
        img = cover_image(path) if path else None
        if img is not None:
            found[p] = art_level(img)
    per = (ART_SIZE // ART_CELL) ** 2
    cells, additions = {}, []
    order = sorted(found)
    # rounded corners like the HUD panels (player, 2026-11-16): an alpha mask per cell, so the sheets are DXT5
    # rounded corners like the HUD panels (player, 2026-11-16); the cover sits on the banner's own backing (side by side
    # with the text, player 2026-11-16), so no band of its own: alpha mask, DXT5 sheets
    from PIL import ImageDraw
    big = Image.new("L", (ART_CELL * 4, ART_CELL * 4))     # drawn 4x larger, then reduced: smooth edges
    ImageDraw.Draw(big).rounded_rectangle((0, 0, ART_CELL * 4 - 1, ART_CELL * 4 - 1), int(ART_CELL * 4 * ART_RADIUS), fill=255)
    mask = big.resize((ART_CELL, ART_CELL), Image.LANCZOS)
    for a in range(0, len(order), per):
        sheet = Image.new("RGBA", (ART_SIZE, ART_SIZE), (0, 0, 0, 0))
        name = f"{ART_NAME}{a // per}"
        for k, p in enumerate(order[a:a + per]):
            x, y = (k % 4) * ART_CELL, (k // 4) * ART_CELL
            cell = found[p].convert("RGBA")
            cell.putalpha(mask)
            sheet.paste(cell, (x, y))
            cells[p] = (name, x / ART_SIZE, y / ART_SIZE)
        raw = blurbpr.encode(sheet, 5, 1)
        additions.append((name, [0x1C, 0, 0, 1, len(raw), 0, 5, 1, ART_SIZE, ART_SIZE], raw))   # DXT5, 1 mip
    b = blurbpr.Bpr(os.path.join(E, "root", UI_COMMON)).rebuild(additions)
    os.makedirs(os.path.join(out, "ui", "data"), exist_ok=True)
    open(os.path.join(out, UI_COMMON), "wb").write(b.b)
    print(f"  covers: {len(found)} of {len(covers)} tracks ({len(additions)} picture sheet(s))")
    return cells


def write_titles(tracks, out, covers=None):
    """The banner's data, for tracks = [(title, seconds)] in shuffle order (position p = order[p]): hud.loc with one
    text per position (hash TITLE_HASH0 + p; the plugin shows it with ChangeText(id, hash), shown in game 2026-11-13)
    and musicctl.lua from its template, its line "local TRACKS = {}" filled with {hash, seconds} per position."""
    import blurloc
    d = blurloc.parse_raw(open(HUD_LOC, "rb").read())
    for p, (lines, _) in enumerate(tracks):              # hashes: title TITLE_HASH0 + p, info line i: + 0x800 + 4p + i
        for i, text in enumerate(lines):
            h = TITLE_HASH0 + p if i == 0 else TITLE_HASH0 + 0x800 + 4 * p + i
            blurloc.add_text(d, f"BLURMUSIC_TRACK_{p}_{i}", h, {"en": text})
    os.makedirs(os.path.join(out, "gamedata", "xt", "loc"), exist_ok=True)
    open(os.path.join(out, "gamedata", "xt", "loc", "hud.loc"), "wb").write(blurloc.build(d))
    lua = open(PLUGIN_TEMPLATE, encoding="utf-8").read()
    line = "local TRACKS = {}"
    assert lua.count(line) == 1, "musicctl.lua: no 'local TRACKS = {}' line"
    lua = lua.replace(line, "local TRACKS = { " + ", ".join(
        "{ " + ", ".join([str(TITLE_HASH0 + p), f"{sec:.1f}"] + [str(TITLE_HASH0 + 0x800 + 4 * p + i) for i in range(1, min(len(lines), 4))]) + " }"
        for p, (lines, sec) in enumerate(tracks)) + " }")
    line = "local COVERS = {}"                                # {[position + 1] = {atlas, u, v}}: the cover square
    assert lua.count(line) == 1, "musicctl.lua: no 'local COVERS = {}' line"
    lua = lua.replace(line, "local COVERS = { " + ", ".join(
        f'[{p + 1}] = {{ "{n}", {u:g}, {v:g} }}' for p, (n, u, v) in sorted((covers or {}).items())) + " }")
    os.makedirs(os.path.join(out, "amax", "plugins", "musicctl"), exist_ok=True)
    open(os.path.join(out, "amax", "plugins", "musicctl", "musicctl.lua"), "w", encoding="utf-8", newline="\n").write(lua)
    for p, (lines, sec) in enumerate(tracks):
        print(f"  position {p}: {' / '.join(lines)} ({sec:.0f} s)")


def install(out=OUT, test=TEST):
    """Copy the built files into the test copy (Blur must be closed)."""
    if b"Blur.exe" in subprocess.run(["tasklist", "/fi", "imagename eq Blur.exe"], capture_output=True).stdout:
        raise SystemExit("Blur is running: close it and try again.")
    for rel in ("audio/ingamemusic.baf", "audio/dat/music_controller.dat", "audio/dat/finalsubmix.dat",
                "audio/dat/finalperksubmix.dat", "gamedata/xt/loc/hud.loc", "amax/plugins/musicctl/musicctl.lua",
                "ui/data/ui_common.bpr"):
        src, dst = os.path.join(out, rel), os.path.join(test, rel)
        if not os.path.exists(dst) or open(src, "rb").read() != open(dst, "rb").read():
            shutil.copyfile(src, dst)
            print("installed:", rel)


if __name__ == "__main__":
    print(build(sys.argv[1:]))
    install()
