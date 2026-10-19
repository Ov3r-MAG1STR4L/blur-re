"""Probe the structure of the loc-key hash using (key, hash) pairs from all .loc files."""
import glob, struct, collections, sys
sys.path.insert(0, r"C:\Users\sanqu\Jeux_WII\blur_tools")

pairs = {}
for f in glob.glob(r"C:\Users\sanqu\Jeux_WII\blur_extracted\gamedata\gamedata\xt\loc\*.loc"):
    b = open(f, "rb").read()
    nlang = struct.unpack_from("<I", b, 0x14)[0]
    kb = 0x1C + 24 * nlang
    cnt, es = struct.unpack_from("<II", b, kb)
    for i in range(cnt):
        h, off = struct.unpack_from("<II", b, kb + 8 + 8 * i)
        o = kb + off
        pairs[b[o:b.index(b"\0", o)]] = h
print(len(pairs), "keys")

# group by (prefix without last char)
g = collections.defaultdict(list)
for k, h in pairs.items():
    g[k[:-1]].append((k[-1], h))
xor_map = collections.defaultdict(set)
sub_map = collections.defaultdict(set)
n = 0
for pre, lst in g.items():
    for i in range(len(lst)):
        for j in range(i + 1, len(lst)):
            (c1, h1), (c2, h2) = lst[i], lst[j]
            xor_map[c1 ^ c2].add(h1 ^ h2)
            sub_map[(c1 - c2) & 255].add((h1 - h2) & 0xffffffff)
            n += 1
print("pairs differing only in last char:", n)
print("xor-consistent (H depends only on c1^c2):", sum(1 for v in xor_map.values() if len(v) == 1), "/", len(xor_map))
print("sub-consistent:", sum(1 for v in sub_map.values() if len(v) == 1), "/", len(sub_map))
for d, v in list(xor_map.items())[:6]:
    print(d, len(v), [hex(x) for x in list(v)[:3]])
# case sensitivity: any keys equal ignoring case?
low = collections.Counter(k.lower() for k in pairs)
print("case-collisions:", sum(1 for v in low.values() if v > 1))
print("all upper-case keys:", sum(1 for k in pairs if k == k.upper()), "of", len(pairs))
