#!/usr/bin/env python3
"""Read-only recorder: positions every DT s to a CSV, until Ctrl+C / SECS. Re-attaches if the game restarts.
  default: the player only           -> t, x, y, z, kmh
  --all:   every car of the race      -> t, car, player (1/0), x, y, z, kmh
Used to map the drivable ground (driving over it) and to compare AI pace between two races.
usage: trackrec.py OUT.csv [SECS] [--all]
"""
import math, sys, time
import pymem

DT = 0.25


def attach():
    """Blur.exe process, or None; re-attaching matters: the game is often restarted during a recording."""
    try:
        return pymem.Pymem("Blur.exe")
    except Exception:
        return None


def main(out, secs=900, every=False):
    pm = attach()
    t0 = time.time()
    with open(out, "w") as o:
        o.write("t,car,player,x,y,z,kmh\n" if every else "t,x,y,z,kmh\n")
        while time.time() - t0 < secs:
            try:
                u, f = pm.read_uint, pm.read_float           # AttributeError if not attached yet
                R = u(u(u(u(0x11AA04C) + 0xC90) + 0x30) + 0xA10)
                me = pm.read_uchar(R + 0x2EC)
                cars = range(u(R + 0x1A0)) if every else [me]
                t = time.time() - t0
                rows = []
                for i in cars:
                    v = u(R + 0x68 + i * 0x10)
                    x, y, z, vx, vy, vz = (f(v + a) for a in (0x130, 0x134, 0x138, 0x13C, 0x140, 0x144))
                    kmh = math.sqrt(vx * vx + vy * vy + vz * vz) * 3.6
                    rows.append(f"{t:.2f},{i},{int(i == me)},{x:.2f},{y:.2f},{z:.2f},{kmh:.1f}\n" if every
                                else f"{t:.2f},{x:.2f},{y:.2f},{z:.2f},{kmh:.1f}\n")
                o.write("".join(rows))
                o.flush()
            except Exception:                      # menus / loading: no vehicle; game closed: re-attach
                new = attach()
                if new is not None and (pm is None or new.process_id != pm.process_id):
                    print(f"{time.time() - t0:.0f}s : attaché à Blur.exe pid {new.process_id}", flush=True)
                    pm = new
            time.sleep(DT)


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if a != "--all"]
    main(args[0], float(args[1]) if len(args) > 1 else 900, "--all" in sys.argv)
