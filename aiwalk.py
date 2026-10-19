"""Read-only: find AIPerkSkillz / AISkillz float blocks reachable from vehicle objects."""
import json, struct, sys, pymem
from blur_live import chain, vehicles

a = json.load(open("../blur_extracted/xt_json/air.json", encoding="utf-8"))
sig = {}
for n, v in a["AIPerkSkillz"].items():
    sig[struct.pack("<5f", *(v[k] for k in ("Racing", "Aggression", "Blocking", "Slamming", "Mistakes")))] = "PerkSkillz/" + n
for n, v in a["AISkillz"].items():
    p = v["SkillParams"]
    sig[struct.pack("<9f", *p.values())] = "Skillz/" + n
sig = {k: n for k, n in sig.items()
       if len({x for x in struct.unpack(f"<{len(k)//4}f", k) if x}) >= 3}   # zero-filled profiles match anything
pm = pymem.Pymem("Blur.exe")
vs = vehicles(pm, chain(pm))

def rd(x, n):
    try:
        return pm.read_bytes(x, n)
    except Exception:
        return None

for vi in map(int, sys.argv[1:] or ["1", "2"]):
    seen, front, found = set(), [(vs[vi], ())], []
    for depth in range(3):
        nxt = []
        for addr, path in front:
            if addr in seen:
                continue
            seen.add(addr)
            b = rd(addr, 0x2000 if depth == 0 else 0x400)
            if not b:
                continue
            for s, name in sig.items():
                k = b.find(s)
                if k >= 0:
                    found.append((path, k, name))
            for o in range(0, len(b) - 3, 4):
                p = struct.unpack_from("<I", b, o)[0]
                if 0x10000 < p < 0x7FFF0000 and depth < 2:
                    nxt.append((p, path + (o,)))
        front = nxt
    print(f"vehicle {vi}:")
    for path, k, name in found[:10]:
        print("   ", " -> ".join(f"+{o:#x}" for o in path), f"@+{k:#x}", name)
