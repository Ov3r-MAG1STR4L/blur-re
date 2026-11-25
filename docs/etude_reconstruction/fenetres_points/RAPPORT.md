# 1000tipla avec encadrements, conforme à la limite de points de Map Builder (2026-11-26)

**Fichier : `glb/1000tipla_cadres_15386.glb`** (copie de `glb/1000tipla_D2_16000.glb`, nom de sortie du script).
Non importé dans Blur. KN5 et versions précédentes non modifiés (la version refusée reste dans `../D2_fenetres_16k`).

## Pourquoi cette version
Map Builder (`Ui.cs`, `Fits`) exige : place en points de la Bowler (16 128) ≥ 1,1 × points soudés du `.glb`
(position 0,1 mm, UV 1e-5, coutures d'UV comprises), soit **≤ 14 661 points**. La version avec cadres de
`D2_fenetres_16k` (15 644 triangles) en avait 14 698 pour Map Builder : refusée de 37 points.

## Résultat
| | Refusée | **Conforme** |
|---|---|---|
| Triangles | 15 644 | **15 386** |
| Points soudés (comptage `glb_check.py`, ~0,5 % sous Map Builder) | 14 630 (Map Builder : 14 698) | **14 406** (≈ 14 475 pour Map Builder) |
| Marge sous 14 661 | −37 | **≈ +190 (1,3 %)** |
| Intégrité | intègre | **intègre** |
| Pièces / faces retournées | 131 / aucune | **131 / aucune** |
| Fenêtres vides là où le KN5 est rempli | 154 cm² | **154 cm²** |

Triangles retirés (258) : **baguettes chromées −231** (pire écart inchangé, 4,7 mm), tôles −16, peinture avant −6,
supports de roue −5. **Cadres (1 753), feux, échappements, contours, rétros, vitres : inchangés.** Aucun écart max de
zone ne change, sauf la peinture avant (1,9 → 2,2 mm).

Méthode : même source (`../D2_fenetres_16k/src_obj`), même répartition par tolérance avec cadres et détails protégés,
budget de planification abaissé à 15 450 (`plan.py`), points vérifiés après construction.

Gros plans (`cmp_<zone>.png` : KN5 / refusée / conforme) et vues (`planche_globale_*.png`) : aucune différence visible
avec la version refusée. Défauts déjà connus toujours présents : ombrage de la portière avant, montant central un peu
dentelé, calandre en carte.
