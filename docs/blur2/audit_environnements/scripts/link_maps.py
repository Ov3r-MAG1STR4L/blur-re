"""Audit A : relie chaque ville Blur 2 (tracks.bin) à ses réglages d'environnement (environmentalsettings.bin)
et vérifie la présence des textures citées (ciel, cubemap, LUT) dans les paks Blur 2 X360 et Blur 1 PC.

Entrées : ../data/<build>/env_records.json (env_records.py).
Sortie : ../environnements.json (inventaire par map) + ../data/textures_citees.json
Usage : python -I link_maps.py
"""
import json
import os
import sys

JEUX = r"C:\Users\sanqu\Jeux_WII"
sys.path.insert(0, os.path.join(JEUX, "blur_tools", "x360"))
sys.path.insert(0, os.path.join(JEUX, "blur_tools"))
import blurpak_be  # noqa: E402
import blurpak     # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
PAKS = {
    "b2_nov10": (blurpak_be, [r"blur_extracted\b2_x360_nov\full\Blur 2 (Nov 10, 2010)\cache\root.pak",
                              r"blur_extracted\b2_x360_nov\gamedata.pak"]),
    "b2_nov04": (blurpak_be, [r"blur_extracted\b2_x360_nov04\!Blur 2 (Nov 04, 2010) [Unreleased]\cache\root.pak",
                              r"blur_extracted\b2_x360_nov04\!Blur 2 (Nov 04, 2010) [Unreleased]\cache\gamedata.pak"]),
    "b1_pc": (blurpak, [r"C:\Program Files (x86)\Activision\Blur(TM)\cache\root.pak",
                        r"C:\Program Files (x86)\Activision\Blur(TM)\cache\lut_rampak.pak",
                        r"C:\Program Files (x86)\Activision\Blur(TM)\cache\root_streaming.pak"]),
}
SLOTS = ("lightingSettings", "lightFlareSettings", "postFxSettings", "roadTrackSettings", "shadowSettings",
         "carLightSettings", "windSettings", "layerFogSettings")


def base(p):
    return os.path.basename((p or "").replace("\\", "/")).lower()


def pak_names():
    out = {}
    for k, (mod, paths) in PAKS.items():
        names = {}
        for p in paths:
            full = p if os.path.isabs(p) else os.path.join(JEUX, p)
            if os.path.exists(full):
                for e in mod.Pak(full).entries:
                    if e.usize:
                        names[base(e.path)] = (e.path, e.usize)
        out[k] = names
    return out


def presence(tex, names):
    """présence par nom de fichier ; la même ressource peut exister en .dds et .texture"""
    if not tex:
        return None
    b = base(tex)
    stem = os.path.splitext(b)[0]
    r = {}
    for k, n in names.items():
        hit = n.get(b) or n.get(stem + ".texture") or n.get(stem + ".dds")
        r[k] = list(hit) if hit else None
    return r


def strip(v):
    return {k: x for k, x in v.items() if k not in ("item",)} if isinstance(v, dict) else v


def main():
    names = pak_names()
    inv = {"_source": "tracks.bin (City) + environmentalsettings.bin, builds X360 Blur 2 ; décodage env_records.py",
           "_presence": "chemin et taille dans le pak, null = absent (par nom de fichier)", "builds": {}}
    cited = {}
    for build in ("nov10", "nov04", "aug31"):
        d = json.load(open(os.path.join(ROOT, "data", build, "env_records.json"), encoding="utf-8"))
        es = d["environmentalsettings.bin"]
        byhash = {}
        for typ, recs in es.items():
            for r in recs:
                byhash["@" + r["hash"]] = (typ, r)
        cities = d["tracks.bin"]["City"] + d.get("tracks_archive.bin", {}).get("City", [])
        routes = d["tracks.bin"].get("Route", [])
        cityhash = {"@" + c["hash"]: c["Name"] for c in cities}
        out = {}
        for c in cities:
            ent = {"hash": c["hash"], "dev_only": c["DevOnly"], "dossier_acteurs": c["ActorListFolder"],
                   "routes": sorted(r["Name"] for r in routes if cityhash.get(r.get("City")) == c["Name"]),
                   "far_clip": c.get("mainFarClip"), "env_far_clip": c.get("environmentFarClip"),
                   "reflection_resolution": c.get("reflectionResolution"),
                   "environment_resolution": c.get("environmentResolution"),
                   "headlight_scale": c.get("headlightIntensityScale")}
            for mode in ("EnvironmentSettings", "FlashbackSettings"):
                refs = c.get(mode) or {}
                m = {}
                for slot in SLOTS:
                    h = refs.get(slot)
                    if not h:
                        m[slot] = None
                        continue
                    typ, r = byhash.get(h, (None, None))
                    m[slot] = {"ref": h, "non_resolu": True} if r is None else {"ref": h, **strip(r)}
                ent[mode] = m
            ls = (ent["EnvironmentSettings"].get("lightingSettings") or {})
            pf = (ent["EnvironmentSettings"].get("postFxSettings") or {})
            sky = (ls.get("skySettings") or {}).get("texture")
            cube = ls.get("cubemapTexture")
            lut = pf.get("lookupTexture")
            ent["ressources"] = {}
            for kind, tex in (("ciel", sky), ("cubemap", cube), ("lut", lut)):
                if tex:
                    pres = presence(tex, names)
                    ent["ressources"][kind] = {"reference": tex, "presence": pres}
                    cited.setdefault(tex, {"type": kind, "presence": pres, "villes": []})["villes"].append(
                        f"{build}:{c['Name']}")
            out[c["Name"]] = ent
        # réglages non référencés par une ville (préréglages, tests, FX)
        used = {v["ref"] for e in out.values() for mode in ("EnvironmentSettings", "FlashbackSettings")
                for v in e[mode].values() if v}
        inv["builds"][build] = {"villes": out,
                                "lighting_non_references": len([1 for r in es["LightingSettings"]
                                                                if "@" + r["hash"] not in used])}
        for r in es["LightingSettings"]:
            for kind, tex in (("ciel", (r.get("skySettings") or {}).get("texture")),
                              ("cubemap", r.get("cubemapTexture"))):
                if tex and tex not in cited:
                    cited[tex] = {"type": kind, "presence": presence(tex, names), "villes": []}
    # niveaux : tailles dans les archives (archive_maps.py) et blocs CubePt / LSData (levelrender_scan.py)
    arch = os.path.join(ROOT, "data", "archives_maps.json")
    scan = os.path.join(ROOT, "data", "levelrender_env.json")
    arch = json.load(open(arch, encoding="utf-8")) if os.path.exists(arch) else {}
    scan = json.load(open(scan, encoding="utf-8")) if os.path.exists(scan) else {}
    niveaux = {}
    for build in ("aug31", "nov04", "nov10"):
        for m, files in arch.get(build, {}).items():
            s = scan.get(f"{build}/{m}", {})
            niveaux.setdefault(m, {})[build] = {
                "fichiers_octets": files,
                "levelrender": {k: s[k] for k in ("LSData", "CubePt2", "CubePt3", "g_tEnvironment", "g_tLightmap0/1",
                                                  "pages_lightmap") if k in s} or None}
    inv["niveaux"] = niveaux
    u = os.path.join(ROOT, "data", "unity_env.json")
    if os.path.exists(u):
        u = json.load(open(u, encoding="utf-8"))
        rs = u["level1"]["RenderSettings"][0]
        inv["unity_blur2dubaitest"] = {
            "_nature": "réglages de la reconstruction Unity (uKER), pas des données Blur 2",
            "skybox": "Default-Skybox (procédural Unity) + Default-Skybox-Cubemap 128²",
            "fog_actif": rs["m_Fog"], "ambient_mode": rs["m_AmbientMode"],
            "ambient_sky_equator_ground": [rs["m_AmbientSkyColor"], rs["m_AmbientEquatorColor"],
                                           rs["m_AmbientGroundColor"]],
            "lumiere_directionnelle": {k: u["level1"]["Light"][0][k] for k in ("m_Color", "m_Intensity",
                                                                               "m_ColorTemperature")},
            "sky_rotation_offsets": r"Blur2DubaiTest_Data\Blur2Survey\sky_rotation_offsets.csv (dubai -30°, "
                                    "_test_lighting -176°, autres 30°)",
            "dubai_lights": r"resources.assets TextAsset dubai_lights : 44 lumières ponctuelles (x,y,z,r,g,b,"
                            "intensity,range)"}
    inv["_niveaux"] = ("levelrender lu en mémoire depuis les archives (7z -so) ; null = non lu (fichier < 4 Ko, "
                       "build 4 nov hors Dubaï non relu)")
    inv["blur1_pc_niveaux"] = {k.split("/", 1)[1]: {x: v[x] for x in ("LSData", "CubePt2") if x in v}
                               for k, v in scan.items() if k.startswith("b1_pc/")}
    json.dump(inv, open(os.path.join(ROOT, "environnements.json"), "w", encoding="utf-8"), indent=1,
              ensure_ascii=False)
    json.dump(cited, open(os.path.join(ROOT, "data", "textures_citees.json"), "w", encoding="utf-8"), indent=1,
              ensure_ascii=False)
    for c, e in inv["builds"]["nov10"]["villes"].items():
        if not e["dev_only"]:
            print(c, {k: (v["reference"], {b: bool(x) for b, x in v["presence"].items()})
                      for k, v in e["ressources"].items()})


if __name__ == "__main__":
    main()
