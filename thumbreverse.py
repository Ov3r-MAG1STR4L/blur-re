#!/usr/bin/env python3
"""Route picture for a reversed route: the original picture + a Blur-style neon U-turn sign.

The menu shows the left ~330 px of the 512x256 picture; the sign sits in its bottom left corner.
usage: thumbreverse.py IN.png OUT.png
"""
import sys
from PIL import Image, ImageDraw, ImageFilter

GLOW = (40, 200, 255)          # Blur UI blue
SIGN_BOX = (14, 158, 94, 238)  # x0, y0, x1, y1 in the 512x256 picture: bottom LEFT (asked 2026-10-19)
SS = 4                         # supersampling


def sign(size):
    """RGBA U-turn arrow (hairpin, like the road), white core + blue glow."""
    s = size * SS
    layer = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    w = int(s * 0.11)
    r = int(s * 0.22)
    cx, top = s // 2, int(s * 0.18)
    left, right = cx - r, cx + r
    bottom = int(s * 0.86)
    # hairpin: up the left leg, round the top, down the right leg to the arrow head
    d.line([(left, bottom), (left, top + r)], fill="white", width=w)
    d.arc([left - w // 2 + w // 2 - r + r, top, right, top + 2 * r], 180, 360, fill="white", width=w)
    d.line([(right, top + r), (right, bottom - int(s * 0.16))], fill="white", width=w)
    h = int(s * 0.19)
    tip = bottom
    d.polygon([(right - h, tip - h), (right + h, tip - h), (right, tip)], fill="white")
    core = layer.resize((size, size), Image.LANCZOS)
    a = core.getchannel("A")
    glow = Image.new("RGBA", core.size, GLOW + (0,))
    glow.putalpha(a.filter(ImageFilter.GaussianBlur(size * 0.06)).point(lambda v: min(255, v * 3)))
    tint = Image.new("RGBA", core.size, (190, 240, 255, 0))
    tint.putalpha(a)
    out = Image.new("RGBA", core.size, (0, 0, 0, 0))
    out.alpha_composite(glow)
    out.alpha_composite(glow)
    out.alpha_composite(tint)
    return out


def make(src, dst=None):
    im = src.convert("RGBA")
    x0, y0, x1, y1 = SIGN_BOX
    size = min(x1 - x0, y1 - y0)
    disc = Image.new("RGBA", im.size, (0, 0, 0, 0))     # dark halo so the sign reads on any picture
    ImageDraw.Draw(disc).ellipse([x0 - 4, y0 - 4, x0 + size + 4, y0 + size + 4], fill=(0, 10, 25, 150))
    im.alpha_composite(disc.filter(ImageFilter.GaussianBlur(6)))
    im.alpha_composite(sign(size), (x0, y0))
    im = im.convert("RGB")
    if dst:
        im.save(dst)
    return im


if __name__ == "__main__":
    make(Image.open(sys.argv[1]), sys.argv[2])
