#!/usr/bin/env python3
"""Install the Railgun (natif/railgun, v2) in the TEST copy only; --remove puts everything back.

The Railgun takes the place of the cut SuperShield power-up (own enum, HUD entry and name); the Bolt stays the Bolt.
- railgun.dll + railgun.txt -> Blur_test\\amax\\dlls (AMAX's d3d9.dll loads every .dll / .asi there);
- pickups.bin: the Bolt back to the original (v1 changed it); SuperShield level (uid 0x9B08F5FA) Delay = DELAY,
  the time between the button and the shot (Shunt 0.5 s, Bolt 0.1 s);
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

SUPERSHIELD_LEVEL = 0x9B08F5FA
DELAY = 1.5
PINK = b"!255 153 153 255"
TITANIUM = b"!232 236 242 255"          # same length: the string zone keeps its layout
NAME_HASH, NAME = 1665195695, "RAILGUN"
SOUNDS = os.path.join(config.BLUR_EXTRACTED, "mods", "railgun_sounds")
FILES = {"pickups.bin": ("gamedata", "xt"), "ui.bin": ("gamedata", "xt"), "common.loc": ("gamedata", "xt", "loc")}


def level(x, uid):
    hit = [(n, v) for n, t, v, h in x.records() if h == uid]
    assert len(hit) == 1, hit
    return hit[0]


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


def make_sound(path, delay=DELAY, rate=44100):
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


def _load(path, rate):
    import numpy as np
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-f", "f32le", "-ac", "2", "-ar", str(rate), "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32).reshape(-1, 2).copy()


def mix_sound(charge, shot, impact=None, out=None, delay=DELAY, rate=44100):
    """Railgun sound from the user's files: the end of `charge` fills the firing delay (its quiet start is cut),
    `shot` starts exactly at the delay, `impact` (optional) = the loudest moment of another file, layered under the
    shot for weight. Stereo 16-bit WAV in SOUNDS (outside the repo: third-party sounds)."""
    import numpy as np, wave
    n = int(rate * delay)
    c = _load(charge, rate)[-n:]
    c[:int(rate * 0.05)] *= np.linspace(0, 1, int(rate * 0.05))[:, None]
    s = _load(shot, rate)
    s /= np.abs(s).max()                             # shootBeamPlasma peaks at 1.44: clipped as it is
    if impact:
        i = _load(impact, rate)
        env = np.convolve(np.abs(i).mean(1), np.ones(441) / 441, "same")
        k = max(0, int(np.argmax(np.diff(env, prepend=0) * (env > 0.5 * env.max()))) - int(rate * 0.01))
        i = i[k:k + int(rate * 1.2)]
        i *= np.linspace(1, 0, len(i))[:, None] ** 2
        layer = np.zeros((max(len(s), len(i)), 2), np.float32)
        layer[:len(s)] += s
        layer[:len(i)] += 0.5 * i / np.abs(i).max()
        s = layer
    x = np.concatenate([c / np.abs(c).max() * 0.6, s])
    x = np.int16(np.clip(x / np.abs(x).max() * 0.8, -1, 1) * 32767)
    out = out or os.path.join(SOUNDS, "railgun_fire.wav")
    os.makedirs(os.path.dirname(out), exist_ok=True)
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
        for f in ("railgun.dll", "railgun.txt", "railgun_fire.wav"):
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
    name, _ = level(XT(work["pickups.bin"]), SUPERSHIELD_LEVEL)
    data = XT(work["pickups.bin"]).patched(name, "BalancingData.Delay", DELAY)
    open(work["pickups.bin"], "wb").write(data)
    changed = [n for (n, _, v, _), (_, _, w, _) in zip(XT(os.path.join(bakdir, "pickups.bin")).records(),
                                                       XT(work["pickups.bin"]).records()) if v != w]
    assert changed == [name], changed
    assert abs(level(XT(work["pickups.bin"]), SUPERSHIELD_LEVEL)[1]["BalancingData"]["Delay"] - DELAY) < 1e-4
    hud = recolour(work["ui.bin"])
    rename(work["common.loc"])
    for f, path in live.items():
        shutil.copyfile(work[f], path)
    for f in ("railgun.dll", "railgun.txt"):
        shutil.copyfile(os.path.join(HERE, "natif", "railgun", f), os.path.join(dlls, f))
    own = os.path.join(SOUNDS, "railgun_fire.wav")    # made by --sound from the user's files, else our synth
    if os.path.exists(own):
        shutil.copyfile(own, os.path.join(dlls, "railgun_fire.wav"))
    else:
        make_sound(os.path.join(dlls, "railgun_fire.wav"))
    print("railgun installed in", dlls, "| delay", DELAY, "s | HUD", hud["colour_fill"], "| name", NAME)


if __name__ == "__main__":
    if sys.argv[1:2] == ["--sound"]:                  # --sound CHARGE SHOT [IMPACT]: build the sound, then install
        print("sound:", mix_sound(*sys.argv[2:5]))
    else:
        main("--remove" in sys.argv)
