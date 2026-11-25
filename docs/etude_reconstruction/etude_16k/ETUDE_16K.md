# Étude chiffrée : 1000tipla jusqu'à 16 000 triangles (2026-11-25)

Étude seulement : rien reconstruit, KN5 et reconstructions précédentes non modifiés. Référence : D2R 8600.
Données : `courbes.csv` (par pièce, triangles nécessaires pour tenir 0,5 à 30 mm d'écart max, même réduction que
`reduce_d2_blender.py`, refus des faces retournées compris ; paliers de x1,25, donc chiffres à ~±10 %), `zones.json`
(127 pièces rangées en 14 zones d'après la position des roues), `scenarios.json` (répartition retenue par budget).
Outil : `blur_tools/cost_curve_blender.py`.

## 1. Pièces encore déformées dans D2R 8600 (écart max mesuré)
| Catégorie | Pièces | Triangles | > 5 mm | > 10 mm | > 20 mm | Pire |
|---|---|---|---|---|---|---|
| Pièces noires / aéro | 38 | 2 867 | 28 | 17 | 7 | `polymsh_detached20` 29 mm |
| Baguettes chromées | 14 | 486 | 10 | 8 | 0 | `Circle.030` 18 mm |
| Peinture | 23 | 1 591 | 10 | 7 | 2 | `body_main.011` (carrosserie principale) 23 mm |
| Contours de vitres, feux, rétros, vitres, échappements | 52 | 3 653 | 0 | 0 | 0 | ≤ 5 mm (restaurés) |

Écart moyen pondéré par la surface : **9,4 mm** ; 47 pièces au-delà de 5 mm.

## 2. Coût par zone (triangles pour tenir l'écart max indiqué sur toutes les pièces de la zone)
| Zone | Pièces | D2R | 10 mm | 5 mm | 3 mm | 2 mm | 1 mm |
|---|---|---|---|---|---|---|---|
| Peinture (tôles) | 12 | 1 494 | 1 938 | 3 712 | 7 181 | 7 337 | 21 314 |
| Feux | 17 | 1 468 | 663 | 1 160 | 2 088 | 2 771 | 5 236 |
| **Baguettes chromées** | 14 | 486 | 408 | 1 038 | 1 940 | 2 313 | 4 079 |
| Autres pièces noires | 7 | 925 | 663 | 1 035 | 1 418 | 1 873 | 3 055 |
| **Diffuseur / bas arrière** | 7 | 266 | 340 | 554 | 1 043 | 1 353 | 2 025 |
| **Supports de passages de roue** | 8 | 354 | 453 | 739 | 1 038 | 1 231 | 1 394 |
| **Bouclier avant** | 11 | 544 | 434 | 700 | 930 | 1 224 | 1 782 |
| Contours de vitres | 26 | 633 | 386 | 516 | 785 | 1 169 | 2 039 |
| Échappements | 3 | 704 | 347 | 536 | 859 | 1 039 | 2 036 |
| Vitres | 4 | 576 | 201 | 369 | 655 | 985 | 1 681 |
| Bas de caisse / dessous | 7 | 694 | 414 | 424 | 596 | 634 | 1 054 |
| Rétros | 2 | 272 | 152 | 241 | 306 | 475 | 1 145 |
| Aileron | 3 | 70 | 98 | 146 | 246 | 353 | 604 |
| Peinture avant | 5 | 47 | 50 | 55 | 67 | 72 | 131 |
| **Total** (+ carte calandre 64) | 126 | 8 533 | 6 547 | **11 225** | 19 152 | 22 829 | 47 575 |

Calandre en nid d'abeille : en vraie géométrie, ~13 300 triangles quel que soit l'écart (ses trous empêchent la
réduction) → **reste une carte même à 16 000** (elle prendrait 83 % du budget). Toutes les autres pièces gardent leurs
vrais trous et reliefs.

## 3. Surfaces surdimensionnées dans D2R
- Au-delà du besoin à 1 mm : 10 pièces, **277 triangles** récupérables (`Fiat_Multipla_28` dessous 512 → 288…).
- Le vrai gaspillage est la **répartition par surface** : elle donne beaucoup à des pièces déjà précises et trop peu à la
  carrosserie principale (1 141 triangles, 23 mm). Une répartition par **tolérance** fait mieux au même budget (ci-dessous).

## 4. Scénarios (répartition par tolérance, meilleur réglage trouvé par budget)
Règle : tolérance de chaque pièce = proportionnelle à sa taille, bornée entre 1 mm et un plafond ; détails restaurés
≤ 5 mm ; réglage choisi pour minimiser l'écart moyen pondéré par la surface.

| Budget | Total estimé | Plafond | Écart moyen pondéré | Pièces > 5 mm | Pièces > 3 mm | Carrosserie principale |
|---|---|---|---|---|---|---|
| D2R actuel 8 600 | 8 597 | - | 9,4 mm | 47 | - | 23 mm (1 141 tri.) |
| 8 600 redistribués | 8 593 | 7 mm | 6,8 mm | 64 (toutes ≤ 7) | 105 | 7 mm (1 733 tri.) |
| 10 000 | 9 998 | 7 mm | 6,7 mm | 36 (toutes ≤ 7) | 75 | 7 mm |
| **12 000** | 11 968 | **5 mm** | **5,0 mm** | **0** | 80 | 5 mm (3 388 tri.) |
| 14 000 | 13 713 | 5 mm | 5,0 mm | 0 | 57 | 5 mm |
| 16 000 | 15 902 | 4 mm | 4,0 mm | 0 | 57 | 4 mm (4 237 tri.) |

Gains visuels attendus :
- **8 600 redistribués** : plus aucune pièce au-delà de 7 mm (contre 29 mm) ; la carrosserie principale passe de 23 à
  7 mm. Gain net sans un triangle de plus.
- **10 000** : baguettes chromées restaurées (≤ 5 mm) ; supports de roue, bouclier et diffuseur encore à 7 mm.
- **12 000** : **toutes les pièces ≤ 5 mm** (supports de roue, bouclier, diffuseur, chromes compris) ; carrosserie à
  5 mm. C'est le palier où tous les défauts relevés disparaissent à l'échelle des gros plans.
- **14 000** : gain faible (pièces ≤ 3 mm : 80 → 57 environ), même plafond de 5 mm.
- **16 000** : plafond 4 mm partout, carrosserie à 4 mm ; gain visible surtout sur les reflets des grandes tôles.
Rendements décroissants au-delà de 12 000 : tout à 3 mm demanderait ~19 000 triangles (au-delà du plafond).

## 5. Stratégie de répartition proposée
1. **Tolérance par pièce** = min(plafond, max(1 mm, k × taille)), taille = racine de la surface ; plafond et k choisis
   par budget (tableau 4). Remplace la répartition par surface et les poids x3.
2. **Détails restaurés protégés** : plancher actuel (5 mm) et jamais moins de triangles que dans D2R 8600.
3. **Coût lu dans les courbes** (`courbes.csv`) : chaque pièce reçoit exactement le besoin de sa tolérance, sans
   plafond de surface ; aucune pièce au-delà de son besoin à 1 mm.
4. **Trous et reliefs** : géométrie d'origine pour toutes les pièces, carte pour la seule calandre.
5. **Faces retournées** : refus au-delà de 1 % (déjà dans le script), contrôle `audit_details_blender.py`.
6. **Matériaux, UV, textures, 127 pièces** : inchangés (pièces d'origine réduites, pas de cuisson).
7. Contrôles de chaque version : `glb_check.py` (intégrité, budget ≤ 16 000), écart par pièce, audit, gros plans et
   vues comparées avec l'original et D2R.
