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


def test_add_colour():
    """stride 20 -> 24 on the project J template: geometry, faces, textures unchanged, sizes and offsets coherent,
    both readers agree, build() with colours round-trips them, build() without colours unchanged (HEAD copy)"""
    import importlib.util
    import blurmodel_write as W
    t = open(W.os.path.join(W.config.BLUR_EXTRACTED, "nfs_models", "sign_wetfloor.model"), "rb").read()
    c = W.add_colour(t)
    a, b = bm.read(t), bm.read(c)
    s0, s1 = a["vertex_streams"][0], b["vertex_streams"][0]
    assert (s1["stride"], s1["count"], bm.colour_offset(s1)) == (24, s0["count"], 20)
    assert set(bm.colours(c, s1)) == {(255, 255, 255, 255)}
    for k in range(s0["count"]):
        assert t[s0["start"] + 20 * k:][:20] == c[s1["start"] + 24 * k:][:20]
    f0, f1 = a["face_streams"][0], b["face_streams"][0]
    assert t[f0["start"]:f0["start"] + f0["length"]] == c[f1["start"]:f1["start"] + f1["length"]]
    assert t.count(b"default_NB_NL_NV.fx") == 2 and c.count(b"default_NB_NL_NV.fx") == 0
    assert c.count(b"default_NB_NL.fx") == 2
    assert struct.unpack_from("<I", c, 0xC)[0] - struct.unpack_from("<I", t, 0xC)[0] == len(c) - len(t)
    tail = t[f0["start"] + f0["length"]:]                       # everything after the faces is unchanged
    assert c.endswith(tail[-2000:])
    V, I = W.cube()
    rgb = bytes(range(256)) * 48
    cols = [(k, 255 - k, 7 * k % 256, 200) for k in range(len(V))]
    out = W.build(c, V, I, rgb, 64, 64, colours=cols, pad_verts=40, pad_indices=60)
    s2 = bm.read(out)["vertex_streams"][0]
    assert (s2["stride"], s2["count"]) == (24, 40) and bm.colours(out, s2)[:len(V)] == cols
    spec = importlib.util.spec_from_file_location("bw_head", sys.argv[2] if len(sys.argv) > 2 else "")
    if spec:
        head = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(head)
        assert head.build(t, V, I, rgb, 64, 64) == W.build(t, V, I, rgb, 64, 64), "stride 20 output changed"
        print("build() without colours identical to HEAD")
    try:
        W.add_colour(c)
        raise AssertionError("colour added twice")
    except AssertionError as e:
        assert "twice" not in str(e)
    print("add_colour OK")


def test_stream_padding():
    """vertex and face streams: zeros before the data in 5..20, data aligned on 16 from the Scene section start.
    The rule (empirical) must hold on the original models and on every model our writer builds, colour or not,
    whatever the vertex count (the bug: 0 bytes, game crash at Blur.exe+0x2E380E)"""
    import blurmodel_write as W
    n = 0
    for p in sorted(glob.glob(ROOT + "/**/*.model", recursive=True))[::25]:
        if "flat_earth" in p:
            continue
        d = open(p, "rb").read()
        try:
            m = bm.read(d)
        except ValueError:
            continue
        sc = W.scene_start(d)
        for s in m["vertex_streams"] + m["face_streams"]:
            assert W.stream_pad(s["start"] - s["pad"] - sc) == s["pad"], (p, s["pad"])
            n += 1
    assert n > 50, n
    t = open(W.os.path.join(W.config.BLUR_EXTRACTED, "nfs_models", "sign_wetfloor.model"), "rb").read()
    c = W.add_colour(t)
    V, I = W.cube()
    rgb = bytes(64 * 64 * 3)
    for tpl, cols in ((t, None), (c, True)):
        for nv in range(len(V), len(V) + 16):        # every alignment of the header end
            out = W.build(tpl, V, I, rgb, 64, 64, pad_verts=nv, pad_indices=36 + 3 * (nv % 5),
                          colours=[(1, 2, 3, 4)] * len(V) if cols else None)
            sc = W.scene_start(out)
            m = bm.read(out)
            for s in m["vertex_streams"] + m["face_streams"]:
                assert 5 <= s["pad"] <= 20 and (s["start"] - sc) % 16 == 0, (nv, cols, s["pad"])
    for tag, d in (("template", t), ("colour template", c)):
        for s in bm.read(d)["vertex_streams"] + bm.read(d)["face_streams"]:
            assert 5 <= s["pad"] <= 20, (tag, s["pad"])
    print("stream padding OK (%d original streams, 32 builds)" % n)


if __name__ == "__main__":
    test_stream_padding()
    test_add_colour()
    test_layouts()
    test_positions()
    test_round_trip()
    test_against_addon()
