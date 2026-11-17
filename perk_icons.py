#!/usr/bin/env python3
"""Contact sheet of the power-up HUD icons (2026-11-17, read only).

The HUD gadgets (ui.bin `hud_objects`: Perks_MainHUD, Perks_MainAttached, ai_perks) cut their icon in a vertical
strip: V = pos.v + size.v * index, size.v = 96 px / texture height. Index < 100 -> perk_sheet (+ _inverted),
index >= 100 -> perk_sheet_support (+ _inverted), index - 100 (UIPerks::Render, UIPerks2::Render).
Each icon is shown as stored (grey) and tinted by its colour_fill (ui.bin PerkDisplayParameters).

usage: perk_icons.py [OUT.png]   (default: blur_extracted\\hud_icons\\perk_icons_sheet.png, outside the repo)
"""
import json, os, sys
from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from blurbpr import Bpr  # noqa: E402

EXT = r"C:\Users\sanqu\Jeux_WII\blur_extracted"
BPR = os.path.join(EXT, r"root\ui\data\ui_common.bpr")
UI = os.path.join(EXT, r"xt_json\ui.json")
CELL = 96                                   # strip height in pixels (size.v 0.09375 x 1024 = 0.1875 x 512)


def cell(img, k):
    return img.crop((0, k * CELL, img.width, (k + 1) * CELL))


def tint(im, rgb):
    """multiply the grey icon by the fill colour, as the HUD sprite colour does"""
    r, g, b, a = im.split()
    return Image.merge("RGBA", [c.point(lambda v, f=f: int(v * f)) for c, f in zip((r, g, b), rgb)] + [a])


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(EXT, r"hud_icons\perk_icons_sheet.png")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    ui = json.load(open(UI))
    colours = {k: v["top_left"] for k, v in ui["UISpriteColours"].items()}
    perks = ui["UiXtConfig"]["#187"]["PerkDisplayParameters"]
    bpr = Bpr(BPR)
    sheets = {s: bpr.image(s).convert("RGBA") for s in
              ("perk_sheet", "perk_sheet_inverted", "perk_sheet_support", "perk_sheet_support_inverted")}
    rows = sorted(perks.items(), key=lambda kv: kv[1]["texture_index"])
    W, H = 128, CELL
    sheet = Image.new("RGBA", (W * 3 + 330, H * len(rows)), (24, 24, 30, 255))
    d = ImageDraw.Draw(sheet)
    for y, (name, p) in enumerate(rows):
        i = p["texture_index"]
        base, k = ("perk_sheet", i) if i < 100 else ("perk_sheet_support", i - 100)
        ico, inv = cell(sheets[base], k), cell(sheets[base + "_inverted"], k)
        fill = p["colour_fill"]
        rgb = ([int(x) / 255 for x in fill[1:].split()[:3]] if fill.startswith("!")
               else [colours[fill][c] for c in "rgb"] if fill in colours else [1, 1, 1])
        for x, im in enumerate((ico, inv, tint(ico, rgb))):
            sheet.alpha_composite(im, (x * W, y * H))
        d.text((W * 3 + 10, y * H + 20), f"index {i}  ->  {base}[{k}]", fill=(255, 255, 255, 255))
        d.text((W * 3 + 10, y * H + 40), f"{name}  ({fill})", fill=(200, 200, 200, 255))
        d.text((W * 3 + 10, y * H + 60), f"v = {k * CELL}..{(k + 1) * CELL} px", fill=(160, 160, 160, 255))
    sheet.save(out)
    print("saved", out)


if __name__ == "__main__":
    main()
