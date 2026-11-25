# Audit des détails extérieurs : original contre `1000tipla_D2_8000.glb` (2026-11-25)

Rien reconstruit, rien importé dans Blur. KN5 et reconstructions précédentes non modifiés.
Fichiers : `audit_pieces.csv` (127 pièces : catégorie, triangles, présence, matériau, faces retournées, surface perdue,
apparence), `cout_pieces.csv` (triangles nécessaires pour 1 / 3 / 5 mm d'écart max, par pièce), `gros_plans/cmp_*.png`
(7 zones, original / D2, texture et gris, faces arrière masquées comme dans Blur).
Outils : `blur_tools/render_closeups_blender.py`, `audit_details_blender.py`, `audit_cost_blender.py`.

## 1. Ce qui a été vérifié et écarté
- **Présence** : les 127 pièces sont dans le GLB, aucune supprimée ni fusionnée avec une autre.
- **Matériaux, textures, UV** : chaque pièce garde son matériau d'origine et ses UV ; textures d'origine liées (sauf les 2
  cartes, voulues).
- **Faces invisibles dans Blur** : aucune face retournée (0 % sur toutes les pièces) ; aucune pièce d'origine n'a de
  faces doubles, donc le retrait des doublons n'a rien caché.
- **Normales** : recalculées, aucune tache (vérifié sur les gros plans gris).

**Conclusion : les détails manquants sont des pertes de GÉOMÉTRIE, pas de texture, de matériau ou de normales.**

## 2. Détails perdus, par élément (5 mm = écart visible de près ; coût = triangles pour tenir 5 mm, arrondi aux puissances de 2)

| Élément | Pièces (exemples) | État dans D2 | Tri. origine → D2 | Coût 5 mm | Apparence | Cause |
|---|---|---|---|---|---|---|
| Contours / encadrements de vitres | 26 pièces (`Fiat_Multipla_53`, `_100`, `_48`, `body_main.018/020/024/026`) | présents, simplifiés | 23 628 → 245 | 599 (+366) | forme = géométrie, texture unie | pièces fines : tolérance 3 cm > leur largeur |
| Phares ronds (pied de pare-brise) | `Fiat_Multipla_66`, `_71` (+ réflecteurs `_69`, `_74`) | octogones froissés | 1 024 → 11 chacun | 32 (+21 chacun) | géométrie | plancher trop bas pour une pièce petite et bombée |
| Rétroviseurs | `Cube.001` (coques), `Cube.002` (miroirs) | coque devenue un coin | 3 808 → 54 / 416 → 13 | 256 / 16 (+205) | géométrie | petite surface → petite part du budget |
| Feux arrière et clignotants | 17 pièces (`Fiat_Multipla_123/128` boîtiers, `_124/_130` chromes, `_120/_127` orange, `_65.001` rouge, `Turnsignal`) | bosses fondues, boîtiers perdus à 40-46 % | 59 788 → 348 | 1 460 (+1 120) | géométrie (couleurs unies) | idem |
| Baguettes chromées | 14 pièces (`Circle.026` tour de voiture, `Circle.030`, `Fiat_Multipla_105/109/55`) | présentes, amincies / coupées | 17 360 → 362 | 1 634 (+1 280) | géométrie (couleur unie) | pièces fines, longues |
| Sorties d'échappement | `Circle.019` (pots), `Circle.018` (bague), `Circle.020` | rond → octogone | 7 520 → 235 | 704 (+469) | géométrie + texture | idem |
| Montants d'aileron ajourés | `Circle.015` | **carte** : trous peints, bords dentelés | 3 592 → 189 | **512 (+323)** en géométrie d'origine | géométrie | règle « carte » trop large : cette pièce est réductible |
| Calandre en nid d'abeille | `Circle.027` | carte (couleur cuite) | 20 448 → 64 | 13 305 | géométrie trouée | carte justifiée (irréductible) |
| Contours de portes, joints de carrosserie | panneaux séparés (`body_main.*`) | joint présent (pièces séparées), atténué | - | - | géométrie (écart entre pièces) | correct, rien à faire |
| Poignées et serrures de portes | dans les panneaux de porte | relief disparu, dessin dans la texture | - | - | **texture** (relief < 5 mm) | relief plat : rester en texture |
| Protections latérales / bas de caisse | `Fiat_Multipla_90` (barres), `Circle.009`, `polymsh_detached19-22` | perte 30-45 % | 13 536 → 6 … | 127 … | géométrie | idem pièces fines |

## 3. Causes
1. **Tolérance absolue (3 cm) inadaptée aux pièces fines ou petites** : 3 cm d'écart sur une baguette de 2 cm la fait
   disparaître sans qu'aucune alerte ne se déclenche (rapport D2 : « aucune pièce au-delà de 3 cm »). La tolérance doit
   être relative à la taille de la pièce.
2. **Budget par surface** : juste pour les tôles, mais une pièce petite et très travaillée (rétro, feu, phare) reçoit
   presque rien. Les poids x3 « importants » ne compensent pas une surface 100 fois plus petite.
3. **Règle « carte » trop large** : `Circle.015` est passée en carte alors qu'elle tient 5 mm avec 512 triangles.
4. Les vitres et pièces plates ne sont que **peu** sur-servies : 1 889 triangles récupérables en ramenant chaque pièce au
   besoin réel pour 5 mm (`Fiat_Multipla_94.004` 224 → 64, `Fiat_Multipla_28` 716 → 512…).

## 4. Coût de la restauration (pièces visibles à 5 mm, le reste inchangé, sur-servies ramenées à 5 mm)
| Scénario | Total |
|---|---|
| Contours de vitres + rétros + échappements | 7 143 |
| + montants d'aileron en géométrie | 7 466 |
| + feux et phares | 8 586 (**> 8 000**) |
| + baguettes chromées | 9 866 (**> 8 000**) |
| Tout à 5 mm (pour info) | 27 702 |

Dans les 8 000 : contours de vitres, rétros, échappements, montants d'aileron en géométrie, et environ la moitié du
surcoût des feux (boîtiers et chromes du feu arrière, phares ronds en priorité). Tout restaurer sauf les baguettes
chromées demande ~8 600 ; avec les baguettes, ~9 900. **Dépassement à décider par l'utilisateur.**

## 5. Méthode de restauration proposée (pour la prochaine reconstruction, après accord)
- Tolérance **relative** : écart max ≤ 5 mm ou ≤ 10 % de la plus petite dimension de la pièce.
- Plancher par catégorie pour les détails importants (rétros, feux, phares, échappements, contours de vitres) calculé à
  5 mm (`cout_pieces.csv`), avant la répartition par surface.
- Pièces sur-servies ramenées à leur besoin à 1-5 mm, surplus redistribué.
- Carte seulement si la géométrie d'origine coûte plus de ~2 000 triangles à 5 mm (calandre oui, montants d'aileron non).
- Poignées, serrures, inscriptions : restent dans la texture (relief < 5 mm, déjà dessiné). Rien de géométrique ne passe
  en texture.
