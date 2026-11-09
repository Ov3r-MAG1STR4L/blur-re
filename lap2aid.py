#!/usr/bin/env python3
"""Driven lap -> AI track data (.aid), for levels that have none (Blur 2 cities).

Input: a trackrec.py CSV (t, x, y, z, kmh; game coordinates) of ONE clean lap, driven in the middle of the road.
The lap is resampled every SPACING m into Blur Map Builder road points {x, z, w, h} and handed to Map Builder's
own lap-track generator (flat_earth/gen_aid.build_loop: MainLoop, LOGIC, Start/InterOne/InterTwo gates).
Height comes from the lap (y). Width is one value for the whole lap (the trace says nothing about road edges).

usage: lap2aid.py LAP.csv OUT.aid [--width 24] [--self-test REAL.aid]
--self-test REAL.aid: ignore LAP.csv, build the "lap" from the middle of REAL.aid's main loop, then report the
distance between the generated and the real main-loop centres (pipeline check, no driving needed).
"""
import argparse, csv, math, os, sys

MB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "bmb_game", "map_builder")
sys.path[:0] = [MB, os.path.join(MB, "flat_earth"), os.path.join(MB, "aid")]
import gen_aid, road  # noqa: E402  (Blur Map Builder by MDPRO, MIT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import blurroute  # noqa: E402

TEMPLATE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "blur_extracted", "gamedata", "gamedata",
                        "levels", "jpn_mharuna", "jpn_mharuna_1.aid")
SPACING = 20.0


def read_lap(path):
    with open(path, newline="") as f:
        return [(float(r["x"]), float(r["y"]), float(r["z"])) for r in csv.DictReader(f)]


def resample(pts, step):
    """points every `step` m along the polyline (x, y, z); the lap's end is dropped if it overlaps its start"""
    out, carry = [pts[0]], 0.0
    for a, b in zip(pts, pts[1:]):
        seg = math.hypot(b[0] - a[0], b[2] - a[2])
        d = step - carry
        while d <= seg:
            t = d / seg
            out.append(tuple(a[k] + (b[k] - a[k]) * t for k in range(3)))
            d += step
        carry = (carry + seg) % step
    if len(out) > 2 and math.hypot(out[-1][0] - out[0][0], out[-1][2] - out[0][2]) < step:
        out.pop()
    return out


def build(lap, width):
    pts = resample(lap, SPACING)
    y0 = min(p[1] for p in pts)
    rd = road.Road([{"x": x, "z": z, "w": width, "h": y - y0} for x, y, z in pts], width=width,
                   auto_bridges=False, closed=True)
    gen_aid.TEMPLATE = TEMPLATE
    return gen_aid.build_loop(rd, y0)


def main_centres(data):
    """(x, y, z) of the middle of the road at every main-loop node"""
    d = blurroute.parse(data)
    main = next(s for s in d["sections"] if s["type"] & 1 and not s["type"] & 0x20)
    return [(n["x"] + n["lateral"][0] * n["width"] / 2, n["y"], n["z"] + n["lateral"][1] * n["width"] / 2)
            for n in main["nodes"]]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("lap"), ap.add_argument("out")
    ap.add_argument("--width", type=float, default=24.0)
    ap.add_argument("--self-test", metavar="REAL_AID")
    a = ap.parse_args()
    real = main_centres(open(a.self_test, "rb").read()) if a.self_test else None
    data, info = build(real or read_lap(a.lap), a.width)
    open(a.out, "wb").write(data)
    print("written", a.out, len(data), "bytes,", info["points"], "points")
    if real:
        gen = main_centres(data)
        err = sorted(min(math.hypot(gx - rx, gz - rz) for rx, _, rz in real) for gx, _, gz in gen)
        print("self-test: generated centre to nearest real centre, median %.2f m, 95%% %.2f m, max %.2f m"
              % (err[len(err) // 2], err[int(len(err) * .95)], err[-1]))
        assert err[len(err) // 2] < 2.0, "generated line does not follow the real one"


if __name__ == "__main__":
    main()
