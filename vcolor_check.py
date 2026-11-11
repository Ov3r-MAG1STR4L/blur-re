"""Checks of the second vertex colour test before / after install (read only on the game copy)."""
import sys, os, struct, contextlib, io, hashlib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import blurmesh as bm, blurmodel_write as W, vcolor_scene as S
sys.path[:0] = [r"C:/Users/sanqu/Jeux_WII/bmb_game/map_builder/model"]
import cpmodel


def check(name, d, glow=None, n_colours=None):
    m = bm.read(d); sc = W.scene_start(d)
    s, f = m["vertex_streams"][0], m["face_streams"][0]
    assert 5 <= s["pad"] <= 20 and 5 <= f["pad"] <= 20 and (s["start"] - sc) % 16 == 0 and (f["start"] - sc) % 16 == 0, name
    assert s["stride"] == 24 and s["count"] == S.PAD[0] and f["count"] == S.PAD[1] and bm.colour_offset(s) == 20, name
    secs = W._sections(d)
    assert struct.unpack_from("<I", d, 0xC)[0] + 4 == len(d) - (len(d) - 4 - struct.unpack_from("<I", d, 0xC)[0]), name
    for lf, st, L in secs:                                     # every section inside the file and inside Model
        assert st + L <= len(d), (name, st, L)
    with contextlib.redirect_stdout(io.StringIO()):
        Q = cpmodel.parse(d)
    assert Q["stride"] == 24 and Q["vcount"] == S.PAD[0], name
    P = cpmodel.parse(d)
    moff, mw, mh, mm = P["textures"][W.MAT]
    if glow is not None:                                       # material texture = solid (0, glow, 0)
        assert d[moff:moff + 8] == cpmodel.encode_mips(cpmodel.solid(mw, mh, (0, glow, 0)), mw, mh, mm)[:8], name
    return s["pad"], f["pad"]


if __name__ == "__main__":
    out, best, labels, p, start, groups = S.build_all(sys.argv[1])
    sizes = {len(d) for d in out.values()}
    assert len(sizes) == 1, sizes
    for f, d in sorted(out.items()):
        pads = check(f, d, glow=groups.get(f, S.GLOW))
    ref = out[best]
    for f, g in groups.items():                                 # groups: same vertex data layout as the reference, scaled
        cg = bm.colours(out[f], bm.read(out[f])["vertex_streams"][0])
        cr = bm.colours(ref, bm.read(ref)["vertex_streams"][0])
        assert cg[:236] == cr[:236]
    print("%d models of %d bytes checked (pads %s), reference %s, groups %s" % (len(out), sizes.pop(), pads, best, groups))
