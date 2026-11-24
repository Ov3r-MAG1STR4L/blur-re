"""Réécrit la vitesse de pointe d'une voiture perso de Map Builder dans le pak de REBORN (après chaque Build).

Map Builder tire la physique des stats de la classe (voir CONNAISSANCES « classe S ») : au-delà de la classe, la
stat vitesse donne un rapport final négatif. Ici on pose directement les valeurs :
  amax.bin          AmaxVehicle <car>            GameplayTopSpeed, UiMaxSpeed
  racingphysics.bin RP_CarDynamics <car>_physics gears.finalRatio, friction.airFriction
Le pak est réécrit comme le fait Map Builder (Pak.ReplaceFiles) : fichiers neufs ajoutés à la fin, entrée mise à jour.

  python boost_car.py "C:\\...\\Blur_test_hud\\rebrn\\gamedata.pak" BMB_Ryback_Vulkan_S [--mph 260 --final 2.33 --air 0.40]
"""
import argparse, hashlib, os, shutil, struct, sys, tempfile, zlib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from blurpak import Pak
import blurxt


def game_crc(data):
    """ce que vérifie le jeu : somme des ~crc32 de chaque bloc de 32 Ko (Map Builder, Pak.GameCrc)"""
    return sum(zlib.crc32(data[i:i + 0x8000]) ^ 0xFFFFFFFF for i in range(0, len(data), 0x8000)) & 0xFFFFFFFF


def chunked(data, cs=0x10000):
    out = bytearray(struct.pack('<I', cs))
    for i in range(0, len(data), cs):
        c = zlib.compressobj(9, zlib.DEFLATED, -15); z = c.compress(data[i:i + cs]) + c.flush()
        out += struct.pack('<I', len(z)) + z
    return bytes(out)


def replace_files(path, new):
    """{chemin dans le pak: octets} -> réécrit le pak sur place"""
    p = Pak(path)
    idx = {e.path.lower(): i for i, e in enumerate(p.entries)}
    stride, al, tab = p.stride, p.pagesize, p.tab_off
    p.f.close()
    with open(path, 'r+b') as f:
        f.seek(0, 2); end = f.tell()
        for name, data in new.items():
            i = idx[name.lower()]
            comp = zlib.compress(data, 9) if stride == 64 else chunked(data)
            pos = (end + al - 1) // al * al
            f.seek(end); f.write(bytes(pos - end)); f.write(comp); end = pos + len(comp)
            at = tab + 8 + i * stride
            f.seek(at + 12); f.write(struct.pack('<I', len(data)))
            f.seek(at + 24); f.write(struct.pack('<Q', pos // al))
            f.seek(at + 32); f.write(struct.pack('<II', game_crc(data), len(comp)))
            if stride == 64:
                f.seek(at + 44); f.write(hashlib.sha1(comp).digest())
        pad = (end + al - 1) // al * al - end
        f.seek(end); f.write(bytes(pad))


def patch(blob, record, sets):
    with tempfile.TemporaryDirectory() as d:
        fn = os.path.join(d, 'x.bin')
        for path, value in sets.items():
            open(fn, 'wb').write(blob)
            blob = blurxt.XT(fn).patched(record, path, value)
    return blob


def values(blob, kind, record):
    with tempfile.TemporaryDirectory() as d:
        fn = os.path.join(d, 'x.bin'); open(fn, 'wb').write(blob)
        return {n: v for n, t, v, h in blurxt.XT(fn).records() if t == kind}[record]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('pak'); ap.add_argument('car')
    ap.add_argument('--mph', type=int, default=260)
    ap.add_argument('--final', type=float, default=2.33)   # ponytail: estimé d'après la CCXR (7600 tr/min, 0,59 x 4,2 = 221 mph), roues non prises en compte
    ap.add_argument('--air', type=float, default=0.40)
    a = ap.parse_args()
    A, R = r'\gamedata\xt\amax.bin', r'\gamedata\xt\racingphysics.bin'
    p = Pak(a.pak); files = {e.path.lower(): e for e in p.entries}
    amax, rp = p.read(files[A]), p.read(files[R]); p.f.close()
    if not os.path.exists(a.pak + '.avant_boost'):
        shutil.copy2(a.pak, a.pak + '.avant_boost')
    amax2 = patch(amax, a.car, {'GameplayTopSpeed': a.mph, 'UiMaxSpeed': a.mph})
    rp2 = patch(rp, a.car + '_physics', {'gears.finalRatio': a.final, 'friction.airFriction': a.air})
    replace_files(a.pak, {A: amax2, R: rp2})
    # relecture depuis le pak réécrit
    p = Pak(a.pak); files = {e.path.lower(): e for e in p.entries}
    v = values(p.read(files[A]), 'AmaxVehicle', a.car); r = values(p.read(files[R]), 'RP_CarDynamics', a.car + '_physics')
    got = (v['GameplayTopSpeed'], v['UiMaxSpeed'], round(r['gears']['finalRatio'], 3), round(r['friction']['airFriction'], 3))
    assert got == (a.mph, a.mph, round(a.final, 3), round(a.air, 3)), got
    print('ok', a.car, 'mph', got[0], 'rapport final', got[2], 'air', got[3])


if __name__ == '__main__':
    main()
