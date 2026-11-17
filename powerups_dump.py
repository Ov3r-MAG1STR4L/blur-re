#!/usr/bin/env python3
"""Power-up data of Blur, resolved from the JSON export of pickups.bin (blurxt.py --all), as Markdown (2026-11-17).

For each PickupType: its levels (Normal, DoubleTap, Reversed, ...), their BalancingData / BalancingGraph, and every
SpecialFX slot followed down to its components (model + animation, particle event, light, flare, post effect,
camera shake, rumble), with the Local / External / Internal / Global split and the mirror / reflection flags.

usage: powerups_dump.py [XT_JSON_DIR] > docs/POWERUPS_DONNEES.md
"""
import json, os, sys

XT = sys.argv[1] if len(sys.argv) > 1 else r"C:\Users\sanqu\Jeux_WII\blur_extracted\xt_json"
LEVELS = ["Normal", "DoubleTap", "Reversed", "ReversedDoubleTap", "Mini", "Modified", "ReversedModified"]
ROLES = ["LocalSpecialFX", "ExternalSpecialFX", "InternalSpecialFX", "GlobalSpecialFX"]


def ref(db, path):
    """'pickups/SpecialFX/#12' -> record (None for a reference into another file)"""
    f, t, k = path.split("/", 2)
    return db.get(t, {}).get(k) if f == "pickups" else None


def component(db, path):
    """one line for a SpecialFX component"""
    t = path.split("/")[1]
    c = ref(db, path)
    if c is None:
        return f"{t} {path}"
    if t == "AnimatedMeshSpecialFX":
        fl = [n[11:] for n in ("ExcludeFromMirror", "ExcludeFromReflection", "ExcludeFromCubemap") if c[n]]
        inner = [f"{i['AnimationNodeName']} → {' + '.join(fx_tree(db, i['SpecialFX']))}"
                 for i in c["InternalSpecialFX"] or [] if i["SpecialFX"]]     # effects hung on animation nodes
        return (f"mesh `{c['AnimatedMeshFileName']}` anim `{c['AnimationFileName']}`"
                + (f" far {c['FarDistance']:g}" if c["FarDistance"] else "") + (f" (not in {', '.join(fl)})" if fl else "")
                + (f" {{nœuds : {' ; '.join(inner)}}}" if inner else ""))
    if t == "ParticleSpecialFX":
        return f"particles `{c['ParticleEvent'].split('/')[-1]}`"
    if t == "FlareSpecialFX":
        return f"flare `{c['Flare'].split('/')[-1]}` {c['Time']:g} s"
    if t in ("CameraSpecialFX", "CameraNoiseSpecialFX", "RumbleSpecialFX", "PostSpecialFX"):
        return f"{t[:-9]} {c.get('Time', 0):g} s"
    return t[:-9]


def fx_tree(db, path):
    """component lines of a SpecialFX record"""
    sfx = ref(db, path)
    if sfx is None:
        return [path]
    return [component(db, c["Component"]) + (f" ×{c['SpeedFactor']:g}" if c["SpeedFactor"] != 1 else "")
            for c in sfx["Components"]]


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    db =json.load(open(os.path.join(XT, "pickups.json")))
    out = ["# Données des bonus (`pickups.bin`), résolues", "",
           "Généré par `powerups_dump.py` depuis l'export JSON de `pickups.bin`. Rien d'interprété : valeurs du fichier.",
           "Rôles d'un effet : **L** Local (vu par le joueur concerné), **E** External (vu par les autres), "
           "**I** Internal (vue intérieure), **G** Global (tout le monde). « ×n » = SpeedFactor de l'animation.", ""]
    for k, t in sorted(db["PickupType"].items(), key=lambda kv: kv[1]["Type"]):
        out += [f"## {t['Type']} (`PickupType` {k})", "",
                f"- LocString {t['LocString']}, BaseProbability {t['BaseProbability']:g}, AIUsageType {t['AIUsageType']}, "
                f"DoNotRandomise {t['DoNotRandomise']}",
                f"- AIPickupTypes : `{json.dumps(t['AIPickupTypes'])}`"]
        if t["PositionModifiers"]:
            out.append(f"- PositionModifiers : `{json.dumps(t['PositionModifiers'])}`")
        for f in [n for n in t if "FX" in n and isinstance(t[n], str)]:
            out.append(f"- {f} : " + " ; ".join(fx_tree(db, t[f])))
        for lv in LEVELS:
            if not t[lv]:
                continue
            L = db["PickupLevel"][t[lv].split("/")[-1]]
            out += ["", f"### {t['Type']} · {lv} ({t[lv].split('/')[-1]})", "",
                    f"- BalancingData : `{json.dumps(L['BalancingData'])}`"]
            g = L["BalancingGraph"]
            if g and (g["EffectGraph"] or g["MaxBoost"]):
                pts = ", ".join(f"({p['Time']:g} ; {p['Value']:g})" for p in g["EffectGraph"])
                out.append(f"- BalancingGraph : MaxBoost {g['MaxBoost']:g}, courbe {pts}")
            for slot, entries in (L["SpecialFX"] or {}).items():
                for e in entries or []:
                    dur = e["DurationIntro"]
                    out.append(f"- **{slot}** [{e['SpecialFXLocation']}, {dur['StartTime']:g}–{dur['EndTime']:g} s]")
                    for r in ROLES:
                        if e[r]:
                            out.append(f"  - {r[0]} : " + " ; ".join(fx_tree(db, e[r])))
        out.append("")
    print("\n".join(out))


if __name__ == "__main__":
    main()
