#!/usr/bin/env python3
"""Install the Railgun (natif/railgun, v2) in the TEST copy only; --remove puts everything back.

The Railgun takes the place of the cut SuperShield power-up (own enum, HUD entry and name); the Bolt stays the Bolt.
- railgun.dll + railgun.txt -> Blur_test\\amax\\dlls (AMAX's d3d9.dll loads every .dll / .asi there);
  railgun.txt holds the firing delays (forward `delay`, backward `rear_delay`), set by the dll, used for the sounds;
- railgun_fire.wav (forward, remix FRONT) / railgun_fire_rear.wav (backward, remix REAR), charge as long as each
  delay, made from the sources in SOUNDS (else our synth);
- pickups.bin: back to the original (v1 changed the Bolt, the first v2 the SuperShield Delay);
- ui.bin: HUD colours of the SuperShield entry (UiXtConfig.PerkDisplayParameters.superShield), pink -> titanium
  white (same-length string, rewritten in the record's scrambled string zone);
- loc\\common.loc: "SUPER SHIELD" / "SUPER BOUCLIER"... (hash 1665195695) -> NAME in every language.
Originals kept once in blur_extracted\\mods\\railgun_backup. Refused unless Blur_test has
COPIE_DE_TEST_HORS_LIGNE.txt and Blur.exe is not running.
usage: railgun_install.py [--remove]
"""
import os, shutil, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import config  # noqa: E402
import blurloc  # noqa: E402
from blurxt import XT, decode_names, encode_names  # noqa: E402

FRONT, REAR = "A_titane", "B_lourd"           # user's choice (2026-11-16): A forward, B backward
PINK = b"!255 153 153 255"
TITANIUM = b"!232 236 242 255"          # same length: the string zone keeps its layout
NAME_HASH, NAME = 1665195695, "RAILGUN"
SOUNDS = os.path.join(config.BLUR_EXTRACTED, "mods", "railgun_sounds")
SOURCES = dict(charge="core_assets_sounds_charge_chargeCorvus.ogg", shot="ShuntFire.wav", lfe="ShuntFireLFE.wav",
               plasma="core_assets_sounds_shoot_shootBeamPlasma.ogg")
FILES = {"pickups.bin": ("gamedata", "xt"), "ui.bin": ("gamedata", "xt"), "common.loc": ("gamedata", "xt", "loc")}


def delays():
    """(forward, backward) firing delays from natif/railgun/railgun.txt, as the dll reads them."""
    d = {"delay": 1.0, "rear_delay": 0.5}
    for line in open(os.path.join(HERE, "natif", "railgun", "railgun.txt"), encoding="utf-8"):
        k = line.split()
        if len(k) > 1 and k[0] in d:
            d[k[0]] = float(k[1])
    return d["delay"], d["rear_delay"]


def recolour(path):
    """Replace PINK by TITANIUM in the string zone of the UiXtConfig record (the superShield HUD colours)."""
    x = XT(path)
    b = bytearray(x.b)
    base, p, done = x.sec[7][0], 0, 0
    names = [n for n, *_ in x.records()]           # fills x internals; walk the items again for the offsets
    for (idx, nch, dsize, ssize), (n, t, v, h) in zip(x.items(), XT(path).records()):
        if t == "UiXtConfig" and ssize:
            z = base + p + dsize
            plain = decode_names(bytes(b[z:z + ssize]))
            if PINK + b"\0" in plain:
                plain = plain.replace(PINK + b"\0", TITANIUM + b"\0")
                b[z:z + ssize] = encode_names(plain)
                done += 1
        p += dsize + ssize
    assert names and done == 1, done
    open(path, "wb").write(bytes(b))
    got = next(v for n, t, v, h in XT(path).records() if t == "UiXtConfig")["PerkDisplayParameters"]["superShield"]
    assert got["colour_fill"] == TITANIUM.decode() and got["colour_glow"] == TITANIUM.decode(), got
    return got


def make_sound(path, delay, rate=44100):
    """Our own railgun sound (no third-party asset): a charge that rises during the firing delay, then the shot
    (crack + low thump + metallic ring). 16-bit mono WAV, played by railgun.dll when the player fires."""
    import numpy as np, wave
    rng = np.random.default_rng(7)
    t = np.arange(int(rate * delay)) / rate
    f = 180 + 2600 * (t / delay) ** 2                                   # rising whine
    ph = 2 * np.pi * np.cumsum(f) / rate
    charge = (np.sin(ph) + 0.35 * np.sin(2.01 * ph) + 0.15 * np.sin(3.98 * ph)) * (0.08 + 0.5 * (t / delay) ** 1.5)
    charge *= 1 + 0.25 * np.sin(2 * np.pi * (6 + 30 * t / delay) * t)   # shimmer speeding up
    s = np.arange(int(rate * 0.9)) / rate
    crack = rng.standard_normal(len(s)) * np.exp(-s / 0.012)
    thump = np.sin(2 * np.pi * (90 - 40 * s) * s) * np.exp(-s / 0.09)
    ring = sum(a * np.sin(2 * np.pi * fr * s) for a, fr in ((0.5, 1870), (0.35, 2911), (0.25, 4357), (0.15, 6533)))
    shot = 1.0 * crack + 0.9 * thump + 0.6 * ring * np.exp(-s / 0.25)
    x = np.concatenate([charge, shot])
    x[:int(rate * 0.02)] *= np.linspace(0, 1, int(rate * 0.02))
    x = np.int16(np.clip(x / np.max(np.abs(x)) * 0.7, -1, 1) * 32767)
    with wave.open(path, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(rate); w.writeframes(x.tobytes())


def _load(path, rate, af=None):
    """Decode to float stereo at `rate`, through an optional ffmpeg filter chain (af)."""
    import numpy as np
    cmd = ["ffmpeg", "-v", "error", "-i", path] + (["-af", af] if af else [])
    raw = subprocess.run(cmd + ["-f", "f32le", "-ac", "2", "-ar", str(rate), "-"], capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32).reshape(-1, 2).copy()


def _pitch(semitones, rate=44100):
    """Tape-style pitch shift (length changes with it), as an ffmpeg filter."""
    return f"asetrate={rate}*{2 ** (semitones / 12):.5f},aresample={rate}"


# Remixes of the charge (chargeCorvus) and of the game's Shunt shot (ShuntFire + ShuntFireLFE) so that the
# railgun stops sounding like them; same shape: charge as long as the delay, then the shot (boom + falling tail).
# charge / shot / lfe: ffmpeg filters; ring: (start Hz, end Hz, mix) ring modulation of the charge; trem: (start Hz,
# end Hz) tremolo; swell: gain of a reversed, pitched-up Shunt tail rising into the shot; drive: tanh saturation of
# the shot; haas: right channel delay (ms) for width; plasma: gain of the user's plasma crack.
REMIXES = {
    "A_titane": dict(charge=_pitch(4) + ",highpass=f=250", ring=(300, 900, 0.35), trem=(8, 40), swell=0.5,
                     shot=_pitch(-3) + ",flanger=delay=2:depth=4:speed=0.3", drive=2.0, lfe=_pitch(-2), lfe_gain=0.5,
                     plasma=0.6, haas=12),
    "B_lourd": dict(charge=_pitch(-3) + ",lowpass=f=3000", ring=(60, 120, 0.2), trem=(4, 18), swell=0.35,
                    shot=_pitch(-6) + ",aecho=0.8:0.7:60|140:0.4|0.25", drive=3.0, lfe=_pitch(-4), lfe_gain=0.8,
                    plasma=0.4, haas=18),
    "C_electrique": dict(charge=_pitch(2) + ",aphaser=speed=2:decay=0.6", ring=(800, 1600, 0.5), trem=(12, 60),
                         swell=0.45, shot=_pitch(2) + ",aphaser=speed=0.7:decay=0.5", drive=1.5, lfe=None,
                         lfe_gain=0.4, plasma=0.8, haas=8),
}


def remix_sound(name, charge, shot, lfe, plasma, delay, out=None, rate=44100):
    """One REMIXES variant, its charge `delay` s long -> out (default SOUNDS/railgun_<name>.wav), stereo 16-bit."""
    import numpy as np, wave
    p = REMIXES[name]
    n = int(rate * delay)
    t = np.arange(n) / rate
    c = _load(charge, rate, p["charge"])[-n:]
    c /= np.abs(c).max()
    f0, f1, mix = p["ring"]
    car = np.sin(2 * np.pi * np.cumsum(f0 + (f1 - f0) * t / delay) / rate)[:, None]
    c = c * (1 - mix) + c * car * mix
    a0, a1 = p["trem"]
    c *= (0.75 + 0.25 * np.sin(2 * np.pi * np.cumsum(a0 + (a1 - a0) * (t / delay) ** 2) / rate))[:, None]
    c *= (0.5 + 0.5 * (t / delay) ** 1.5)[:, None]                  # rises towards the shot
    tail = _load(shot, rate, _pitch(7))[::-1]                         # reversed Shunt tail: swell into the shot
    k = min(len(tail), int(rate * 0.6), n)
    sw = tail[-k:] / np.abs(tail[-k:]).max() * np.linspace(0, 1, k)[:, None] ** 2
    c[-k:] += p["swell"] * sw
    c[:int(rate * 0.03)] *= np.linspace(0, 1, int(rate * 0.03))[:, None]
    s = _load(shot, rate, p["shot"])
    s = np.tanh(p["drive"] * s / np.abs(s).max()) / np.tanh(p["drive"])
    for path, af, g in ((lfe, p["lfe"], p["lfe_gain"]), (plasma, None, p["plasma"])):
        y = _load(path, rate, af)
        y = y / np.abs(y).max() * g
        if len(y) > len(s):
            s = np.vstack([s, np.zeros((len(y) - len(s), 2), np.float32)])
        s[:len(y)] += y
    d = int(rate * p["haas"] / 1000)
    s[d:, 1] = s[:-d, 1].copy()
    s[-int(rate * 0.05):] *= np.linspace(1, 0, int(rate * 0.05))[:, None]
    x = np.concatenate([c * 0.85, s])
    x = np.int16(np.clip(x / np.abs(x).max() * 0.8, -1, 1) * 32767)
    out = out or os.path.join(SOUNDS, f"railgun_{name}.wav")
    with wave.open(out, "wb") as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(rate); w.writeframes(x.tobytes())
    return out


def rename(path):
    d = blurloc.parse_raw(open(path, "rb").read())
    for code, texts in d["langs"]:
        assert NAME_HASH in texts
        texts[NAME_HASH] = NAME
    open(path, "wb").write(blurloc.build(d))


def main(remove=False):
    game = config.BLUR_TEST
    assert os.path.isfile(os.path.join(game, "COPIE_DE_TEST_HORS_LIGNE.txt")), "not the test copy"
    run = subprocess.run(["tasklist", "/FI", "IMAGENAME eq Blur.exe"], capture_output=True, text=True).stdout
    assert "Blur.exe" not in run, "Blur is running: close it first"
    dlls = os.path.join(game, "amax", "dlls")
    bakdir = os.path.join(config.BLUR_EXTRACTED, "mods", "railgun_backup")
    os.makedirs(bakdir, exist_ok=True)
    live = {f: os.path.join(game, *sub, f) for f, sub in FILES.items()}
    for f, path in live.items():                   # pickups.bin backup = the original (made before v1 changed it)
        if not os.path.exists(os.path.join(bakdir, f)):
            shutil.copyfile(path, os.path.join(bakdir, f))
    if remove:
        for f in ("railgun.dll", "railgun.txt", "railgun_fire.wav", "railgun_fire_rear.wav"):
            if os.path.exists(os.path.join(dlls, f)):
                os.remove(os.path.join(dlls, f))
        for f, path in live.items():
            shutil.copyfile(os.path.join(bakdir, f), path)
        print("railgun removed, originals back")
        return
    tmp = tempfile.mkdtemp(prefix="railgun_")
    work = {f: os.path.join(tmp, f) for f in FILES}
    for f in FILES:
        shutil.copyfile(os.path.join(bakdir, f), work[f])     # always from the originals: running twice is harmless
    hud = recolour(work["ui.bin"])
    rename(work["common.loc"])
    for f, path in live.items():
        shutil.copyfile(work[f], path)
    for f in ("railgun.dll", "railgun.txt"):
        shutil.copyfile(os.path.join(HERE, "natif", "railgun", f), os.path.join(dlls, f))
    front, rear = delays()
    src = {k: os.path.join(SOUNDS, f) for k, f in SOURCES.items()}
    for wav, remix, delay in (("railgun_fire.wav", FRONT, front), ("railgun_fire_rear.wav", REAR, rear)):
        if all(map(os.path.exists, src.values())):    # the final sounds also stay in SOUNDS, to listen to
            shutil.copyfile(remix_sound(remix, delay=delay, out=os.path.join(SOUNDS, wav), **src), os.path.join(dlls, wav))
        else:
            make_sound(os.path.join(dlls, wav), delay)
    print("railgun installed in", dlls, f"| delay {front} s, rear {rear} s | HUD", hud["colour_fill"], "| name", NAME)


if __name__ == "__main__":
    if sys.argv[1:2] == ["--remix"]:                  # --remix: every variant in SOUNDS, to listen and choose
        for k in REMIXES:
            print(remix_sound(k, delay=delays()[0], **{k2: os.path.join(SOUNDS, f) for k2, f in SOURCES.items()}))
    else:
        main("--remove" in sys.argv)
