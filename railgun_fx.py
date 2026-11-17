#!/usr/bin/env python3
"""Railgun visual effects: its own PickupLevel in pickups.bin (and two particle events in dynamiceffects.bin),
built from the game's own effects, reachable from the SuperShield PickupType's `Modified` slot. railgun.dll hands
this level to the railgun projectile (charge, firing flash, projectile, vehicle hit). Bolt, Shunt, Shock, Nitro
keep theirs: every record we change is a clone (new hashes above every existing one, appended in order).

- charge = clone of the Shunt charge (ShuntBuild2 model, camera shake) with the reverse Nitro blast rings in place
  of the screen effect, and a titanium white light instead of the red one;
- firing flash = the Bolt's, white;
- projectile = the Bolt's spiral (Blind_projectile_01) with a white light, a long white light trail (clone of the
  Bolt's RearLightTrail: 0.15 s -> TRAIL_LIFE, fading slowly) and a neon core trail
  (the user wanted a luminous neon line, not smoke: a second, thin and bright light trail) in place of the halo;
- vehicle hit = the Bolt's impact (Global) + the Shock's whole-car electric shell and sparks (External / Local),
  lights in white, HIT_TIME long.
usage: build(pickups_in, dyn_in, pickups_out, dyn_out) -> dict of what was made. Self-check: python railgun_fx.py
"""
import re, struct
from blurxt import XT
from kslfwrite import KSLF

TITANIUM = (0.91, 0.93, 0.96)
TRAIL_LIFE, TRAIL_SIZE, TRAIL_STEP = 2.5, 1.2, 0.75       # s, m, m between two particles
NEON_LIFE, NEON_SIZE, NEON_STEP, NEON_ALPHA = 2.5, 0.45, 0.2, 0.35   # thin bright core: a neon tube
CHARGE_SPEED = 0.5                            # charge animations (Shunt build, Nitro rings) played at half speed
HIT_TIME = 2.5
BASE = 0xFFFF2000                                          # above every hash of every Blur file (max 0xFFFE3216)

BOLT_LEVEL, SUPERSHIELD_TYPE = 0xDD8A965A, 0xB85C8D7A
PROJ, PROJ_LIGHT, PROJ_MESH, PROJ_INNER, PROJ_PART = 0xF6ABA9FE, 0x3521EF73, 0x1CE75F16, 0xCEAFD367, 0x2607B072
SHUNT_CHARGE, SHUNT_RED, NITRO_RINGS = 0x3B3B8C89, 0xD7F8C4E6, 0x6EF7CFB3
SHUNT_REV_CHARGE, REAR_BUILD_SPEED = 0x0E21E55E, 1.75   # ShuntBuildRev at 4.375 fits the Shunt's 0.2 s; ours 0.5 s
NULL_REF = 0xFFFFFFFF
FIRED, FIRED_LIGHT = 0xB965D104, 0x602C1239
SHOCK_EXT, SHOCK_LOCAL, SHOCK_LIGHTS = 0x79746C67, 0x2482A962, (0xFCDCEFDA, 0x6F4C6268, 0xF232D009)
TRAIL_EVENT, TRAIL_EFFECT = 0xC6DD8255, 0x0C399DBB


class Edit:
    """KSLF file + record numbers by hash + nested field offsets (paths as blurxt.XT.locate)."""

    def __init__(self, path):
        self.k = KSLF(path)
        self.next = None

    def slot(self, h):
        return next(i for i, e in enumerate(self.k.index) if e[0] == h)

    def rec(self, h):
        return self.k.index[self.slot(h)][2]          # record number (local item) of an own record

    def offset(self, k, path):
        """offset in the data of record k (or of any clone of it: clones are byte copies) of a nested field"""
        x = self.k.x
        for i, _ in enumerate(x.records()):
            if i == k:
                break
        t, o, fl = x._ch[0][0], x._ch[0][2], 3
        for seg in path.split("."):
            fname, i = re.fullmatch(r"(\w+)(?:\[(\d+)\])?", seg).groups()
            ft, fo, fl = x._field(t, fname)
            if fl & 0x100:
                ref, n = struct.unpack_from("<II", x._d, o + fo)
                assert i is not None and int(i) < n, (path, n)
                ct, _, co, sz = x._ch[ref & 0xFFFF]
                t, o = ct, co + ((ref >> 16) + int(i)) * sz
            else:
                t, o = ft, o + fo
            if fl & 0xFF == 4:
                u = struct.unpack_from("<I", x._d, o)[0]
                ct, _, co, sz = x._ch[u & 0xFFFF]
                t, o = ct, co + (u >> 16) * sz
        return self.k._rel(x.sec[7][0] + o, k)

    def new_hash(self):
        self.next += 1
        return self.next

    def clone(self, h):
        """clone of own record h; returns (record number of the clone, source record number, new slot)"""
        src = self.rec(h)
        idx, chunks, data, strings = self.k.records[src]
        self.k.index.append((self.new_hash(), self.k.index[idx][1], len(self.k.records)))
        self.k.records.append([len(self.k.index) - 1, list(chunks), data, strings])
        return len(self.k.records) - 1, src, len(self.k.index) - 1

    def put(self, k, src, path, fmt, value):
        data = bytearray(self.k.records[k][2])
        struct.pack_into(fmt, data, self.offset(src, path), value)
        self.k.records[k][2] = bytes(data)

    def set_str(self, k, src, field, value):
        """top-level string field of record k (a clone of record number src) -> value"""
        if not hasattr(self, "_names"):
            self._names = [n for n, *_ in self.k.x.records()]
        self.k.set_string(self._names[src], k, field, value)

    def external(self, h, like):
        """index slot for record h of another file, typed like the existing external slot of hash `like`"""
        assert h > self.k.index[-1][0]
        self.k.index.append((h, self.k.index[self.slot(like)][1], 0xFFFF))
        return len(self.k.index) - 1


def _white_light(e, h, scale=1.0):
    k, src, slot = e.clone(h)
    for c, v in zip("rgb", TITANIUM):
        e.put(k, src, "Colour." + c, "<f", v * scale)
    return slot


# The effect models are grey (greyscale textures, white vertex colours): their colour is the animated shader parameter
# "hlslShaderN.Colour" of their .cycle (animations/perks), stored as a constant RGB triple before the packed curves
# (found by hand: shuntbuild2 at 0x15E = 1.0 0.3 0.3, the Shunt's red). The railgun gets recoloured copies
# (railgun_<name>.cycle next to the originals) and clones of the AnimatedMeshSpecialFX records that point to them.
# name: (record hash, offsets of the colour triples)
CYCLES = {"shuntbuild2": (0xA4D6F3F5, (0x15E,)), "shuntbuildrev": (0xD0D5DBBF, (0x18B,)),
          "nitroreverseblastrings": (0x6EF7CFB3, (0x268,)), "shocked02": (0x40900025, (0x225, 0x22D)),
          "shocksparks02": (0x4365D47A, (0x291, 0x29D)), "shocksparks03": (0x77CF9027, (0x256,)),
          "blindfire_hit_01": (0xE0D33BBD, (0x1EC,)), "blindfire_pow_01": (0x9C2F9D93, (0x2CD, 0x2D9))}
BOLT_HIT, BOLT_HIT_LIGHT = 0xF54BA12D, 0xC1E4C744


def recolour_cycle(src, dst, offsets):
    """copy of a .cycle with its colour triples turned titanium white, same brightness (max component)"""
    b = bytearray(open(src, "rb").read())
    for o in offsets:
        rgb = struct.unpack_from("<3f", b, o)
        assert 0 < max(rgb) <= 20 and max(rgb) - min(rgb) >= 0.25 * max(rgb), (src, hex(o), rgb)   # a real colour
        struct.pack_into("<3f", b, o, *(v * max(rgb) / max(TITANIUM) for v in TITANIUM))
    open(dst, "wb").write(bytes(b))


def _white_mesh(e, name):
    """clone of an AnimatedMeshSpecialFX record playing railgun_<name>.cycle; returns its slot"""
    k, src, slot = e.clone(CYCLES[name][0])
    e.set_str(k, src, "AnimationFileName", f"animations/perks/railgun_{name}.cycle")
    return slot


def build(pk_in, dyn_in, pk_out, dyn_out):
    made = {}
    # ---- dynamiceffects.bin: long light trail (own effect: slow fade) and neon core ----
    d = Edit(dyn_in)
    d.next = BASE
    k, src, eff_slot = d.clone(TRAIL_EFFECT)
    for curve in ("sizeCurveX", "colourCurveA"):                # 1 -> 0 almost at once; now a slow, even fade
        d.put(k, src, f"render.{curve}[0].outTangent", "<f", -1.0)
        d.put(k, src, f"render.{curve}[1].inTangent", "<f", -1.0)
    d.put(k, src, "render.cullDistance", "<f", 600.0)
    trail_effect = d.k.index[eff_slot][0]
    k, src, slot = d.clone(TRAIL_EVENT)
    p = "emitters[0]."
    d.put(k, src, p + "effect", "<I", eff_slot)
    d.put(k, src, p + "spawn.amount.distance", "<f", TRAIL_STEP)
    d.put(k, src, p + "particle.life.mean", "<f", TRAIL_LIFE)
    d.put(k, src, p + "particle.size.mean", "<f", TRAIL_SIZE)
    for c, v in zip("rgb", TITANIUM):
        d.put(k, src, p + "particle.colour." + c, "<f", v)
    d.put(k, src, p + "particle.colour.a", "<f", 0.06)
    trail = d.k.index[slot][0]
    k, src, slot = d.clone(TRAIL_EVENT)                      # neon core (user: a luminous line, not smoke)
    d.put(k, src, p + "effect", "<I", eff_slot)
    d.put(k, src, p + "spawn.amount.distance", "<f", NEON_STEP)
    d.put(k, src, p + "particle.life.mean", "<f", NEON_LIFE)
    d.put(k, src, p + "particle.size.mean", "<f", NEON_SIZE)
    for c, v in zip("rgb", TITANIUM):
        d.put(k, src, p + "particle.colour." + c, "<f", v)
    d.put(k, src, p + "particle.colour.a", "<f", NEON_ALPHA)
    neon = d.k.index[slot][0]
    open(dyn_out, "wb").write(d.k.build())
    made.update(trail_effect=trail_effect, trail=trail, neon=neon)

    # ---- pickups.bin ----
    e = Edit(pk_in)
    t_slot, n_slot = e.external(trail, TRAIL_EVENT), e.external(neon, TRAIL_EVENT)
    e.next = max(BASE + 0x10, neon)
    # projectile
    k, src, part_trail = e.clone(PROJ_PART)
    e.put(k, src, "ParticleEvent", "<I", t_slot)
    k, src, part_neon = e.clone(PROJ_PART)
    e.put(k, src, "ParticleEvent", "<I", n_slot)
    k, src, inner = e.clone(PROJ_INNER)
    e.put(k, src, "Components[0].Component", "<I", part_trail)
    k, src, mesh = e.clone(PROJ_MESH)
    e.put(k, src, "InternalSpecialFX[0].SpecialFX", "<I", inner)
    light = _white_light(e, PROJ_LIGHT, 4.0)                      # the Bolt's is dim (0.25 0.19 0.38)
    k, src, proj = e.clone(PROJ)
    for i, s in enumerate((mesh, light, part_neon)):            # [2] was the Barge_Flare halo
        e.put(k, src, f"Components[{i}].Component", "<I", s)
    # charge, as the Shunt does it: Local = the shooter's own view (camera shake), External = what the others see
    # (no shake); [0] screen effect -> reverse Nitro rings, [3] red light -> white, [2] camera (Local only)
    white = _white_light(e, SHUNT_RED, 1.4)
    rings, build2, build_rev = (_white_mesh(e, n) for n in ("nitroreverseblastrings", "shuntbuild2", "shuntbuildrev"))
    charges = {}
    for view in ("local", "external"):
        k, src, charges[view] = e.clone(SHUNT_CHARGE)
        e.put(k, src, "Components[0].Component", "<I", rings)
        e.put(k, src, "Components[1].Component", "<I", build2)
        e.put(k, src, "Components[3].Component", "<I", white)
        if view == "external":
            e.put(k, src, "Components[2].Component", "<I", white)
        for i in (0, 1):                                          # rings, ShuntBuild2: stretched over the delay
            e.put(k, src, f"Components[{i}].SpeedFactor", "<f", CHARGE_SPEED)
    charge = charges["local"]
    # rear charge: the Shunt's reverse charge (ShuntBuildRev) for the 0.5 s rear delay, white light
    rear = {}
    for view in ("local", "external"):
        k, src, rear[view] = e.clone(SHUNT_REV_CHARGE)
        e.put(k, src, "Components[1].SpeedFactor", "<f", REAR_BUILD_SPEED)
        e.put(k, src, "Components[1].Component", "<I", build_rev)
        e.put(k, src, "Components[3].Component", "<I", white)
        if view == "external":                                   # no screen effect, no shake for the others
            e.put(k, src, "Components[0].Component", "<I", white)
            e.put(k, src, "Components[2].Component", "<I", white)
    # firing flash
    flash = _white_light(e, FIRED_LIGHT, 2.8)
    k, src, fired = e.clone(FIRED)
    e.put(k, src, "Components[0].Component", "<I", flash)
    # vehicle hit: Shock shell + sparks, white lights (External = seen by others, Local = the victim's view)
    lights = [_white_light(e, h, 4.5) for h in SHOCK_LIGHTS]
    shell, sparks2, sparks3 = (_white_mesh(e, n) for n in ("shocked02", "shocksparks02", "shocksparks03"))
    hits = {}
    for name, h, at, meshes in (("ext", SHOCK_EXT, (1, 2, 3), (0, 5, 6)), ("local", SHOCK_LOCAL, (1, 2, 3), (4, 7, 8))):
        k, src, hits[name] = e.clone(h)
        for i, s in zip(at + meshes, lights + [shell, sparks2, sparks3]):
            e.put(k, src, f"Components[{i}].Component", "<I", s)
    # the orb's own impact (Global), white: its two models and its light
    k, src, bolt_hit = e.clone(BOLT_HIT)
    for i, s in ((2, _white_mesh(e, "blindfire_hit_01")), (4, _white_light(e, BOLT_HIT_LIGHT, 1.0)),
                 (5, _white_mesh(e, "blindfire_pow_01"))):
        e.put(k, src, f"Components[{i}].Component", "<I", s)
    # the levels: forward (SuperShield.Modified) and rear (SuperShield.ReverseModified), same but the charge
    levels = {}
    sfx = "SpecialFX."
    for name, ch in (("front", charges), ("rear", rear)):
        k, src, levels[name] = e.clone(BOLT_LEVEL)
        e.put(k, src, sfx + "ProjectileSpecialFX[0].GlobalSpecialFX", "<I", proj)
        e.put(k, src, sfx + "ChargingSpecialFX[0].GlobalSpecialFX", "<I", NULL_REF)
        e.put(k, src, sfx + "ChargingSpecialFX[0].LocalSpecialFX", "<I", ch["local"])
        e.put(k, src, sfx + "ChargingSpecialFX[0].InternalSpecialFX", "<I", ch["local"])
        e.put(k, src, sfx + "ChargingSpecialFX[0].ExternalSpecialFX", "<I", ch["external"])
        e.put(k, src, sfx + "FiredSpecialFX[0].GlobalSpecialFX", "<I", fired)
        e.put(k, src, sfx + "HitVehicleSpecialFX[0].ExternalSpecialFX", "<I", hits["ext"])
        e.put(k, src, sfx + "HitVehicleSpecialFX[0].LocalSpecialFX", "<I", hits["local"])
        e.put(k, src, sfx + "HitVehicleSpecialFX[0].DurationIntro.EndTime", "<f", HIT_TIME)
        e.put(k, src, sfx + "HitVehicleSpecialFX[0].GlobalSpecialFX", "<I", bolt_hit)
        e.put(k, src, sfx + "HitEnvironmentSpecialFX[0].GlobalSpecialFX", "<I", bolt_hit)
    level = levels["front"]
    k = e.rec(SUPERSHIELD_TYPE)
    e.put(k, k, "Modified", "<I", levels["front"])
    e.put(k, k, "ReversedModified", "<I", levels["rear"])
    assert [h for h, _, _ in e.k.index] == sorted(h for h, _, _ in e.k.index), "index must stay sorted"
    open(pk_out, "wb").write(e.k.build())
    made.update(level=e.k.index[level][0], projectile=e.k.index[proj][0], charge=e.k.index[charge][0])
    return made


def graph(pk, dyn):
    """the SuperShield's Modified level and a resolver, read back by blurxt (self-check, docs)"""
    R = {h: (t, v) for f in (pk, dyn) for n, t, v, h in XT(f).records() if h}
    st = next(v for t, v in R.values() if t == "PickupType" and v["Type"] == "SuperShield")
    lv = R[int(st["Modified"][1:], 16)][1]

    def comps(h):
        t, v = R[int(h[1:], 16)]
        return [R[int(c["Component"][1:], 16)] for c in v["Components"]]
    return st, lv, comps, R


if __name__ == "__main__":                                    # self-check on copies of the test game's files
    import os, tempfile, config
    pk_in = os.path.join(config.BLUR_EXTRACTED, "mods", "railgun_backup", "pickups.bin")
    dyn_in = os.path.join(config.BLUR_EXTRACTED, "mods", "railgun_backup", "dynamiceffects.bin")
    t = tempfile.mkdtemp()
    pk, dyn = os.path.join(t, "pickups.bin"), os.path.join(t, "dynamiceffects.bin")
    made = build(pk_in, dyn_in, pk, dyn)
    print({k: "%08x" % v for k, v in made.items()})
    for a, b in ((pk_in, pk), (dyn_in, dyn)):                 # originals untouched, only additions
        old, new = list(XT(a).records()), list(XT(b).records())
        changed = [n for (n, _, v, _), (_, _, w, _) in zip(old, new) if v != w]
        print(os.path.basename(a), len(old), "->", len(new), "records; changed:", changed)
    st, lv, comps, R = graph(pk, dyn)
    s = lv["SpecialFX"]
    proj = comps(s["ProjectileSpecialFX"][0]["GlobalSpecialFX"])
    assert proj[0][0] == "AnimatedMeshSpecialFX" and "Blind_projectile_01" in proj[0][1]["AnimatedMeshFileName"]
    assert proj[1][0] == "LightSpecialFX" and proj[1][1]["Colour"]["r"] > 3
    neon_ev = R[int(proj[2][1]["ParticleEvent"][1:], 16)][1]
    assert neon_ev["name"] == "RearLightTrail" and abs(neon_ev["emitters"][0]["particle"]["colour"]["a"] - NEON_ALPHA) < 1e-4
    inner = R[int(proj[0][1]["InternalSpecialFX"][0]["SpecialFX"][1:], 16)][1]
    trail_ev = R[int(R[int(inner["Components"][0]["Component"][1:], 16)][1]["ParticleEvent"][1:], 16)][1]
    assert trail_ev["name"] == "RearLightTrail" and abs(trail_ev["emitters"][0]["particle"]["life"]["mean"] - TRAIL_LIFE) < 1e-4
    eff = R[int(trail_ev["emitters"][0]["effect"][1:], 16)][1]
    assert eff["render"]["colourCurveA"][0]["outTangent"] == -1.0
    ch = comps(s["ChargingSpecialFX"][0]["LocalSpecialFX"])
    assert s["ChargingSpecialFX"][0]["GlobalSpecialFX"] is None
    assert comps(s["ChargingSpecialFX"][0]["ExternalSpecialFX"])[2][0] == "LightSpecialFX"   # no shake for the others
    rl = R[int(st["ReversedModified"][1:], 16)][1]
    assert "ShuntBuildRev" in comps(rl["SpecialFX"]["ChargingSpecialFX"][0]["LocalSpecialFX"])[1][1]["AnimatedMeshFileName"]
    assert "NitroReverseBlastRings" in ch[0][1]["AnimatedMeshFileName"] and "ShuntBuild2" in ch[1][1]["AnimatedMeshFileName"]
    assert ch[3][1]["Colour"]["g"] > 1
    assert R[int(s["ChargingSpecialFX"][0]["LocalSpecialFX"][1:], 16)][1]["Components"][1]["SpeedFactor"] == CHARGE_SPEED
    hit = s["HitVehicleSpecialFX"][0]
    ext = comps(hit["ExternalSpecialFX"])
    assert "Shocked02" in ext[0][1]["AnimatedMeshFileName"] and all(c[1]["Colour"]["r"] > 4 for c in ext[1:4])
    assert "railgun_blindfire_hit_01" in comps(hit["GlobalSpecialFX"])[2][1]["AnimationFileName"] and hit["DurationIntro"]["EndTime"] == HIT_TIME
    assert lv["BalancingData"]["Speed"] == 300.0                # a byte copy of the Bolt's level
    print("graph ok: projectile", [c[0] for c in proj], "| charge", [c[1].get("AnimatedMeshFileName", c[0]) for c in ch])
