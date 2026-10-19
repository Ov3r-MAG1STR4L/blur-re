"""Read-only: BFS over pointers from a vehicle object, report paths that reach known record names."""
import json, struct, sys, pymem
from blur_live import chain, vehicles

J = "../blur_extracted/xt_json/"
names = {}
for fn, typ in [("amax", "AmaxVehicle"), ("racingphysics", "RP_CarDynamics"), ("air", None), ("finalracebook", None)]:
    d = json.load(open(J + fn + ".json", encoding="utf-8"))
    for t, recs in d.items():
        if typ and t != typ:
            continue
        for n in recs:
            names.setdefault(n.split(" (")[0].encode(), f"{fn}/{t}")

pm = pymem.Pymem("Blur.exe")
vs = vehicles(pm, chain(pm))
vi = int(sys.argv[1]) if len(sys.argv) > 1 else 0
depth_max = int(sys.argv[2]) if len(sys.argv) > 2 else 3
SPAN = 0x800

def rd(a, n):
    try:
        return pm.read_bytes(a, n)
    except Exception:
        return None

seen, frontier, hits = set(), [(vs[vi], ())], []
for depth in range(depth_max + 1):
    nxt = []
    for addr, path in frontier:
        if addr in seen:
            continue
        seen.add(addr)
        b = rd(addr, SPAN if depth == 0 else 0x200)
        if not b:
            continue
        for o in range(0, len(b) - 3, 4):
            p = struct.unpack_from("<I", b, o)[0]
            if not 0x10000 < p < 0x7FFF0000:
                continue
            s = rd(p, 64)
            if s and b"\0" in s:
                z = s[:s.index(b"\0")]
                if z in names:
                    hits.append((path + (o,), z.decode(), names[z]))
            if depth < depth_max:
                nxt.append((p, path + (o,)))
    frontier = nxt
for path, n, src in hits[:80]:
    print(" -> ".join(f"+{o:#x}" for o in path), n, src)
print(len(hits), "hits")
