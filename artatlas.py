#!/usr/bin/env python3
"""Album-art atlas probe (Blur_test only, 2026-11-16): one DXT1 1024 x 1024 texture "blur_music_art" (4 x 4 cells of
256 px) appended to ui\\data\\ui_common.bpr (the bundle of hud_main / light_paint_02), cells = the embedded covers of
the music files (ffmpeg, cropped square), else a numbered tile. artprobe shows a cell with
ChangeTexture({filename="blur_music_art", pos={u,v}, size={u=0.25,v=0.25}}).
usage: artatlas.py [--undo]   (Blur closed; the original ui_common.bpr is kept in blur_extracted/mods/artprobe)"""
import os, shutil, subprocess, sys, tempfile
from PIL import Image, ImageDraw
import blurbpr, make_music as mm

NAME, SIZE, CELL = "blur_music_art", 1024, 256
BPR = os.path.join(mm.TEST, "ui", "data", "ui_common.bpr")
BACKUP = os.path.join(mm.E, "mods", "artprobe", "ui_common.original.bpr")
AUDIO = (".mp3", ".wav", ".flac", ".ogg", ".m4a")


def cover(path, tmp):
    """Embedded cover of an audio file, cropped to a CELL square (None if it has none)."""
    out = os.path.join(tmp, "c.png")
    if os.path.exists(out):
        os.remove(out)
    r = subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", path, "-an", "-frames:v", "1", "-vf",
                        f"scale={CELL}:{CELL}:force_original_aspect_ratio=increase,crop={CELL}:{CELL}", out],
                       capture_output=True)
    return Image.open(out).convert("RGB") if r.returncode == 0 and os.path.exists(out) else None


TARGET = 0.30          # mean luminance of a cell after levelling (probe 5: the HUD bloom burns bright covers)
KNEE = 0.75            # highlights above it are compressed (white areas stay readable)


def level(img):
    """Per-cover brightness (player, 2026-11-16: one fixed brightness cannot suit every cover): scale to TARGET mean
    luminance (never brighten more than x1.3), then a soft knee on the highlights."""
    import numpy as np
    a = np.asarray(img, dtype=np.float32) / 255.0
    lum = (a @ np.array([0.2126, 0.7152, 0.0722], np.float32)).mean()
    a *= min(1.3, TARGET / max(lum, 1e-3))
    hi = a > KNEE
    a[hi] = KNEE + (1 - KNEE) * (1 - np.exp(-(a[hi] - KNEE) / (1 - KNEE)))
    return Image.fromarray((np.clip(a, 0, 1) * 255 + 0.5).astype("uint8"))


def atlas(files):
    img = Image.new("RGB", (SIZE, SIZE), (40, 40, 40))
    with tempfile.TemporaryDirectory() as tmp:
        for k in range((SIZE // CELL) ** 2):
            c = cover(files[k], tmp) if k < len(files) else None
            print(f"cell {k}: {os.path.basename(files[k]) if k < len(files) else '-'} {'cover' if c else 'tile'}")
            if c is None:
                c = Image.new("RGB", (CELL, CELL), (60 + 12 * k, 60, 120))
                ImageDraw.Draw(c).text((CELL // 2 - 8, CELL // 2 - 8), str(k), fill=(255, 255, 255))
            img.paste(level(c), ((k % 4) * CELL, (k // 4) * CELL))
    return img


def main():
    if "--undo" in sys.argv:
        shutil.copyfile(BACKUP, BPR)
        print("ui_common.bpr put back")
        return
    if not os.path.exists(BACKUP):
        os.makedirs(os.path.dirname(BACKUP), exist_ok=True)
        shutil.copyfile(BPR, BACKUP)
    files = sorted(os.path.join(d, f) for d, _, fs in os.walk(mm.MUSIC_DIR) for f in fs if f.lower().endswith(AUDIO))
    img = atlas(files)
    img.save(os.path.join(os.path.dirname(BACKUP), "blur_music_art.png"))
    raw = blurbpr.encode(img, 1, 1)
    rec = [0x1C, 0, 0, 1, len(raw), 0, 1, 1, SIZE, SIZE]          # DXT1, 1 mip
    b = blurbpr.Bpr(BACKUP).rebuild([(NAME, rec, raw)])          # always from the original: rerun = same result
    open(BPR, "wb").write(b.b)
    print(f"{NAME} added to {BPR} ({len(b.names)} images)")


if __name__ == "__main__":
    main()
