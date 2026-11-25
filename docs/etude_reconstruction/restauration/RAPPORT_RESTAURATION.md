# 1000tipla D2 restaurée (D2R) à 8 600 triangles : rapport (2026-11-25)

**Statut : construite et inspectée en rendu, PAS validée, PAS importée dans Blur.** Budget de 8 600 accordé par
l'utilisateur (au-delà des 8 000). KN5 et reconstructions précédentes (`D2_full`, `glb/`) non modifiés.

Fichier : `glb/1000tipla_D2_8600.glb` — **8 597 triangles, 127 pièces, 16 matériaux, 14 images, INTÈGRE**
(`glb_check.py`). Comptage par pièce : `glb/pieces_8600.csv` ; audit : `audit_pieces.csv` ; gros plans
`gros_plans/cmp3_*.png` (original / D2 8000 / D2R 8600) ; vues `rendus/planche_8600_texture.png`, `_gris.png`.

## Méthode (après l'audit `../D2_detail_audit/RAPPORT_AUDIT.md`)
`reduce_d2_blender.py ... 8600 --planchers=planchers.csv --plafonds=plafonds.csv --cartes=cartes.txt` :
- **planchers à 5 mm** (52 pièces, 3 931 triangles) : contours de vitres, rétros, feux et phares, échappements,
  montants d'aileron, pare-brise (il contient les lentilles des phares du pied de pare-brise), réflecteurs
  `Fiat_Multipla_69/74` (classés « chrome » par l'audit, oubliés au premier passage) ;
- **plafonds** : besoin à 1 mm pour chaque pièce, 5 mm pour les vitres latérales plates (339 → 128) ;
- **une seule carte** : la calandre `Circle.027` (13 305 triangles en géométrie à 5 mm) ; montants d'aileron en
  géométrie d'origine ;
- **refus des faces retournées** (nouveau) : une réduction qui retourne plus de 1 % de la surface d'une pièce est
  refusée (+50 % de triangles jusqu'à une pièce propre). Sans cette règle, 9 pièces fines avaient jusqu'à 29 % de
  faces retournées, invisibles dans Blur ;
- reste réparti par surface. Tolérance générale des autres pièces : **3 cm** (2 cm demandait 8 897 triangles).

## Résultat par catégorie (écart max de la pire pièce)
| Catégorie | D2 8000 | D2R 8600 | Pire écart 8000 → 8600 |
|---|---|---|---|
| Contours de vitres | 245 | ~611 | 23,3 → < 5 mm |
| Feux et phares | 348 | ~1 470 | 30,0 → < 5 mm |
| Rétros | 67 | 272 | 24,0 → 3,5 mm |
| Échappements | 235 | 704 | 21,4 → 3,8 mm |
| Montants d'aileron | 189 (carte) | 512 (géométrie, ajourés) | → 3,0 mm |
| Pare-brise | 56 | 256 | 13,7 → 3,3 mm |
| Vitres latérales | 1 067 | 256 | → 4,6 mm |

Vérifications : 127 pièces présentes, matériaux / UV / textures d'origine, aucune pièce signalée « faces retournées »
(deux à 1 % arrondi, au seuil : `Circle.004`, `polymsh_detached20`).

## Défauts restants (inspection visuelle)
- Phare au pied du pare-brise : rond de trois-quarts, encore un peu facetté de très près ; le reste vient de la
  carrosserie principale `body_main.011` autour de la lentille (1 087 triangles, 23 mm au pire).
- Supports noirs des passages de roue arrière un peu dentelés ; bas du bouclier avant légèrement ondulé (pièces à
  3 cm de tolérance).
- Baguettes chromées non restaurées (choix de budget : ~1 280 triangles de plus).
- Poignées et serrures de portes : relief laissé dans la texture (choix de l'audit).
