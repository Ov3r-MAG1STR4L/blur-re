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
    ap.add_argument('--mph', type=int, default=290)
    # boîte de la CCXR (dont la S a le son : le régime monte comme le son l'attend), rapport final pour ~290 mph :
    # CCXR 221 mph à 7600 tr/min avec 0,59 x 4,2 = 2,478 -> S (7800 tr/min) : 2,478 x 7800/7600 x 221/290 / 0,59 = 3,285
    # ponytail: taille des roues ignorée, la vitesse réelle peut s'écarter un peu
    ap.add_argument('--gears', default='2.62,1.94,1.47,1.14,0.74,0.59')
    ap.add_argument('--final', type=float, default=3.285)
    ap.add_argument('--air', type=float, default=0.32)
    ap.add_argument('--health', default='Low')               # HealthGroup : Low / Medium / High (la base Opel a High)
    ap.add_argument('--grip', type=float, default=1.3)       # multiplie grip.yScale et transverseGripScale avant / arrière
    ap.add_argument('--traction', type=float, default=1.6)   # tyres.rearTyres.forwardsGripScale (patinage au départ)
    ap.add_argument('--downforce', type=float, default=2.0)
    a = ap.parse_args()
    A, R = r'\gamedata\xt\amax.bin', r'\gamedata\xt\racingphysics.bin'
    # .avant_boost = le pak tel que Map Builder l'a construit ; .boost = empreinte du pak que nous avons écrit.
    # Pak différent de notre empreinte = nouveau Build -> il devient la référence (relancer ne cumule pas les x1,3).
    mark = a.pak + '.boost'
    sha = lambda f: hashlib.sha256(open(f, 'rb').read()).hexdigest()
    if not (os.path.exists(mark) and open(mark).read().strip() == sha(a.pak)):
        shutil.copy2(a.pak, a.pak + '.avant_boost')
    phys = a.car + '_physics'
    # valeurs Map Builder (avant boost) : relues dans le fichier d'origine, pour que relancer ne multiplie pas deux fois
    p0 = Pak(a.pak + '.avant_boost'); f0 = {e.path.lower(): e for e in p0.entries}
    amax, rp = p0.read(f0[A]), p0.read(f0[R]); p0.f.close()
    base = values(rp, 'RP_CarDynamics', phys)
    gears = [float(x) for x in a.gears.split(',')]
    sets = {'gears.finalRatio': a.final, 'friction.airFriction': a.air, 'friction.downforce': a.downforce,
            'tyres.rearTyres.forwardsGripScale': a.traction}
    sets.update({f'gears.gearRatios[{i}]': g for i, g in enumerate(gears)})
    for side in ('frontTyres', 'rearTyres'):
        t = base['tyres'][side]
        sets[f'tyres.{side}.grip.yScale'] = t['grip']['yScale'] * a.grip
        sets[f'tyres.{side}.transverseGripScale'] = t['transverseGripScale'] * a.grip
    amax2 = patch(amax, a.car, {'GameplayTopSpeed': a.mph, 'UiMaxSpeed': a.mph, 'HealthGroup': a.health})
    rp2 = patch(rp, phys, sets)
    shutil.copy2(a.pak + '.avant_boost', a.pak)      # repart toujours du pak de Map Builder (pas d'ajouts en chaîne)
    replace_files(a.pak, {A: amax2, R: rp2})
    open(mark, 'w').write(sha(a.pak))
    # relecture depuis le pak réécrit
    p = Pak(a.pak); files = {e.path.lower(): e for e in p.entries}
    v = values(p.read(files[A]), 'AmaxVehicle', a.car); r = values(p.read(files[R]), 'RP_CarDynamics', phys)
    assert (v['GameplayTopSpeed'], v['HealthGroup']) == (a.mph, a.health), (v['GameplayTopSpeed'], v['HealthGroup'])
    assert [round(x, 3) for x in r['gears']['gearRatios']] == [round(g, 3) for g in gears], r['gears']['gearRatios']
    assert abs(r['gears']['finalRatio'] - a.final) < 1e-3 and abs(r['friction']['airFriction'] - a.air) < 1e-3
    print('ok', a.car, 'mph', a.mph, 'vie', a.health, 'boite', gears, 'final', a.final, 'air', a.air,
          'grip x%.2f' % a.grip, 'traction', a.traction, 'appui', a.downforce)


if __name__ == '__main__':
    main()
