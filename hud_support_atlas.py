#!/usr/bin/env python3
"""HUD support sheet grown to 10 cells (indices 100-109), prototype (2026-11-17). Writes files for a TEST COPY only.

perk_sheet_support (DXT1) and perk_sheet_support_inverted (DXT5) go from 128x512 to 128x1024, 3 mips, i.e. the same
shape as perk_sheet / perk_sheet_inverted. Cells 100-104 (pixel rows 0-480) keep their original compressed blocks at
every mip (480, 240, 120 rows are whole DXT block rows); cells 105-109 are new test icons (rows 480-960).
ui.bin: size.v 0.1875 -> 0.09375 for the support textures of the three HUD gadgets (Perks_MainHUD, Perks_MainAttached:
textures 6 and 7; ai_perks: texture 2), so V = (index - 100) * 96 / 1024 still picks 96-pixel cells; then
shield.texture_index -> 105. Step 2: variants/ui_shield_106..109.bin = the same file with shield.texture_index only
changed to 106, 107, 108 or 109 (one index per test, Nitro untouched).
Every change is checked: other 61 images and cells 100-104 byte-identical, only the expected u32 of ui.bin change.

usage: hud_support_atlas.py            build into blur_extracted\\mods\\hud_support_atlas (never the game folder)
"""
import hashlib, io, os, struct, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import blurbpr  # noqa: E402
from blurxt import XT  # noqa: E402

EXT = r"C:\Users\sanqu\Jeux_WII\blur_extracted"
SRC_BPR = os.path.join(EXT, r"root\ui\data\ui_common.bpr")
SRC_UI = os.path.join(EXT, r"gamedata\gamedata\xt\ui.bin")           # = cache\gamedata.pak (SHA-1 3f235b34...)
OUT = os.path.join(EXT, r"mods\hud_support_atlas")
CELL, KEEP, W, H, MIPS = 96, 480, 128, 1024, 3                      # cells 100-104 = rows 0..480
SHEETS = {"perk_sheet_support": 1, "perk_sheet_support_inverted": 5}
SIZE_V = [(61, 6), (61, 7), (22, 6), (22, 7), (26, 2)]              # (hud_objects element, texture) of the support sheet
NEW = [(105, "circle", (255, 80, 80)), (106, "triangle", (80, 255, 80)), (107, "square", (80, 140, 255)),
       (108, "diamond", (255, 230, 60)), (109, "cross", (255, 80, 255))]     # step 2 (2026-11-17): 108 / 109 swapped
SHIELD_STEPS = [106, 107, 108, 109]       # step 2: one ui.bin per index, shield.texture_index only (Nitro untouched)


def sha1(b):
    return hashlib.sha1(b).hexdigest()


def cell(idx, shape, rgb, inverted):
    """one 128x96 test icon: rounded frame, a big shape, the index number (not an existing game icon)"""
    im = Image.new("RGBA", (W, CELL), (0, 0, 0, 0 if inverted else 255))
    d = ImageDraw.Draw(im)
    frame = (14, 8, 113, 87)
    if inverted:
        d.rounded_rectangle(frame, 14, fill=(215, 215, 215, 255))
        ink = (20, 20, 20, 255)
    else:
        d.rounded_rectangle(frame, 14, outline=(230, 230, 230, 255), width=4)
        ink = rgb + (255,)
    cx, cy, r = 46, 48, 24
    if shape == "circle":
        d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=ink)
    elif shape == "triangle":
        d.polygon([(cx, cy - r), (cx - r, cy + r), (cx + r, cy + r)], fill=ink)
    elif shape == "square":
        d.rectangle((cx - r + 3, cy - r + 3, cx + r - 3, cy + r - 3), fill=ink)
    elif shape == "cross":
        d.line((cx - r, cy - r, cx + r, cy + r), fill=ink, width=12)
        d.line((cx - r, cy + r, cx + r, cy - r), fill=ink, width=12)
    else:
        d.polygon([(cx, cy - r), (cx + r, cy), (cx, cy + r), (cx - r, cy)], fill=ink)
    d.text((76, 30), str(idx % 100), fill=ink, font=ImageFont.load_default(size=34))
    return im


def mip_bytes(fmt, w, h):
    return (w // 4) * (h // 4) * (8 if fmt == 1 else 16)


def grow(bpr, name, fmt):
    """new 128x1024 raw mip chain: original blocks for rows < 480 (at each mip), new encode below"""
    old_raw = bpr.raw(name)[1]
    full = Image.new("RGBA", (W, H), (0, 0, 0, 0 if fmt == 5 else 255))
    full.paste(bpr.image(name).convert("RGBA").crop((0, 0, W, KEEP)), (0, 0))
    for k, (idx, shape, rgb) in enumerate(NEW):
        full.paste(cell(idx, shape, rgb, fmt == 5), (0, KEEP + k * CELL))
    out, o_old, level = b"", 0, full
    for m in range(MIPS):
        w, h, h_old = W >> m, H >> m, 512 >> m
        enc = blurbpr.encode(level, fmt, 1)
        assert len(enc) == mip_bytes(fmt, w, h), (name, m, len(enc))
        keep = mip_bytes(fmt, w, KEEP >> m)                         # whole block rows of cells 100-104
        out += old_raw[o_old:o_old + keep] + enc[keep:]
        o_old += mip_bytes(fmt, w, h_old)
        level = level.resize((w // 2, h // 2), Image.BOX)
    assert o_old == len(old_raw) and len(out) == sum(mip_bytes(fmt, W >> m, H >> m) for m in range(MIPS))
    return out, full


def main():
    os.makedirs(os.path.join(OUT, "original"), exist_ok=True)
    src_bpr, src_ui = open(SRC_BPR, "rb").read(), open(SRC_UI, "rb").read()
    open(os.path.join(OUT, "original", "ui_common.bpr"), "wb").write(src_bpr)
    open(os.path.join(OUT, "original", "ui.bin"), "wb").write(src_ui)
    bpr = blurbpr.Bpr(data=src_bpr)
    # rebuild re-aligns images on 16 bytes (some ui_common.bpr offsets are not, e.g. 147029): not byte-identical
    # to the file, but every image and record field is kept (same as artatlas.py, validated in game 2026-11-16)
    same = bpr.rebuild()
    assert all(same.raw(n)[1] == bpr.raw(n)[1] and same.raw(n)[0][3:] == bpr.raw(n)[0][3:] for n in bpr.names)

    # --- textures
    resize, previews = {}, {}
    for name, fmt in SHEETS.items():
        raw, full = grow(bpr, name, fmt)
        resize[name] = (W, H, raw)
        previews[name] = full
    new = bpr.rebuild(resize=resize)
    for name, rec in zip(new.names, new.recs):                       # checks
        r_old, raw_old = bpr.raw(name)
        r_new, raw_new = new.raw(name)
        if name in SHEETS:
            assert r_new[6:] == [SHEETS[name], MIPS, W, H], r_new
            old_l, new_l, oo, on = r_old[1:2], 0, 0, 0
            for m in range(MIPS):
                k = mip_bytes(SHEETS[name], W >> m, KEEP >> m)
                assert raw_new[on:on + k] == raw_old[oo:oo + k], (name, m)
                oo += mip_bytes(SHEETS[name], W >> m, 512 >> m)
                on += mip_bytes(SHEETS[name], W >> m, H >> m)
        else:
            assert raw_new == raw_old and r_new[6:] == r_old[6:], name
    assert new.names == bpr.names and new.recs[-1][0] == 0
    for name in SHEETS:                                              # decoded rows 0-480 identical
        a = np.asarray(bpr.image(name).convert("RGBA"))[:KEEP]
        b = np.asarray(new.image(name).convert("RGBA"))[:KEEP]
        assert (a == b).all(), name
    files = os.path.join(OUT, "files")
    os.makedirs(os.path.join(files, "ui", "data"), exist_ok=True)
    open(os.path.join(files, "ui", "data", "ui_common.bpr"), "wb").write(new.b)

    # --- ui.bin (in-place u32 writes, offsets from blurxt.locate on the original)
    x = XT(SRC_UI)
    names = {i: n for i, n in [(61, "Perks_MainHUD"), (22, "Perks_MainAttached"), (26, "ai_perks")]}
    edits = []
    for el, tex in SIZE_V:
        off, _, _ = x.locate("hud_objects", f"Elements[{el}].textures[{tex}].size.v")
        assert abs(struct.unpack_from("<f", src_ui, off)[0] - 0.1875) < 1e-6, (el, tex)
        fn, _, _ = x.locate("hud_objects", f"Elements[{el}].textures[{tex}].filename")
        edits.append((off, "<f", 0.09375, f"{names[el]}.textures[{tex}].size.v 0.1875 -> 0.09375"))
    shield, _, _ = x.locate("#187", "PerkDisplayParameters.shield.texture_index")
    assert struct.unpack_from("<i", src_ui, shield)[0] == 7
    outputs = [("files/gamedata/xt/ui.bin", 105)] + [(f"variants/ui_shield_{n}.bin", n) for n in SHIELD_STEPS]
    step1 = None
    for label, v in outputs:
        b = bytearray(src_ui)
        for off, f, val, _ in edits:
            struct.pack_into(f, b, off, val)
        struct.pack_into("<i", b, shield, v)
        diff = [i for i in range(0, len(b), 4) if b[i:i + 4] != src_ui[i:i + 4]]
        assert diff == sorted([e[0] for e in edits] + [shield]), (label, diff)
        if step1 is None:
            step1 = bytes(b)
        else:                                                        # vs the validated step 1: shield only
            assert [i for i in range(0, len(b), 4) if b[i:i + 4] != step1[i:i + 4]] == [shield], label
        path = os.path.join(OUT, *label.split("/"))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        open(path, "wb").write(b)
        print(f"{label}: SHA-1 {sha1(b)}  shield.texture_index @0x{shield:06X} = {v}"
              + ("" if v == 105 else f"  (step 1: 105 -> {v}, only change)"))
    for off, f, v, what in edits:
        print(f"   all files: 0x{off:06X}  {src_ui[off:off + 4].hex()} -> {struct.pack(f, v).hex()}  {what}")
    for el, tex in SIZE_V:                                           # the patched fields are the support sheet
        x2 = XT(os.path.join(OUT, "files", "gamedata", "xt", "ui.bin"))
        for name, t, val, _ in x2.records():
            if name == "hud_objects":
                e = val["Elements"][el]
                assert e["name"] == names[el] and e["textures"][tex]["filename"].startswith("perk_sheet_support")
                assert abs(e["textures"][tex]["size"]["v"] - 0.09375) < 1e-6
                break

    os.makedirs(os.path.join(OUT, "preview"), exist_ok=True)
    for name, im in previews.items():
        im.save(os.path.join(OUT, "preview", name + "_1024.png"))
    print("ui_common.bpr: original", sha1(src_bpr), "-> new", sha1(new.b), f"({len(src_bpr)} -> {len(new.b)} bytes)")
    for name in SHEETS:
        print(f"   {name}: {bpr.raw(name)[0][8:]} {len(bpr.raw(name)[1])} B -> {new.raw(name)[0][8:]} "
              f"{len(new.raw(name)[1])} B, SHA-1 {sha1(new.raw(name)[1])}")
    print("all checks passed ->", OUT)


if __name__ == "__main__":
    main()
