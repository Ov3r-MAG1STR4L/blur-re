#!/usr/bin/env python3
"""Read-only recorder of every car's speed and AI target ("track") speed, every DT s, until SECS / Ctrl+C.
Chain (2026-10-20, from the controls function 0x4C28F0): AI manager 0x1134D88, interface [+0x2C],
car array [I+0x4C] .. [I+0x50]; follower object = [[array + 4*i] + 0x10] + 8:
  +0x134 speed (m/s, = vehicle speed), +0x36C target speed (m/s; above it the brake check fires).
Car index i = trackrec.py car index (same order).
usage: aispeedrec.py OUT.csv [SECS]   -> t, car, player, x, z, kmh, target_kmh
"""
import sys, time
import pymem

DT = 0.1


def main(out, secs=1800):
    pm, t0, last = None, time.time(), ""
    with open(out, "w") as o:
        o.write("t,car,player,x,z,kmh,target_kmh\n")
        while time.time() - t0 < secs:
            try:
                u, f = pm.read_uint, pm.read_float          # AttributeError if not attached yet
                R = u(u(u(u(0x11AA04C) + 0xC90) + 0x30) + 0xA10)
                me = pm.read_uchar(R + 0x2EC)
                I = u(0x1134D88 + 0x2C)
                arr = u(I + 0x4C)
                t = time.time() - t0
                rows = []
                for i in range((u(I + 0x50) - arr) // 4):
                    ob, v = u(u(arr + 4 * i) + 0x10) + 8, u(R + 0x68 + i * 0x10)
                    rows.append(f"{t:.2f},{i},{int(i == me)},{f(v + 0x130):.1f},{f(v + 0x138):.1f},"
                                f"{f(ob + 0x134) * 3.6:.1f},{f(ob + 0x36C) * 3.6:.1f}\n")
                o.write("".join(rows))
                o.flush()
            except Exception as e:                         # menus / loading / game restarted: re-attach
                if str(e) != last:                         # a silent failure lost a whole race once
                    print(f"{time.time() - t0:.0f}s : {type(e).__name__} {e}", flush=True)
                    last = str(e)
                try:
                    pm = pymem.Pymem("Blur.exe")
                except Exception:
                    pm = None
            time.sleep(DT)


if __name__ == "__main__":
    main(sys.argv[1], float(sys.argv[2]) if len(sys.argv) > 2 else 1800)
