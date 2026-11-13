"""Audit A : environnement de Blur2DubaiTest (Unity) en lecture seule.

RenderSettings, lumières, caméras, LightmapSettings, objets de sharedassets0 (ciel / cubemap ?), TextAsset et
Texture2D de resources.assets, MonoBehaviour liés à l'éclairage / au ciel / au brouillard / à l'exposition.
Sortie : ../data/unity_env.json (aucune texture copiée).
Usage : python unity_env.py   (UnityPy est dans le site utilisateur : pas de -I)
"""
import json
import os
import re

import UnityPy

D = r"C:\Users\sanqu\Jeux_WII\Blur2DubaiTest\Blur2DubaiTest_Data"
KEY = re.compile(r"sky|fog|light|expos|sun|ambient|env|cube|tonemap|bloom|post|atmos|weather|lut|colou?r|grade",
                 re.I)
HERE = os.path.dirname(os.path.abspath(__file__))


def tt(o):
    try:
        return o.read_typetree()
    except Exception as ex:                       # MonoBehaviour sans typetree
        return {"_erreur": repr(ex)[:120]}


def short(v, n=4000):
    s = json.dumps(v, default=str)
    return v if len(s) <= n else {"_tronque": s[:n]}


def main():
    out = {}
    for f in ("level0", "level1"):
        env = UnityPy.load(os.path.join(D, f))
        sec = out.setdefault(f, {})
        for o in env.objects:
            t = o.type.name
            if t in ("RenderSettings", "LightmapSettings", "Light", "Camera"):
                sec.setdefault(t, []).append(short(tt(o)))
            elif t == "MonoBehaviour":
                d = tt(o)
                script = ""
                try:
                    script = o.read().m_Script.read().m_ClassName
                except Exception:
                    pass
                if KEY.search(script) or KEY.search(json.dumps(list(d.keys()))):
                    sec.setdefault("MonoBehaviour", []).append({"script": script, "data": short(d, 6000)})
    env = UnityPy.load(os.path.join(D, "sharedassets0.assets"))
    out["sharedassets0"] = [{"type": o.type.name, "data": short(tt(o), 3000)} for o in env.objects]
    env = UnityPy.load(os.path.join(D, "resources.assets"))
    res = out.setdefault("resources", {"TextAsset": [], "Texture2D": [], "MonoBehaviour": [], "Material": []})
    for o in env.objects:
        t = o.type.name
        if t == "TextAsset":
            d = o.read()
            txt = d.m_Script if isinstance(d.m_Script, str) else d.m_Script.decode("utf-8", "replace")
            res["TextAsset"].append({"name": d.m_Name, "len": len(txt),
                                     "head": txt[:1500] if KEY.search(d.m_Name + txt[:3000]) else ""})
        elif t == "Texture2D":
            d = o.read()
            res["Texture2D"].append([d.m_Name, d.m_Width, d.m_Height, str(d.m_TextureFormat)])
        elif t == "Material":
            d = tt(o)
            if KEY.search(d.get("m_Name", "")) or "Sky" in json.dumps(d)[:2000]:
                res["Material"].append(short(d, 3000))
        elif t == "MonoBehaviour":
            d = tt(o)
            nm = d.get("m_Name", "") if isinstance(d, dict) else ""
            if KEY.search(nm):
                res["MonoBehaviour"].append({"name": nm, "data": short(d, 6000)})
    dst = os.path.join(HERE, "..", "data", "unity_env.json")
    json.dump(out, open(dst, "w", encoding="utf-8"), indent=1, ensure_ascii=False, default=str)
    print("écrit", dst)


if __name__ == "__main__":
    main()
