#!/usr/bin/env python3
"""Driven lap -> AI track data (.aid), for levels that have none (Blur 2 cities).

Input: a trackrec.py CSV (t, x, y, z, kmh[, w]; game coordinates) of ONE clean lap, driven in the middle of the road,
starting on the start/finish line (the line is put at the lap's first point). Optional w = road width there.
The lap is resampled every SPACING m into Blur Map Builder road points {x, z, w, h} and handed to Map Builder's
own lap-track generator (flat_earth/gen_aid.build_loop: MainLoop, LOGIC, Start/InterOne/InterTwo gates).
Height comes from the lap (y). Width: the CSV's w column if present, else --width for the whole lap.

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
LOGIC_MARGIN = 8.0    # LOGIC band (cars outside are reset) = road + this much each side: real Brighton 1 LOGIC ~15 m wider than the road


def read_lap(path):
    with open(path, newline="") as f:
        return [(float(r["x"]), float(r["y"]), float(r["z"]), float(r["w"]) if r.get("w") else None)
                for r in csv.DictReader(f)]


def resample(pts, step):
    """points every `step` m along the polyline (x, y, z); the lap's end is dropped if it overlaps its start"""
    out, carry = [pts[0]], 0.0
    for a, b in zip(pts, pts[1:]):
        seg = math.hypot(b[0] - a[0], b[2] - a[2])
        d = step - carry
        while d <= seg:
            t = d / seg
            out.append(tuple(a[k] + (b[k] - a[k]) * t for k in range(3)) + (a[3],))
            d += step
        carry = (carry + seg) % step
    if len(out) > 2 and math.hypot(out[-1][0] - out[0][0], out[-1][2] - out[0][2]) < step:
        out.pop()
    return out


def build(lap, width):
    pts = resample(lap, SPACING)
    y0 = min(p[1] for p in pts)
    rd = road.Road([{"x": x, "z": z, "w": w or width, "h": y - y0} for x, y, z, w in pts], width=width,
                   auto_bridges=False, closed=True)
    gen_aid.TEMPLATE = TEMPLATE
    band = [(-w / 2 - LOGIC_MARGIN, w / 2 + LOGIC_MARGIN) for w in rd.width_at]
    orig = gen_aid.band_points

    def band_points(r, ranges=None):
        """Map Builder's band, but where its loop-free edges (road._unloop) squeezed a band narrower than asked
        (wide LOGIC band near a hairpin: 170 of 738 points on Brighton 1 -> players reset in a loop), rebuild it
        straight from the centre line: lo edge + full width, facing along the road"""
        out = orig(r, ranges)
        if ranges:
            for i, (lo, hi) in enumerate(ranges):
                if out[i][2] < (hi - lo) - 2.0:
                    (cx, cz), (sx, sz) = r.centre[i], r.side(i)
                    out[i] = (cx + sx * lo, cz + sz * lo, hi - lo, sz, -sx)
        return out
    gen_aid.band_points = band_points
    return gen_aid.build_loop(rd, y0, lines=(gen_aid.GATE_LEAD, gen_aid.GATE_LEAD), band=band)   # start = lap start


def main_centres(data):
    """(x, y, z) of the middle of the road at every main-loop node"""
    d = blurroute.parse(data)
    main = next(s for s in d["sections"] if s["type"] & 1 and not s["type"] & 0x20)
    return [(n["x"] + n["lateral"][0] * n["width"] / 2, n["y"], n["z"] + n["lateral"][1] * n["width"] / 2, n["width"])
            for n in main["nodes"]]


def lap_from_aid(data):
    """self-test 'lap': the real main loop's road middle + width, rotated to begin at the real Start gate"""
    d = blurroute.parse(data)
    pts = main_centres(data)
    s = next(s for s in d["sections"] if s["type"] & 2)["nodes"][0]
    i0 = min(range(len(pts)), key=lambda i: math.hypot(pts[i][0] - s["x"], pts[i][2] - s["z"]))
    return pts[i0:] + pts[:i0]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("lap"), ap.add_argument("out")
    ap.add_argument("--width", type=float, default=24.0)
    ap.add_argument("--self-test", metavar="REAL_AID")
    a = ap.parse_args()
    real = lap_from_aid(open(a.self_test, "rb").read()) if a.self_test else None
    data, info = build(real or read_lap(a.lap), a.width)
    open(a.out, "wb").write(data)
    print("written", a.out, len(data), "bytes,", info["points"], "points")
    if real:
        gen = main_centres(data)
        err = sorted(min(math.hypot(gx - rx, gz - rz) for rx, _, rz, _ in real) for gx, _, gz, _ in gen)
        st = [next(s for s in blurroute.parse(x)["sections"] if s["type"] & 2)["nodes"][0]
              for x in (data, open(a.self_test, "rb").read())]
        print("start gate: generated (%.0f, %.0f), real (%.0f, %.0f)" % (st[0]["x"], st[0]["z"], st[1]["x"], st[1]["z"]))
        print("widths: generated %.1f..%.1f m" % (min(g[3] for g in gen), max(g[3] for g in gen)))
        print("self-test: generated centre to nearest real centre, median %.2f m, 95%% %.2f m, max %.2f m"
              % (err[len(err) // 2], err[int(len(err) * .95)], err[-1]))
        assert err[len(err) // 2] < 2.0, "generated line does not follow the real one"


if __name__ == "__main__":
    main()
