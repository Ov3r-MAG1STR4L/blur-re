#!/usr/bin/env python3
"""Read-only live inspector for Blur.exe (never writes game memory).

Static chain found in Blur.exe (Lua binding GetPlayerVehicleIndex -> 0xc31f30 -> 0xb824a0 -> 0x49b310):
    R = [[[[0x11AA04C] + 0xC90] + 0x30] + 0xA10]      race vehicle manager
    [R + 0x1A0]            vehicle count
    [R + 0x64 + i*0x10]    vehicle i handle, [R + 0x68 + i*0x10] vehicle i object
    byte [R + 0x2EC + p*2] vehicle index of local player p ([R + 0x2F4] = local player count)
Vehicle object (verified live 2026-10-18, player + 19 AI):
    +0x130/+0x134/+0x138   world position (m), Y up        (copies at +0xF0.., +0x1CC.., +0x5B0..)
    +0x13C/+0x140/+0x144   velocity vector (m/s), |v|*3.6 = km/h  (copy at +0x65C)
    +0xCC.. / +0x10C..     rotation matrix rows
    [+0x2A8]               -> RP_CarDynamics name string (racingphysics); AmaxVehicle = the one whose
                              (string can dangle: some cars show '?' -> identify by mass/physics instead)
                              'dynamics' ref is that name (some physics are shared, e.g. *_Shannon variants)
    [+0x238]               -> runtime physics object, +0x1D4 = mass (kg, matches racingphysics)
AI profiles (RaceDirectorSystem, CSV parser 0x4c5e20; event CSV = AIBalancingFileName):
    X = [[0x1134DC0] + 0x2C] (vtable 0xEC3B94); [X+0x48] -> car c entry ptr (c < [X+0x50]);
    always 20 entries (one per CSV column, col 0 = player) even with fewer cars on track
    entry = {stages ptr, cap, n}; stage k = stages + k*0x20 (one per CSV block):
        +0 i32, +4 f32 (CSV row 0,400,3,5..), +8 f32 (row 1,0.95,0.91..), +0x10 i32 (row 1,1,0..), +0x18 AIPerkSkillz hash, +0x1C AIPerkPrefs hash
    loaded profile lists: [0x1134E9C] x [0x1134EA4] AIPerkSkillz, [0x1134E84] x [0x1134E8C] AIPerkPrefs;
        record +0x10 name ptr, +0x14 hash, +0x18 Index, then the xt fields.
Race positions object 0x12260A8 (GetVehiclePosition -> 0xbbd420) read as empty: NOT verified.
    (20 slots stride 0xD4 from +0x10C8: byte position, byte vehicleIndex)

usage:
    blur_live.py                  list vehicles (player marked)
    blur_live.py record [i] 0 [secs]  wait for unpause, sample 0x2000 B every 0.1 s -> rec_<i>.bin
    blur_live.py diff [i] [secs]  snapshot vehicle i (default player) twice, print changed floats
    blur_live.py dump [i] [size]  float/pointer dump of vehicle i
"""
import struct, sys, time
import pymem


def chain(pm):
    p = pm.read_uint(0x11AA04C)
    for off in (0xC90, 0x30, 0xA10):
        if not p:
            return None
        p = pm.read_uint(p + off)
    return p or None


def vehicles(pm, R):
    n = pm.read_uint(R + 0x1A0)
    if not 0 < n <= 20:
        raise SystemExit(f"vehicle count {n} looks wrong (not in a race?)")
    return [pm.read_uint(R + 0x68 + i * 0x10) for i in range(n)]


def profiles(pm, arr, cnt):
    out = {}
    base = pm.read_uint(arr)
    for k in range(pm.read_uint(cnt)):
        r = pm.read_uint(base + 4 * k)
        out[pm.read_uint(r + 0x14)] = cstr(pm, pm.read_uint(r + 0x10))
    return out


def ai_stages(pm):
    """car index -> list of (gap, f4, f8, i10, PerkSkillz name, PerkPrefs name)"""
    sk, pp = profiles(pm, 0x1134E9C, 0x1134EA4), profiles(pm, 0x1134E84, 0x1134E8C)
    x = pm.read_uint(pm.read_uint(0x1134DC0) + 0x2C)
    vec, n = pm.read_uint(x + 0x48), pm.read_uint(x + 0x50)
    out = []
    for c in range(n):
        st, _, ns = struct.unpack("<3I", pm.read_bytes(pm.read_uint(vec + 4 * c), 12))
        rows = []
        for k in range(ns):
            g, f4, f8, _, i10, _, h1, h2 = struct.unpack("<iffIiIII", pm.read_bytes(st + k * 0x20, 0x20))
            rows.append((g, f4, f8, i10, sk.get(h1, hex(h1)), pp.get(h2, hex(h2))))
        out.append(rows)
    return out


def cstr(pm, a):
    b = pm.read_bytes(a, 64)
    z = b[:b.index(b"\0")] if b"\0" in b else b""
    return z.decode("ascii") if z and all(32 <= c < 127 for c in z) else "?"


def floats(buf):
    return [(o, struct.unpack_from("<f", buf, o)[0]) for o in range(0, len(buf) - 3, 4)]


def main():
    pm = pymem.Pymem("Blur.exe")
    R = chain(pm)
    if not R:
        raise SystemExit("chain is null: start a race first")
    vs = vehicles(pm, R)
    player = pm.read_bytes(R + 0x2EC, 1)[0]
    cmd = sys.argv[1] if len(sys.argv) > 1 else "list"
    i = int(sys.argv[2]) if len(sys.argv) > 2 else player
    if cmd == "list":
        print(f"R={R:#x}  vehicles={len(vs)}  player vehicle index={player}")
        try:
            ai = ai_stages(pm)
        except Exception:
            ai = []
        for k, v in enumerate(vs):
            x, y, z, vx, vy, vz = struct.unpack("<6f", pm.read_bytes(v + 0x130, 24))
            kmh = (vx * vx + vy * vy + vz * vz) ** 0.5 * 3.6
            car = cstr(pm, pm.read_uint(v + 0x2A8))
            mass = struct.unpack("<f", pm.read_bytes(pm.read_uint(v + 0x238) + 0x1D4, 4))[0]
            print(f"  [{k:2}] {v:#010x}  {car:34} {mass:6.0f} kg  xyz=({x:8.1f},{y:6.1f},{z:8.1f})"
                  f"  {kmh:6.1f} km/h{'  <== PLAYER' if k == player else ''}")
            if k < len(ai) and ai[k]:
                g, f4, f8, i10, skz, prf = ai[k][0]
                print(f"         AI stage0: {skz} / {prf}  (+0 {g}, +4 {f4:g}, +8 {f8:g}, +0x10 {i10})")
    elif cmd == "dump":
        size = int(sys.argv[3], 0) if len(sys.argv) > 3 else 0x400
        b = pm.read_bytes(vs[i], size)
        for o in range(0, size, 16):
            w = struct.unpack_from("<4I", b, o)
            f = struct.unpack_from("<4f", b, o)
            print(f"+{o:04x}  " + "  ".join(f"{x:08x}" for x in w) + "   " +
                  "  ".join(f"{y:10.3f}" if 1e-4 < abs(y) < 1e6 else "         ." for y in f))
    elif cmd == "record":                             # record [i] [wait] [secs] -> rec_<i>.bin (game pauses when unfocused)
        wait = float(sys.argv[3]) if len(sys.argv) > 3 else 10
        secs = float(sys.argv[4]) if len(sys.argv) > 4 else 10
        ref = pm.read_bytes(vs[i], 0x2000)
        t0 = time.time()
        while pm.read_bytes(vs[i], 0x2000) == ref:     # wait until the game is unpaused (object changes)
            if time.time() - t0 > 120 + wait:
                raise SystemExit("object never changed: game still paused?")
            time.sleep(0.05)
        with open(f"rec_{i}.bin", "wb") as f:
            t0 = time.time()
            while time.time() - t0 < secs:
                f.write(struct.pack("<d", time.time() - t0) + pm.read_bytes(vs[i], 0x2000))
                time.sleep(0.1)
        print("recorded", f"rec_{i}.bin")
    elif cmd == "recall":                             # recall [secs] -> rec_all.npz: every vehicle + its racer object
        import numpy as np
        secs = float(sys.argv[2]) if len(sys.argv) > 2 else 30
        rv, rn = pm.read_uint(0x1134DCC), pm.read_uint(0x1134DD4)
        racers = {pm.read_uint(pm.read_uint(rv + 4 * k) + 0xC): pm.read_uint(rv + 4 * k) for k in range(rn)}
        rac = [racers.get(v, 0) for v in vs]
        x = pm.read_uint(pm.read_uint(0x1134DC0) + 0x2C)
        def safe(a, n):                               # pad with zeros past the end of a region
            out = b""
            while len(out) < n:
                try:
                    out += pm.read_bytes(a + len(out), 0x100)
                except Exception:
                    break
            return out[:n].ljust(n, b"\0")
        snap = lambda: (b"".join(pm.read_bytes(v, 0x2000) + (safe(r, 0x800) if r else bytes(0x800))
                                 for v, r in zip(vs, rac)) + pm.read_bytes(x, 0x400))
        ref, t0 = snap(), time.time()
        while snap() == ref:                          # game pauses while unfocused
            if time.time() - t0 > 180:
                raise SystemExit("game still paused?")
            time.sleep(0.05)
        T, S, t0 = [], [], time.time()
        while time.time() - t0 < secs:
            T.append(time.time() - t0); S.append(np.frombuffer(snap(), np.uint8)); time.sleep(0.1)
        np.savez_compressed("rec_all.npz", t=np.array(T), s=np.array(S), vs=np.array(vs), rac=np.array(rac), x=x)
        print("recorded", len(T), "samples ->rec_all.npz; per vehicle 0x2000 veh + 0x800 racer, then 0x400 X")
    elif cmd == "diff":
        secs = float(sys.argv[3]) if len(sys.argv) > 3 else 1.0
        size = 0x2000
        a = pm.read_bytes(vs[i], size); time.sleep(secs); b = pm.read_bytes(vs[i], size)
        for (o, x), (_, y) in zip(floats(a), floats(b)):
            if x != y and all(1e-4 < abs(z) < 1e6 for z in (x, y)):
                print(f"+{o:04x}  {x:12.4f} -> {y:12.4f}")


if __name__ == "__main__":
    main()
