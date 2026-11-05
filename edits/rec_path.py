"""Record the player's path (read only): waits for a race, starts when the car moves, stops after 10 s still."""
import json, math, struct, sys, time
sys.path.insert(0, r"C:\Users\sanqu\Jeux_WII\blur_tools")
import pymem, blur_live as L
out = sys.argv[1]
while True:
    try:
        pm = pymem.Pymem("Blur.exe"); R = L.chain(pm)
        if R and 0 < pm.read_uint(R + 0x1A0) <= 20: break
    except Exception: pass
    time.sleep(1)
print("race found", flush=True)
def pos():
    try:                                  # None while a race loads / restarts (chain or vehicle list empty)
        R = L.chain(pm); v = L.vehicles(pm, R)[pm.read_bytes(R + 0x2EC, 1)[0]]
        return struct.unpack("<3f", pm.read_bytes(v + 0x130, 12))
    except BaseException:
        return None
p0 = None; pts = []; still = None
while True:
    p = pos()
    if p is None or p0 is None:
        p0 = p; time.sleep(0.2); continue
    if not pts:
        if math.dist(p, p0) > 1: pts.append(p); print("recording", flush=True)
    else:
        if math.dist(p, pts[-1]) > 1.5: pts.append(p); still = None
        else:
            still = still or time.time()
            if time.time() - still > 10: break
    time.sleep(0.1)
json.dump([[round(c, 2) for c in q] for q in pts], open(out, "w"))
print(len(pts), "points,", round(sum(math.dist(a, b) for a, b in zip(pts, pts[1:])), 1), "m", flush=True)
