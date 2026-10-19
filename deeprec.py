#!/usr/bin/env python3
"""Read-only: record every vehicle + racer + physics object AND every object they point to (depth 1).

usage: deeprec.py [secs]  -> rec_deep.npz
  blocks[k] = (car, source, srcOffset, addr, size) ; data[sample, blockOffset...] = raw bytes
  source: 'veh' (0x2000), 'rac' (0x800), 'phy' (0x800) or 'veh+0xNN' etc. for depth-1 targets (0x200)
Waits until the game is unpaused (Blur pauses when unfocused).
"""
import struct, sys, time
import numpy as np
import pymem
from blur_live import chain, vehicles

pm = pymem.Pymem("Blur.exe")


def rd(a, n):                                         # zero-padded past the end of a region
    out = b""
    while len(out) < n:
        try:
            out += pm.read_bytes(a + len(out), 0x100)
        except Exception:
            break
    return out[:n].ljust(n, b"\0")


vs = vehicles(pm, chain(pm))
rv, rn = pm.read_uint(0x1134DCC), pm.read_uint(0x1134DD4)
rac = {pm.read_uint(pm.read_uint(rv + 4 * k) + 0xC): pm.read_uint(rv + 4 * k) for k in range(rn)}
blocks = []
for c, v in enumerate(vs):
    roots = [("veh", v, 0x2000), ("rac", rac.get(v, 0), 0x800), ("phy", pm.read_uint(v + 0x238), 0x800)]
    seen = set()
    for name, a, n in roots:
        if not a:
            continue
        blocks.append((c, name, 0, a, n))
        b = rd(a, n)
        for o in range(0, n, 4):
            p = struct.unpack_from("<I", b, o)[0]
            if 0x1000000 < p < 0x7FFF0000 and p % 4 == 0 and p not in seen and p not in (v,):
                try:
                    pm.read_bytes(p, 0x100)
                except Exception:
                    continue
                seen.add(p)
                blocks.append((c, name, o, p, 0x200))
print(len(blocks), "blocks,", sum(b[4] for b in blocks) // 1024, "KiB per sample")

snap = lambda: b"".join(rd(a, n) for _, _, _, a, n in blocks)
secs = float(sys.argv[1]) if len(sys.argv) > 1 else 40
ref, t0 = pm.read_bytes(vs[0], 0x200), time.time()
while pm.read_bytes(vs[0], 0x200) == ref:             # wait for unpause
    if time.time() - t0 > 180:
        raise SystemExit("game still paused?")
    time.sleep(0.05)
T, D, t0 = [], [], time.time()
while time.time() - t0 < secs:
    T.append(time.time() - t0)
    D.append(np.frombuffer(snap(), np.uint8))
np.savez_compressed("rec_deep.npz", t=np.array(T), d=np.array(D),
                    blocks=np.array([(c, ["veh", "rac", "phy"].index(s), o, a, n) for c, s, o, a, n in blocks]))
print("recorded", len(T), "samples ->rec_deep.npz")
