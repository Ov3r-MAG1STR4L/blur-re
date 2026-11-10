#!/usr/bin/env python3
"""Checks of blurmesh on real Blur models (read only: originals are never written).
python test_blurmesh.py [MODELS_DIR]   (default: Blur_test/models)"""
import contextlib
import glob
import io
import os
import struct
import sys
import tempfile

import blurmesh as bm

ROOT = sys.argv[1] if len(sys.argv) > 1 else r"C:/Users/sanqu/Jeux_WII/Blur_test/models"


def load(name):
    return open(glob.glob(ROOT + "/**/" + name + ".model", recursive=True)[0], "rb").read()


def addon_streams(d):
    """(start, count, stride) of each vertex stream by the Blender add-on, or None when it cannot read the file"""
    sys.path[:0] = [r"C:/Users/sanqu/Jeux_WII/bmb_game/map_builder/model", r"C:/Users/sanqu/Jeux_WII/bmb_game/map_builder"]
    os.environ.setdefault("BMB_GAME", r"C:/Users/sanqu/Jeux_WII/bmb_game")
    os.environ.setdefault("BMB_INSTALLED", "1")
    import cpmodel
    f = tempfile.NamedTemporaryFile(delete=False, suffix=".model")
    f.write(d)
    f.close()
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            M = cpmodel._reader().read_cpmodel_data(None, f.name)
        return [(s["start"], s["count"], s["bytes"]) for s in M["vertex_streams"]]
    except Exception:
        return None
    finally:
        os.unlink(f.name)


def test_layouts():
    """1-2: single and multi stream models, with and without colour (4)"""
    expect = {"nfs_004": [(20, False)], "arrowa": [(20, False)], "directionsigna": [(24, True)],
              "bargehit1": [(24, True)], "mur_10": [(20, False), (24, False)],
              "traffic_cone_hviz": [(24, False), (20, False), (24, False)],
              "n01": [(60, False), (20, False)]}
    for name, want in expect.items():
        m = bm.read(load(name))
        got = [(s["stride"], bm.colour_offset(s) is not None) for s in m["vertex_streams"]]
        assert got == want, (name, got)
    m = bm.read(load("audi_r8v10_stock"))
    assert len(m["vertex_streams"]) == 10 and len(m["face_streams"]) == 2
    print("layouts OK")


def test_against_addon():
    """3: same stream offsets, counts and strides as the add-on wherever the add-on can read the file"""
    n = 0
    for name in ["nfs_004", "arrowa", "mur_10", "barrier2", "bargehit1", "audi_r8v10_stock", "hack_postbox02",
                 "igm_japan_minor6", "destructionmodecolumn_blue", "mineblastimplode"]:
        d = load(name)
        ref = addon_streams(d)
        if ref is None:
            continue
        mine = [(s["start"], s["count"], s["stride"]) for s in bm.read(d)["vertex_streams"]]
        assert mine == ref, (name, mine, ref)
        n += 1
    assert n >= 8, n
    print("add-on agreement OK on", n, "models")


def test_positions():
    """3: decoded positions are finite and inside a sane range (catches a wrong data start)"""
    for name in ["directionsigna", "mur_10", "n01", "traffic_cone_hviz", "nfs_004"]:
        d = load(name)
        for s in bm.read(d)["vertex_streams"]:
            if s["elements"][0]["type"] != 6:
                continue
            for i in range(0, s["count"], max(1, s["count"] // 50)):
                p = struct.unpack_from("<3f", d, s["start"] + i * s["stride"])
                assert all(abs(c) < 1e5 for c in p), (name, i, p)
    print("positions OK")


def test_round_trip():
    """4: change one colour, re-read: only those 4 bytes differ, structure and other vertex data identical"""
    d = load("directionsigna")
    s = bm.read(d)["vertex_streams"][0]
    before = bm.colours(d, s)
    out = bm.set_colours(d, s, {7: (12, 34, 56, 78)})
    diff = [k for k in range(len(d)) if d[k] != out[k]]
    o = s["start"] + 7 * s["stride"] + bm.colour_offset(s)
    assert diff and set(diff) <= set(range(o, o + 4)), diff
    s2 = bm.read(out)["vertex_streams"][0]
    assert s2 == s
    after = bm.colours(out, s2)
    assert after[7] == (12, 34, 56, 78) and after[:7] + after[8:] == before[:7] + before[8:]
    assert bm.set_colours(out, s2, {7: before[7]}) == d          # and back to the original bytes
    for bad in ({s["count"]: (0, 0, 0, 0)}, {0: (256, 0, 0, 0)}, {0: (1, 2, 3)}):
        try:
            bm.set_colours(d, s, bad)
            raise AssertionError("accepted %r" % bad)
        except (IndexError, ValueError, AssertionError) as e:
            assert "accepted" not in str(e), e
    try:
        bm.colours(load("nfs_004"), bm.read(load("nfs_004"))["vertex_streams"][0])
        raise AssertionError("colour read on a stream without colour")
    except ValueError:
        pass
    print("round trip OK")


if __name__ == "__main__":
    test_layouts()
    test_positions()
    test_round_trip()
    test_against_addon()
