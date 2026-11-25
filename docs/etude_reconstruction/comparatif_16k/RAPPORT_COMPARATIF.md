# 1000tipla : V8600 / V12000 / V16000 contre D2R 8600 (2026-11-25)

**Statut : construites, contrôlées et inspectées en rendu ; non validées, non importées dans Blur.** KN5, D2R 8600 et
reconstructions précédentes non modifiés. Méthode : répartition par tolérance de `../D2_etude_16k/ETUDE_16K.md`
(tolérance de chaque pièce proportionnelle à sa taille, bornée 1 mm / plafond), détails restaurés jamais réduits par
rapport à D2R 8600, calandre en carte, refus des faces retournées, pièces / matériaux / UV / textures d'origine.
Chaque dossier `8600/`, `12000/`, `16000/` contient `planchers.csv` (triangles par pièce), `tolerances.json`,
`glb/1000tipla_D2_<b>.glb`, `glb/pieces_<b>.csv` (écart par pièce), `audit_pieces.csv`, `rendus/`.

## Contrôles (les trois versions)
| | V8600 | V12000 | V16000 |
|---|---|---|---|
| Budget | 8 600 | 12 000 | 16 000 |
| **Triangles réels (GLB)** | **8 466** | **11 794** | **15 745** |
| Intégrité (`glb_check.py`) | intègre | intègre | intègre |
| Pièces présentes | 127/127 | 127/127 | 127/127 |
| Faces retournées (> 1 %) | aucune | aucune | aucune |
| Primitives sans UV | 0 | 0 | 0 |
| Matériaux changés | aucun | aucun | aucun |
| Détails restaurés réduits vs D2R | aucun | aucun | aucun |

## Écarts géométriques mesurés (par pièce, écart max à l'original ; calandre-carte exclue)
| | D2R 8600 | V8600 | V12000 | V16000 |
|---|---|---|---|---|
| Écart moyen pondéré par la surface | 9,4 mm | 8,6 mm | 5,5 mm | **2,5 mm** |
| Pièces > 5 mm | 48 | 42 | 16 | **0** |
| Pièces > 10 mm | 32 | 15 | 1 | 0 |
| Pire pièce | 29,3 mm | 15,5 mm | 10,4 mm | **4,0 mm** |
| Carrosserie principale `body_main.011` | 23,2 mm (1 141 tri.) | 15,5 mm (1 387) | 10,4 mm (1 731) | 3,0 mm |

Pire écart par zone (mm) :
| Zone | D2R 8600 | V8600 | V12000 | V16000 |
|---|---|---|---|---|
| Supports de passages de roue | 29,3 | 14,9 | 6,9 | 3,5 |
| Diffuseur / bas arrière | 27,0 | 11,6 | 6,3 | 3,9 |
| Peinture (tôles) | 23,2 | 15,5 | 10,4 | 4,0 |
| Bouclier avant (hors calandre) | 22,5 | 13,2 | ≤ 7 | ≤ 4 |
| Aileron | 18,9 | 13,0 | 5,8 | 3,6 |
| Baguettes chromées | 18,1 | 9,7 | 3,9 | 3,9 |
| Bas de caisse / dessous | 14,3 | 14,3 | 6,4 | 3,9 |
| Autres pièces noires | 12,4 | 9,8 | 5,7 | 3,9 |
| Contours de vitres, feux, rétros, vitres, échappements | ≤ 4,8 | ≤ 4,8 | ≤ 4,8 | ≤ 3,8 |

Écart avec l'étude : V12000 visait un plafond de 7 mm et mesure 10,4 mm sur la carrosserie principale ; V8600 visait
15 mm et tient. Les courbes de coût et la mesure finale n'échantillonnent pas les mêmes points (paliers x1,25) : les
estimations sont justes à quelques mm près. La protection des détails de D2R (qui avaient parfois plus que leur besoin)
coûte environ 300 à 400 triangles par version.

## Inspection visuelle (`planche_globale_*.png`, `cmp_<zone>.png` pour 11 zones, `zoom_av34_gris.png`)
- **V8600** : nettement plus propre que D2R au même budget sur les passages de roue et le bouclier ; carrosserie
  encore un peu ondulée.
- **V12000** : passages de roue, diffuseur, aileron, chromes proches de l'original ; bas du bouclier encore un peu
  ondulé ; carrosserie principale correcte. **Aucun défaut d'ombrage relevé.**
- **V16000** : la plus fidèle en géométrie (bouclier lisse, élargisseurs et diffuseur nets, catadioptre rond). **Défaut
  d'ombrage** : bande sombre verticale sur la portière avant et reflets irréguliers sur l'aile avant (gros plan
  `zoom_av34_gris.png`). Cause probable : le bord de portière enroulé vers le joint est maintenant représenté et le
  lissage à 30° le fond avec la face de la portière. Correction possible (non appliquée) : normales reprises de
  l'original pièce par pièce, ou angle de lissage plus bas sur les tôles.
- Toutes : calandre en carte (pas de relief en nid d'abeille) ; poignées de portes dans la texture.

## Points à décider
1. Version à retenir pour l'essai dans Map Builder (16 000 = maximum conseillé par Map Builder).
2. Correction de l'ombrage de V16000 avant tout essai.
