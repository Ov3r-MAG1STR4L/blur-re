#!/usr/bin/env python3
"""Read-only recorder: player position every DT s to a CSV (t, x, y, z, speed km/h), until Ctrl+C / SECS.
Used to map the drivable ground (e.g. the run-off past a finish line) by driving over it.
usage: trackrec.py OUT.csv [SECS]
"""
import math, sys, time
import pymem

DT = 0.25


def main(out, secs=900):
    pm = pymem.Pymem("Blur.exe")
    u, f = pm.read_uint, pm.read_float
    t0 = time.time()
    with open(out, "w") as o:
        o.write("t,x,y,z,kmh\n")
        while time.time() - t0 < secs:
            try:
                R = u(u(u(u(0x11AA04C) + 0xC90) + 0x30) + 0xA10)
                v = u(R + 0x68 + pm.read_uchar(R + 0x2EC) * 0x10)
                x, y, z, vx, vy, vz = (f(v + a) for a in (0x130, 0x134, 0x138, 0x13C, 0x140, 0x144))
                o.write(f"{time.time() - t0:.2f},{x:.2f},{y:.2f},{z:.2f},{math.sqrt(vx*vx+vy*vy+vz*vz)*3.6:.1f}\n")
                o.flush()
            except Exception:                      # menus / loading: no vehicle
                pass
            time.sleep(DT)


if __name__ == "__main__":
    main(sys.argv[1], float(sys.argv[2]) if len(sys.argv) > 2 else 900)
