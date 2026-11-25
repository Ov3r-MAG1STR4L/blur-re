# Encadrements de fenêtres : KN5 original contre V16000 (2026-11-25)

Rien modifié ni reconstruit. Fichiers : `rayons.csv` (relevé par rayons, 1 cm, flancs gauche et droit, bande des
fenêtres Y −1,95..1,95, Z 0,80..1,60, 31 671 rayons par flanc et par modèle), `gros_plans/cmp_*.png` (original complet /
original extérieur / V16000, texture et gris, faces arrière masquées comme dans Blur), `cout_contours_retires.csv`.
Outil : `blur_tools/window_raymap_blender.py`.

## Réponse
**Non, les contours de V16000 ne correspondent pas au KN5 original — mais V16000 n'y est pour rien.** Ils manquent
dans toutes les reconstructions depuis la première conversion : les pièces qui forment les encadrements ont été retirées
comme « habitacle » par le tri initial (pièces entièrement contenues dans le volume de l'habitacle,
`interior_skip.txt`). Vues de l'extérieur, ce sont pourtant les joints et cadres de fenêtres. **V16000 reproduit
fidèlement l'original extérieur** qui lui sert de base.

## Ce qui remplit les fenêtres (relevé par rayons, deux flancs)
| Original complet → original extérieur → V16000 | Rayons (1 cm² chacun) |
|---|---|
| pièce → pièce → pièce | 33 057 |
| vide → vide → vide (ouvertures réelles : fond vu à travers) | 24 246 |
| **pièce → vide → vide (encadrements retirés au tri)** | **5 652** |
| petits écarts de bord original extérieur ↔ V16000 (≤ quelques mm, dans la tolérance) | ~300 |

Pièces visibles par les fenêtres dans le KN5 et absentes des reconstructions :
| Pièce | Vue de côté | Triangles | Rôle (d'après les gros plans) |
|---|---|---|---|
| `Fiat_Multipla_96` | 4 856 cm² | 51 050 | joints et encadrements noirs des vitres, montant central, cadres intérieurs de portes |
| `Fiat_Multipla_94.002`, `94.003` | 412 cm² chacun | 2 138 chacun | encadrement de fenêtre (montant), gauche et droite |
| `Fiat_Multipla_135` | 85 cm² | 6 544 | élément noir derrière le pare-brise / montant |
| `Fiat_Multipla_89`, `_88` | 19 / 8 cm² | 17 104 / 13 312 | planche de bord (habitacle, à peine visible) |
| `Fiat_Multipla_2`, `Cage` (`COCKPIT_HR`) | 40 / 14 cm² | | habitacle et arceau (vus à travers, retirés volontairement) |

## Contours, côté par côté (gros plans `fenetre_avant`, `fenetre_arriere`, `fenetre_haut`, `fenetre_bas`, `vitres_laterales`)
- **Supérieur** : KN5 = cadre noir continu sous la gouttière de toit ; reconstructions = jour clair entre verre et toit.
- **Inférieur** : KN5 = joint de bas de vitre ; reconstructions = fine bande claire (fond vu à travers).
- **Avant** (montant de pare-brise, rétro) : KN5 = cadre noir arrondi ; reconstructions = jour clair, coin du verre visible.
- **Arrière / montant central** : KN5 = montant noir entre les deux vitres ; reconstructions = ouverture, pièces derrière
  visibles.

## Nature des bordures
Ce sont de **vrais maillages** (matériau `BlackMatte`, texture noire générique), pas des dessins de la livrée ni des
matériaux à part. La livrée (`CarPaint`) ne dessine aucun cadre de fenêtre.

## Trous et discontinuités dans les pièces présentes
Aucun : les 30 pièces de vitres et de contours de V16000 ont **les mêmes boucles de bord** que l'original extérieur
(même nombre, même longueur à 1 cm près) et **aucune arête à plus de deux faces**. Les jours clairs ne sont pas des trous
créés par la réduction : ce sont les ouvertures laissées par les pièces retirées.

## Coût d'une restauration (non faite)
| Pièce | 3 mm | 4 mm | 5 mm |
|---|---|---|---|
| `Fiat_Multipla_96` | 1 734 | 1 386 | 1 108 |
| `Fiat_Multipla_135` | 452 | 362 | 288 |
| `Fiat_Multipla_94.002` + `94.003` | 74 | 32 | 24 |
| **Total** | 2 260 | **1 780** | 1 420 |

V16000 a 255 triangles libres : restaurer les encadrements à 4 mm demande de refaire la répartition sous 16 000 (le
reste de la voiture passerait d'environ 4 à 4,5 mm). Option : ne garder de `Fiat_Multipla_96` que la partie visible de
l'extérieur (cadres intérieurs de portes cachés retirés), pour un coût plus faible.
