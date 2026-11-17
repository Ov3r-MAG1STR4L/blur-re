#!/usr/bin/env python3
"""Test look for the Shield power-up lying on the track (2026-11-17): hexagon -> triangle + "6". TEST COPY only.

models/perks/pickups/shieldpickup.model (root.pak; same bytes in boot.pak) embeds its own 2 textures, used by
nothing else: icon_shield_01 (glowing box + dark hexagon) and icon_shield_01_inverse (white hexagon on black), both
DXT1 256x256, 9 mips, opaque grey (colour comes from the shader / effect). The textures live INSIDE the .model: only
their bytes change (blurtex.inject, same size); geometry, materials and every other byte are checked identical.

usage: shield_pickup_icon.py      writes blur_extracted\\mods\\hud_shield_pickup\\{textures_new, files, preview}
"""
import hashlib, os, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import blurtex  # noqa: E402

MOD = r"C:\Users\sanqu\Jeux_WII\blur_extracted\mods\hud_shield_pickup"
SRC = os.path.join(MOD, "original", "shieldpickup.model")          # = root.pak / boot.pak copy, SHA-1 d56a40d7...
ORIG = os.path.join(MOD, "textures_orig")                           # blurtex.extract of SRC
NEW = os.path.join(MOD, "textures_new")
OUT = os.path.join(MOD, "files", "models", "perks", "pickups", "shieldpickup.model")
TRI = [(112, 112), (72, 212), (152, 212)]                           # inside the old hexagon box (x 62-192, y 103-220)
STROKE = 18


def font(size):
    for f in (r"C:\Windows\Fonts\arialbd.ttf", r"C:\Windows\Fonts\arial.ttf"):
        if os.path.exists(f):
            return ImageFont.truetype(f, size)
    return ImageFont.load_default(size=size)


def symbol(ink, bg):
    """triangle outline + '6' on a 256x256 L image"""
    im = Image.new("L", (256, 256), bg)
    d = ImageDraw.Draw(im)
    d.line(TRI + [TRI[0]], fill=ink, width=STROKE, joint="curve")
    d.text((150, 118), "6", fill=ink, font=font(92))
    return im


def fill_hole(a, mask, steps=600):
    """diffuse the surrounding glow into the masked pixels (removes the old hexagon)"""
    a = a.astype(np.float64)
    a[mask] = a[~mask].mean()
    for _ in range(steps):
        n = (np.roll(a, 1, 0) + np.roll(a, -1, 0) + np.roll(a, 1, 1) + np.roll(a, -1, 1)) / 4
        a[mask] = n[mask]
    return a


def main():
    os.makedirs(NEW, exist_ok=True)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    box = np.asarray(Image.open(os.path.join(ORIG, "icon_shield_01.png")).convert("L"))
    hexa = np.asarray(Image.open(os.path.join(ORIG, "icon_shield_01_inverse.png")).convert("L"))
    hole = np.asarray(Image.fromarray((hexa > 20).astype(np.uint8) * 255).filter(ImageFilter.MaxFilter(13))) > 0
    clean = fill_hole(box, hole)
    dark = symbol(255, 0).filter(ImageFilter.GaussianBlur(2))        # soft dark outline, like the hexagon
    k = np.asarray(dark, np.float64) / 255
    icon = np.clip(clean * (1 - k) + 8 * k, 0, 255).astype(np.uint8)
    Image.fromarray(icon).convert("RGB").save(os.path.join(NEW, "icon_shield_01.png"))
    symbol(255, 0).filter(ImageFilter.GaussianBlur(0.6)).convert("RGB").save(os.path.join(NEW, "icon_shield_01_inverse.png"))

    done = blurtex.inject(SRC, NEW, OUT)
    assert sorted(done) == ["icon_shield_01", "icon_shield_01_inverse"], done
    a, b = open(SRC, "rb").read(), open(OUT, "rb").read()
    assert len(a) == len(b)
    ranges = [(t["off"], t["off"] + len(t["data"])) for t in blurtex.records(a) if t["name"].startswith("icon_shield")]
    assert len(ranges) == 2
    changed = np.flatnonzero(np.frombuffer(a, np.uint8) != np.frombuffer(b, np.uint8))
    assert all(any(s <= i < e for s, e in ranges) for i in changed), "a byte outside the textures changed"
    for t in blurtex.records(b):                                     # re-read: same records, new pictures
        assert t["fourcc"] == b"DXT1" and (t["w"], t["h"], t["mips"]) == (256, 256, 9)
    print("model", hashlib.sha1(a).hexdigest(), "->", hashlib.sha1(b).hexdigest(), f"({len(b)} bytes)")
    for s, e in ranges:
        print(f"   texture bytes 0x{s:06X}-0x{e:06X} ({e - s} B), changed {sum(s <= i < e for i in changed)}")
    print("bytes changed:", len(changed), "all inside the 2 textures ->", OUT)
    prev = os.path.join(MOD, "preview")
    os.makedirs(prev, exist_ok=True)
    blurtex.extract(OUT, prev)                                       # decoded back from the new model


if __name__ == "__main__":
    main()
