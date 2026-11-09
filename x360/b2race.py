"""Blur 2 X360 actorpack.xt: StartPosition / AILinkNode / AIRaceLine elements read straight from their chunks."""
import sys, struct, collections
import os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import blurxt_be as m
def read(path):
    x = m.XT(path); ts = x.types(); names = [x.name(t[0]) for t in ts]
    chunks = [struct.unpack('>3H', e) for e in x.section(6, 6)]
    d, p, c, out = x.data, 0, 0, collections.defaultdict(list)
    for idx, nch, ds, ss in x.items():
        strs = m.decode_names(d[p + ds:p + ds + ss]) if ss else b''
        o = p
        for t, n, z in chunks[c:c + nch]:
            esz = 4 if z else ts[t][5]
            if not z:
                for k in range(n): out[names[t]].append((d[o + k * esz:o + (k + 1) * esz], strs, idx, (len(out["#chunks"]), k)))
                out["#chunks"].append(names[t])
            o += esz * n
        c += nch; p += ds + ss
    return out
f = lambda b, o: struct.unpack_from('>f', b, o)[0]
def s8(strs, b, o):
    u = struct.unpack_from('>I', b, o)[0]
    return strs[u:strs.index(b'\0', u)].decode('latin-1') if u < len(strs) else ''
if __name__ == '__main__':
    r = read(sys.argv[2])
    st = [(s8(s, b, 4), struct.unpack_from('>i', b, 60)[0], f(b, 48), f(b, 52), f(b, 56)) for b, s, i, k in r['StartPosition']]
    print('StartPosition', len(st)); [print('  ', x[0], x[1], [round(v) for v in x[2:]]) for x in st[:8]]
    groups = collections.Counter(x[0].rsplit('_', 1)[0] if '_' in x[0] else x[0][:-2] for x in st); print('  groupes de noms', groups.most_common(10))
    ln = r['AILinkNode']; print('AILinkNode', len(ln), 'ex', [[round(f(b, o)) for o in (0, 4, 8)] + [round(f(b, o), 2) for o in (12, 16, 20)] for b, *_ in ln[:3]])
    rp = r['AIRaceLinePoint']; print('AIRaceLinePoint', len(rp), 'ex', [(struct.unpack_from('>I', b, 0)[0], round(f(b, 4)), round(f(b, 8), 1)) for b, *_ in rp[:5]])
    ra = r['AIRaceLineActor']; print('AIRaceLineActor', len(ra), [s8(s, b, 4) for b, s, i, k in ra])
