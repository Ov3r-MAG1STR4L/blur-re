"""Répartition par tolérance sous un budget de triangles (étude 16k), cadres et détails protégés.
python plan.py budget -> planchers.csv / plafonds.csv (noms avec « _ » comme dans la source fusionnée)"""
import csv, json, sys
B = int(sys.argv[1]); R = '../'
TOLS = [0.5, 1, 1.5, 2, 3, 4, 5, 7, 10, 15, 20, 30]
cur = list(csv.DictReader(open(R + 'D2_etude_16k/courbes.csv', encoding='utf-8'), delimiter=';')) + \
      list(csv.DictReader(open(R + 'D2_fenetres_16k/courbes_cadres.csv', encoding='utf-8'), delimiter=';'))
N = lambda n: n.replace(' ', '_')
need = {N(r['pièce']): {t: int(r[f'{t} mm']) for t in TOLS} for r in cur if r['0.5 mm']}
size = {N(r['pièce']): float(r['taille mm']) for r in cur}; area = {N(r['pièce']): float(r['surface cm²']) for r in cur}
zone = {N(k): v for k, v in json.load(open(R + 'D2_etude_16k/zones.json', encoding='utf-8')).items()}
NEW = ['Fiat_Multipla_96', 'Fiat_Multipla_94.002', 'Fiat_Multipla_94.003', 'Fiat_Multipla_135']
for n in NEW: zone[n] = 'contour de vitre'
prev = {r['pièce']: int(r['tri. réduits']) for r in csv.DictReader(open(R + 'D2_fenetres_16k/glb/pieces_16000.csv', encoding='utf-8'), delimiter=';')}
PROT = {'contour de vitre', 'feu', 'rétro', 'vitre', 'échappement'}
prot = {n for n in need if zone[n] in PROT} | {'Circle.015'}
CARD = {'Circle.027': prev['Circle.027']}
def cost(n, tol):
    t = max([t for t in TOLS if t <= tol] or [0.5]); return need[n][t], t
def plan(f, T):
    p = {}
    for n in need:
        tol = min(T, max(1.0, f * size[n]))
        if n in prot: tol = min(tol, 5)
        c, t = cost(n, tol)
        if n in prot and c < prev[n]: c = prev[n]        # détails et cadres : jamais moins que la version précédente
        p[n] = (c, t)
    return p
A = sum(area.values()); cands = []
for T in (2, 3, 4, 5, 6, 7):
    lo, hi = 0.0, 1.0
    for _ in range(40):
        mid = (lo + hi) / 2
        if sum(c for c, _ in plan(mid, T).values()) + sum(CARD.values()) <= B: hi = mid
        else: lo = mid
    p = plan(hi, T); tot = sum(c for c, _ in p.values()) + sum(CARD.values())
    if tot <= B: cands.append((sum(area[n] * t for n, (c, t) in p.items()) / A, T, tot, p))
M, T, tot, p = min(cands, key=lambda x: x[0])
fl = {n: c for n, (c, t) in p.items()}; fl.update(CARD)
for f in ('planchers.csv', 'plafonds.csv'): open(f, 'w', encoding='utf-8').writelines(f'{n};{v}\n' for n, v in sorted(fl.items()))
json.dump({n: t for n, (c, t) in p.items()}, open('tolerances.json', 'w'))
print(f'PLAN {B} : prévu {tot} triangles, plafond {T} mm, écart moyen pondéré {M:.2f} mm')
